"""Fix low-quality thumbnails (Facebook s200x200 profile pics & Google favicons).

176件中14件のサムネイルが低品質:
  - 10件: Facebookプロフィール画像 (s200x200)
  - 4件: Google Favicon (favicons)

Priority order for replacement:
  1. Playwright render_ad: load ad page in headless browser, intercept creative images
  2. destination_url og:image: fetch Open Graph image from landing page
  3. Keep current thumbnail: if all methods fail

Run from the backend directory:
    cd backend
    python scripts/fix_bad_thumbnails.py
"""

import re
import sys
import time

sys.path.insert(0, ".")

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import or_
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.api.endpoints.settings import load_api_keys_from_db


# ── Config ────────────────────────────────────────────────────────

REQUEST_DELAY = 1.0  # seconds between HTTP requests
REQUEST_TIMEOUT = 10.0
PLAYWRIGHT_WAIT_MS = 8000  # time to wait for JS rendering
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Low-quality URL patterns to ignore when selecting new thumbnails
_BAD_PATTERNS = ["s200x200", "s100x100", "s60x60", "hsts-pixel", "favicons", "rsrc.php", "static.xx.fbcdn"]


# ── Thumbnail fetch strategies ────────────────────────────────────


def _upgrade_fbcdn_url(url: str) -> str:
    """Remove size restrictions from Facebook CDN URLs to get full resolution.

    Facebook CDN URLs contain 'stp=dst-jpg_sWIDTHxHEIGHT_...' parameter
    that limits the image size. Removing or modifying it returns the original.
    """
    # Remove size parameter from stp (e.g., stp=dst-jpg_s60x60_tt6 -> stp=dst-jpg_tt6)
    upgraded = re.sub(r"(_s\d+x\d+)", "", url)
    return upgraded


def _is_good_image_url(url: str) -> bool:
    """Check if URL is a real creative image (not UI asset, tracking pixel, etc.)."""
    if not url or not url.startswith("http"):
        return False
    for pattern in _BAD_PATTERNS:
        if pattern in url:
            return False
    # Must be scontent (actual content) not static assets
    return "scontent" in url


def _try_playwright_render_ad(external_id: str, access_token: str | None) -> str | None:
    """Strategy 1: Playwright-based render_ad extraction.

    Loads the render_ad page in a headless browser, waits for JS to render,
    and captures creative image URLs from network responses and DOM.
    """
    if not external_id or not access_token:
        return None

    url = f"https://www.facebook.com/ads/archive/render_ad/?id={external_id}&access_token={access_token}"
    captured_images = []

    def on_response(response):
        resp_url = response.url
        ct = response.headers.get("content-type", "")
        if "image" in ct and _is_good_image_url(resp_url):
            captured_images.append(resp_url)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("response", on_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass  # Page may not fully load, that's OK

            # Wait for JS rendering and image loading
            page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)

            # Also check DOM for img elements with scontent URLs
            imgs = page.query_selector_all("img")
            for img in imgs:
                src = img.get_attribute("src") or ""
                if _is_good_image_url(src):
                    captured_images.append(src)

            browser.close()

        if not captured_images:
            return None

        # Pick the best image: prefer URLs without small size restrictions
        best = None
        for img_url in captured_images:
            # Skip tiny thumbnails (s60x60 etc.)
            if re.search(r"_s\d{1,2}x\d{1,2}", img_url):
                if best is None:
                    best = img_url  # Keep as fallback
                continue
            best = img_url
            break

        if best:
            return _upgrade_fbcdn_url(best)
        return None

    except Exception as e:
        print(f"    playwright error: {e}")
        return None


def _try_og_image(destination_url: str | None, metadata: dict | None) -> str | None:
    """Strategy 2: Extract og:image from the ad's destination URL (LP) via HTTP."""
    dest = destination_url
    if not dest and metadata:
        dest = metadata.get("destination_url") or metadata.get("display_url")

    if not dest or not isinstance(dest, str):
        return None

    if not dest.startswith("http"):
        dest = "https://" + dest

    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(dest)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            # Try og:image first, then twitter:image
            for prop in ["og:image", "twitter:image"]:
                tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
                if tag and tag.get("content"):
                    img_url = tag["content"]
                    if img_url.startswith("http"):
                        return img_url

    except Exception as e:
        print(f"    og:image error: {e}")

    return None


