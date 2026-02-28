"""Aggressive multi-phase media recovery for uncached thumbnails.

Targets ads where thumbnail_s3_key is NULL (no cached thumbnail).
Uses 4 phases with increasing effort to recover as many as possible.

  Phase 1: Retry thumbnail_url directly (temp failures may have resolved)
  Phase 2: Use image_url as thumbnail fallback (download & copy)
  Phase 3: Parse snapshot_url HTML for og:image meta tags
  Phase 4: Playwright screenshot of snapshot_url (heavy, optional)

Run from the backend directory:
    cd backend
    python scripts/aggressive_media_recovery.py
"""

import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# -- Config --
REQUEST_DELAY = 0.4
REQUEST_TIMEOUT = 12.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MIN_FILE_SIZE = 500  # bytes - smaller files are likely error pages
BATCH_SIZE = 20

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")


def ensure_dirs():
    os.makedirs(THUMB_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)


def _is_valid_image_file(path: str) -> bool:
    """Check if a file is a valid image by magic bytes and size."""
    if not os.path.exists(path):
        return False
    size = os.path.getsize(path)
    if size < MIN_FILE_SIZE:
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        # JPEG: FF D8, PNG: 89 50 4E 47, GIF: 47 49 46, WebP: RIFF
        return (
            header[:2] == b'\xff\xd8'
            or header[:4] == b'\x89PNG'
            or header[:3] == b'GIF'
            or header[:4] == b'RIFF'
        )
    except Exception:
        return False


def _download_url(url: str, dest_path: str) -> bool:
    """Download URL to file. Returns True on success."""
    if not url or not url.startswith(("http://", "https://")):
        return False

    try:
        import requests
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            stream=True,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return False

        # Check content-type - reject HTML responses
        ct = resp.headers.get("content-type", "").lower()
        if "text/html" in ct and "image" not in ct:
            return False

        total = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                total += len(chunk)
                if total > 20 * 1024 * 1024:  # 20MB max for images
                    break

        if total > 20 * 1024 * 1024:
            os.remove(dest_path)
            return False

        # Validate the downloaded file
        if not _is_valid_image_file(dest_path):
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

        return True

    except Exception:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def _set_thumbnail(ad, source_label: str, session, also_set_image: bool = False):
    """Update DB fields after successful thumbnail recovery."""
    ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad.id}.jpg"

    if also_set_image and not ad.image_s3_key:
        # Copy thumbnail to image dir as well
        thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")
        img_path = os.path.join(IMAGE_DIR, f"{ad.id}.jpg")
        if os.path.exists(thumb_path) and not os.path.exists(img_path):
            try:
                import shutil
                shutil.copy2(thumb_path, img_path)
                ad.image_s3_key = f"media_cache/images/{ad.id}.jpg"
            except Exception:
                pass

    meta = dict(ad.ad_metadata or {})
    meta["media_cached"] = True
    meta["thumbnail_recovery_source"] = source_label
    meta["thumbnail_fixed"] = True
    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")


# ============================================================
# Phase 1: Retry thumbnail_url
# ============================================================

def phase1_retry_thumbnail_url(session, missing_ads):
    """Re-attempt downloading thumbnail_url for ads that failed before."""
    print("\n" + "=" * 60)
    print("  Phase 1: Retry thumbnail_url (may have been temp failure)")
    print("=" * 60)

    candidates = [ad for ad in missing_ads if ad.thumbnail_url]
    if not candidates:
        print("  No candidates with thumbnail_url. Skipping.")
        return 0, set()

    print(f"  Candidates: {len(candidates)}")
    recovered = 0
    recovered_ids = set()

    for i, ad in enumerate(candidates):
        label = f"  [{i+1}/{len(candidates)}] Ad {ad.id}"
        thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")

        if _download_url(ad.thumbnail_url, thumb_path):
            _set_thumbnail(ad, "retry_thumbnail_url", session, also_set_image=True)
            recovered += 1
            recovered_ids.add(ad.id)
            size_kb = os.path.getsize(thumb_path) / 1024
            print(f"{label}: OK ({size_kb:.1f}KB)")
        else:
            print(f"{label}: FAIL")

        time.sleep(REQUEST_DELAY)

        if (i + 1) % BATCH_SIZE == 0:
            session.commit()

    session.commit()
    print(f"  Phase 1 result: {recovered}/{len(candidates)} recovered")
    return recovered, recovered_ids


# ============================================================
# Phase 2: Use image_url as thumbnail fallback
# ============================================================

