"""TikTok Ad Library crawler."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

TIKTOK_AD_LIBRARY_URL = "https://library.tiktok.com/ads"
TIKTOK_COMMERCIAL_API = "https://business-api.tiktok.com/open_api/v1.3"


class TikTokAdCrawler(BaseCrawler):
    """Crawler for TikTok Ad Library / Commercial Content API."""

    def __init__(self, access_token: Optional[str] = None, rate_limit_delay: float = 2.0):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.access_token = access_token

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        region: str = "JP",
        **kwargs,
    ) -> list[CrawledAd]:
        """Search TikTok Ad Library for ads."""
        results: list[CrawledAd] = []

        if self.access_token:
            results = await self._search_via_api(query, category, limit, region)
        else:
            results = await self._search_via_scraping(query, limit, region)

        logger.info("tiktok_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        region: str,
    ) -> list[CrawledAd]:
        """Search using TikTok Commercial Content API."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            headers = {
                "Access-Token": self.access_token,
                "Content-Type": "application/json",
            }

            payload = {
                "search_term": query,
                "region_code": region,
                "search_type": "AD",
                "start_date": None,
                "end_date": None,
                "page": 1,
                "page_size": min(limit, 50),
            }

            response = await client.post(
                f"{TIKTOK_COMMERCIAL_API}/creative/ad/search/",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            for ad_data in data.get("data", {}).get("ads", []):
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    results.append(crawled_ad)

        except Exception as e:
            logger.error("tiktok_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
        region: str,
    ) -> list[CrawledAd]:
        """Fallback: scrape TikTok Ad Library."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            params = {
                "q": query,
                "region": region,
                "type": "video",
            }

            response = await client.get(TIKTOK_AD_LIBRARY_URL, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_cards = soup.select(".ad-card, [data-ad-id], .search-result-item")

            for card in ad_cards[:limit]:
                crawled_ad = self._parse_scraped_card(card)
                if crawled_ad:
                    results.append(crawled_ad)

                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("tiktok_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad from TikTok API response."""
        try:
            first_seen = None
            if ad_data.get("first_shown_date"):
                first_seen = datetime.fromisoformat(ad_data["first_shown_date"])

            last_seen = None
            if ad_data.get("last_shown_date"):
                last_seen = datetime.fromisoformat(ad_data["last_shown_date"])

            return CrawledAd(
                external_id=str(ad_data.get("ad_id", "")),
                platform="tiktok",
                title=ad_data.get("ad_title"),
                description=ad_data.get("ad_text"),
                advertiser_name=ad_data.get("business_name"),
                video_url=ad_data.get("video_url"),
                thumbnail_url=ad_data.get("image_url"),
                duration_seconds=ad_data.get("video_duration"),
                view_count=ad_data.get("reach"),
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                metadata={
                    "paid_for_by": ad_data.get("paid_for_by"),
                    "target_audience": ad_data.get("target_audience"),
                    "reach": ad_data.get("reach"),
                },
            )
        except Exception as e:
            logger.error("tiktok_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card) -> Optional[CrawledAd]:
        """Parse ad from scraped HTML card."""
        try:
            ad_id = card.get("data-ad-id", "")
            title_el = card.select_one(".ad-title, h3")
            desc_el = card.select_one(".ad-body, .ad-text, p")
            advertiser_el = card.select_one(".business-name, .advertiser")

            video_el = card.select_one("video source")
            video_url = video_el.get("src") if video_el else None

            return CrawledAd(
                external_id=ad_id or f"tt_{hash(str(card)):#010x}",
                platform="tiktok",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
            )
        except Exception as e:
            logger.error("tiktok_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific TikTok ad."""
        if self.access_token:
            client = await self._get_client()
            try:
                response = await client.get(
                    f"{TIKTOK_COMMERCIAL_API}/creative/ad/detail/",
                    params={"ad_id": external_id},
                    headers={"Access-Token": self.access_token},
                )
                response.raise_for_status()
                data = response.json()
                ad_data = data.get("data", {})
                return self._parse_api_ad(ad_data) if ad_data else None
            except Exception as e:
                logger.error("tiktok_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a TikTok advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
