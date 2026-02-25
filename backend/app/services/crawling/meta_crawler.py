"""Meta (Facebook/Instagram) Ad Library crawler.

Supports three data sources in priority order:
1. Official Meta Graph API (ads_archive) — requires access_token
2. Playwright browser scraping — headless Chromium fallback
3. httpx + BeautifulSoup scraping — lightweight last resort
"""

import asyncio
import re
import urllib.parse
from datetime import datetime
from typing import Optional

import structlog

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd

logger = structlog.get_logger()

META_AD_LIBRARY_URL = "https://www.facebook.com/ads/library/"
META_GRAPH_API_VERSION = "v25.0"
META_AD_LIBRARY_API = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/ads_archive"

# JavaScript to extract ad data from the rendered Ad Library page.
# Facebook renders ad cards with ライブラリID, 掲載開始日, advertiser info, etc.
_BROWSER_EXTRACT_JS = r"""() => {
    const results = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const idElements = [];
    while (walker.nextNode()) {
        if (walker.currentNode.textContent.includes('\u30e9\u30a4\u30d6\u30e9\u30eaID')) {
            idElements.push(walker.currentNode.parentElement);
        }
    }

    for (const el of idElements) {
        let card = el;
        for (let i = 0; i < 15; i++) {
            if (!card.parentElement) break;
            card = card.parentElement;
            const text = card.innerText || '';
            if (text.includes('\u30e9\u30a4\u30d6\u30e9\u30eaID') &&
                text.includes('\u63b2\u8f09\u958b\u59cb\u65e5') &&
                text.includes('\u5e83\u544a\u306e\u8a73\u7d30\u3092\u898b\u308b')) {
                break;
            }
        }

        const text = card.innerText || '';
        const idMatch = text.match(/\u30e9\u30a4\u30d6\u30e9\u30eaID:\s*(\d+)/);
        const dateMatch = text.match(/\u63b2\u8f09\u958b\u59cb\u65e5:\s*(\d{4}\/\d{2}\/\d{2})/);

        const sponsorIdx = text.indexOf('\u30b9\u30dd\u30f3\u30b5\u30fc\u5e83\u544a');
        let advertiser = null;
        if (sponsorIdx > 0) {
            const before = text.slice(0, sponsorIdx).trim();
            const lines = before.split('\n').filter(l => l.trim());
            advertiser = lines[lines.length - 1].trim();
        }

        let body = '';
        if (sponsorIdx > 0) {
            const after = text.slice(sponsorIdx + 7).trim();
            const bodyLines = after.split('\n').filter(l => l.trim() && !l.includes('\u5e83\u544a\u306e\u8a73\u7d30'));
            body = bodyLines.join('\n').slice(0, 2000);
        }

        const links = card.querySelectorAll('a[href]');
        const extLinks = [];
        for (const link of links) {
            const href = link.getAttribute('href') || '';
            if (href.includes('l.facebook.com/l.php')) {
                try {
                    const u = new URL(href).searchParams.get('u');
                    if (u) extLinks.push(decodeURIComponent(u));
                } catch(e) {}
            } else if (href.startsWith('http') &&
                       !href.includes('facebook.com') &&
                       !href.includes('instagram.com') &&
                       !href.includes('metastatus.com')) {
                extLinks.push(href);
            }
        }

        let displayUrl = null;
        const spans = card.querySelectorAll('span');
        for (const sp of spans) {
            const t = (sp.innerText || '').trim();
            if (/^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,}(\/.*)?$/.test(t) && t.length < 100) {
                displayUrl = t;
                break;
            }
        }

        // Detect platforms from icons/text
        const platformText = text.toLowerCase();
        const platforms = [];
        if (platformText.includes('facebook') || card.querySelector('[aria-label*="Facebook"]')) platforms.push('facebook');
        if (platformText.includes('instagram') || card.querySelector('[aria-label*="Instagram"]')) platforms.push('instagram');
        if (platformText.includes('messenger') || card.querySelector('[aria-label*="Messenger"]')) platforms.push('messenger');
        if (platformText.includes('threads') || card.querySelector('[aria-label*="Threads"]')) platforms.push('threads');

        if (idMatch || advertiser) {
            results.push({
                ad_id: idMatch ? idMatch[1] : null,
                start_date: dateMatch ? dateMatch[1] : null,
                advertiser: advertiser,
                body: body,
                destination_url: extLinks.length > 0 ? extLinks[0] : null,
                all_external_links: extLinks,
                display_url: displayUrl,
                platforms: platforms.length > 0 ? platforms : ['facebook'],
            });
        }
    }
    return results;
}"""


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
        """Search Meta Ad Library for ads.

        Strategy:
        1. If access_token is set, try the official API first.
        2. If the API fails (e.g. 500 for certain queries), fall back
           to browser-based scraping via Playwright.
        3. If Playwright is unavailable, fall back to httpx scraping.
        """
        results: list[CrawledAd] = []

        if self.access_token:
            results = await self._search_via_api(query, category, limit, country, ad_type)

        # If API returned nothing (error or empty), try browser fallback
        if not results:
            logger.info("meta_api_empty_or_failed_trying_browser", query=query)
            results = await self._search_via_browser(query, category, limit, country)

        # If browser also failed, try lightweight scraping
        if not results:
            logger.info("meta_browser_failed_trying_httpx", query=query)
            results = await self._search_via_scraping(query, category, limit, country)

        logger.info("meta_ads_search", query=query, results_count=len(results))
        return results

    # ── 1. Official API ──────────────────────────────────────────

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
            "ad_reached_countries": f'["{country}"]',
            "ad_type": ad_type,
            "limit": min(limit, 100),
            "fields": (
                "id,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,"
                "ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions,"
                "ad_creative_link_captions,languages,"
                "page_id,page_name,publisher_platforms,estimated_audience_size,"
                "impressions,spend,currency,demographic_distribution,"
                "delivery_by_region,ad_snapshot_url"
            ),
        }

        if category:
            params["ad_active_status"] = "ALL"

        try:
            response = await client.get(META_AD_LIBRARY_API, params=params)
            if response.status_code != 200:
                try:
                    error_body = response.json()
                except Exception:
                    error_body = response.text[:500]
                logger.warning(
                    "meta_api_non_200",
                    status=response.status_code,
                    query=query,
                    error_body=error_body,
                )
                if response.status_code == 500:
                    return []  # trigger browser fallback
                response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.warning("meta_api_error", error=data["error"])
                return []

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
                if response.status_code != 200:
                    break
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

    # ── 2. Playwright browser scraping ───────────────────────────

    async def _search_via_browser(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        country: str,
    ) -> list[CrawledAd]:
        """Fallback: use Playwright headless browser to scrape Ad Library."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright_not_installed")
            return []

        results: list[CrawledAd] = []

        params = urllib.parse.urlencode({
            "active_status": "all",
            "ad_type": "all",
            "country": country,
            "q": query,
        })
        url = f"{META_AD_LIBRARY_URL}?{params}"

        pw = None
        browser = None
        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                locale="ja-JP",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Wait for initial ad cards to render
            await page.wait_for_timeout(5000)

            # Scroll down to load more ads (Facebook lazy-loads)
            scroll_rounds = max(1, limit // 5)
            for _ in range(min(scroll_rounds, 30)):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

            # Extract ad data from the rendered page
            ads_data = await page.evaluate(_BROWSER_EXTRACT_JS)

            seen_ids = set()
            for ad in ads_data:
                if len(results) >= limit:
                    break

                ad_id = ad.get("ad_id") or ""
                if ad_id and ad_id in seen_ids:
                    continue
                if ad_id:
                    seen_ids.add(ad_id)

                destination_url = ad.get("destination_url")
                display_url = ad.get("display_url")
                if not destination_url and display_url:
                    destination_url = (
                        display_url
                        if display_url.startswith("http")
                        else f"https://{display_url}"
                    )

                first_seen = None
                if ad.get("start_date"):
                    try:
                        first_seen = datetime.strptime(ad["start_date"], "%Y/%m/%d")
                    except ValueError:
                        pass

                # Determine platform from detected platforms
                platforms = ad.get("platforms", ["facebook"])
                platform = "instagram" if "instagram" in platforms else "facebook"

                results.append(CrawledAd(
                    external_id=ad_id or f"meta_browser_{hash(ad.get('body', '')):#010x}",
                    platform=platform,
                    title=None,
                    description=ad.get("body"),
                    advertiser_name=ad.get("advertiser"),
                    first_seen_at=first_seen,
                    metadata={
                        "source": "browser_scraping",
                        "publisher_platforms": platforms,
                        "destination_url": destination_url,
                        "display_url": display_url,
                        "all_external_links": ad.get("all_external_links", []),
                        "destination_type": "LP" if destination_url else None,
                    },
                ))

            logger.info(
                "meta_browser_scraping_done",
                query=query,
                results=len(results),
            )

        except Exception as e:
            logger.error("meta_browser_scraping_failed", error=str(e))
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

        return results

    # ── 3. Lightweight httpx scraping (last resort) ──────────────

    async def _search_via_scraping(
        self,
        query: str,
        category: Optional[str],
        limit: int,
        country: str,
    ) -> list[CrawledAd]:
        """Last resort: httpx + BeautifulSoup scrape (no JS rendering)."""
        from bs4 import BeautifulSoup

        client = await self._get_client()
        results: list[CrawledAd] = []

        try:
            params = {
                "active_status": "all",
                "ad_type": "all",
                "country": country,
                "q": query,
            }

            response = await client.get(META_AD_LIBRARY_URL, params=params)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

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

    # ── Parsers ──────────────────────────────────────────────────

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
                try:
                    first_seen = datetime.fromisoformat(
                        ad_data["ad_delivery_start_time"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            last_seen = None
            if ad_data.get("ad_delivery_stop_time"):
                try:
                    last_seen = datetime.fromisoformat(
                        ad_data["ad_delivery_stop_time"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Extract destination URL from link captions/descriptions
            link_descriptions = ad_data.get("ad_creative_link_descriptions", [])
            link_captions = ad_data.get("ad_creative_link_captions", [])
            destination_url = ad_data.get("link_url") or ad_data.get("website_url")

            display_url = None
            if not destination_url and link_captions:
                caption = link_captions[0]
                if caption:
                    display_url = caption
                    # Caption is a domain or URL (e.g. "hypnozio.com", "example.com/offer")
                    if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,}', caption):
                        destination_url = (
                            caption
                            if caption.startswith("http")
                            else f"https://{caption}"
                        )
                    elif "http" in caption:
                        destination_url = caption

            return CrawledAd(
                external_id=ad_id,
                platform=platform,
                title=titles[0] if titles else None,
                description=bodies[0] if bodies else None,
                advertiser_name=ad_data.get("page_name"),
                snapshot_url=ad_data.get("ad_snapshot_url"),
                creative_type="unknown",
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                metadata={
                    "source": "api",
                    "page_id": ad_data.get("page_id"),
                    "publisher_platforms": platforms,
                    "estimated_audience_size": ad_data.get("estimated_audience_size"),
                    "spend": ad_data.get("spend"),
                    "currency": ad_data.get("currency"),
                    "demographic_distribution": ad_data.get("demographic_distribution"),
                    "delivery_by_region": ad_data.get("delivery_by_region"),
                    "impressions_lower": impressions_lower,
                    "languages": ad_data.get("languages"),
                    "link_descriptions": link_descriptions or None,
                    "destination_url": destination_url,
                    "display_url": display_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("meta_api_parse_failed", error=str(e))
            return None

    def _parse_scraped_card(self, card) -> Optional[CrawledAd]:
        """Parse ad data from BeautifulSoup scraped HTML card."""
        try:
            ad_id = card.get("data-ad-id", "")
            title_el = card.select_one("h3, .x1heor9g")
            desc_el = card.select_one("p, .xdj266r")
            advertiser_el = card.select_one("[data-testid='page_name'], .x1i10hfl")

            # Extract destination URL from card link
            link_el = card.select_one(
                "a[href*='l.facebook.com'], a[href*='http'], a.see-ad-link"
            )
            destination_url = None
            if link_el:
                href = link_el.get("href", "")
                if "l.facebook.com/l.php" in href:
                    parsed = urllib.parse.urlparse(href)
                    params = urllib.parse.parse_qs(parsed.query)
                    raw_url = params.get("u", [None])[0]
                    destination_url = (
                        urllib.parse.unquote(raw_url) if raw_url else None
                    )
                elif href.startswith("http") and "facebook.com" not in href:
                    destination_url = href

            return CrawledAd(
                external_id=ad_id or f"meta_scraped_{hash(str(card)):#010x}",
                platform="facebook",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=(
                    advertiser_el.get_text(strip=True) if advertiser_el else None
                ),
                metadata={
                    "source": "httpx_scraping",
                    "destination_url": destination_url,
                    "destination_type": "LP" if destination_url else None,
                },
            )
        except Exception as e:
            logger.error("meta_scrape_parse_failed", error=str(e))
            return None

    # ── Detail / advertiser lookups ──────────────────────────────

    async def get_ad_details(self, external_id: str) -> Optional[CrawledAd]:
        """Get details for a specific Meta ad."""
        if self.access_token:
            client = await self._get_client()
            try:
                response = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{external_id}",
                    params={
                        "access_token": self.access_token,
                        "fields": (
                            "id,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,"
                            "ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions,"
                            "ad_creative_link_captions,languages,"
                            "page_id,page_name,publisher_platforms,ad_snapshot_url"
                        ),
                    },
                )
                response.raise_for_status()
                return self._parse_api_ad(response.json())
            except Exception as e:
                logger.error("meta_ad_details_failed", ad_id=external_id, error=str(e))
        return None

    async def get_advertiser_ads(
        self, advertiser_name: str, limit: int = 50
    ) -> list[CrawledAd]:
        """Get all ads from a specific Meta advertiser."""
        return await self.search_ads(query=advertiser_name, limit=limit)