def phase2_image_url_fallback(session, missing_ads, already_recovered):
    """Download image_url and use it as thumbnail."""
    print("\n" + "=" * 60)
    print("  Phase 2: Use image_url as thumbnail fallback")
    print("=" * 60)

    candidates = [
        ad for ad in missing_ads
        if ad.id not in already_recovered and ad.image_url
    ]
    if not candidates:
        print("  No candidates with image_url. Skipping.")
        return 0, set()

    print(f"  Candidates: {len(candidates)}")
    recovered = 0
    recovered_ids = set()

    for i, ad in enumerate(candidates):
        label = f"  [{i+1}/{len(candidates)}] Ad {ad.id}"
        thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")

        # Try image_url
        if _download_url(ad.image_url, thumb_path):
            _set_thumbnail(ad, "image_url_fallback", session, also_set_image=True)
            recovered += 1
            recovered_ids.add(ad.id)
            size_kb = os.path.getsize(thumb_path) / 1024
            print(f"{label}: OK from image_url ({size_kb:.1f}KB)")
        else:
            print(f"{label}: FAIL")

        time.sleep(REQUEST_DELAY)

        if (i + 1) % BATCH_SIZE == 0:
            session.commit()

    session.commit()
    print(f"  Phase 2 result: {recovered}/{len(candidates)} recovered")
    return recovered, recovered_ids


# ============================================================
# Phase 3: Parse snapshot_url for og:image
# ============================================================

def phase3_snapshot_og_image(session, missing_ads, already_recovered):
    """Fetch snapshot_url HTML and extract og:image meta tag."""
    print("\n" + "=" * 60)
    print("  Phase 3: Parse snapshot_url for og:image")
    print("=" * 60)

    candidates = [
        ad for ad in missing_ads
        if ad.id not in already_recovered and ad.snapshot_url
    ]
    if not candidates:
        print("  No candidates with snapshot_url. Skipping.")
        return 0, set()

    # Check for BeautifulSoup
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("  beautifulsoup4 not installed. Skipping Phase 3.")
        return 0, set()

    print(f"  Candidates: {len(candidates)}")
    recovered = 0
    recovered_ids = set()

    import requests as req

    for i, ad in enumerate(candidates):
        label = f"  [{i+1}/{len(candidates)}] Ad {ad.id}"

        try:
            resp = req.get(
                ad.snapshot_url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
            )
            if resp.status_code != 200:
                print(f"{label}: snapshot returned HTTP {resp.status_code}")
                time.sleep(REQUEST_DELAY)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            og_url = None

            # Look for og:image, twitter:image, or any large image
            for prop in ["og:image", "twitter:image", "og:image:secure_url"]:
                tag = (
                    soup.find("meta", property=prop)
                    or soup.find("meta", attrs={"name": prop})
                )
                if tag and tag.get("content"):
                    val = tag["content"]
                    if val.startswith("http"):
                        og_url = val
                        break

            if not og_url:
                print(f"{label}: no og:image in snapshot")
                time.sleep(REQUEST_DELAY)
                continue

            thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")
            if _download_url(og_url, thumb_path):
                _set_thumbnail(ad, "snapshot_og_image", session, also_set_image=True)
                recovered += 1
                recovered_ids.add(ad.id)
                size_kb = os.path.getsize(thumb_path) / 1024
                print(f"{label}: OK from og:image ({size_kb:.1f}KB)")
            else:
                print(f"{label}: og:image download failed")

        except Exception as e:
            print(f"{label}: error - {e}")

        time.sleep(REQUEST_DELAY)

        if (i + 1) % BATCH_SIZE == 0:
            session.commit()

    session.commit()
    print(f"  Phase 3 result: {recovered}/{len(candidates)} recovered")
    return recovered, recovered_ids


# ============================================================
# Phase 4: Playwright screenshot
# ============================================================

