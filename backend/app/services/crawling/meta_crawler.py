"""Meta (Facebook/Instagram) Ad Library crawler.

Supports three data sources in priority order:
1. Official Meta Graph API (ads_archive) — requires access_token
2. Playwright browser scraping — headless Chromium fallback
3. httpx + BeautifulSoup scraping — lightweight last resort

Post-crawl enrichment:
- Visit individual ad pages to extract impression/spend ranges (commercial ads)
- Extract ad creative images for thumbnail
"""

import asyncio
import re
import urllib.parse
from datetime import datetime
from typing import Optional

import structlog

from app.services.crawling.base_crawler import BaseCrawler, CrawledAd
from app.utils.text import ad_market_is_japanese, japanese_text_ratio

logger = structlog.get_logger()

META_AD_LIBRARY_URL = "https://www.facebook.com/ads/library/"
META_GRAPH_API_VERSION = "v25.0"
META_AD_LIBRARY_API = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/ads_archive"

_DOMAIN_ONLY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,}(/.*)?$")


def _classify_meta_failure(error: object = None, *, status_code: Optional[int] = None) -> str:
    text = str(error or "").lower()
    if status_code == 401 or "token expired" in text or "oauth" in text or "access token" in text:
        return "token_expired"
    if status_code == 429 or "rate limit" in text or "too many requests" in text:
        return "rate_limited"
    if status_code == 403 or "client challenge" in text or "challenge" in text:
        return "client_challenge"
    if "execution context was destroyed" in text:
        return "execution_context_destroyed"
    if "target page, context or browser has been closed" in text:
        return "browser_closed"
    if "timeout" in text:
        return "timeout"
    if status_code and status_code >= 500:
        return "api_server_error"
    if "detail_enrich_no_card_data" in text:
        return "detail_card_not_found"
    if "empty" in text:
        return "empty_result"
    return "unknown"


def _mark_meta_recovery(ad: CrawledAd, reason: str, *, source: Optional[str] = None) -> None:
    meta = _ensure_meta_sources(ad.metadata or {})
    ad.metadata = meta
    meta["meta_recovery_reason"] = reason
    if source:
        meta["meta_recovery_source"] = source


def _set_meta_success_timestamp(ad: CrawledAd, when: Optional[datetime] = None) -> None:
    meta = _ensure_meta_sources(ad.metadata or {})
    ad.metadata = meta
    meta["last_meta_success_at"] = (when or datetime.utcnow()).isoformat()


def _new_search_diagnostics() -> dict:
    return {
        "api_attempted": False,
        "api_status": "not_attempted",
        "api_failure_reason": None,
        "api_result_count": 0,
        "browser_attempted": False,
        "browser_status": "not_attempted",
        "browser_failure_reason": None,
        "browser_result_count": 0,
        "httpx_attempted": False,
        "httpx_status": "not_attempted",
        "httpx_failure_reason": None,
        "httpx_result_count": 0,
    }


def _normalize_external_url(raw: Optional[str]) -> Optional[str]:
    """Normalize destination URL and unwrap Meta redirect links."""
    if not raw:
        return None
    url = str(raw).strip()
    if not url:
        return None

    for _ in range(2):
        dec = urllib.parse.unquote(url)
        if dec == url:
            break
        url = dec

    if not url.startswith(("http://", "https://")):
        if _DOMAIN_ONLY_RE.match(url):
            url = f"https://{url}"
        else:
            return None

    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()
    if "facebook.com" in host and parsed.path.startswith("/l.php"):
        qs = urllib.parse.parse_qs(parsed.query)
        inner = qs.get("u", [None])[0] or qs.get("url", [None])[0]
        return _normalize_external_url(inner)

    internal_hosts = ("facebook.com", "fb.com")
    if any(host == h or host.endswith(f".{h}") for h in internal_hosts):
        return None

    return url


def _pick_destination_url(*candidates: Optional[str]) -> Optional[str]:
    for c in candidates:
        normalized = _normalize_external_url(c)
        if normalized:
            return normalized
    return None


def _ensure_meta_sources(meta: dict) -> dict:
    meta.setdefault("metric_source", "missing")
    meta.setdefault("creative_source", "missing")
    meta.setdefault("lp_source", "missing")
    meta.setdefault("meta_quality_state", "missing")
    return meta


def _refresh_meta_quality_state(ad: "CrawledAd") -> None:
    meta = _ensure_meta_sources(ad.metadata or {})
    ad.metadata = meta
    metric_source = str(meta.get("metric_source") or "missing")
    if metric_source == "api":
        meta["meta_quality_state"] = "real"
    elif metric_source == "estimated":
        meta["meta_quality_state"] = "estimated"
    elif metric_source == "stale":
        meta["meta_quality_state"] = "stale"
    else:
        has_creative = bool(ad.thumbnail_url or ad.image_urls or ad.video_url or ad.snapshot_url)
        has_lp = bool(ad.destination_url)
        meta["meta_quality_state"] = "partial" if (has_creative or has_lp) else "missing"


def _detail_page_candidates(ad: "CrawledAd", access_token: Optional[str]) -> list[str]:
    candidates: list[str] = []
    ad_id = str(ad.external_id or "").strip()
    snapshot_url = str(ad.snapshot_url or "").strip()
    if ad_id.isdigit() and access_token:
        candidates.append(
            f"https://www.facebook.com/ads/archive/render_ad/?id={ad_id}&access_token={access_token}"
        )
    if snapshot_url:
        candidates.append(snapshot_url)
    if ad_id.isdigit():
        candidates.append(f"{META_AD_LIBRARY_URL}?id={ad_id}")
    deduped: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        if url and url not in seen:
            deduped.append(url)
            seen.add(url)
    return deduped


