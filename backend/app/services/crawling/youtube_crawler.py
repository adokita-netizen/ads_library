"""YouTube Ad crawler using YouTube Ads Transparency Center."""

import asyncio
import re
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

YOUTUBE_ADS_TRANSPARENCY_URL = "https://adstransparency.google.com"


class YouTubeAdCrawler(BaseCrawler):
    """Crawler for YouTube / Google Ads Transparency Center."""

    def __init__(self, api_key: Optional[str] = None, rate_limit_delay: float = 2.0):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.api_key = api_key

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        region: str = "JP",
        date_range: Optional[str] = None,
        **kwargs,
    ) -> list[CrawledAd]:
        """Search Google Ads Transparency Center for ads."""
        results: list[CrawledAd] = []
        client = await self._get_client()

        try:
            search_url = f"{YOUTUBE_ADS_TRANSPARENCY_URL}/advertiser"
            params = {
                "query": query,
                "region": region,
                "format": "VIDEO",
            }
            if date_range:
                params["date_range"] = date_range

            response = await client.get(search_url, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_elements = soup.select("[data-creative-id], .creative-card, .ad-card")

            for element in ad_elements[:limit]:
                crawled_ad = self._parse_ad_element(element)
                if crawled_ad:
                    results.append(crawled_ad)

                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("youtube_search_failed", query=query, error=str(e))

        logger.info("youtube_ads_search", query=query, results_count=len(results))
        return results

    def _parse_ad_element(self, element) -> Optional[CrawledAd]:
        """Parse an ad element from the transparency page."""
        try:
            creative_id = element.get("data-creative-id", "")
            title_el = element.select_one("h3, .ad-title, .creative-title")
            desc_el = element.select_one(".ad-description, .creative-body")
            advertiser_el = element.select_one(".advertiser-name, .page-name")

            video_el = element.select_one("video source, iframe")
            video_url = None
            if video_el:
                video_url = video_el.get("src") or video_el.get("data-src")

            thumbnail_el = element.select_one("img.thumbnail, img.creative-image")
            thumbnail_url = thumbnail_el.get("src") if thumbnail_el else None

            date_el = element.select_one(".date-range, .delivery-date")
            first_seen = None
            if date_el:
                date_text = date_el.get_text(strip=True)
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
                if date_match:
                    first_seen = datetime.fromisoformat(date_match.group(1))

            return CrawledAd(
                external_id=creative_id or f"yt_{hash(str(element)):#010x}",
                platform="youtube",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                first_seen_at=first_seen,
                metadata={"source": "google_ads_transparency"},
            )
        except Exception as e:
            logger.error("youtube_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific YouTube/Google ad."""
        client = await self._get_client()
        try:
            url = f"{YOUTUBE_ADS_TRANSPARENCY_URL}/advertiser/{external_id}"
            response = await client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_element = soup.select_one("[data-creative-id], .creative-detail")
            if ad_element:
                return self._parse_ad_element(ad_element)
        except Exception as e:
            logger.error("youtube_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific advertiser on YouTube/Google."""
        return await self.search_ads(query=advertiser_name, limit=limit)

    async def search_by_youtube_channel(
        self,
        channel_id: str,
        limit: int = 50,
    ) -> list[CrawledAd]:
        """Search for ads associated with a YouTube channel."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            url = f"{YOUTUBE_ADS_TRANSPARENCY_URL}/advertiser"
            params = {
                "advertiser_id": channel_id,
                "format": "VIDEO",
            }

            response = await client.get(url, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_elements = soup.select("[data-creative-id], .creative-card")

            for element in ad_elements[:limit]:
                crawled_ad = self._parse_ad_element(element)
                if crawled_ad:
                    results.append(crawled_ad)

        except Exception as e:
            logger.error("youtube_channel_search_failed", channel_id=channel_id, error=str(e))

        return results
