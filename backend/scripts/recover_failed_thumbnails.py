"""Recover thumbnails for ads where D3 cache download failed (HTTP 403).

68 ads have thumbnail_s3_key=NULL after D3. This script tries alternative
sources to fill the gap:

  Phase 0: Validate existing cached files (remove broken/tiny files)
  Phase 1: destination_url og:image (HTTP, fast)
  Phase 2: Playwright screenshot of snapshot_url (heavy, optional)
  Phase 3: Video poster fallback (for video ads without thumbnail)

Run from the backend directory:
    cd backend
    python scripts/recover_failed_thumbnails.py
"""

import os
import sys
import time

sys.path.insert(0, ".")

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# -- Config --
REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 10.0
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")


def _download(url, dest_path):
    """Download a URL to a file. Returns True on success."""
    try:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return False

            ct = resp.headers.get("content-type", "")
            if "image" not in ct and "octet" not in ct:
                return False

            data = resp.content
            if len(data) < 500:
                return False

            with open(dest_path, "wb") as f:
                f.write(data)
            return True
    except Exception:
        return False


# -- Phase 0: Validate existing cached files --

def phase0_validate(session):
    """Remove broken/tiny cached files and reset their s3_keys."""
    print("== Phase 0: Validate existing cached files ==")
    removed = 0

    ads_with_thumb = session.query(Ad).filter(Ad.thumbnail_s3_key.isnot(None)).all()
    for ad in ads_with_thumb:
        path = os.path.join(BASE_DIR, ad.thumbnail_s3_key)
        if not os.path.exists(path):
            ad.thumbnail_s3_key = None
            removed += 1
            continue

        size = os.path.getsize(path)
        if size < 500:
            os.remove(path)
            ad.thumbnail_s3_key = None
            removed += 1
            continue

        # Check if file is actually an image (not HTML error page)
        with open(path, "rb") as f:
            header = f.read(16)
        # JPEG: FF D8, PNG: 89 50 4E 47, GIF: 47 49 46, WebP: 52 49 46 46
        is_image = (
            header[:2] == b'\xff\xd8'
            or header[:4] == b'\x89PNG'
            or header[:3] == b'GIF'
            or header[:4] == b'RIFF'
        )
        if not is_image:
            os.remove(path)
            ad.thumbnail_s3_key = None
            removed += 1

    session.commit()
    print(f"  Removed {removed} broken/invalid files")
    return removed


# -- Phase 1: destination_url og:image --

def phase1_og_image(session):
    """Fetch og:image from destination_url for ads missing thumbnails."""
    print("\n== Phase 1: destination_url og:image ==")

    ads = session.query(Ad).filter(
        Ad.thumbnail_s3_key.is_(None),
        Ad.destination_url.isnot(None),
    ).all()

    if not ads:
        print("  No candidates. Skipping.")
        return 0

    print(f"  Candidates: {len(ads)}")
    recovered = 0

    for i, ad in enumerate(ads):
        dest = ad.destination_url
        if not dest or not dest.startswith("http"):
            continue

        label = f"  [{i+1}/{len(ads)}] Ad {ad.id}"

        try:
            with httpx.Client(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = client.get(dest)
                if resp.status_code != 200:
                    print(f"{label}: LP returned {resp.status_code}")
                    time.sleep(REQUEST_DELAY)
                    continue

            soup = BeautifulSoup(resp.text, "html.parser")
            og_url = None

            for prop in ["og:image", "twitter:image"]:
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
                print(f"{label}: no og:image found")
                time.sleep(REQUEST_DELAY)
                continue

            thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")
            if _download(og_url, thumb_path):
                ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad.id}.jpg"
                if not ad.image_s3_key:
                    img_path = os.path.join(IMAGE_DIR, f"{ad.id}.jpg")
                    if _download(og_url, img_path):
                        ad.image_s3_key = f"media_cache/images/{ad.id}.jpg"

                meta = dict(ad.ad_metadata or {})
                meta["media_cached"] = True
                meta["thumbnail_recovery_source"] = "og_image"
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

                recovered += 1
                print(f"{label}: OK (og:image)")
            else:
                print(f"{label}: og:image download failed")

        except Exception as e:
            print(f"{label}: error {e}")

        time.sleep(REQUEST_DELAY)

        if (i + 1) % 20 == 0:
            session.commit()

    session.commit()
    print(f"  Phase 1 recovered: {recovered}")
    return recovered


# -- Phase 2: Playwright screenshot --