def phase4_playwright_screenshot(session, missing_ads, already_recovered):
    """Screenshot snapshot_url or destination_url using Playwright."""
    print("\n" + "=" * 60)
    print("  Phase 4: Playwright screenshot (heavy fallback)")
    print("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed. Skipping Phase 4.")
        return 0, set()

    candidates = [
        ad for ad in missing_ads
        if ad.id not in already_recovered
        and (ad.snapshot_url or ad.destination_url)
    ]
    if not candidates:
        print("  No candidates with snapshot/destination URL. Skipping.")
        return 0, set()

    print(f"  Candidates: {len(candidates)}")
    recovered = 0
    recovered_ids = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            for i, ad in enumerate(candidates):
                label = f"  [{i+1}/{len(candidates)}] Ad {ad.id}"
                thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")
                target_url = ad.snapshot_url or ad.destination_url

                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 800})

                    try:
                        page.goto(
                            target_url,
                            wait_until="domcontentloaded",
                            timeout=15000,
                        )
                    except Exception:
                        pass

                    page.wait_for_timeout(4000)

                    # Try to find the largest image on the page
                    img_src = page.evaluate("""() => {
                        const imgs = document.querySelectorAll('img');
                        let best = null;
                        let bestArea = 0;
                        imgs.forEach(img => {
                            const rect = img.getBoundingClientRect();
                            const src = img.currentSrc || img.src || '';
                            if (src && src.startsWith('http')
                                && rect.width > 80 && rect.height > 80
                                && !src.includes('favicon')
                                && !src.includes('pixel')
                                && !src.includes('emoji')
                                && !src.includes('logo')) {
                                const area = rect.width * rect.height;
                                if (area > bestArea) {
                                    bestArea = area;
                                    best = src;
                                }
                            }
                        });
                        return best;
                    }""")

                    saved = False
                    source = None

                    if img_src and _download_url(img_src, thumb_path):
                        saved = True
                        source = "playwright_img"
                    else:
                        # Fallback: full page screenshot
                        page.screenshot(path=thumb_path, type="jpeg", quality=85)
                        if _is_valid_image_file(thumb_path):
                            saved = True
                            source = "playwright_screenshot"

                    if saved:
                        _set_thumbnail(ad, source, session, also_set_image=True)
                        recovered += 1
                        recovered_ids.add(ad.id)
                        size_kb = os.path.getsize(thumb_path) / 1024
                        print(f"{label}: OK ({source}, {size_kb:.1f}KB)")
                    else:
                        if os.path.exists(thumb_path):
                            os.remove(thumb_path)
                        print(f"{label}: screenshot failed")

                    page.close()

                except Exception as e:
                    print(f"{label}: error - {e}")

                time.sleep(REQUEST_DELAY)

                if (i + 1) % 10 == 0:
                    session.commit()

            browser.close()

    except Exception as e:
        print(f"  Playwright global error: {e}")

    session.commit()
    print(f"  Phase 4 result: {recovered}/{len(candidates)} recovered")
    return recovered, recovered_ids


# ============================================================
# Main
# ============================================================

def main():
    ensure_dirs()

    print("=" * 60)
    print("  AGGRESSIVE MEDIA RECOVERY")
    print("  Target: >85% thumbnail cache rate")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        total = session.query(Ad).count()
        before_thumb = session.query(Ad).filter(
            Ad.thumbnail_s3_key.isnot(None)
        ).count()
        before_img = session.query(Ad).filter(
            Ad.image_s3_key.isnot(None)
        ).count()

        print(f"\n  Total ads: {total}")
        print(f"  BEFORE: thumbnails={before_thumb}/{total} ({before_thumb*100//total}%)")
        print(f"  BEFORE: images={before_img}/{total} ({before_img*100//total}%)")
        missing_count = total - before_thumb
        print(f"  Missing thumbnails: {missing_count}")

        if missing_count == 0:
            print("\n  All thumbnails cached! Nothing to do.")
            return

        # Get all ads missing thumbnails
        missing_ads = session.query(Ad).filter(
            Ad.thumbnail_s3_key.is_(None)
        ).order_by(Ad.id).all()

        all_recovered = set()

        # Phase 1: Retry thumbnail_url
        p1_count, p1_ids = phase1_retry_thumbnail_url(session, missing_ads)
        all_recovered.update(p1_ids)

        # Phase 2: image_url fallback
        p2_count, p2_ids = phase2_image_url_fallback(session, missing_ads, all_recovered)
        all_recovered.update(p2_ids)

        # Phase 3: snapshot og:image
        p3_count, p3_ids = phase3_snapshot_og_image(session, missing_ads, all_recovered)
        all_recovered.update(p3_ids)

        # Phase 4: Playwright screenshot
        p4_count, p4_ids = phase4_playwright_screenshot(session, missing_ads, all_recovered)
        all_recovered.update(p4_ids)

        # Final report
        after_thumb = session.query(Ad).filter(
            Ad.thumbnail_s3_key.isnot(None)
        ).count()
        after_img = session.query(Ad).filter(
            Ad.image_s3_key.isnot(None)
        ).count()

        print("\n" + "=" * 60)
        print("  RECOVERY RESULTS")
        print("=" * 60)
        print(f"  Phase 1 (retry thumbnail_url):   {p1_count}")
        print(f"  Phase 2 (image_url fallback):    {p2_count}")
        print(f"  Phase 3 (snapshot og:image):     {p3_count}")
        print(f"  Phase 4 (playwright screenshot): {p4_count}")
        total_recovered = p1_count + p2_count + p3_count + p4_count
        print(f"  ----------------------------------------")
        print(f"  Total recovered:                 {total_recovered}")
        print()
        print(f"  Thumbnails: {before_thumb} -> {after_thumb} / {total} "
              f"({after_thumb*100//total}%)")
        print(f"  Images:     {before_img} -> {after_img} / {total} "
              f"({after_img*100//total}%)")
        print()

        still_missing = total - after_thumb
        cache_rate = after_thumb * 100 / total if total > 0 else 0
        if cache_rate >= 85:
            print(f"  TARGET MET: {cache_rate:.1f}% cache rate (>= 85%)")
        else:
            print(f"  Cache rate: {cache_rate:.1f}% (target: 85%)")
            print(f"  Still missing: {still_missing} ads")

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
