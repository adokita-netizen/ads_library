"""Base crawler interface for ad collection."""

import abc
import asyncio
import hashlib
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds; exponential backoff: 1s, 2s, 4s
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# CI-102: Blocked domains and paths — requests to these are rejected before sending
BLOCKED_DOMAINS = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",       # AWS metadata
    "metadata.google.internal",
    "10.0.0.0",
})

BLOCKED_PATH_PREFIXES = (
    "/admin",
    "/login",
    "/logout",
    "/api/v1/auth",
    "/wp-admin",
    "/.env",
    "/.git",
)


def _is_blocked_url(url: str) -> bool:
    """CI-102: Check if URL targets a blocked domain or path."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        # Block internal/metadata IPs
        if host in BLOCKED_DOMAINS:
            return True
        # Block private IP ranges
        if host.startswith(("10.", "192.168.", "172.16.", "172.17.", "172.18.",
                            "172.19.", "172.2", "172.30.", "172.31.")):
            return True

        # Block sensitive paths
        path = parsed.path.lower()
        for prefix in BLOCKED_PATH_PREFIXES:
            if path.startswith(prefix):
                return True

        return False
    except Exception:
        return False


# CI-098: Layered timeout presets for different operation types
TIMEOUT_PRESETS = {
    "thumbnail": httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
    "image":     httpx.Timeout(connect=8.0, read=20.0, write=5.0, pool=8.0),
    "video":     httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
    "api":       httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
    "browser":   httpx.Timeout(connect=15.0, read=90.0, write=10.0, pool=15.0),
    "health":    httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
}


# ── CI-064: Source Health Tracker ─────────────────────────────
class SourceHealthTracker:
    """Track per-source success/failure rates and compute health scores.

    Health score: 0.0 (all failures) to 1.0 (all successes).
    When health drops, crawl delays are automatically increased.
    """

    _WINDOW = 600.0          # 10-minute sliding window
    _MIN_SAMPLES = 5         # minimum requests before scoring
    _THROTTLE_MULTIPLIERS = {
        # health_range: delay_multiplier
        0.9: 1.0,   # healthy: no throttle
        0.7: 1.5,   # degraded: 1.5x delay
        0.5: 3.0,   # unhealthy: 3x delay
        0.3: 5.0,   # critical: 5x delay
        0.0: 10.0,  # failing: 10x delay
    }

    def __init__(self):
        # {source_key: [(timestamp, success_bool), ...]}
        self._records: dict[str, list[tuple[float, bool]]] = {}

    def record(self, source: str, success: bool) -> None:
        """Record a request outcome for the given source."""
        now = time.time()
        if source not in self._records:
            self._records[source] = []
        entries = self._records[source]
        entries.append((now, success))
        # Prune old entries
        cutoff = now - self._WINDOW
        self._records[source] = [(t, s) for t, s in entries if t > cutoff]

    def health_score(self, source: str) -> float:
        """Return health score (0.0-1.0) for the given source."""
        entries = self._records.get(source, [])
        now = time.time()
        cutoff = now - self._WINDOW
        recent = [(t, s) for t, s in entries if t > cutoff]
        if len(recent) < self._MIN_SAMPLES:
            return 1.0  # not enough data, assume healthy
        successes = sum(1 for _, s in recent if s)
        return successes / len(recent)

    def get_throttle_multiplier(self, source: str) -> float:
        """Return delay multiplier based on source health."""
        score = self.health_score(source)
        for threshold, multiplier in sorted(
            self._THROTTLE_MULTIPLIERS.items(), reverse=True
        ):
            if score >= threshold:
                return multiplier
        return 10.0

    def get_all_scores(self) -> dict[str, float]:
        """Return health scores for all tracked sources."""
        return {src: self.health_score(src) for src in self._records}


# Global singleton shared across all crawler instances
_health_tracker = SourceHealthTracker()


@dataclass
class CrawledAd:
    """Standardized ad data from any platform."""

    external_id: str
    platform: str
    title: Optional[str] = None
    description: Optional[str] = None
    advertiser_name: Optional[str] = None
    advertiser_url: Optional[str] = None
    brand_name: Optional[str] = None
    creative_type: str = "unknown"  # "video" / "image" / "carousel" / "unknown"
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_urls: list[str] = field(default_factory=list)
    snapshot_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    category: Optional[str] = None
    destination_url: Optional[str] = None
    spend: Optional[float] = None
    impressions: Optional[int] = None
    reach: Optional[int] = None
    cpc: Optional[float] = None
    cpm: Optional[float] = None
    frequency: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def unique_hash(self) -> str:
        return hashlib.sha256(f"{self.platform}:{self.external_id}".encode()).hexdigest()


class BaseCrawler(abc.ABC):
    """Abstract base crawler for ad platforms.

    Provides:
    - HTTP client with separate connect/read/write timeouts
    - Automatic retry with exponential backoff for transient errors (429, 5xx)
    - Structured logging with platform and ad context
    - CI-110: Emergency suppression mode on 429/5xx spikes
    """

    # CI-110: Emergency suppression — shared across all crawler instances
    _error_window: list[float] = []  # timestamps of recent 429/5xx errors
    _suppression_active: bool = False
    _SUPPRESSION_THRESHOLD = 5       # errors within window to trigger
    _SUPPRESSION_WINDOW = 60.0       # seconds
    _SUPPRESSION_COOLDOWN = 300.0    # seconds to wait before resuming

    # CI-139: Proxy rotation configuration
    _proxy_list: list[str] = []      # e.g. ["http://proxy1:8080", "http://proxy2:8080"]
    _proxy_index: int = 0
    _proxy_failures: dict[str, int] = {}  # proxy_url -> consecutive failure count
    _PROXY_MAX_FAILURES = 3               # failures before marking proxy unhealthy

    def __init__(self, rate_limit_delay: float = 1.0):
        self.rate_limit_delay = rate_limit_delay
        self._base_rate_limit_delay = rate_limit_delay
        self._client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _record_error(cls):
        """Record a 429/5xx error for suppression tracking."""
        import time
        now = time.time()
        cls._error_window = [t for t in cls._error_window if now - t < cls._SUPPRESSION_WINDOW]
        cls._error_window.append(now)
        if len(cls._error_window) >= cls._SUPPRESSION_THRESHOLD:
            cls._suppression_active = True
            logger.warning("emergency_suppression_activated",
                           error_count=len(cls._error_window),
                           cooldown_seconds=cls._SUPPRESSION_COOLDOWN)

    @classmethod
    def is_suppressed(cls) -> bool:
        """Check if emergency suppression is active."""
        if not cls._suppression_active:
            return False
        import time
        if cls._error_window and time.time() - cls._error_window[-1] > cls._SUPPRESSION_COOLDOWN:
            cls._suppression_active = False
            cls._error_window.clear()
            logger.info("emergency_suppression_lifted")
            return False
        return True

    @property
    def platform_name(self) -> str:
        """Return the platform name for logging. Subclasses may override."""
        return self.__class__.__name__

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=30.0,
                    write=10.0,
                    pool=10.0,
                ),
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    )
                },
            )
        return self._client

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        max_retries: int = MAX_RETRIES,
        context: Optional[dict] = None,
        timeout_preset: Optional[str] = None,
        **kwargs,
    ) -> httpx.Response:
        """Execute an HTTP request with exponential backoff retry.

        Retries on:
        - httpx.TimeoutException (connect/read timeout)
        - httpx.ConnectError (network-level failure)
        - HTTP 429 (rate limited) and 5xx (server errors)

        Args:
            method: HTTP method ("GET" or "POST")
            url: Request URL
            max_retries: Maximum number of retry attempts (default: 3)
            context: Extra fields for structured log messages (e.g. ad_id, platform)
            timeout_preset: CI-098 timeout preset name (thumbnail/image/video/api/browser/health)
            **kwargs: Passed through to httpx (params, json, headers, etc.)

        Returns:
            httpx.Response on success

        Raises:
            Last exception if all retries exhausted
        """
        # CI-098: Apply timeout preset if specified and no explicit timeout in kwargs
        if timeout_preset and "timeout" not in kwargs:
            preset = TIMEOUT_PRESETS.get(timeout_preset)
            if preset:
                kwargs["timeout"] = preset

        # CI-102: Block requests to forbidden domains/paths
        if _is_blocked_url(url):
            logger.warning("blocked_url_rejected", url=url, platform=self.platform_name)
            raise ValueError(f"URL blocked by guardrail: {url}")

        # CI-110: Check emergency suppression before making requests
        if self.is_suppressed():
            raise RuntimeError("Emergency suppression active — crawling paused due to 429/5xx spike")

        client = await self._get_client()
        source_key = self.platform_name
        ctx = {"platform": source_key, "url": url, **(context or {})}
        last_exc: Optional[Exception] = None

        # CI-064: Apply health-based throttle before request
        throttle_mult = _health_tracker.get_throttle_multiplier(source_key)
        if throttle_mult > 1.0:
            health = _health_tracker.health_score(source_key)
            logger.info("source_health_throttle",
                        source=source_key, health=round(health, 2),
                        multiplier=throttle_mult)

        for attempt in range(1, max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)

                # Retry on transient HTTP errors
                if response.status_code in RETRYABLE_STATUS_CODES:
                    self._record_error()  # CI-110: Track for suppression
                    _health_tracker.record(source_key, False)  # CI-064
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) * throttle_mult
                    # Respect Retry-After header if present
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning(
                        "http_retryable_status",
                        status=response.status_code,
                        attempt=attempt,
                        max_retries=max_retries,
                        delay=delay,
                        **ctx,
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(delay)
                        continue
                    # Last attempt: raise
                    response.raise_for_status()

                # CI-064: Record success
                _health_tracker.record(source_key, True)

                # CI-072: Compliance access log
                from urllib.parse import urlparse
                _parsed = urlparse(url)
                logger.debug("crawl_access_log",
                             domain=_parsed.netloc,
                             path=_parsed.path[:100],
                             method=method,
                             status=response.status_code,
                             platform=source_key)

                return response

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                _health_tracker.record(source_key, False)  # CI-064
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) * throttle_mult
                logger.warning(
                    "http_retry_on_error",
                    error_type=type(e).__name__,
                    error=str(e),
                    attempt=attempt,
                    max_retries=max_retries,
                    delay=delay,
                    **ctx,
                )
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                else:
                    raise

        # Should not reach here, but just in case
        if last_exc:
            raise last_exc
        raise RuntimeError("Unexpected retry loop exit")

    @classmethod
    def configure_proxies(cls, proxy_urls: list[str]) -> None:
        """CI-139: Set proxy list for rotation. Call before crawling starts."""
        cls._proxy_list = [p for p in proxy_urls if p]
        cls._proxy_index = 0
        cls._proxy_failures = {}
        logger.info("proxy_rotation_configured", count=len(cls._proxy_list))

    @classmethod
    def _next_proxy(cls) -> Optional[str]:
        """CI-139: Get next healthy proxy from rotation."""
        if not cls._proxy_list:
            return None
        for _ in range(len(cls._proxy_list)):
            proxy = cls._proxy_list[cls._proxy_index % len(cls._proxy_list)]
            cls._proxy_index += 1
            if cls._proxy_failures.get(proxy, 0) < cls._PROXY_MAX_FAILURES:
                return proxy
        # All proxies unhealthy — reset and try first
        cls._proxy_failures.clear()
        return cls._proxy_list[0] if cls._proxy_list else None

    @classmethod
    def _record_proxy_result(cls, proxy: str, success: bool) -> None:
        """CI-139: Track proxy success/failure for health-based rotation."""
        if success:
            cls._proxy_failures.pop(proxy, None)
        else:
            cls._proxy_failures[proxy] = cls._proxy_failures.get(proxy, 0) + 1
            if cls._proxy_failures[proxy] >= cls._PROXY_MAX_FAILURES:
                logger.warning("proxy_marked_unhealthy", proxy=proxy,
                               failures=cls._proxy_failures[proxy])

    def get_source_health(self) -> float:
        """CI-064: Return current health score for this crawler's source."""
        return _health_tracker.health_score(self.platform_name)

    @staticmethod
    def get_all_source_health() -> dict[str, float]:
        """CI-064: Return health scores for all tracked sources."""
        return _health_tracker.get_all_scores()

    async def check_egress_health(self) -> dict:
        """CI-080: Validate egress connectivity before crawling.

        Returns dict with:
          - healthy (bool): whether egress is working
          - ip (str|None): detected egress IP
          - latency_ms (float): round-trip latency
          - error (str|None): error message if unhealthy
        """
        result = {"healthy": False, "ip": None, "latency_ms": 0.0, "error": None}
        try:
            client = await self._get_client()
            start = time.time()
            resp = await client.get(
                "https://httpbin.org/ip",
                timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            )
            latency = (time.time() - start) * 1000
            result["latency_ms"] = round(latency, 1)
            if resp.status_code == 200:
                data = resp.json()
                result["ip"] = data.get("origin", "unknown")
                result["healthy"] = True
                logger.info("egress_health_ok",
                            platform=self.platform_name,
                            ip=result["ip"],
                            latency_ms=result["latency_ms"])
            else:
                result["error"] = f"HTTP {resp.status_code}"
                logger.warning("egress_health_bad_status",
                               platform=self.platform_name,
                               status=resp.status_code)
        except Exception as e:
            result["error"] = str(e)[:200]
            logger.error("egress_health_failed",
                         platform=self.platform_name,
                         error=result["error"])
        return result

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @abc.abstractmethod
    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        **kwargs,
    ) -> list[CrawledAd]:
        """Search for ads matching the query."""
        ...

    @abc.abstractmethod
    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get detailed information for a specific ad."""
        ...

    @abc.abstractmethod
    async def get_advertiser_ads(
        self,
        advertiser_name: str,
        limit: int = 50,
    ) -> list[CrawledAd]:
        """Get all ads from a specific advertiser."""
        ...

    async def download_video(self, video_url: str, output_dir: Optional[str] = None) -> Optional[Path]:
        """Download video from URL to local file with retry."""
        try:
            response = await self._request_with_retry(
                "GET", video_url,
                context={"operation": "download_video"},
                timeout_preset="video",
            )
            response.raise_for_status()

            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = Path(tempfile.mkdtemp())

            url_hash = hashlib.md5(video_url.encode()).hexdigest()[:12]
            file_path = output_path / f"video_{url_hash}.mp4"

            file_path.write_bytes(response.content)
            logger.info("video_downloaded", url=video_url, path=str(file_path), size=len(response.content))
            return file_path

        except Exception as e:
            logger.error("video_download_failed", url=video_url, error=str(e))
            return None

    async def download_thumbnail(self, thumbnail_url: str) -> Optional[bytes]:
        """Download thumbnail image with retry."""
        try:
            response = await self._request_with_retry(
                "GET", thumbnail_url,
                context={"operation": "download_thumbnail"},
                timeout_preset="thumbnail",
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error("thumbnail_download_failed", url=thumbnail_url, error=str(e))
            return None
