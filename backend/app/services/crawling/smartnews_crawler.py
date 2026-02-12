"""SmartNews Ads crawler (SmartNews広告)."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

# SmartNews Ads - no public ad library, use standard ads API
SMARTNEWS_ADS_API = "https://partners.smartnews-ads.com/api/v1"
# SmartNews web (for ad creative discovery)
SMARTNEWS_WEB_URL = "https://www.smartnews.com"


class SmartNewsAdCrawler(BaseCrawler):
    """Crawler for SmartNews Ads.

    SmartNewsは公開の広告ライブラリを持っていないため、
    以下のアプローチで広告データを収集します:

    1. SmartNews Ads API (パートナーAPIキーが必要)
    2. SmartNews記事面からのインフィード広告検出
    3. SmartNews内コンテンツからの広告クリエイティブ収集

    SmartNews広告の種類:
    - Standard Ads (インフィード広告)
    - Video Ads (動画広告)
    - Carousel Ads (カルーセル)
    - Premium Display
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
        """Search SmartNews ads."""
        results: list[CrawledAd] = []

        if self.api_key:
            results = await self._search_via_api(query, category, limit)
        else:
            results = await self._search_via_scraping(query, limit)

        logger.info("smartnews_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
    ) -> list[CrawledAd]:
        """Search using SmartNews Ads API."""
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
                "format": "ALL",
            }

            if category:
                payload["category"] = category

            response = await client.post(
                f"{SMARTNEWS_ADS_API}/creatives/search",
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
            logger.error("smartnews_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
    ) -> list[CrawledAd]:
        """Fallback: detect ads from SmartNews web content.

        SmartNewsはインフィード広告が中心のため、
        記事フィードからスポンサード記事・広告を検出します。
        """
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            # Try SmartNews web feed with category filtering
            categories = ["top", "business", "technology", "entertainment", "sports"]
            for cat in categories:
                if len(results) >= limit:
                    break

                response = await client.get(
                    f"{SMARTNEWS_WEB_URL}/{cat}",
                    headers={"Accept-Language": "ja"},
                )
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "lxml")

                # Detect sponsored/ad content
                ad_indicators = soup.select(
                    "[data-ad-id], [data-sponsored], .sponsored, .ad-unit, "
                    ".promotion, [data-type='ad'], .smartnews-ad"
                )

                for card in ad_indicators:
                    if len(results) >= limit:
                        break
                    crawled_ad = self._parse_scraped_card(card, cat)
                    if crawled_ad:
                        results.append(crawled_ad)

                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("smartnews_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from SmartNews Ads API response."""
        try:
            ad_id = str(ad_data.get("creativeId") or ad_data.get("id", ""))

            creative = ad_data.get("creative", ad_data)

            first_seen = None
            if ad_data.get("startDate") or ad_data.get("createdAt"):
                date_str = ad_data.get("startDate") or ad_data.get("createdAt")
                first_seen = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            video_url = creative.get("videoUrl")
            thumbnail_url = creative.get("imageUrl") or creative.get("thumbnailUrl")

            return CrawledAd(
                external_id=ad_id,
                platform="smartnews",
                title=creative.get("title") or creative.get("headline"),
                description=creative.get("description") or creative.get("body"),
                advertiser_name=ad_data.get("advertiserName") or ad_data.get("sponsorName"),
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                first_seen_at=first_seen,
                metadata={
                    "source": "smartnews_ads_api",
                    "campaign_id": ad_data.get("campaignId"),
                    "ad_format": creative.get("format"),
                    "placement": ad_data.get("placement"),
                    "destination_url": creative.get("landingUrl") or creative.get("clickUrl"),
                    "call_to_action": creative.get("ctaText"),
                    "category": ad_data.get("category"),
                    "impression_count": ad_data.get("impressions"),
                    "click_count": ad_data.get("clicks"),
                },
            )
        except Exception as e:
            logger.error("smartnews_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card, category: str = "") -> Optional[CrawledAd]:
        """Parse ad from scraped HTML content."""
        try:
            ad_id = card.get("data-ad-id", "") or card.get("data-sponsored", "")
            title_el = card.select_one("h2, h3, .title, .headline, a")
            desc_el = card.select_one("p, .description, .summary")
            advertiser_el = card.select_one(".sponsor, .advertiser, .source")

            video_el = card.select_one("video source")
            video_url = video_el.get("src") if video_el else None

            img_el = card.select_one("img")
            thumbnail_url = img_el.get("src") if img_el else None

            link_el = card.select_one("a[href]")
            destination_url = link_el.get("href") if link_el else None

            return CrawledAd(
                external_id=ad_id or f"sn_{hash(str(card)):#010x}",
                platform="smartnews",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                category=category,
                metadata={
                    "source": "smartnews_web_scrape",
                    "destination_url": destination_url,
                },
            )
        except Exception as e:
            logger.error("smartnews_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific SmartNews ad."""
        if self.api_key:
            client = await self._get_client()
            try:
                headers = {"X-Api-Key": self.api_key}
                response = await client.get(
                    f"{SMARTNEWS_ADS_API}/creatives/{external_id}",
                    headers=headers,
                )
                response.raise_for_status()
                return self._parse_api_ad(response.json())
            except Exception as e:
                logger.error("smartnews_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific SmartNews advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
