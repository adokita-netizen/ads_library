"""LP (Landing Page) deep crawler.

For each ad with destination_url:
  1. Fetch the LP with requests (follow redirects)
  2. Save HTML to media_cache/lp_html/{ad_id}.html
  3. Take screenshot with Playwright -> media_cache/lp_screenshots/{ad_id}.png
  4. Measure: load_time, page_size, redirect_count, final_url
  5. Extract: title, meta description, og:image, canonical URL
  6. Classify destination type (official site, article LP, EC site, LINE, app DL)
  7. Store in ad_metadata["lp_data"]

Run from the backend directory:
    cd backend
    python scripts/crawl_landing_pages.py
"""

import os
import sys
import re
import time
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests as http_requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad


def _get_session() -> Session:
    """Get a DB session, connecting to vaap_local.db if SQLite fallback is active."""
    if not is_in_memory_mode():
        return SyncSessionLocal()
    db_path = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return sessionmaker(bind=engine)()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30      # seconds per LP fetch
REQUEST_DELAY = 1.0       # seconds between requests (rate limit)
BATCH_SIZE = 10           # commit every N rows
MAX_HTML_SIZE = 5 * 1024 * 1024  # 5MB max HTML to save

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
LP_HTML_DIR = os.path.join(CACHE_DIR, "lp_html")
LP_SCREENSHOT_DIR = os.path.join(CACHE_DIR, "lp_screenshots")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
}

# ── Playwright check ─────────────────────────────────────────────────
_playwright_available = False
try:
    from playwright.sync_api import sync_playwright
    _playwright_available = True
except ImportError:
    pass

# EC site domain patterns
EC_DOMAINS = [
    "amazon.co.jp", "amazon.com",
    "rakuten.co.jp", "rakuten.ne.jp",
    "yahoo.co.jp", "shopping.yahoo.co.jp",
    "zozo.jp", "zozotown.com",
    "qoo10.jp",
    "mercari.com",
    "shopify.com",
    "stores.jp",
    "base.shop", "thebase.in",
    "minne.com",
    "creema.jp",
]

# LINE domain patterns
LINE_DOMAINS = ["line.me", "lin.ee", "liff.line.me"]

# App store domain patterns
APP_STORE_DOMAINS = [
    "apps.apple.com", "itunes.apple.com",
    "play.google.com",
    "onelink.me",
    "app.adjust.com",
    "go.onelink.me",
]


def ensure_dirs():
    """Create LP cache directories."""
    os.makedirs(LP_HTML_DIR, exist_ok=True)
    os.makedirs(LP_SCREENSHOT_DIR, exist_ok=True)


def classify_destination(url: str, html: str = "") -> str:
    """Classify the destination URL type.

    Returns one of:
      - "EC_site" (e-commerce)
      - "LINE_add" (LINE friend add)
      - "app_download" (app store)
      - "article_lp" (article-style landing page)
      - "official_site" (official/corporate site)
    """
    if not url:
        return "official_site"

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")

    # Check LINE domains
    for ld in LINE_DOMAINS:
        if ld in domain:
            return "LINE_add"

    # Check app store domains
    for ad in APP_STORE_DOMAINS:
        if ad in domain:
            return "app_download"

    # Check EC domains
    for ec in EC_DOMAINS:
        if ec in domain:
            return "EC_site"

    # Check URL path patterns for EC
    path_lower = parsed.path.lower()
    if any(p in path_lower for p in ["/product/", "/shop/", "/cart/", "/checkout/", "/item/"]):
        return "EC_site"

    # Check HTML content for article LP indicators
    if html:
        html_lower = html.lower()
        # Article LP: long-form content with specific patterns
        article_indicators = 0
        if len(html) > 30000:  # Long page
            article_indicators += 1
        if html_lower.count("<h2") >= 3:  # Multiple sections
            article_indicators += 1
        if html_lower.count("<h3") >= 5:
            article_indicators += 1
        # Common JP article LP patterns
        jp_article_patterns = [
            "pr_article", "advertorial", "native_ad",
            "sponsored", "ad_article",
        ]
        for pat in jp_article_patterns:
            if pat in html_lower:
                article_indicators += 2
                break
        if article_indicators >= 2:
            return "article_lp"

    return "official_site"


