"""YouTube Ad crawler using YouTube Ads Transparency Center."""

import asyncio
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import structlog
from bs4 import BeautifulSoup

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

YOUTUBE_ADS_TRANSPARENCY_URL = "https://adstransparency.google.com"


def _candidate_search_urls(query: str, region: str, format_type: str = "VIDEO") -> list[str]:
    params = urlencode({"query": query, "region": region, "format": format_type})
    return [
        f"{YOUTUBE_ADS_TRANSPARENCY_URL}/?{params}",
        f"{YOUTUBE_ADS_TRANSPARENCY_URL}/advertiser?{params}",
    ]


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
            params = {"query": query, "region": region, "format": "VIDEO"}
            if date_range:
                params["date_range"] = date_range

            for search_url in _candidate_search_urls(query, region):
                response = await client.get(search_url, params=None if "?" in search_url else params)
                if response.status_code >= 400:
                    logger.info(
                        "youtube_search_url_failed",
                        query=query,
                        url=search_url,
                        status_code=response.status_code,
                    )
                    continue

                soup = BeautifulSoup(response.text, "lxml")
                ad_elements = soup.select("[data-creative-id], .creative-card, .ad-card")

                for element in ad_elements[:limit]:
                    crawled_ad = self._parse_ad_element(element)
                    if crawled_ad:
                        results.append(crawled_ad)

                    await asyncio.sleep(self.rate_limit_delay)

                if results:
                    break

        except Exception as e:
            logger.error("youtube_search_failed", query=query, error=str(e))

        if not results:
            results = await self._search_via_playwright(query=query, limit=limit, region=region)

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

            # Extract destination URL from ad link elements
            link_el = element.select_one(
                "a.ad-destination, a[data-destination-url], a.landing-page-link, "
                "a[href]:not([href*='google.com']):not([href*='youtube.com'])"
            )
            destination_url = None
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("http") and "google.com" not in href and "youtube.com" not in href:
                    destination_url = href
            # Also check for destination URL in data attributes
            if not destination_url:
                destination_url = element.get("data-destination-url") or element.get("data-landing-page")

            return CrawledAd(
                external_id=creative_id or f"yt_{hash(str(element)):#010x}",
                platform="youtube",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=advertiser_el.get_text(strip=True) if advertiser_el else None,
                video_url=video_url,
                thumbnail_url=thumbnail_url,
                destination_url=destination_url,
                first_seen_at=first_seen,
                metadata={
                    "source": "google_ads_transparency",
                    "destination_type": "LP" if destination_url else None,
                },
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

    async def _search_via_playwright(self, query: str, limit: int, region: str) -> list[CrawledAd]:
        """Playwright fallback for JS-rendered transparency pages."""
        try:
            from playwright.async_api import async_playwright
        except Exception:
            logger.warning("youtube_playwright_not_installed")
            return []

        results: list[CrawledAd] = []
        browser = None
        pw = None
        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(locale="ja-JP")

            ads_data = []
            extract_js = """(maxCount) => {
                    const cards = Array.from(document.querySelectorAll('[data-creative-id], .creative-card, .ad-card')).slice(0, maxCount);
                    return cards.map((el) => {
                      const pick = (sels) => {
                        for (const s of sels) {
                          const n = el.querySelector(s);
                          if (n && n.textContent) return n.textContent.trim();
                        }
                        return null;
                      };
                      const hrefNode = el.querySelector('a[href]:not([href*="google.com"]):not([href*="youtube.com"])');
                      const imgNode = el.querySelector('img');
                      const videoNode = el.querySelector('video source, iframe');
                      return {
                        ad_id: el.getAttribute('data-creative-id') || null,
                        title: pick(['h3', '.ad-title', '.creative-title']),
                        description: pick(['.ad-description', '.creative-body', 'p']),
                        advertiser_name: pick(['.advertiser-name', '.page-name']),
                        thumbnail_url: imgNode ? (imgNode.getAttribute('src') || imgNode.getAttribute('data-src')) : null,
                        video_url: videoNode ? (videoNode.getAttribute('src') || videoNode.getAttribute('data-src')) : null,
                        destination_url: hrefNode ? hrefNode.getAttribute('href') : null
                      };
                    });
                }"""
            for target_url in _candidate_search_urls(query, region):
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                    await page.wait_for_timeout(3000)
                    ads_data = await page.evaluate(extract_js, limit)
                except Exception as exc:
                    logger.info("youtube_playwright_candidate_failed", query=query, url=target_url, error=str(exc)[:200])
                    continue
                if ads_data:
                    break
            for idx, ad in enumerate(ads_data or []):
                results.append(
                    CrawledAd(
                        external_id=str(ad.get("ad_id") or f"yt_pw_{idx}_{hash(query) & 0xffff:x}"),
                        platform="youtube",
                        title=ad.get("title"),
                        description=ad.get("description"),
                        advertiser_name=ad.get("advertiser_name"),
                        video_url=ad.get("video_url"),
                        thumbnail_url=ad.get("thumbnail_url"),
                        destination_url=ad.get("destination_url"),
                        metadata={"source": "youtube_playwright_fallback"},
                    )
                )
        except Exception as e:
            logger.error("youtube_playwright_fallback_failed", query=query, error=str(e))
        finally:
            try:
                if browser:
                    await browser.close()
                if pw:
                    await pw.stop()
            except Exception:
                pass
        return results