async def _safe_page_evaluate(page, script: str, arg=None, *, fallback=None):
    """Evaluate JS on a Playwright page with retry for transient nav/context failures."""
    attempts = 2
    for idx in range(attempts):
        try:
            if arg is None:
                return await page.evaluate(script)
            return await page.evaluate(script, arg)
        except Exception as exc:
            message = str(exc)
            if idx >= attempts - 1:
                logger.warning("meta_page_evaluate_failed", error=message[:200])
                return fallback
            if "Execution context was destroyed" not in message and "Target page, context or browser has been closed" not in message:
                logger.warning("meta_page_evaluate_non_retryable", error=message[:200])
                return fallback
            await page.wait_for_timeout(1500)
    return fallback


def _parse_metric_range(text: str) -> tuple[Optional[int], Optional[int]]:
    """Parse impression/spend range text into (lower, upper) ints.

    Handles formats like:
      "< 1,000"  "1,000〜5,000"  "1K - 5K"  "10K〜50K"
      "¥1,000 - ¥5,000"  "$100 - $499"  "< ¥1,000"
    """
    if not text:
        return None, None

    # Strip currency symbols
    text = re.sub(r"[¥￥$€]", "", text).strip()

    def _to_int(s: str) -> Optional[int]:
        s = s.strip().replace(",", "").replace("、", "")
        if not s:
            return None
        # Handle K/M suffixes
        m = re.match(r"^([\d.]+)\s*([KMkm万億]?)$", s)
        if not m:
            return None
        val = float(m.group(1))
        suffix = m.group(2).upper()
        if suffix == "K":
            val *= 1_000
        elif suffix == "M":
            val *= 1_000_000
        elif suffix == "万":
            val *= 10_000
        elif suffix == "億":
            val *= 100_000_000
        return int(val)

    # "< N" pattern
    m = re.match(r"^[<＜]\s*(.+)$", text)
    if m:
        upper = _to_int(m.group(1))
        return 0, upper

    # "> N" pattern
    m = re.match(r"^[>＞]\s*(.+)$", text)
    if m:
        lower = _to_int(m.group(1))
        return lower, None

    # "N - M" or "N〜M" range
    parts = re.split(r"\s*[〜～\-–—]\s*", text)
    if len(parts) == 2:
        return _to_int(parts[0]), _to_int(parts[1])

    # Single number
    single = _to_int(text)
    if single is not None:
        return single, single

    return None, None


# JavaScript to extract metrics + creative from an ad detail overlay.
# Takes ad_id as parameter to target the correct card on the search results page.
_AD_DETAIL_EXTRACT_JS = r"""(targetAdId) => {
    const result = {impressions_text: null, spend_text: null, creative_images: [], platforms: [], found_card: false};
    const body = document.body;
    if (!body) return result;

    // --- Find the target ad card by ライブラリID ---
    let targetCard = null;
    const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        const t = walker.currentNode.textContent || '';
        if (t.includes('ライブラリID') && t.includes(targetAdId)) {
            // Walk up to find the card container
            let el = walker.currentNode.parentElement;
            for (let i = 0; i < 20; i++) {
                if (!el || !el.parentElement) break;
                el = el.parentElement;
                const inner = el.innerText || '';
                if (inner.includes('ライブラリID') && inner.includes('広告の詳細を見る')) {
                    targetCard = el;
                    break;
                }
            }
            if (targetCard) break;
        }
    }

    // Fallback: use the first card on the page (for single-ad views)
    if (!targetCard) {
        const allText = body.innerText || '';
        if (allText.includes(targetAdId)) {
            targetCard = body;
        }
    }
    if (!targetCard) return result;
    result.found_card = true;

    const cardText = targetCard.innerText || '';

    // --- Extract creative images from the target card ---
    const imgs = [];
    targetCard.querySelectorAll('img').forEach(img => {
        const src = img.getAttribute('src') || '';
        if (!src || src.startsWith('data:') || src.includes('emoji') || src.includes('rsrc.php')) return;
        // Facebook CDN creative images (scontent-*.fbcdn.net or *.fna.fbcdn.net)
        const isFbCdn = /scontent[^.]*\.fbcdn\.net|\.fna\.fbcdn\.net/.test(src);
        const w = img.naturalWidth || img.width || parseInt(img.getAttribute('width') || '0');
        const h = img.naturalHeight || img.height || parseInt(img.getAttribute('height') || '0');
        const rect = img.getBoundingClientRect();
        const rw = rect.width || 0;
        const rh = rect.height || 0;
        // Use rendered size (getBoundingClientRect) as fallback for naturalWidth
        const effectiveW = w || rw;
        const effectiveH = h || rh;
        if (effectiveW > 80 && effectiveH > 80) {
            imgs.push({url: src, area: effectiveW * effectiveH});
        } else if (isFbCdn && !src.includes('/p50x50/') && !src.includes('/s200x200/')) {
            // Facebook CDN images without known dimensions — likely creative, include them
            imgs.push({url: src, area: 50000});
        } else if (effectiveW === 0 && effectiveH === 0) {
            // Images with no dimensions at all — include if not tiny icons
            if (isFbCdn || (!src.includes('profile') && !src.includes('/s200x200/'))) {
                imgs.push({url: src, area: 10000});
            }
        }
    });
    // Background images
    targetCard.querySelectorAll('div[style*="background-image"]').forEach(div => {
        const style = div.getAttribute('style') || '';
        const m = style.match(/url\(["']?(https?:\/\/[^"')]+)["']?\)/);
        if (m) {
            const rect = div.getBoundingClientRect();
            if (rect.width > 80 && rect.height > 80) {
                imgs.push({url: m[1], area: rect.width * rect.height});
            }
        }
    });
    // Video posters
    targetCard.querySelectorAll('video').forEach(v => {
        const poster = v.getAttribute('poster');
        if (poster && poster.startsWith('http')) {
            imgs.push({url: poster, area: 200000});
        }
    });
    imgs.sort((a, b) => b.area - a.area);
    result.creative_images = [...new Set(imgs.slice(0, 5).map(i => i.url))];

    // --- Platforms from card ---
    if (cardText.includes('Facebook') || targetCard.querySelector('[aria-label*="Facebook"]')) result.platforms.push('facebook');
    if (cardText.includes('Instagram') || targetCard.querySelector('[aria-label*="Instagram"]')) result.platforms.push('instagram');
    if (cardText.includes('Messenger') || targetCard.querySelector('[aria-label*="Messenger"]')) result.platforms.push('messenger');

    return result;
}"""