def _extract_meta(html: str, attr_name: str, attr_value: str, content_attr: str = "content") -> str | None:
    """Extract a meta tag value from HTML."""
    patterns = [
        rf'<meta\s+{attr_name}=["\']?{re.escape(attr_value)}["\']?\s+{content_attr}=["\']([^"\']*)["\']',
        rf'<meta\s+{content_attr}=["\']([^"\']*)["\']?\s+{attr_name}=["\']?{re.escape(attr_value)}["\']?',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_title(html: str) -> str | None:
    """Extract <title> from HTML."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()[:500]
    return None


def _extract_canonical(html: str) -> str | None:
    """Extract canonical URL from HTML."""
    m = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _detect_elements(html: str) -> dict:
    """Detect key LP elements in HTML."""
    html_lower = html.lower()

    # Detect forms
    has_form = bool(re.search(r"<form[\s>]", html_lower))

    # Detect video embeds
    has_video = bool(
        re.search(r"<video[\s>]", html_lower)
        or re.search(r'<iframe[^>]*(youtube|vimeo|wistia)', html_lower)
        or re.search(r"(youtube\.com/embed|player\.vimeo)", html_lower)
    )

    # Detect testimonials (JP patterns)
    testimonial_patterns = [
        r"\u304a\u5ba2\u69d8\u306e\u58f0",       # "customer voice" in unicode
        r"testimonial",
        r"review",
        r"voice",
        r"\u53e3\u30b3\u30df",                     # "reviews/kuchikomi" in unicode
        r"\u4f53\u9a13\u8ac7",                     # "experience stories" in unicode
    ]
    has_testimonials = any(re.search(pat, html, re.IGNORECASE) for pat in testimonial_patterns)

    # Detect price display
    price_patterns = [
        r"\u00a5[\d,]+",                            # yen symbol
        r"[\d,]+\u5186",                            # "XXX yen" in unicode
        r"\$[\d,]+\.?\d*",
        r"price",
        r"\u4fa1\u683c",                            # "price" in unicode
        r"\u6599\u91d1",                            # "fee" in unicode
    ]
    has_price = any(re.search(pat, html, re.IGNORECASE) for pat in price_patterns)

    # Detect countdown/timer
    countdown_patterns = [
        r"countdown",
        r"timer",
        r"\u6b8b\u308a",                            # "remaining" in unicode
        r"\u9650\u5b9a",                            # "limited" in unicode
        r"\u7d42\u4e86\u307e\u3067",                # "until end" in unicode
        r"limited.?time",
    ]
    has_countdown = any(re.search(pat, html, re.IGNORECASE) for pat in countdown_patterns)

    # Extract CTA buttons
    cta_patterns = [
        r'<(?:a|button)[^>]*class=["\'][^"\']*(?:cta|btn|button)[^"\']*["\'][^>]*>(.*?)</(?:a|button)>',
        r'<input[^>]*type=["\']submit["\'][^>]*value=["\']([^"\']+)["\']',
    ]
    cta_buttons = []
    for pat in cta_patterns:
        matches = re.findall(pat, html, re.IGNORECASE | re.DOTALL)
        for m in matches:
            text = re.sub(r"<[^>]+>", "", m).strip()
            if text and len(text) < 100:
                cta_buttons.append(text)
    # Deduplicate
    cta_buttons = list(dict.fromkeys(cta_buttons))[:10]

    # Extract dominant colors from CSS/inline styles
    color_matches = re.findall(r"#([0-9a-fA-F]{6})", html)
    # Count frequency and take top 5
    color_freq: dict[str, int] = {}
    for c in color_matches:
        c_upper = f"#{c.upper()}"
        color_freq[c_upper] = color_freq.get(c_upper, 0) + 1
    top_colors = sorted(color_freq.items(), key=lambda x: -x[1])[:5]
    color_scheme = [c for c, _ in top_colors]

    return {
        "has_form": has_form,
        "has_video": has_video,
        "has_testimonials": has_testimonials,
        "has_price": has_price,
        "has_countdown": has_countdown,
        "cta_buttons": cta_buttons,
        "color_scheme": color_scheme,
    }


def take_screenshot(url: str, output_path: str) -> bool:
    """Take a screenshot of a URL using Playwright.

    Returns True on success, False on failure/unavailable.
    """
    if not _playwright_available:
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, timeout=30000, wait_until="networkidle")
            # Wait a bit for lazy-loaded content
            page.wait_for_timeout(2000)
            # Take full page screenshot
            page.screenshot(path=output_path, full_page=True)
            browser.close()
        return True
    except Exception as e:
        logger.debug("Screenshot failed for %s: %s", url, e)
        return False


def crawl_single_lp(ad: Ad) -> dict | None:
    """Crawl a single landing page and return LP data dict."""
    url = ad.destination_url
    if not url:
        return None

    ad_id = ad.id
    result = {
        "final_url": url,
        "load_time_ms": 0,
        "page_size_kb": 0,
        "redirect_count": 0,
        "title": None,
        "meta_description": None,
        "og_image": None,
        "canonical_url": None,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }

    # ── Fetch HTML ──
    try:
        start_time = time.time()
        resp = http_requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers=HEADERS,
            allow_redirects=True,
        )
        elapsed_ms = int((time.time() - start_time) * 1000)

        result["load_time_ms"] = elapsed_ms
        result["redirect_count"] = len(resp.history)
        result["final_url"] = resp.url
        result["status_code"] = resp.status_code

        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code} for ad {ad_id}")
            return result

        html = resp.text
        html_bytes = len(resp.content)
        result["page_size_kb"] = round(html_bytes / 1024, 1)

        # Save HTML to file
        html_path = os.path.join(LP_HTML_DIR, f"{ad_id}.html")
        if html_bytes <= MAX_HTML_SIZE:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

        # Extract metadata
        result["title"] = _extract_title(html)
        result["meta_description"] = _extract_meta(html, "name", "description")
        result["og_image"] = _extract_meta(html, "property", "og:image")
        result["canonical_url"] = _extract_canonical(html)

        # Detect LP elements
        elements = _detect_elements(html)
        result.update(elements)

        # Classify destination type
        dest_type = classify_destination(resp.url, html)
        result["destination_type"] = dest_type

    except http_requests.exceptions.Timeout:
        print(f"    TIMEOUT for ad {ad_id}")
        result["error"] = "timeout"
        return result
    except http_requests.exceptions.ConnectionError:
        print(f"    CONNECTION ERROR for ad {ad_id}")
        result["error"] = "connection_error"
        return result
    except Exception as e:
        print(f"    ERROR for ad {ad_id}: {e}")
        result["error"] = str(e)[:200]
        return result

    # ── Take screenshot ──
    screenshot_path = os.path.join(LP_SCREENSHOT_DIR, f"{ad_id}.png")
    if _playwright_available:
        if take_screenshot(result["final_url"], screenshot_path):
            result["screenshot_path"] = f"media_cache/lp_screenshots/{ad_id}.png"
        else:
            print(f"    Screenshot failed for ad {ad_id}")
    else:
        # Only log once (handled at main level)
        pass

    return result


def main():
    ensure_dirs()

    print("=" * 60)
    print("  Landing Page Deep Crawler")
    print("=" * 60)
    if _playwright_available:
        print("  Playwright: available (screenshots enabled)")
    else:
        print("  Playwright: NOT available (screenshots disabled)")
        print("  Install with: pip install playwright && python -m playwright install chromium")
    print()

    session = _get_session()
    try:
        # Find ads with destination_url
        ads = (
            session.query(Ad)
            .filter(Ad.destination_url.isnot(None))
            .filter(Ad.destination_url != "")
            .order_by(Ad.id)
            .all()
        )
        total = len(ads)
        print(f"Ads with destination_url: {total}")

        if total == 0:
            print("No ads with destination URLs. Nothing to do.")
            return

        # Check how many are already crawled
        already_crawled = sum(
            1 for ad in ads
            if (ad.ad_metadata or {}).get("lp_data")
        )
        print(f"Already crawled: {already_crawled}")
        print(f"To crawl: {total - already_crawled}")

        crawled = 0
        errors = 0
        skipped = 0
        type_counts: dict[str, int] = {}

        for i, ad in enumerate(ads):
            # Skip if already crawled
            meta = ad.ad_metadata or {}
            if meta.get("lp_data") and not os.environ.get("FORCE_RECRAWL"):
                skipped += 1
                continue

            label = f"[{i + 1}/{total}] Ad {ad.id}"
            print(f"  {label}: {ad.destination_url[:80]}...")

            lp_data = crawl_single_lp(ad)

            if lp_data:
                # Store in ad_metadata
                meta = dict(ad.ad_metadata or {})
                meta["lp_data"] = lp_data

                # Also store destination_type at top level of metadata
                dest_type = lp_data.get("destination_type", "official_site")
                meta["destination_type"] = dest_type
                type_counts[dest_type] = type_counts.get(dest_type, 0) + 1

                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

                if lp_data.get("error"):
                    errors += 1
                    print(f"    -> error: {lp_data['error']}")
                else:
                    crawled += 1
                    print(f"    -> {dest_type} | {lp_data.get('load_time_ms', 0)}ms | {lp_data.get('page_size_kb', 0)}KB")
            else:
                errors += 1

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"  -- committed batch ({i + 1}/{total}) --")

            time.sleep(REQUEST_DELAY)

        # Final commit
        session.commit()

        # ── Summary ──
        print(f"\n{'=' * 60}")
        print(f"  LP CRAWL RESULTS")
        print(f"{'=' * 60}")
        print(f"  Total ads processed:    {total}")
        print(f"  Successfully crawled:   {crawled}")
        print(f"  Errors:                 {errors}")
        print(f"  Skipped (already done): {skipped}")
        print()
        print(f"  Destination type distribution:")
        for dtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {dtype}: {count}")
        print()

        # Count saved files
        html_files = len([f for f in os.listdir(LP_HTML_DIR) if f.endswith(".html")]) if os.path.isdir(LP_HTML_DIR) else 0
        screenshot_files = len([f for f in os.listdir(LP_SCREENSHOT_DIR) if f.endswith(".png")]) if os.path.isdir(LP_SCREENSHOT_DIR) else 0
        print(f"  Saved HTML files:       {html_files}")
        print(f"  Saved screenshots:      {screenshot_files}")
        print(f"{'=' * 60}")

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        logger.exception("crawl_landing_pages failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
