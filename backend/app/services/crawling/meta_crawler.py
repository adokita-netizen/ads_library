"""Meta (Facebook/Instagram) Ad Library crawler."""

import asyncio
from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

META_AD_LIBRARY_URL = "https://www.facebook.com/ads/library/"
META_AD_LIBRARY_API = "https://graph.facebook.com/v19.0/ads_archive"


class MetaAdLibraryCrawler(BaseCrawler):
    """Crawler for Meta Ad Library (Facebook / Instagram)."""

    def __init__(self, access_token: Optional[str] = None, rate_limit_delay: float = 2.0):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.access_token = access_token

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        country: str = "JP",
        ad_type: str = "ALL",
        **kwargs,
    ) -> list[CrawledAd]:
        """Search Meta Ad Library for ads."""
        results: list[CrawledAd] = []

        if self.access_token:
            results = await self._search_via_api(query, category, limit, country, ad_type)
        else:
            results = await self._search_via_scraping(query, category, limit, country)

        logger.info("meta_ads_search", query=query, results_count=len(results))
        return results

    async def _search_via_api(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        country: str,
        ad_type: str,
    ) -> list[CrawledAd]:
        """Search using official Meta Ad Library API."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        params = {
            "access_token": self.access_token,
            "search_terms": query,
            "ad_reached_countries": country,
            "ad_type": ad_type,
            "limit": min(limit, 50),
            "fields": (
                "id,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,"
                "ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions,"
                "page_id,page_name,publisher_platforms,estimated_audience_size,"
                "impressions,spend,currency,demographic_distribution,"
                "delivery_by_region,ad_snapshot_url"
            ),
        }

        if category:
            params["ad_active_status"] = "ALL"

        try:
            response = await client.get(META_AD_LIBRARY_API, params=params)
            response.raise_for_status()
            data = response.json()

            for ad_data in data.get("data", []):
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    results.append(crawled_ad)
                    if len(results) >= limit:
                        break

            # Handle pagination
            next_url = data.get("paging", {}).get("next")
            while next_url and len(results) < limit:
                await asyncio.sleep(self.rate_limit_delay)
                response = await client.get(next_url)
                response.raise_for_status()
                data = response.json()

                for ad_data in data.get("data", []):
                    crawled_ad = self._parse_api_ad(ad_data)
                    if crawled_ad:
                        results.append(crawled_ad)
                        if len(results) >= limit:
                            break

                next_url = data.get("paging", {}).get("next")

        except Exception as e:
            logger.error("meta_api_search_failed", error=str(e))

        return results

    async def _search_via_scraping(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        country: str,
    ) -> list[CrawledAd]:
        """Fallback: scrape Meta Ad Library web interface."""
        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            params = {
                "active_status": "all",
                "ad_type": "all",
                "country": country,
                "q": query,
                "media_type": "video",
            }

            response = await client.get(META_AD_LIBRARY_URL, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            ad_cards = soup.select("[data-testid='ad_library_card']")
            if not ad_cards:
                ad_cards = soup.select(".xrvj5dj")

            for card in ad_cards[:limit]:
                crawled_ad = self._parse_scraped_card(card)
                if crawled_ad:
                    results.append(crawled_ad)

        except Exception as e:
            logger.error("meta_scraping_failed", error=str(e))

        return results

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from Meta API response."""
        try:
            ad_id = ad_data.get("id", "")
            bodies = ad_data.get("ad_creative_bodies", [])
            titles = ad_data.get("ad_creative_link_titles", [])

            impressions = ad_data.get("impressions", {})
            impressions_lower = None
            if isinstance(impressions, dict) and impressions.get("lower_bound"):
                impressions_lower = int(impressions["lower_bound"])

            platforms = ad_data.get("publisher_platforms", [])
            platform = "facebook"
            if "instagram" in platforms:
                platform = "instagram"

            first_seen = None
            if ad_data.get("ad_delivery_start_time"):
                first_seen = datetime.fromisoformat(
                    ad_data["ad_delivery_start_time"].replace("Z", "+00:00")
                )

            # Extract destination URL from link descriptions or creative data
            link_descriptions = ad_data.get("ad_creative_link_descriptions", [])
            link_captions = ad_data.get("ad_creative_link_captions", [])
            destination_url = ad_data.get("link_url") or ad_data.get("website_url")
            if not destination_url and link_captions:
                # Caption often contains the display URL (e.g., "example.com/product")
                caption = link_captions[0]
                if caption and ("http" in caption or ("." in caption and "/" in caption)):
                    destination_url = caption if caption.startswith("http") else f"https://{caption}"

            return CrawledAd(
                external_id=ad_id,
                platform=platform,
                title=titles[0] if titles else None,
                description=bodies[0] if bodies else None,
                advertiser_name=ad_data.get("page_name"),
                video_url=ad_data.get("ad_snapshot_url"),
                first_seen_at=first_seen,
                metadata={
                    "page_id": ad_data.get("page_id"),
                    "publisher_platforms": platforms,
                    "estimated_audience_size": ad_data.get("estimated_audience_size"),
                    "spend": ad_data.get("spend"),
                    "currency": ad_data.get("currency"),
                    "demographic_distribution": ad_data.get("demographic_distribution"),
                    "delivery_by_region": ad_data.get("delivery_by_region"),
                    "impressions_lower": impressions_lower,
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("meta_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card) -> Optional[CrawledAd]:
        """Parse ad data from scraped HTML card."""
        try:
            ad_id = card.get("data-ad-id", "")
            title_el = card.select_one("h3, .x1heor9g")
            desc_el = card.select_one("p, .xdj266r")
            advertiser_el = card.select_one("[data-testid='page_name'], .x1i10hfl")

            # Extract destination URL from card link
            link_el = card.select_one("a[href*='l.facebook.com'], a[href*='http'], a.see-ad-link")
            destination_url = None
            if link_el:
                href = link_el.get("href", "")
                if "l.facebook.com/l.php" in href:
                    # Facebook redirect URL - extract and decode the actual URL param
                    import urllib.parse
                    parsed = urllib.parse.urlparse(href)
                    params = urllib.parse.parse_qs(parsed.query)
                    raw_url = params.get("u", [None])[0]
                    destination_url = urllib.parse.unquote(raw_url) if raw_url else None
                elif href.startswith("http") and "facebook.com" not in href:
                    destination_url = href

            return CrawledAd(
                external_id=ad_id or f"meta_scraped_{hash(str(card)):#010x}",
                platform="facebook",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                metadata={
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("meta_scrape_parse_failed", error=str(e))
            return None

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific Meta ad."""
        if self.access_token:
            client = await self._get_client()
            try:
                response = await client.get(
                    f"https://graph.facebook.com/v19.0/{external_id}",
                    params={
                        "access_token": self.access_token,
                        "fields": (
                            "id,ad_creation_time,ad_creative_bodies,ad_creative_link_titles,"
                            "page_name,publisher_platforms,ad_snapshot_url"
                        ),
                    },
                )
                response.raise_for_status()
                return self._parse_api_ad(response.json())
            except Exception as e:
                logger.error("meta_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(self, advertiser_name: str, limit: int = 50) -> list[CrawledAd]:
        """Get all ads from a specific Meta advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
