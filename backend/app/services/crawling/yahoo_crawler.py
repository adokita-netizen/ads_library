"""Yahoo! Ad Library crawler (Yahoo! JAPAN 広告)."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

# Yahoo! JAPAN Ad Transparency Center
YAHOO_AD_TRANSPARENCY_URL = "https://adstransparency.yahoo.co.jp"
# Yahoo! Ads API (Search Ads / Display Ads)
YAHOO_ADS_API_BASE = "https://ads-search.yahooapis.jp/api/v13"
YAHOO_DISPLAY_ADS_API = "https://ads-display.yahooapis.jp/api/v13"


class YahooAdCrawler(BaseCrawler):
    """Crawler for Yahoo! JAPAN Ad Transparency / Yahoo! Ads API.

    Supports:
    - Yahoo! JAPAN 広告透明性センター (public transparency page)
    - Yahoo! Ads Display API (with API key)
    - Yahoo! Ads Search API (with API key)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        rate_limit_delay: float = 2.0,
    ):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.api_key = api_key
        self.api_secret = api_secret

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        ad_type: str = "VIDEO",
        **kwargs,
    ) -> list[CrawledAd]:
        """Search Yahoo! JAPAN ads."""
        results: list[CrawledAd] = []

        if self.api_key:
            results = await self._search_via_api(query, category, limit, ad_type)
        else:
            results = await self._search_via_scraping(query, limit)

        logger.info("yahoo_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        ad_type: str,
    ) -> list[CrawledAd]:
        """Search using Yahoo! Ads Display API."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "accountId": None,
                "searchKeyword": query,
                "adType": ad_type,
                "numberResults": min(limit, 100),
                "startIndex": 1,
            }

            response = await client.post(
                f"{YAHOO_DISPLAY_ADS_API}/AdGroupAdService/get",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("rval", {}).get("values", []):
                ad_data = item.get("adGroupAd", {})
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    results.append(crawled_ad)
                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.error("yahoo_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
    ) -> list[CrawledAd]:
        """Fallback: scrape Yahoo! Ad Transparency Center."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            params = {
                "q": query,
                "type": "all",
                "region": "JP",
            }

            response = await client.get(YAHOO_AD_TRANSPARENCY_URL, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_cards = soup.select(
                "[data-ad-id], .ad-card, .adTransparency-card, .search-result-item"
            )

            for card in ad_cards[:limit]:
                crawled_ad = self._parse_scraped_card(card)
                if crawled_ad:
                    results.append(crawled_ad)
                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("yahoo_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from Yahoo! Ads API response."""
        try:
            ad_id = str(ad_data.get("adId", ""))
            ad_info = ad_data.get("ad", {})

            video_url = None
            thumbnail_url = None
            if ad_info.get("video"):
                video_url = ad_info["video"].get("videoUrl")
                thumbnail_url = ad_info["video"].get("thumbnailUrl")

            return CrawledAd(
                external_id=ad_id,
                platform="yahoo",
                title=ad_info.get("headline") or ad_info.get("title"),
                description=ad_info.get("description") or ad_info.get("description2"),
                advertiser_name=ad_data.get("accountName"),
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                metadata={
                    "source": "yahoo_ads_api",
                    "campaign_id": ad_data.get("campaignId"),
                    "ad_group_id": ad_data.get("adGroupId"),
                    "ad_type": ad_data.get("adType"),
                    "approval_status": ad_data.get("approvalStatus"),
                    "display_url": ad_info.get("displayUrl"),
                    "final_url": ad_info.get("finalUrl"),
                },
            )
        except Exception as e:
            logger.error("yahoo_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card) -> Optional[CrawledAd]:
        """Parse ad from scraped HTML card."""
        try:
            ad_id = card.get("data-ad-id", "")
            title_el = card.select_one("h3, .ad-title, .headline")
            desc_el = card.select_one("p, .ad-description, .ad-body")
            advertiser_el = card.select_one(".advertiser-name, .account-name")

            video_el = card.select_one("video source")
            video_url = video_el.get("src") if video_el else None

            thumbnail_el = card.select_one("img.thumbnail, img")
            thumbnail_url = thumbnail_el.get("src") if thumbnail_el else None

            return CrawledAd(
                external_id=ad_id or f"yahoo_{hash(str(card)):#010x}",
                platform="yahoo",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                metadata={"source": "yahoo_transparency_scrape"},
            )
        except Exception as e:
            logger.error("yahoo_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific Yahoo! ad."""
        if self.api_key:
            client = await self._get_client()
            try:
                headers = {"Authorization": f"Bearer {self.api_key}"}
                payload = {"adIds": [int(external_id)]}
                response = await client.post(
                    f"{YAHOO_DISPLAY_ADS_API}/AdGroupAdService/get",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                values = data.get("rval", {}).get("values", [])
                if values:
                    return self._parse_api_ad(values[0].get("adGroupAd", {}))
            except Exception as e:
                logger.error("yahoo_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific Yahoo! advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
