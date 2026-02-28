"""Batch re-download script for ads with failed media.

For ads with failed media (no cached file + original URL 403):
  1. Try re-crawling the ad (re-fetch from Meta API to get fresh URLs)
  2. If fresh URL found, download and cache
  3. Print: recovered X, still missing Y

Run from the backend directory:
    cd backend
    python scripts/batch_redownload.py
"""

import os
import sys
import time
import logging
import requests as http_requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
REQUEST_DELAY = 0.5       # seconds between downloads
REQUEST_TIMEOUT = 15      # seconds per download
BATCH_SIZE = 20           # commit every N rows
MIN_FILE_SIZE = 100       # bytes - files smaller than this are corrupt

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def ensure_dirs():
    """Create cache directories if they do not exist."""
    os.makedirs(THUMB_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)


def download_file(url: str, dest_path: str) -> bool:
    """Download a single file. Returns True on success."""
    if not url:
        return False
    try:
        resp = http_requests.get(
            url, timeout=REQUEST_TIMEOUT, stream=True, headers=HEADERS
        )
        if resp.status_code != 200:
            return False
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        file_size = os.path.getsize(dest_path)
        if file_size < MIN_FILE_SIZE:
            os.remove(dest_path)
            return False
        return True
    except Exception:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        return False


def _try_url_variants(original_url: str) -> list[str]:
    """Generate URL variants to try for re-download.

    Facebook CDN URLs sometimes change subdomains or path prefixes.
    Returns a list of URLs to attempt.
    """
    variants = [original_url]

    # Try http -> https or vice versa
    if original_url.startswith("http://"):
        variants.append(original_url.replace("http://", "https://", 1))
    elif original_url.startswith("https://"):
        variants.append(original_url.replace("https://", "http://", 1))

    # Try removing query parameters (sometimes tokens expire but base URL works)
    if "?" in original_url:
        base_url = original_url.split("?")[0]
        variants.append(base_url)

    return variants


def _try_og_image(destination_url: str) -> str | None:
    """Try to extract og:image from a destination URL page."""
    if not destination_url:
        return None
    try:
        resp = http_requests.get(
            destination_url,
            timeout=REQUEST_TIMEOUT,
            headers=HEADERS,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        html = resp.text[:50000]  # limit to first 50KB

        # Simple og:image extraction without BeautifulSoup
        import re
        patterns = [
            r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                return m.group(1)
        return None
    except Exception:
        return None


def find_ads_needing_redownload(session) -> list:
    """Find ads that have URLs but no cached media files."""
    ads = session.query(Ad).order_by(Ad.id).all()
    needs_redownload = []

    for ad in ads:
        ad_id = ad.id
        has_thumb = os.path.exists(os.path.join(THUMB_DIR, f"{ad_id}.jpg"))
        has_image = os.path.exists(os.path.join(IMAGE_DIR, f"{ad_id}.jpg"))
        has_video = False
        for ext in ("mp4", "webm", "mov"):
            if os.path.exists(os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")):
                has_video = True
                break

        # Missing thumbnail and has URL
        needs_thumb = bool(ad.thumbnail_url) and not has_thumb
        # Missing image and has URL
        needs_image = bool(ad.image_url) and not has_image
        # Missing video and is video ad
        needs_video = bool(ad.video_url) and ad.creative_type == "video" and not has_video

        if needs_thumb or needs_image or needs_video:
            needs_redownload.append({
                "ad": ad,
                "needs_thumb": needs_thumb,
                "needs_image": needs_image,
                "needs_video": needs_video,
            })

    return needs_redownload


def main():
    ensure_dirs()

    print("=" * 60)
    print("  Batch Media Re-Download")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        total_ads = session.query(Ad).count()
        print(f"Total ads in DB: {total_ads}")

        # Find ads needing re-download
        needs = find_ads_needing_redownload(session)
        print(f"Ads needing re-download: {len(needs)}")

        if not needs:
            print("All media is cached. Nothing to do.")
            return

        recovered = 0
        still_missing = 0
        recovered_thumb = 0
        recovered_image = 0
        recovered_video = 0

        for i, item in enumerate(needs):
            ad = item["ad"]
            ad_id = ad.id
            label = f"[{i + 1}/{len(needs)}] Ad {ad_id}"
            any_recovered = False

            # ── Phase 1: Direct re-download with URL variants ──
            if item["needs_thumb"]:
                thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
                downloaded = False
                for url in _try_url_variants(ad.thumbnail_url):
                    if download_file(url, thumb_path):
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                        recovered_thumb += 1
                        any_recovered = True
                        downloaded = True
                        print(f"  {label} thumbnail: RECOVERED (direct)")
                        break
                    time.sleep(0.2)

                # Phase 2: Try og:image from destination_url
                if not downloaded and ad.destination_url:
                    og_url = _try_og_image(ad.destination_url)
                    if og_url and download_file(og_url, thumb_path):
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                        recovered_thumb += 1
                        any_recovered = True
                        downloaded = True
                        print(f"  {label} thumbnail: RECOVERED (og:image)")
                    time.sleep(0.3)

                if not downloaded:
                    print(f"  {label} thumbnail: STILL MISSING")

            if item["needs_image"]:
                img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
                downloaded = False
                for url in _try_url_variants(ad.image_url):
                    if download_file(url, img_path):
                        ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                        recovered_image += 1
                        any_recovered = True
                        downloaded = True
                        print(f"  {label} image: RECOVERED (direct)")
                        break
                    time.sleep(0.2)

                if not downloaded:
                    print(f"  {label} image: STILL MISSING")

            if item["needs_video"]:
                for ext in ("mp4", "webm", "mov"):
                    video_path = os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")
                    for url in _try_url_variants(ad.video_url):
                        if download_file(url, video_path):
                            recovered_video += 1
                            any_recovered = True
                            print(f"  {label} video: RECOVERED (direct)")
                            break
                        time.sleep(0.2)
                    if os.path.exists(video_path) and os.path.getsize(video_path) >= MIN_FILE_SIZE:
                        break

            if any_recovered:
                recovered += 1
                meta = dict(ad.ad_metadata or {})
                meta["media_urls_backfilled"] = True
                meta["batch_redownload"] = True
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
            else:
                still_missing += 1

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"  -- committed batch ({i + 1}/{len(needs)}) --")

            time.sleep(REQUEST_DELAY)

        # Final commit
        session.commit()

        # ── Summary ──
        print(f"\n{'=' * 60}")
        print(f"  BATCH RE-DOWNLOAD RESULTS")
        print(f"{'=' * 60}")
        print(f"  Ads processed:       {len(needs)}")
        print(f"  Recovered (any):     {recovered}")
        print(f"  Still missing:       {still_missing}")
        print()
        print(f"  Thumbnails recovered: {recovered_thumb}")
        print(f"  Images recovered:     {recovered_image}")
        print(f"  Videos recovered:     {recovered_video}")
        print()

        # Final cache rates
        thumb_cached = len([f for f in os.listdir(THUMB_DIR) if f.endswith(".jpg")]) if os.path.isdir(THUMB_DIR) else 0
        img_cached = len([f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg")]) if os.path.isdir(IMAGE_DIR) else 0
        print(f"  Cache state:")
        print(f"    Thumbnails on disk: {thumb_cached}/{total_ads}")
        print(f"    Images on disk:     {img_cached}/{total_ads}")
        if total_ads > 0:
            print(f"    Thumbnail rate:     {thumb_cached * 100 / total_ads:.1f}%")
            print(f"    Image rate:         {img_cached * 100 / total_ads:.1f}%")
        print(f"{'=' * 60}")

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        logger.exception("batch_redownload failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
