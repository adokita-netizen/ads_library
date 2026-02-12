"""Google Ads Transparency Center crawler (Google広告).

YouTubeクローラーはYouTube動画広告に特化していますが、
このクローラーはGoogle検索広告・ディスプレイ広告・ショッピング広告など
YouTube以外のGoogle広告を網羅します。
"""

import asyncio
import re
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

# Google Ads Transparency Center
GOOGLE_ADS_TRANSPARENCY_URL = "https://adstransparency.google.com"
# Google Ads API
GOOGLE_ADS_API_BASE = "https://googleads.googleapis.com/v17"


class GoogleAdsCrawler(BaseCrawler):
    """Crawler for Google Ads Transparency Center / Google Ads API.

    YouTube以外のGoogle広告を取得:
    - Google検索広告 (Search Ads)
    - Googleディスプレイ広告 (Display Network)
    - Googleショッピング広告
    - Gmail広告
    - Google Discover広告

    Supports:
    - Google Ads Transparency Center (public page)
    - Google Ads API v17 (with developer token + OAuth)
    """

    def __init__(
        self,
        developer_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        rate_limit_delay: float = 2.0,
    ):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.developer_token = developer_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self._access_token: Optional[str] = None

    async def _get_access_token(self) -> Optional[str]:
        """Get OAuth2 access token using refresh token."""
        if not self.refresh_token or not self.client_id:
            return None

        if self._access_token:
            return self._access_token

        client = await self._get_client()
        try:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
            )
            response.raise_for_status()
            self._access_token = response.json().get("access_token")
            return self._access_token
        except Exception as e:
            logger.error("google_oauth_token_failed", error=str(e))
            return None

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        region: str = "JP",
        ad_format: Optional[str] = None,
        **kwargs,
    ) -> list[CrawledAd]:
        """Search Google ads (non-YouTube)."""
        results: list[CrawledAd] = []

        if self.developer_token and self.refresh_token:
            results = await self._search_via_api(query, category, limit, region)

        if not results:
            results = await self._search_via_scraping(query, limit, region, ad_format)

        logger.info("google_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        region: str,
    ) -> list[CrawledAd]:
        """Search using Google Ads API (requires developer token + OAuth)."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        access_token = await self._get_access_token()
        if not access_token:
            return results

        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "developer-token": self.developer_token,
                "Content-Type": "application/json",
            }

            # Google Ads API uses GAQL for querying
            gaql_query = (
                "SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, "
                "ad_group_ad.ad.type, ad_group_ad.ad.final_urls, "
                "ad_group_ad.ad.responsive_display_ad.headlines, "
                "ad_group_ad.ad.responsive_display_ad.descriptions, "
                "ad_group_ad.ad.video_ad.video.id, "
                "campaign.name, campaign.advertising_channel_type, "
                "customer.descriptive_name "
                "FROM ad_group_ad "
                f"WHERE ad_group_ad.ad.name LIKE '%{query}%' "
                f"LIMIT {min(limit, 100)}"
            )

            payload = {"query": gaql_query}

            response = await client.post(
                f"{GOOGLE_ADS_API_BASE}/customers/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            for row in data.get("results", []):
                crawled_ad = self._parse_api_ad(row)
                if crawled_ad:
                    results.append(crawled_ad)

        except Exception as e:
            logger.error("google_ads_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        limit: int,
        region: str,
        ad_format: Optional[str] = None,
    ) -> list[CrawledAd]:
        """Scrape Google Ads Transparency Center (non-VIDEO formats)."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            # Search across different ad formats
            formats = ["TEXT", "IMAGE", "VIDEO"] if not ad_format else [ad_format]

            for fmt in formats:
                if len(results) >= limit:
                    break

                params = {
                    "query": query,
                    "region": region,
                    "format": fmt,
                }

                response = await client.get(
                    f"{GOOGLE_ADS_TRANSPARENCY_URL}/advertiser",
                    params=params,
                )
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "lxml")
                ad_elements = soup.select(
                    "[data-creative-id], .creative-card, .ad-card, "
                    "[data-ad-format], .creative-preview"
                )

                for element in ad_elements:
                    if len(results) >= limit:
                        break
                    crawled_ad = self._parse_scraped_element(element, fmt)
                    if crawled_ad:
                        results.append(crawled_ad)

                await asyncio.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error("google_ads_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, row: dict) -> Optional[CrawledAd]:
        """Parse ad data from Google Ads API response."""
        try:
            ad = row.get("adGroupAd", {}).get("ad", {})
            campaign = row.get("campaign", {})
            customer = row.get("customer", {})

            ad_id = str(ad.get("id", ""))

            # Extract headlines and descriptions
            responsive = ad.get("responsiveDisplayAd", {})
            headlines = responsive.get("headlines", [])
            descriptions = responsive.get("descriptions", [])

            title = headlines[0].get("text") if headlines else ad.get("name")
            description = descriptions[0].get("text") if descriptions else None

            final_urls = ad.get("finalUrls", [])
            destination_url = final_urls[0] if final_urls else None
            video_id = ad.get("videoAd", {}).get("video", {}).get("id")
            video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None

            return CrawledAd(
                external_id=ad_id,
                platform="google_ads",
                title=title,
                description=description,
                advertiser_name=customer.get("descriptiveName"),
                video_url=video_url,
                metadata={
                    "source": "google_ads_api",
                    "ad_type": ad.get("type"),
                    "campaign_name": campaign.get("name"),
                    "channel_type": campaign.get("advertisingChannelType"),
                    "final_urls": final_urls,
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                    "responsive_headlines": [h.get("text") for h in headlines],
                    "responsive_descriptions": [d.get("text") for d in descriptions],
                },
            )
        except Exception as e:
            logger.error("google_ads_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_element(self, element, ad_format: str = "") -> Optional[CrawledAd]:
        """Parse ad from scraped transparency page."""
        try:
            creative_id = element.get("data-creative-id", "")
            title_el = element.select_one("h3, .ad-title, .creative-title, .headline")
            desc_el = element.select_one(".ad-description, .creative-body, .description")
            advertiser_el = element.select_one(".advertiser-name, .page-name")

            video_el = element.select_one("video source, iframe")
            video_url = None
            if video_el:
                video_url = video_el.get("src") or video_el.get("data-src")

            img_el = element.select_one("img.thumbnail, img.creative-image, img")
            thumbnail_url = img_el.get("src") if img_el else None

            # Extract destination URL from ad links
            link_el = element.select_one(
                "a[href]:not([href*='google.com']):not([href*='transparencyreport'])"
            )
            destination_url = None
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("http") and "google.com" not in href:
                    destination_url = href

            date_el = element.select_one(".date-range, .delivery-date")
            first_seen = None
            if date_el:
                date_text = date_el.get_text(strip=True)
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
                if date_match:
                    first_seen = datetime.fromisoformat(date_match.group(1))

            return CrawledAd(
                external_id=creative_id or f"gads_{hash(str(element)):#010x}",
                platform="google_ads",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                first_seen_at=first_seen,
                metadata={
                    "source": "google_ads_transparency",
                    "ad_format": ad_format,
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("google_ads_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific Google ad."""
        client = await self._get_client()
        try:
            url = f"{GOOGLE_ADS_TRANSPARENCY_URL}/advertiser/{external_id}"
            response = await client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")
            element = soup.select_one("[data-creative-id], .creative-detail")
            if element:
                return self._parse_scraped_element(element)
        except Exception as e:
            logger.error("google_ads_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific Google advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
