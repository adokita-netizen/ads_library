"""X (Twitter) Ad Transparency crawler."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

# X Ads Transparency Center
X_ADS_TRANSPARENCY_URL = "https://ads.x.com/transparency"
# X Ads API v2
X_ADS_API_BASE = "https://ads-api.x.com/12"


class XTwitterAdCrawler(BaseCrawler):
    """Crawler for X (Twitter) Ad Transparency Center / Ads API.

    Supports:
    - X Ads Transparency Center (public page)
    - X Ads API (with Bearer token)
    """

    def __init__(
        self,
        bearer_token: Optional[str] = None,
        rate_limit_delay: float = 2.0,
    ):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.bearer_token = bearer_token

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        region: str = "JP",
        **kwargs,
    ) -> list[CrawledAd]:
        """Search X/Twitter ads."""
        results: list[CrawledAd] = []

        if self.bearer_token:
            results = await self._search_via_api(query, category, limit, region)
        else:
            results = await self._search_via_scraping(query, limit, region)

        logger.info("x_twitter_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        region: str,
    ) -> list[CrawledAd]:
        """Search using X Ads API."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            headers = {
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
            }

            # Use Ads Transparency endpoint
            params = {
                "query": query,
                "country_code": region,
                "count": min(limit, 100),
            }

            response = await client.get(
                f"{X_ADS_API_BASE}/transparency/ads",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            for ad_data in data.get("data", []):
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    results.append(crawled_ad)
                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.error("x_twitter_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
        region: str,
    ) -> list[CrawledAd]:
        """Fallback: scrape X Ads Transparency Center."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            params = {
                "q": query,
                "country": region,
            }

            response = await client.get(X_ADS_TRANSPARENCY_URL, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            ad_cards = soup.select(
                "[data-ad-id], .ad-card, .transparency-ad, .tweet-ad"
            )

            for card in ad_cards[:limit]:
                crawled_ad = self._parse_scraped_card(card)
                if crawled_ad:
                    results.append(crawled_ad)
                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("x_twitter_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from X Ads API response."""
        try:
            ad_id = str(ad_data.get("id", ""))

            first_seen = None
            if ad_data.get("created_at"):
                first_seen = datetime.fromisoformat(
                    ad_data["created_at"].replace("Z", "+00:00")
                )

            video_url = None
            thumbnail_url = None
            media = ad_data.get("media", {})
            if media:
                video_url = media.get("video_url")
                thumbnail_url = media.get("preview_image_url")

            # Extract destination URL from card data
            card_data = ad_data.get("card", {}) or {}
            destination_url = (
                ad_data.get("website_url")
                or ad_data.get("card_url")
                or card_data.get("url")
                or card_data.get("website_url")
            )

            return CrawledAd(
                external_id=ad_id,
                platform="x_twitter",
                title=ad_data.get("name"),
                description=ad_data.get("tweet_text") or ad_data.get("text"),
                advertiser_name=ad_data.get("advertiser_name") or ad_data.get("screen_name"),
                advertiser_url=f"https://x.com/{ad_data['screen_name']}" if ad_data.get("screen_name") else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                view_count=ad_data.get("impression_count"),
                like_count=ad_data.get("like_count"),
                first_seen_at=first_seen,
                metadata={
                    "source": "x_ads_api",
                    "tweet_id": ad_data.get("tweet_id"),
                    "card_type": ad_data.get("card_type"),
                    "targeting": ad_data.get("targeting"),
                    "funding_source": ad_data.get("funding_instrument_name"),
                    "engagement": {
                        "retweets": ad_data.get("retweet_count"),
                        "replies": ad_data.get("reply_count"),
                        "clicks": ad_data.get("click_count"),
                    },
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("x_twitter_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card) -> Optional[CrawledAd]:
        """Parse ad from scraped HTML card."""
        try:
            ad_id = card.get("data-ad-id", "")
            title_el = card.select_one("h3, .ad-title, .tweet-text")
            desc_el = card.select_one("p, .ad-body, .tweet-content")
            advertiser_el = card.select_one(".advertiser-name, .screen-name, .username")

            video_el = card.select_one("video source")
            video_url = video_el.get("src") if video_el else None

            # Extract destination URL from scraped card
            link_el = card.select_one("a[data-card-url], a.card-link, a[href]:not([href*='x.com']):not([href*='twitter.com'])")
            destination_url = None
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("http") and "x.com" not in href and "twitter.com" not in href:
                    destination_url = href

            return CrawledAd(
                external_id=ad_id or f"x_{hash(str(card)):#010x}",
                platform="x_twitter",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                metadata={
                    "source": "x_transparency_scrape",
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("x_twitter_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific X ad."""
        if self.bearer_token:
            client = await self._get_client()
            try:
                headers = {"Authorization": f"Bearer {self.bearer_token}"}
                response = await client.get(
                    f"{X_ADS_API_BASE}/transparency/ads/{external_id}",
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("data"):
                    return self._parse_api_ad(data["data"])
            except Exception as e:
                logger.error("x_twitter_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific X advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