def phase2_playwright_screenshot(session):
    """Take screenshots of snapshot_url using Playwright."""
    print("\n== Phase 2: Playwright screenshot ==")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed. Skipping.")
        return 0

    ads = session.query(Ad).filter(
        Ad.thumbnail_s3_key.is_(None),
        Ad.snapshot_url.isnot(None),
    ).all()

    if not ads:
        print("  No candidates. Skipping.")
        return 0

    print(f"  Candidates: {len(ads)}")
    recovered = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            for i, ad in enumerate(ads):
                label = f"  [{i+1}/{len(ads)}] Ad {ad.id}"
                thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")

                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 800})

                    try:
                        page.goto(
                            ad.snapshot_url,
                            wait_until="domcontentloaded",
                            timeout=15000,
                        )
                    except Exception:
                        pass

                    page.wait_for_timeout(5000)

                    # Try to find creative images first
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
                                && !src.includes('emoji')) {
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
                    if img_src and _download(img_src, thumb_path):
                        saved = True
                        source = "playwright_img"
                    else:
                        # Fallback: screenshot
                        page.screenshot(path=thumb_path, type="jpeg", quality=85)
                        if (
                            os.path.exists(thumb_path)
                            and os.path.getsize(thumb_path) > 500
                        ):
                            saved = True
                            source = "playwright_screenshot"

                    if saved:
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad.id}.jpg"
                        if not ad.image_s3_key:
                            ad.image_s3_key = ad.thumbnail_s3_key

                        meta = dict(ad.ad_metadata or {})
                        meta["media_cached"] = True
                        meta["thumbnail_recovery_source"] = source
                        ad.ad_metadata = meta
                        flag_modified(ad, "ad_metadata")

                        recovered += 1
                        print(f"{label}: OK ({source})")
                    else:
                        print(f"{label}: screenshot failed")

                    page.close()

                except Exception as e:
                    print(f"{label}: error {e}")

                time.sleep(REQUEST_DELAY)

                if (i + 1) % 10 == 0:
                    session.commit()

            browser.close()

    except Exception as e:
        print(f"  Playwright error: {e}")

    session.commit()
    print(f"  Phase 2 recovered: {recovered}")
    return recovered


# -- Phase 3: Video poster fallback --

def phase3_video_poster(session):
    """For video ads without thumbnail, try image_url or mark for poster."""
    print("\n== Phase 3: Video poster fallback ==")

    ads = session.query(Ad).filter(
        Ad.thumbnail_s3_key.is_(None),
        Ad.video_url.isnot(None),
    ).all()

    if not ads:
        print("  No candidates. Skipping.")
        return 0

    print(f"  Candidates: {len(ads)}")
    recovered = 0

    for i, ad in enumerate(ads):
        label = f"  [{i+1}/{len(ads)}] Ad {ad.id}"

        # Try image_url as thumbnail source
        if ad.image_url and ad.image_url != ad.video_url:
            thumb_path = os.path.join(THUMB_DIR, f"{ad.id}.jpg")
            if _download(ad.image_url, thumb_path):
                ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad.id}.jpg"

                meta = dict(ad.ad_metadata or {})
                meta["media_cached"] = True
                meta["thumbnail_recovery_source"] = "image_url_copy"
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

                recovered += 1
                print(f"{label}: OK (image_url copy)")
                time.sleep(REQUEST_DELAY)
                continue

        # Mark for frontend video poster fallback
        meta = dict(ad.ad_metadata or {})
        meta["use_video_poster"] = True
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        print(f"{label}: marked for video poster fallback")

    session.commit()
    print(f"  Phase 3 recovered: {recovered}")
    return recovered


# -- Main --

def main():
    os.makedirs(THUMB_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        total = session.query(Ad).count()
        before_thumb = session.query(Ad).filter(
            Ad.thumbnail_s3_key.isnot(None)
        ).count()
        before_img = session.query(Ad).filter(
            Ad.image_s3_key.isnot(None)
        ).count()
        print(f"Total ads: {total}")
        print(
            f"BEFORE: thumbnail_s3_key={before_thumb}/{total}, "
            f"image_s3_key={before_img}/{total}"
        )
        print(f"Missing thumbnails: {total - before_thumb}")
        print()

        p0 = phase0_validate(session)
        p1 = phase1_og_image(session)
        p2 = phase2_playwright_screenshot(session)
        p3 = phase3_video_poster(session)

        # Final report
        after_thumb = session.query(Ad).filter(
            Ad.thumbnail_s3_key.isnot(None)
        ).count()
        after_img = session.query(Ad).filter(
            Ad.image_s3_key.isnot(None)
        ).count()

        print()
        print("=" * 60)
        print("RECOVERY RESULTS")
        print("=" * 60)
        print(f"  Phase 0 (validate):      {p0} broken files removed")
        print(f"  Phase 1 (og:image):      {p1} recovered")
        print(f"  Phase 2 (playwright):    {p2} recovered")
        print(f"  Phase 3 (video poster):  {p3} recovered")
        print()
        print(f"  thumbnail_s3_key: {before_thumb} -> {after_thumb} / {total}")
        print(f"  image_s3_key:     {before_img} -> {after_img} / {total}")
        print()
        still_missing = total - after_thumb
        print(f"  Still missing: {still_missing}")
        if still_missing > 0:
            print(f"  (These ads have no recoverable thumbnail source)")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
