"""Base crawler interface for ad collection."""

import abc
import asyncio
import hashlib
import tempfile
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
    """

    def __init__(self, rate_limit_delay: float = 1.0):
        self.rate_limit_delay = rate_limit_delay
        self._client: Optional[httpx.AsyncClient] = None

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
            **kwargs: Passed through to httpx (params, json, headers, etc.)

        Returns:
            httpx.Response on success

        Raises:
            Last exception if all retries exhausted
        """
        client = await self._get_client()
        ctx = {"platform": self.platform_name, "url": url, **(context or {})}
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)

                # Retry on transient HTTP errors
                if response.status_code in RETRYABLE_STATUS_CODES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
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

                return response

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
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
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error("thumbnail_download_failed", url=thumbnail_url, error=str(e))
            return None
