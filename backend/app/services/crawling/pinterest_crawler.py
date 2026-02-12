"""Pinterest Ad Library crawler."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

# Pinterest Ad Library (public)
PINTEREST_AD_LIBRARY_URL = "https://www.pinterest.com/ads/transparency"
# Pinterest Ads API v5
PINTEREST_ADS_API = "https://api.pinterest.com/v5"


class PinterestAdCrawler(BaseCrawler):
    """Crawler for Pinterest Ad Library / Ads API.

    Supports:
    - Pinterest Ad Transparency (public page)
    - Pinterest Marketing API v5 (with access token)
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
        country: str = "JP",
        **kwargs,
    ) -> list[CrawledAd]:
        """Search Pinterest ads."""
        results: list[CrawledAd] = []

        if self.access_token:
            results = await self._search_via_api(query, category, limit, country)
        else:
            results = await self._search_via_scraping(query, limit, country)

        logger.info("pinterest_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        country: str,
    ) -> list[CrawledAd]:
        """Search using Pinterest Marketing API."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Search via Ads Transparency endpoint
            params = {
                "query": query,
                "country_code": country,
                "page_size": min(limit, 100),
                "ad_format": "VIDEO",
            }

            response = await client.get(
                f"{PINTEREST_ADS_API}/ads/transparency",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            for ad_data in data.get("items", []):
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    results.append(crawled_ad)
                    if len(results) >= limit:
                        break

            # Handle pagination
            bookmark = data.get("bookmark")
            while bookmark and len(results) < limit:
                await asyncio.sleep(self.rate_limit_delay)
                params["bookmark"] = bookmark
                response = await client.get(
                    f"{PINTEREST_ADS_API}/ads/transparency",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                for ad_data in data.get("items", []):
                    crawled_ad = self._parse_api_ad(ad_data)
                    if crawled_ad:
                        results.append(crawled_ad)
                        if len(results) >= limit:
                            break

                bookmark = data.get("bookmark")

        except Exception as e:
            logger.error("pinterest_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
        country: str,
    ) -> list[CrawledAd]:
        """Fallback: scrape Pinterest Ad Transparency page."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            params = {
                "q": query,
                "country": country,
            }

            response = await client.get(PINTEREST_AD_LIBRARY_URL, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_cards = soup.select(
                "[data-ad-id], .ad-card, .pin-ad, [data-test-id='pin']"
            )

            for card in ad_cards[:limit]:
                crawled_ad = self._parse_scraped_card(card)
                if crawled_ad:
                    results.append(crawled_ad)
                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("pinterest_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from Pinterest API response."""
        try:
            ad_id = str(ad_data.get("id") or ad_data.get("pin_id", ""))

            first_seen = None
            if ad_data.get("created_at"):
                first_seen = datetime.fromisoformat(
                    ad_data["created_at"].replace("Z", "+00:00")
                )

            video_url = None
            thumbnail_url = None
            media = ad_data.get("media", {})
            if media.get("media_type") == "VIDEO":
                video_url = media.get("video_url")
                thumbnail_url = media.get("cover_image_url")
            elif ad_data.get("images"):
                images = ad_data["images"]
                if isinstance(images, dict):
                    # Get the highest resolution
                    for key in ["original", "1200x", "600x"]:
                        if key in images:
                            thumbnail_url = images[key].get("url")
                            break

            return CrawledAd(
                external_id=ad_id,
                platform="pinterest",
                title=ad_data.get("title") or ad_data.get("name"),
                description=ad_data.get("description") or ad_data.get("creative_text"),
                advertiser_name=ad_data.get("advertiser_name") or ad_data.get("payer_name"),
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                first_seen_at=first_seen,
                metadata={
                    "source": "pinterest_ads_api",
                    "pin_id": ad_data.get("pin_id"),
                    "board_id": ad_data.get("board_id"),
                    "ad_account_id": ad_data.get("ad_account_id"),
                    "campaign_id": ad_data.get("campaign_id"),
                    "destination_url": ad_data.get("link") or ad_data.get("click_through_url"),
                    "paid_by": ad_data.get("payer_name"),
                    "targeting": ad_data.get("targeting"),
                    "engagement_metrics": {
                        "saves": ad_data.get("save_count"),
                        "clicks": ad_data.get("click_count"),
                        "comments": ad_data.get("comment_count"),
                    },
                },
            )
        except Exception as e:
            logger.error("pinterest_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card) -> Optional[CrawledAd]:
        """Parse ad from scraped HTML card."""
        try:
            ad_id = card.get("data-ad-id", "") or card.get("data-test-pin-id", "")
            title_el = card.select_one("h3, .ad-title, [data-test-id='pin-title']")
            desc_el = card.select_one("p, .ad-description, [data-test-id='pin-description']")
            advertiser_el = card.select_one(".advertiser-name, .payer-name")

            video_el = card.select_one("video source")
            video_url = video_el.get("src") if video_el else None

            img_el = card.select_one("img")
            thumbnail_url = img_el.get("src") if img_el else None

            # Extract destination URL from pin link
            link_el = card.select_one("a[href]:not([href*='pinterest.'])")
            destination_url = None
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("http") and "pinterest." not in href:
                    destination_url = href

            return CrawledAd(
                external_id=ad_id or f"pin_{hash(str(card)):#010x}",
                platform="pinterest",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                metadata={
                    "source": "pinterest_transparency_scrape",
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("pinterest_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific Pinterest ad."""
        if self.access_token:
            client = await self._get_client()
            try:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                response = await client.get(
                    f"{PINTEREST_ADS_API}/pins/{external_id}",
                    headers=headers,
                )
                response.raise_for_status()
                return self._parse_api_ad(response.json())
            except Exception as e:
                logger.error("pinterest_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific Pinterest advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