def _try_playwright_lp_hero(destination_url: str | None, metadata: dict | None) -> str | None:
    """Strategy 3: Render LP in Playwright and extract the largest visible image.

    Many LPs use lazy loading, so images aren't in the initial HTML.
    Playwright renders JS and loads lazy images, then we pick the largest
    visible image near the top of the page as the hero/main image.
    """
    dest = destination_url
    if not dest and metadata:
        dest = metadata.get("destination_url") or metadata.get("display_url")

    if not dest or not isinstance(dest, str):
        return None

    if not dest.startswith("http"):
        dest = "https://" + dest

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})

            try:
                page.goto(dest, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass

            page.wait_for_timeout(5000)

            # Find all visible images, sorted by area (largest first)
            images = page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('img').forEach(img => {
                    const rect = img.getBoundingClientRect();
                    const src = img.currentSrc || img.src || '';
                    if (src && src.startsWith('http')
                        && rect.width > 100 && rect.height > 100
                        && !src.includes('lazy.png')
                        && !src.includes('tr?')
                        && !src.includes('tag.gif')
                        && !src.includes('pixel')
                        && !src.includes('favicon')) {
                        results.push({
                            src: src,
                            area: Math.round(rect.width * rect.height),
                            top: Math.round(rect.top)
                        });
                    }
                });
                results.sort((a, b) => b.area - a.area);
                return results.slice(0, 5);
            }""")

            browser.close()

            if images:
                return images[0]["src"]

    except Exception as e:
        print(f"    playwright LP error: {e}")

    return None


# ── Main ──────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        # Load Meta access token
        keys = load_api_keys_from_db()
        meta_keys = keys.get("meta", keys.get("facebook", {}))
        access_token = meta_keys.get("access_token")
        if access_token:
            print(f"Meta access token: {access_token[:8]}****")
        else:
            print("WARNING: No Meta access token found. Playwright render_ad will be skipped.")

        print()

        # Find bad thumbnails
        bad_ads = session.query(Ad).filter(
            or_(
                Ad.thumbnail_url.like("%s200x200%"),
                Ad.thumbnail_url.like("%favicons%"),
            )
        ).all()

        total = len(bad_ads)
        print(f"Low-quality thumbnails found: {total}")
        if total == 0:
            print("Nothing to fix. Exiting.")
            return

        print()

        # Show current state
        s200_count = sum(1 for a in bad_ads if a.thumbnail_url and "s200x200" in a.thumbnail_url)
        favicon_count = sum(1 for a in bad_ads if a.thumbnail_url and "favicons" in a.thumbnail_url)
        print(f"  Facebook s200x200: {s200_count}")
        print(f"  Google Favicon:    {favicon_count}")
        print()

        # Process each ad
        stats = {"playwright": 0, "og_image": 0, "lp_hero": 0, "unchanged": 0, "error": 0}

        for i, ad in enumerate(bad_ads):
            label = f"[{i+1}/{total}] Ad {ad.id} (ext={ad.external_id})"
            old_thumb = (ad.thumbnail_url or "")[:60]
            print(f"{label}")
            print(f"  current: {old_thumb}")

            new_url = None
            source = None

            try:
                # Strategy 1: Playwright render_ad (for Facebook profile pic ads)
                new_url = _try_playwright_render_ad(ad.external_id, access_token)
                if new_url:
                    source = "playwright"

                # Strategy 2: og:image from destination URL (HTTP)
                if not new_url:
                    new_url = _try_og_image(ad.destination_url, ad.ad_metadata)
                    if new_url:
                        source = "og_image"

                # Strategy 3: Playwright LP hero image (for lazy-loaded LPs)
                if not new_url:
                    new_url = _try_playwright_lp_hero(ad.destination_url, ad.ad_metadata)
                    if new_url:
                        source = "lp_hero"

            except Exception as e:
                print(f"  ERROR: {e}")
                stats["error"] += 1
                continue

            if new_url and source:
                # Update the ad
                ad.thumbnail_url = new_url
                ad.image_url = ad.image_url or new_url
                meta = dict(ad.ad_metadata or {})
                meta["thumbnail_fixed"] = True
                meta["thumbnail_fix_source"] = source
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

                stats[source] += 1
                print(f"  -> FIXED ({source}): {new_url[:80]}")
            else:
                stats["unchanged"] += 1
                print(f"  -> UNCHANGED (no better image found)")

            # Rate limit between ads
            if i + 1 < total:
                time.sleep(REQUEST_DELAY)

        # Commit all changes
        session.commit()

        # Summary
        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Total processed:     {total}")
        print(f"Fixed (playwright):  {stats['playwright']}")
        print(f"Fixed (og:image):    {stats['og_image']}")
        print(f"Fixed (LP hero):     {stats['lp_hero']}")
        print(f"Unchanged:           {stats['unchanged']}")
        print(f"Errors:              {stats['error']}")
        print()

        # Verify
        remaining = session.query(Ad).filter(
            or_(
                Ad.thumbnail_url.like("%s200x200%"),
                Ad.thumbnail_url.like("%favicons%"),
            )
        ).count()
        print(f"Remaining low-quality thumbnails: {remaining}")
        if remaining == 0:
            print("All thumbnails fixed!")
        else:
            print(f"({total - remaining} fixed, {remaining} could not be improved)")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