# JavaScript to extract metrics from the "ad detail" overlay
# (opened by clicking "広告の詳細を見る")
_AD_DETAIL_OVERLAY_JS = r"""() => {
    const result = {impressions_text: null, spend_text: null, reach_text: null};

    // The overlay/modal typically contains the transparency data
    // Look for dialogs, overlays, or the main visible section
    const containers = [
        ...document.querySelectorAll('[role="dialog"]'),
        ...document.querySelectorAll('[aria-modal="true"]'),
        document.body,
    ];

    for (const container of containers) {
        const text = container.innerText || '';
        if (!text) continue;

        // --- Impressions ---
        // Japanese: "インプレッション: < 1,000" or "表示回数: 1,000〜5,000"
        // EU: "< 100" near "impression" text
        const impPatterns = [
            /(?:インプレッション(?:数)?|表示回数|Impressions?)[\s:：]*([<>＜＞]?\s*[\d,]+(?:\s*[〜～\-–]\s*[\d,]+)?)/i,
            /(?:Potential reach|リーチ数?)[\s:：]*([<>＜＞]?\s*[\d,KMkm]+(?:\s*[〜～\-–]\s*[\d,KMkm]+)?)/i,
        ];
        for (const pat of impPatterns) {
            const m = text.match(pat);
            if (m && !result.impressions_text) {
                result.impressions_text = m[1].trim();
            }
        }

        // --- Spend ---
        const spendPatterns = [
            /(?:消化金額|使用した金額|Amount spent|費用|Spend)[\s:：]*([<>＜＞¥￥$€]?\s*[\d,]+(?:\s*[〜～\-–]\s*[¥￥$€]?\s*[\d,]+)?)/i,
        ];
        for (const pat of spendPatterns) {
            const m = text.match(pat);
            if (m && !result.spend_text) {
                result.spend_text = m[1].trim();
            }
        }

        // --- Reach ---
        const reachPatterns = [
            /(?:リーチ|Reach|到達数)[\s:：]*([<>＜＞]?\s*[\d,KMkm]+(?:\s*[〜～\-–]\s*[\d,KMkm]+)?)/i,
        ];
        for (const pat of reachPatterns) {
            const m = text.match(pat);
            if (m && !result.reach_text) {
                result.reach_text = m[1].trim();
            }
        }

        if (result.impressions_text || result.spend_text) break;
    }
    return result;
}"""

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

        // Extract image URLs from card (thumbnails, creative images)
        const imageUrls = [];
        const imgs = card.querySelectorAll('img');
        for (const img of imgs) {
            const src = img.getAttribute('src') || '';
            if (!src || src.startsWith('data:')) continue;
            // Skip tiny icons/avatars (< 50px)
            const w = img.naturalWidth || img.width || parseInt(img.getAttribute('width') || '0');
            const h = img.naturalHeight || img.height || parseInt(img.getAttribute('height') || '0');
            if ((w > 0 && w < 50) || (h > 0 && h < 50)) continue;
            // Skip common icon/emoji patterns
            if (src.includes('emoji') || src.includes('rsrc.php')) continue;
            if (!imageUrls.includes(src)) imageUrls.push(src);
        }
        // Also check CSS background images on divs
        const bgDivs = card.querySelectorAll('div[style*="background-image"]');
        for (const div of bgDivs) {
            const style = div.getAttribute('style') || '';
            const bgMatch = style.match(/url\(["']?(https?:\/\/[^"')]+)["']?\)/);
            if (bgMatch && !imageUrls.includes(bgMatch[1])) {
                imageUrls.push(bgMatch[1]);
            }
        }

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
                image_urls: imageUrls,
            });
        }
    }
    return results;
}"""


def _estimate_ad_metrics(ad: CrawledAd) -> None:
    """Estimate impressions/spend for a commercial ad based on available signals.

    Meta Ad Library API does not return impressions/spend for commercial ads.
    This function provides estimates using:
    - days_running: longer-running ads have more cumulative impressions
    - platform count: multi-platform ads get wider reach
    - Japan market average CPM: ~¥500-1500 (we use ¥800)

    Estimates are clearly marked in metadata as "estimated".
    """
    from datetime import datetime, timezone

    meta = _ensure_meta_sources(ad.metadata or {})
    ad.metadata = meta

    # Calculate days running
    days_running = 0
    if ad.first_seen_at:
        first = ad.first_seen_at
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_running = max(1, (now - first).days)

    if days_running == 0:
        return  # No date data, can't estimate

    # Base daily impressions (conservative estimate for JP market)
    # Small advertisers: ~100-500/day, Medium: ~500-2000/day, Large: ~2000-10000/day
    # We use a moderate estimate: 300/day base
    base_daily_impressions = 300

    # Multipliers
    multiplier = 1.0

    # Platform multiplier
    platforms = meta.get("publisher_platforms", [])
    if len(platforms) >= 2:
        multiplier *= 1.3  # Multi-platform gets more reach

    # Longevity multiplier: ads running 30+ days likely have higher budget
    if days_running > 180:
        multiplier *= 1.5  # Long-running = proven performer
    elif days_running > 60:
        multiplier *= 1.2

    # Still active multiplier
    if not ad.last_seen_at:
        multiplier *= 1.1  # Currently active

    # Calculate estimates
    estimated_impressions = int(days_running * base_daily_impressions * multiplier)

    # Spend estimate: Japan average CPM ≈ ¥800
    cpm_jpy = 800
    estimated_spend = round(estimated_impressions * cpm_jpy / 1000)

    # Apply estimates
    ad.impressions = estimated_impressions
    ad.view_count = estimated_impressions
    ad.spend = float(estimated_spend)

    # Mark as estimated in metadata
    ad.metadata["metrics_estimated"] = True
    ad.metadata["estimated_days_running"] = days_running
    ad.metadata["estimated_daily_impressions"] = int(base_daily_impressions * multiplier)
    ad.metadata["estimated_cpm_jpy"] = cpm_jpy
    ad.metadata["metric_source"] = "estimated"

    logger.info(
        "metrics_estimated",
        ad_id=ad.external_id,
        days_running=days_running,
        impressions=estimated_impressions,
        spend=estimated_spend,
    )
    _refresh_meta_quality_state(ad)


class MetaAdLibraryCrawler(BaseCrawler):
    """Crawler for Meta Ad Library (Facebook / Instagram)."""

    def __init__(self, access_token: Optional[str] = None, rate_limit_delay: float = 2.0):
        super().__init__(rate_limit_delay=rate_limit_delay)
        self.access_token = access_token
        # CI-054: Adaptive rate limiting — increase delay on 429 spikes
        self._base_delay = rate_limit_delay
        self._consecutive_429s = 0
        self._max_adaptive_delay = 120.0  # cap at 2 minutes
        self._last_search_diagnostics = _new_search_diagnostics()

    async def search_ads(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 50,
        country: str = "JP",
        ad_type: str = "ALL",
        enrich_metrics: bool = True,
        **kwargs,
    ) -> list[CrawledAd]:
        """Search Meta Ad Library for ads.

        Strategy:
        1. If access_token is set, try the official API first.
        2. If the API fails (e.g. 500 for certain queries), fall back
           to browser-based scraping via Playwright.
        3. If Playwright is unavailable, fall back to httpx scraping.
        4. (Post-crawl) Enrich ads missing metrics by visiting individual pages.
        """
        results: list[CrawledAd] = []
        api_failed = False
        self._last_search_diagnostics = _new_search_diagnostics()

        if self.access_token:
            results = await self._search_via_api(query, category, limit, country, ad_type)
            api_failed = not bool(results)

        # If API returned nothing (error or empty), try browser fallback
        if not results:
            logger.info("meta_api_empty_or_failed_trying_browser", query=query)
            results = await self._search_via_browser(query, category, limit, country)

        # CI-126: If API returned too few results, supplement with browser crawl
        if results and len(results) < min(30, limit):
            logger.info("meta_api_low_count_supplementing",
                         query=query, api_count=len(results), target=min(30, limit))
            browser_results = await self._search_via_browser(
                query, category, limit - len(results), country)
            if browser_results:
                existing_ids = {r.external_id for r in results if r.external_id}
                for br in browser_results:
                    if br.external_id not in existing_ids:
                        results.append(br)
                        existing_ids.add(br.external_id)
                logger.info("meta_supplemented_results",
                             total=len(results), added=len(browser_results))

        # If browser also failed, try lightweight scraping
        if not results:
            logger.info("meta_browser_failed_trying_httpx", query=query)
            results = await self._search_via_scraping(query, category, limit, country)

        # Filter and prioritize Japanese-language ads for JP country
        if results and country == "JP":
            for crawled_ad in results:
                if "japanese_ratio" not in crawled_ad.metadata:
                    text = " ".join(
                        filter(
                            None,
                            [
                                crawled_ad.title,
                                crawled_ad.description,
                                crawled_ad.advertiser_name,
                                crawled_ad.brand_name,
                            ],
                        )
                    )
                    ratio = japanese_text_ratio(text)
                    crawled_ad.metadata["japanese_ratio"] = round(ratio, 3)

            jp_ads = [
                a for a in results
                if ad_market_is_japanese(
                    a.title,
                    a.description,
                    a.advertiser_name,
                    a.brand_name,
                    urls=[
                        a.destination_url,
                        a.advertiser_url,
                        a.metadata.get("destination_url"),
                        a.metadata.get("display_url"),
                    ],
                    metadata=a.metadata,
                )
            ]
            non_jp_ads = [a for a in results if a not in jp_ads]
            results = jp_ads + non_jp_ads[:max(0, limit - len(jp_ads))]

            logger.info(
                "meta_japanese_filter_applied",
                total=len(jp_ads) + len(non_jp_ads),
                japanese_ads=len(jp_ads),
                non_japanese_ads=len(non_jp_ads),
                kept=len(results),
            )

        # Post-crawl: enrich ads missing metrics/thumbnails
        if results and enrich_metrics:
            results = await self.enrich_ads_with_page_metrics(results)

        if results:
            for ad in results:
                meta = _ensure_meta_sources(ad.metadata or {})
                ad.metadata = meta
                diag = self._last_search_diagnostics
                meta["meta_api_status"] = diag.get("api_status")
                meta["meta_api_failure_reason"] = diag.get("api_failure_reason")
                meta["meta_browser_status"] = diag.get("browser_status")
                meta["meta_browser_failure_reason"] = diag.get("browser_failure_reason")
                meta["meta_httpx_status"] = diag.get("httpx_status")
                meta["meta_httpx_failure_reason"] = diag.get("httpx_failure_reason")
                if api_failed and meta.get("source") == "browser_scraping":
                    meta["token_source"] = "db_or_env"
                    if diag.get("api_failure_reason") and not meta.get("meta_recovery_reason"):
                        meta["meta_recovery_reason"] = diag["api_failure_reason"]
                        meta["meta_recovery_source"] = "browser_fallback"
                elif meta.get("source") == "httpx_scraping" and not meta.get("meta_recovery_reason"):
                    fallback_reason = diag.get("browser_failure_reason") or diag.get("api_failure_reason")
                    if fallback_reason:
                        meta["meta_recovery_reason"] = fallback_reason
                        meta["meta_recovery_source"] = "httpx_fallback"
                _refresh_meta_quality_state(ad)

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
        diag = self._last_search_diagnostics
        diag["api_attempted"] = True
        diag["api_status"] = "running"

        params = {
            "access_token": self.access_token,
            "search_terms": query,
            "ad_reached_countries": f'["{country}"]',
            "ad_type": ad_type,
            # CI-121: Sort by newest first for latest-first retrieval
            "sort_direction": "desc",
            "sort_field": "DELIVERY_START_TIME",
            # Fetch extra to compensate for post-filter (Japanese ads)
            "limit": min(limit * 3, 100),
            "fields": (
                "id,ad_creation_time,ad_delivery_start_time,ad_delivery_stop_time,"
                "ad_creative_bodies,ad_creative_link_titles,ad_creative_link_descriptions,"
                "ad_creative_link_captions,ad_creative_link_thumbnails,languages,"
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
                if response.status_code == 429:
                    diag["api_status"] = "failed"
                    diag["api_failure_reason"] = _classify_meta_failure(status_code=429)
                    # CI-054: Adaptive rate limiting on 429
                    self._consecutive_429s += 1
                    retry_after = int(response.headers.get("Retry-After", "30"))
                    adaptive_delay = min(
                        retry_after * (2 ** (self._consecutive_429s - 1)),
                        self._max_adaptive_delay,
                    )
                    self.rate_limit_delay = min(
                        self._base_delay * (2 ** self._consecutive_429s),
                        self._max_adaptive_delay,
                    )
                    logger.warning("meta_api_rate_limited",
                                   retry_after=retry_after,
                                   adaptive_delay=adaptive_delay,
                                   consecutive_429s=self._consecutive_429s,
                                   new_rate_limit_delay=self.rate_limit_delay)
                    await asyncio.sleep(adaptive_delay)
                    return []  # trigger browser fallback
                if response.status_code == 401:
                    diag["api_status"] = "failed"
                    diag["api_failure_reason"] = _classify_meta_failure(status_code=401)
                    # Token expired — log critical and stop retrying
                    logger.critical("meta_api_token_expired",
                                    msg="Meta API token expired or invalid. Manual renewal required.")
                    return []
                if response.status_code == 500:
                    diag["api_status"] = "failed"
                    diag["api_failure_reason"] = _classify_meta_failure(status_code=500)
                    return []  # trigger browser fallback
                response.raise_for_status()
            data = response.json()

            # CI-054: Reset adaptive delay on successful response
            if self._consecutive_429s > 0:
                self._consecutive_429s = 0
                self.rate_limit_delay = self._base_delay

            if "error" in data:
                logger.warning("meta_api_error", error=data["error"])
                diag["api_status"] = "failed"
                diag["api_failure_reason"] = _classify_meta_failure(data["error"])
                return []

            for ad_data in data.get("data", []):
                crawled_ad = self._parse_api_ad(ad_data)
                if crawled_ad:
                    _set_meta_success_timestamp(crawled_ad)
                    results.append(crawled_ad)
                    if len(results) >= limit:
                        break

            # Handle pagination
            next_url = data.get("paging", {}).get("next")
            while next_url and len(results) < limit:
                await asyncio.sleep(self.rate_limit_delay)
                response = await client.get(next_url)
                if response.status_code == 429:
                    diag["api_status"] = "partial"
                    diag["api_failure_reason"] = _classify_meta_failure(status_code=429)
                    self._consecutive_429s += 1
                    retry_after = int(response.headers.get("Retry-After", "30"))
                    adaptive_delay = min(
                        retry_after * (2 ** (self._consecutive_429s - 1)),
                        self._max_adaptive_delay,
                    )
                    self.rate_limit_delay = min(
                        self._base_delay * (2 ** self._consecutive_429s),
                        self._max_adaptive_delay,
                    )
                    logger.warning("meta_api_pagination_rate_limited",
                                   retry_after=retry_after,
                                   adaptive_delay=adaptive_delay,
                                   consecutive_429s=self._consecutive_429s)
                    await asyncio.sleep(adaptive_delay)
                    break
                if response.status_code == 401:
                    diag["api_status"] = "partial"
                    diag["api_failure_reason"] = _classify_meta_failure(status_code=401)
                    logger.critical("meta_api_token_expired_during_pagination")
                    break
                if response.status_code != 200:
                    diag["api_status"] = "partial"
                    diag["api_failure_reason"] = _classify_meta_failure(status_code=response.status_code)
                    break
                data = response.json()

                for ad_data in data.get("data", []):
                    crawled_ad = self._parse_api_ad(ad_data)
                    if crawled_ad:
                        _set_meta_success_timestamp(crawled_ad)
                        results.append(crawled_ad)
                        if len(results) >= limit:
                            break

                next_url = data.get("paging", {}).get("next")
            if results:
                diag["api_result_count"] = len(results)
                if diag["api_status"] == "running":
                    diag["api_status"] = "success"
            else:
                diag["api_status"] = "empty"
                diag["api_failure_reason"] = diag.get("api_failure_reason") or "empty_result"

        except Exception as e:
            diag["api_status"] = "failed"
            diag["api_failure_reason"] = _classify_meta_failure(e)
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
        diag = self._last_search_diagnostics
        diag["browser_attempted"] = True
        diag["browser_status"] = "running"

        params = urllib.parse.urlencode({
            "active_status": "all",
            "ad_type": "all",
            "country": country,
            "q": query,
        })
        url = f"{META_AD_LIBRARY_URL}?{params}"

        pw = None
        browser = None
        context = None
        page = None
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
            try:
                await page.goto(url, wait_until="load", timeout=90000)
            except Exception:
                await page.goto(url, wait_until="domcontentloaded", timeout=90000)

            # Wait for initial ad cards to render
            await page.wait_for_timeout(5000)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

            # Scroll down to load more ads (Facebook lazy-loads)
            scroll_rounds = max(1, limit // 5)
            for _ in range(min(scroll_rounds, 30)):
                await _safe_page_evaluate(page, "window.scrollTo(0, document.body.scrollHeight)", fallback=None)
                await page.wait_for_timeout(2000)

            # Extract ad data from the rendered page
            ads_data = await _safe_page_evaluate(page, _BROWSER_EXTRACT_JS, fallback=[])
            if not ads_data:
                await page.reload(wait_until="domcontentloaded", timeout=90000)
                await page.wait_for_timeout(4000)
                await page.keyboard.press("Escape")
                ads_data = await _safe_page_evaluate(page, _BROWSER_EXTRACT_JS, fallback=[])

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
                all_ext_links = ad.get("all_external_links", [])
                first_external = all_ext_links[0] if all_ext_links else None
                destination_url = _pick_destination_url(destination_url, first_external, display_url)

                first_seen = None
                if ad.get("start_date"):
                    try:
                        first_seen = datetime.strptime(ad["start_date"], "%Y/%m/%d")
                    except ValueError:
                        pass

                # Determine platform from detected platforms
                platforms = ad.get("platforms", ["facebook"])
                platform = "instagram" if "instagram" in platforms else "facebook"

                # Derive title from body text (first line, capped)
                body_text = ad.get("body") or ""
                title = None
                if body_text:
                    first_line = body_text.split("\n")[0].strip()
                    title = first_line[:80] if first_line else None

                # Build snapshot URL from ad library ID
                snapshot_url = None
                if ad_id and ad_id.isdigit():
                    snapshot_url = f"https://www.facebook.com/ads/library/?id={ad_id}"

                ad_image_urls = ad.get("image_urls", [])

                results.append(CrawledAd(
                    external_id=ad_id or f"meta_browser_{hash(body_text):#010x}",
                    platform=platform,
                    title=title,
                    description=body_text,
                    advertiser_name=ad.get("advertiser"),
                    image_urls=ad_image_urls,
                    thumbnail_url=ad_image_urls[0] if ad_image_urls else None,
                    snapshot_url=snapshot_url,
                    destination_url=destination_url,
                    first_seen_at=first_seen,
                    metadata={
                        "source": "browser_scraping",
                        "metric_source": "missing",
                        "creative_source": "browser",
                        "lp_source": "browser" if destination_url else "missing",
                        "publisher_platforms": platforms,
                        "destination_url": destination_url,
                        "display_url": display_url,
                        "all_external_links": all_ext_links,
                        "destination_type": "LP" if destination_url else None,
                    },
                ))
                _mark_meta_recovery(results[-1], diag.get("api_failure_reason") or "browser_fallback", source="browser_search")

            # Sort results: prioritize Japanese-language ads
            for crawled_ad in results:
                text = (crawled_ad.title or "") + " " + (crawled_ad.description or "")
                ratio = japanese_text_ratio(text)
                crawled_ad.metadata["japanese_ratio"] = round(ratio, 3)

            jp_ads = [a for a in results if a.metadata.get("japanese_ratio", 0) > 0.1]
            non_jp_ads = [a for a in results if a.metadata.get("japanese_ratio", 0) <= 0.1]
            # Japanese ads first, then fill remaining slots with non-Japanese
            results = jp_ads + non_jp_ads

            logger.info(
                "meta_browser_scraping_done",
                query=query,
                results=len(results),
                japanese_ads=len(jp_ads),
                non_japanese_ads=len(non_jp_ads),
            )
            diag["browser_result_count"] = len(results)
            diag["browser_status"] = "success" if results else "empty"
            if not results:
                diag["browser_failure_reason"] = "empty_result"

        except Exception as e:
            diag["browser_status"] = "failed"
            diag["browser_failure_reason"] = _classify_meta_failure(e)
            logger.error("meta_browser_scraping_failed", error=str(e))
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
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
        diag = self._last_search_diagnostics
        diag["httpx_attempted"] = True
        diag["httpx_status"] = "running"

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
                    _mark_meta_recovery(
                        crawled_ad,
                        diag.get("browser_failure_reason") or diag.get("api_failure_reason") or "httpx_fallback",
                        source="httpx_search",
                    )
                    results.append(crawled_ad)
            diag["httpx_result_count"] = len(results)
            diag["httpx_status"] = "success" if results else "empty"
            if not results:
                diag["httpx_failure_reason"] = "empty_result"

        except Exception as e:
            diag["httpx_status"] = "failed"
            diag["httpx_failure_reason"] = _classify_meta_failure(e)
            logger.error("meta_scraping_failed", error=str(e))

        return results

    # ── Parsers ──────────────────────────────────────────────────

    # Patterns indicating Meta replaced actual ad text with a disclaimer
    _DISCLAIMER_PATTERNS = (
        "this ad ran without",
        "disclaimer",
        "この広告は免責事項なしで",
    )

    def _parse_api_ad(self, ad_data: dict) -> Optional[CrawledAd]:
        """Parse ad data from Meta API response."""
        try:
            ad_id = ad_data.get("id", "")
            bodies = ad_data.get("ad_creative_bodies", [])
            titles = ad_data.get("ad_creative_link_titles", [])

            # Detect disclaimer-replaced text
            needs_text_enrichment = False
            original_bodies = None
            if bodies:
                body_lower = bodies[0].lower() if bodies[0] else ""
                if any(p in body_lower for p in self._DISCLAIMER_PATTERNS):
                    original_bodies = list(bodies)
                    bodies = []  # treat as missing → will be enriched later
                    needs_text_enrichment = True

            impressions = ad_data.get("impressions", {})
            impressions_lower = None
            impressions_upper = None
            if isinstance(impressions, dict):
                if impressions.get("lower_bound"):
                    impressions_lower = int(impressions["lower_bound"])
                if impressions.get("upper_bound"):
                    impressions_upper = int(impressions["upper_bound"])

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
            destination_url = _pick_destination_url(
                ad_data.get("link_url"),
                ad_data.get("website_url"),
            )

            display_url = None
            if not destination_url and link_captions:
                caption = link_captions[0]
                if caption:
                    display_url = caption
                    # Caption is a domain or URL (e.g. "hypnozio.com", "example.com/offer")
                    if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-z]{2,}', caption) or "http" in caption:
                        destination_url = _pick_destination_url(destination_url, caption)

            # Extract spend bounds from API response
            spend_data = ad_data.get("spend", {})
            spend_lower = None
            spend_upper = None
            if isinstance(spend_data, dict):
                if spend_data.get("lower_bound"):
                    try:
                        spend_lower = float(spend_data["lower_bound"])
                    except (ValueError, TypeError):
                        pass
                if spend_data.get("upper_bound"):
                    try:
                        spend_upper = float(spend_data["upper_bound"])
                    except (ValueError, TypeError):
                        pass

            # Use midpoint when both bounds are available
            impressions_midpoint = impressions_lower
            if impressions_lower is not None and impressions_upper is not None:
                impressions_midpoint = (impressions_lower + impressions_upper) // 2

            spend_midpoint = spend_lower
            if spend_lower is not None and spend_upper is not None:
                spend_midpoint = (spend_lower + spend_upper) / 2

            # Extract thumbnail from ad_creative_link_thumbnails
            # Field can be: list of URL strings, or list of dicts with "url" key
            thumbnails = ad_data.get("ad_creative_link_thumbnails", [])
            thumbnail_url = None
            if thumbnails:
                first = thumbnails[0]
                if isinstance(first, str):
                    thumbnail_url = first
                elif isinstance(first, dict):
                    thumbnail_url = first.get("url") or first.get("uri")

            # Build snapshot_url: prefer render_ad (server-rendered) over SPA library URL
            snapshot_url = ad_data.get("ad_snapshot_url")
            if snapshot_url and self.access_token and ad_id:
                # render_ad endpoint returns server-rendered HTML (parseable without JS)
                snapshot_url = (
                    f"https://www.facebook.com/ads/archive/render_ad/"
                    f"?id={ad_id}&access_token={self.access_token}"
                )

            metadata = {
                "source": "api",
                "metric_source": "api" if (impressions_midpoint is not None or spend_midpoint is not None) else "missing",
                "creative_source": "api" if thumbnail_url else "missing",
                "lp_source": "api" if destination_url else "missing",
                "page_id": ad_data.get("page_id"),
                "publisher_platforms": platforms,
                "estimated_audience_size": ad_data.get("estimated_audience_size"),
                "spend": ad_data.get("spend"),
                "currency": ad_data.get("currency"),
                "demographic_distribution": ad_data.get("demographic_distribution"),
                "delivery_by_region": ad_data.get("delivery_by_region"),
                "impressions_lower": impressions_lower,
                "impressions_upper": impressions_upper,
                "spend_lower": spend_lower,
                "spend_upper": spend_upper,
                "languages": ad_data.get("languages"),
                "link_descriptions": link_descriptions or None,
                "destination_url": destination_url,
                "display_url": display_url,
                "destination_type": "LP" if destination_url else None,
            }

            # Add enrichment flags when disclaimer was detected
            if needs_text_enrichment:
                metadata["needs_text_enrichment"] = True
                metadata["original_ad_creative_bodies"] = original_bodies

            ad = CrawledAd(
                external_id=ad_id,
                platform=platform,
                title=titles[0] if titles else None,
                description=bodies[0] if bodies else None,
                advertiser_name=ad_data.get("page_name"),
                snapshot_url=snapshot_url,
                thumbnail_url=thumbnail_url,
                creative_type="unknown",
                destination_url=destination_url,
                view_count=impressions_midpoint,
                impressions=impressions_midpoint,
                spend=spend_midpoint,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                metadata=metadata,
            )
            _set_meta_success_timestamp(ad)
            _refresh_meta_quality_state(ad)
            return ad
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
                    destination_url = _pick_destination_url(raw_url)
                elif href.startswith("http") and "facebook.com" not in href:
                    destination_url = _pick_destination_url(href)

            return CrawledAd(
                external_id=ad_id or f"meta_scraped_{hash(str(card)):#010x}",
                platform="facebook",
                title=title_el.get_text(strip=True) if title_el else None,
                description=desc_el.get_text(strip=True) if desc_el else None,
                advertiser_name=(
                    advertiser_el.get_text(strip=True) if advertiser_el else None
                ),
                destination_url=destination_url,
                metadata={
                    "source": "httpx_scraping",
                    "metric_source": "missing",
                    "creative_source": "missing",
                    "lp_source": "httpx" if destination_url else "missing",
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

    # ── Post-crawl enrichment ─────────────────────────────────

    async def enrich_ads_with_page_metrics(
        self,
        ads: list[CrawledAd],
        concurrency: int = 3,
    ) -> list[CrawledAd]:
        """Visit individual Ad Library pages to extract creative images & card data.

        Also estimates metrics (impressions/spend) for commercial ads where the
        Meta API does not return them.
        """
        # Phase 1: Playwright-based creative image extraction
        ads_needing_thumbs = [
            ad for ad in ads
            if not ad.thumbnail_url
            or "s200x200" in (ad.thumbnail_url or "")
            or "favicons" in (ad.thumbnail_url or "")
        ]

        if ads_needing_thumbs:
            await self._enrich_thumbnails_via_playwright(ads_needing_thumbs, concurrency)

        # Phase 2: Estimate metrics for ads still missing impressions/spend
        for ad in ads:
            if ad.impressions is None and ad.spend is None:
                _estimate_ad_metrics(ad)

        enriched_metrics = sum(1 for a in ads if a.impressions is not None)
        enriched_thumbs = sum(1 for a in ads if a.thumbnail_url is not None)
        logger.info(
            "enrichment_complete",
            total=len(ads),
            with_metrics=enriched_metrics,
            with_thumbnails=enriched_thumbs,
        )
        return ads

    async def _enrich_thumbnails_via_playwright(
        self,
        ads: list[CrawledAd],
        concurrency: int = 3,
    ) -> None:
        """Visit Ad Library pages to extract creative images for thumbnails."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("playwright_not_installed_skipping_enrichment")
            return

        logger.info("enriching_thumbnails_via_playwright", to_enrich=len(ads))

        semaphore = asyncio.Semaphore(concurrency)
        pw = None
        browser = None

        try:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=True)

            async def _enrich_one(ad: CrawledAd) -> None:
                async with semaphore:
                    ad_id = ad.external_id
                    if not ad_id or not ad_id.isdigit():
                        return

                    context = None
                    page = None
                    try:
                        context = await browser.new_context(
                            locale="ja-JP",
                            user_agent=(
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/124.0.0.0 Safari/537.36"
                            ),
                        )
                        page = await context.new_page()
                        card_data = {}
                        used_page_url = None
                        for page_url in _detail_page_candidates(ad, self.access_token):
                            try:
                                await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
                                await page.wait_for_timeout(2500)
                                try:
                                    await page.keyboard.press("Escape")
                                except Exception:
                                    pass
                                try:
                                    await page.wait_for_load_state("networkidle", timeout=10000)
                                except Exception:
                                    pass
                                card_data = await _safe_page_evaluate(page, _AD_DETAIL_EXTRACT_JS, ad_id, fallback={})
                                if card_data:
                                    used_page_url = page_url
                                    break
                            except Exception as nav_err:
                                failure_reason = _classify_meta_failure(nav_err)
                                logger.info(
                                    "meta_detail_candidate_failed",
                                    ad_id=ad_id,
                                    page_url=page_url,
                                    error=str(nav_err)[:160],
                                    failure_reason=failure_reason,
                                )
                                if failure_reason == "execution_context_destroyed":
                                    try:
                                        await page.reload(wait_until="domcontentloaded", timeout=60000)
                                        await page.wait_for_timeout(2000)
                                        card_data = await _safe_page_evaluate(page, _AD_DETAIL_EXTRACT_JS, ad_id, fallback={})
                                        if card_data:
                                            used_page_url = page_url
                                            ad.metadata["detail_retry_recovered"] = True
                                            break
                                    except Exception as retry_err:
                                        logger.info(
                                            "meta_detail_candidate_retry_failed",
                                            ad_id=ad_id,
                                            page_url=page_url,
                                            error=str(retry_err)[:160],
                                            failure_reason=_classify_meta_failure(retry_err),
                                        )
                                continue
                        if not card_data:
                            raise RuntimeError("detail_enrich_no_card_data")

                        # Extract creative images (better thumbnail)
                        creative_images = card_data.get("creative_images", [])
                        if creative_images:
                            # Filter out profile pictures
                            good_images = [
                                u for u in creative_images
                                if "s200x200" not in u
                                and "profile" not in u.split("/")[-1][:10]
                            ]
                            if good_images:
                                creative_images = good_images

                            if not ad.thumbnail_url or "s200x200" in (ad.thumbnail_url or "") or "favicons" in (ad.thumbnail_url or ""):
                                ad.thumbnail_url = creative_images[0]
                                ad.metadata["creative_source"] = "playwright_render_ad"
                                ad.metadata["detail_page_url"] = used_page_url
                                logger.info(
                                    "creative_image_extracted",
                                    ad_id=ad_id,
                                    url=creative_images[0][:80],
                                )
                            if not ad.image_urls:
                                ad.image_urls = creative_images

                        # Save card-level metadata
                        ad.metadata["page_enriched"] = True
                        if ad.destination_url:
                            ad.metadata["lp_source"] = ad.metadata.get("lp_source") or "api"
                        if card_data.get("platforms"):
                            ad.metadata["detected_platforms"] = card_data["platforms"]
                        if used_page_url:
                            ad.metadata["detail_page_url"] = used_page_url
                        _set_meta_success_timestamp(ad)
                        ad.metadata["detail_enrich_status"] = "success"
                        _refresh_meta_quality_state(ad)

                    except Exception as e:
                        failure_reason = _classify_meta_failure(e)
                        ad.metadata["creative_source"] = ad.metadata.get("creative_source") or "missing"
                        ad.metadata["detail_enrich_status"] = "failed"
                        ad.metadata["detail_enrich_failure_reason"] = failure_reason
                        ad.metadata["meta_recovery_reason"] = failure_reason
                        ad.metadata["meta_recovery_source"] = "detail_enrich"
                        logger.warning(
                            "ad_page_enrich_failed",
                            ad_id=ad_id,
                            error=str(e)[:100],
                            failure_reason=failure_reason,
                        )
                    finally:
                        if page:
                            try:
                                await page.close()
                            except Exception:
                                pass
                        if context:
                            await context.close()
                        await asyncio.sleep(1.0)

            tasks = [_enrich_one(ad) for ad in ads]
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error("playwright_enrichment_failed", error=str(e))
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()
