"""LINE Ads crawler (LINE広告)."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

# LINE Ads transparency / public search
LINE_ADS_URL = "https://adcenter.line.me"
# LINE Ads API
LINE_ADS_API_BASE = "https://ads.line.me/api/v3.0"


class LineAdCrawler(BaseCrawler):
    """Crawler for LINE Ads.

    Supports:
    - LINE Ad Center (public page)
    - LINE Ads Platform API (with access token)

    LINE広告はLINE NEWS, LINE VOOM, LINEマンガ, LINE BLOG, LINEポイント等に
    配信される広告を取得します。
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        rate_limit_delay: float = 2.0,
    ):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.access_token = access_token

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        **kwargs,
    ) -> list[CrawledAd]:
        """Search LINE ads."""
        results: list[CrawledAd] = []

        if self.access_token:
            results = await self._search_via_api(query, category, limit)
        else:
            results = await self._search_via_scraping(query, limit)

        logger.info("line_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
    ) -> list[CrawledAd]:
        """Search using LINE Ads Platform API."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            params = {
                "keyword": query,
                "limit": min(limit, 100),
                "offset": 0,
                "status": "ACTIVE",
            }

            if category:
                params["category"] = category

            response = await client.get(
                f"{LINE_ADS_API_BASE}/ads",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            for ad_data in data.get("ads", data.get("data", [])):
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    results.append(crawled_ad)
                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.error("line_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
    ) -> list[CrawledAd]:
        """Fallback: scrape LINE Ad Center."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            params = {
                "q": query,
                "type": "video",
            }

            response = await client.get(f"{LINE_ADS_URL}/search", params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_cards = soup.select(
                "[data-ad-id], .ad-card, .ad-item, .creative-item"
            )

            for card in ad_cards[:limit]:
                crawled_ad = self._parse_scraped_card(card)
                if crawled_ad:
                    results.append(crawled_ad)
                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("line_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from LINE Ads API response."""
        try:
            ad_id = str(ad_data.get("adId") or ad_data.get("id", ""))

            creative = ad_data.get("creative", {})
            video_info = creative.get("video", {})

            first_seen = None
            if ad_data.get("startDate") or ad_data.get("createdAt"):
                date_str = ad_data.get("startDate") or ad_data.get("createdAt")
                first_seen = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            return CrawledAd(
                external_id=ad_id,
                platform="line",
                title=creative.get("title") or ad_data.get("adName"),
                description=creative.get("description") or creative.get("body"),
                advertiser_name=ad_data.get("advertiserName") or ad_data.get("accountName"),
                video_url=video_info.get("videoUrl"),
                thumbnail_url=creative.get("imageUrl") or video_info.get("thumbnailUrl"),
                duration_seconds=video_info.get("durationSeconds"),
                first_seen_at=first_seen,
                metadata={
                    "source": "line_ads_api",
                    "campaign_id": ad_data.get("campaignId"),
                    "ad_group_id": ad_data.get("adGroupId"),
                    "ad_type": creative.get("type"),
                    "placement": ad_data.get("placement"),
                    "bid_type": ad_data.get("bidType"),
                    "destination_url": creative.get("landingPageUrl"),
                    "call_to_action": creative.get("callToAction"),
                },
            )
        except Exception as e:
            logger.error("line_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card) -> Optional[CrawledAd]:
        """Parse ad from scraped HTML card."""
        try:
            ad_id = card.get("data-ad-id", "")
            title_el = card.select_one("h3, .ad-title, .creative-title")
            desc_el = card.select_one("p, .ad-description, .ad-body")
            advertiser_el = card.select_one(".advertiser-name, .account-name")

            video_el = card.select_one("video source")
            video_url = video_el.get("src") if video_el else None

            thumbnail_el = card.select_one("img")
            thumbnail_url = thumbnail_el.get("src") if thumbnail_el else None

            # Extract destination URL from ad link
            link_el = card.select_one("a[href]:not([href*='line.me'])")
            destination_url = None
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("http") and "line.me" not in href:
                    destination_url = href

            return CrawledAd(
                external_id=ad_id or f"line_{hash(str(card)):#010x}",
                platform="line",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                metadata={
                    "source": "line_adcenter_scrape",
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("line_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific LINE ad."""
        if self.access_token:
            client = await self._get_client()
            try:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = await client.get(
                    f"{LINE_ADS_API_BASE}/ads/{external_id}",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                return self._parse_api_ad(data)
            except Exception as e:
                logger.error("line_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific LINE advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
