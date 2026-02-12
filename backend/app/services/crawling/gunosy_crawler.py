"""Gunosy Ads crawler (グノシー広告).

Gunosy (グノシー) はSmartNewsと並ぶ日本の主要ニュースアプリ。
インフィード広告・動画広告を配信しています。
関連媒体: LUCRA, ニュースパス (KDDI)
"""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

# Gunosy Ads API
GUNOSY_ADS_API = "https://ads.gunosy.com/api/v1"
# Gunosy web
GUNOSY_WEB_URL = "https://gunosy.com"


class GunosyAdCrawler(BaseCrawler):
    """Crawler for Gunosy Ads.

    Gunosyは公開の広告ライブラリを持っていないため、
    以下のアプローチで広告データを収集します:

    1. Gunosy Ads API (パートナーAPIキーが必要)
    2. Gunosyウェブ版からのインフィード広告検出

    Gunosy広告の種類:
    - インフィード広告 (ニュースフィード内)
    - 動画広告
    - ネイティブ広告
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit_delay: float = 2.0,
    ):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.api_key = api_key

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        **kwargs,
    ) -> list[CrawledAd]:
        """Search Gunosy ads."""
        results: list[CrawledAd] = []

        if self.api_key:
            results = await self._search_via_api(query, category, limit)
        else:
            results = await self._search_via_scraping(query, limit)

        logger.info("gunosy_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
    ) -> list[CrawledAd]:
        """Search using Gunosy Ads API."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            headers = {
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "keyword": query,
                "limit": min(limit, 100),
                "offset": 0,
            }

            if category:
                payload["category"] = category

            response = await client.post(
                f"{GUNOSY_ADS_API}/creatives/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            for ad_data in data.get("creatives", data.get("data", [])):
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    results.append(crawled_ad)
                    if len(results) >= limit:
                        break

        except Exception as e:
            logger.error("gunosy_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
    ) -> list[CrawledAd]:
        """Fallback: detect ads from Gunosy web content."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            categories = [
                "entertainment", "sports", "funny", "domestic",
                "international", "column", "technology", "gourmet",
            ]

            for cat in categories:
                if len(results) >= limit:
                    break

                response = await client.get(
                    f"{GUNOSY_WEB_URL}/categories/{cat}",
                    headers={"Accept-Language": "ja"},
                )
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "lxml")

                # Detect sponsored/ad content
                ad_indicators = soup.select(
                    "[data-ad-id], .ad-unit, .sponsored, .promotion, "
                    "[data-type='ad'], .list_item--ad, .ad_label"
                )

                for card in ad_indicators:
                    if len(results) >= limit:
                        break
                    crawled_ad = self._parse_scraped_card(card, cat)
                    if crawled_ad:
                        results.append(crawled_ad)

                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("gunosy_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from Gunosy Ads API response."""
        try:
            ad_id = str(ad_data.get("creativeId") or ad_data.get("id", ""))

            creative = ad_data.get("creative", ad_data)

            first_seen = None
            if ad_data.get("startDate") or ad_data.get("createdAt"):
                date_str = ad_data.get("startDate") or ad_data.get("createdAt")
                first_seen = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            return CrawledAd(
                external_id=ad_id,
                platform="gunosy",
                title=creative.get("title") or creative.get("headline"),
                description=creative.get("description") or creative.get("body"),
                advertiser_name=ad_data.get("advertiserName") or ad_data.get("sponsorName"),
                video_url=creative.get("videoUrl"),
                thumbnail_url=creative.get("imageUrl") or creative.get("thumbnailUrl"),
                first_seen_at=first_seen,
                metadata={
                    "source": "gunosy_ads_api",
                    "campaign_id": ad_data.get("campaignId"),
                    "ad_format": creative.get("format"),
                    "destination_url": creative.get("landingUrl"),
                    "category": ad_data.get("category"),
                },
            )
        except Exception as e:
            logger.error("gunosy_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card, category: str = "") -> Optional[CrawledAd]:
        """Parse ad from scraped HTML content."""
        try:
            ad_id = card.get("data-ad-id", "")
            title_el = card.select_one("h2, h3, .title, .headline, a")
            desc_el = card.select_one("p, .description, .summary")
            advertiser_el = card.select_one(".sponsor, .advertiser, .source, .ad_label")

            video_el = card.select_one("video source")
            video_url = video_el.get("src") if video_el else None

            img_el = card.select_one("img")
            thumbnail_url = img_el.get("src") if img_el else None

            link_el = card.select_one("a[href]")
            destination_url = link_el.get("href") if link_el else None

            return CrawledAd(
                external_id=ad_id or f"gn_{hash(str(card)):#010x}",
                platform="gunosy",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                category=category,
                metadata={
                    "source": "gunosy_web_scrape",
                    "destination_url": destination_url,
                },
            )
        except Exception as e:
            logger.error("gunosy_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific Gunosy ad."""
        if self.api_key:
            client = await self._get_client()
            try:
                headers = {"X-Api-Key": self.api_key}
                response = await client.get(
                    f"{GUNOSY_ADS_API}/creatives/{external_id}",
                    headers=headers,
                )
                response.raise_for_status()
                return self._parse_api_ad(response.json())
            except Exception as e:
                logger.error("gunosy_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific Gunosy advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
