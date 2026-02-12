"""Base crawler interface for ad collection."""

import abc
import hashlib
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


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
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    category: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def unique_hash(self) -> str:
        return hashlib.sha256(f"{self.platform}:{self.external_id}".encode()).hexdigest()


class BaseCrawler(abc.ABC):
    """Abstract base crawler for ad platforms."""

    def __init__(self, rate_limit_delay: float = 1.0):
        self.rate_limit_delay = rate_limit_delay
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
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
        """Download video from URL to local file."""
        try:
            client = await self._get_client()
            response = await client.get(video_url)
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
        """Download thumbnail image."""
        try:
            client = await self._get_client()
            response = await client.get(thumbnail_url)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error("thumbnail_download_failed", url=thumbnail_url, error=str(e))
            return None
