"""Download all thumbnail_url / image_url from ads to local media_cache.

Fixes the critical bug where 45% of Facebook CDN URLs return HTTP 403,
and thumbnail_s3_key / image_s3_key are all NULL.

This script:
  1. Creates backend/media_cache/thumbnails/ and backend/media_cache/images/
  2. Downloads each ad's thumbnail_url and image_url
  3. Saves as {ad_id}.jpg
  4. Updates thumbnail_s3_key / image_s3_key in the database
  5. Records media_cached=True in ad_metadata

Run from the backend directory:
    cd backend
    python scripts/download_media_cache.py
"""

import os
import sys
import time
import requests

sys.path.insert(0, ".")

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# ── Config ────────────────────────────────────────────────────────
REQUEST_DELAY = 0.3   # seconds between requests
REQUEST_TIMEOUT = 10  # seconds per download
BATCH_SIZE = 20       # commit every N rows

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")


def ensure_dirs():
    """Create cache directories if they do not exist."""
    os.makedirs(THUMB_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)
    print(f"Cache directories ready:")
    print(f"  thumbnails: {THUMB_DIR}")
    print(f"  images:     {IMAGE_DIR}")


def download_file(url: str, dest_path: str) -> bool:
    """Download a single file. Returns True on success, False on failure."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 403:
            print(f"    SKIP (403 Forbidden): {url[:80]}...")
            return False
        if resp.status_code != 200:
            print(f"    SKIP (HTTP {resp.status_code}): {url[:80]}...")
            return False

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(dest_path)
        if file_size < 100:
            # Too small, probably an error page
            os.remove(dest_path)
            print(f"    SKIP (too small: {file_size}B): {url[:80]}...")
            return False

        return True

    except requests.exceptions.Timeout:
        print(f"    SKIP (timeout): {url[:80]}...")
        return False
    except requests.exceptions.ConnectionError:
        print(f"    SKIP (connection error): {url[:80]}...")
        return False
    except Exception as e:
        print(f"    SKIP (error: {e}): {url[:80]}...")
        return False


def main():
    ensure_dirs()

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total = len(ads)
        print(f"\nTotal ads: {total}")

        thumb_ok = 0
        thumb_skip = 0
        thumb_no_url = 0
        img_ok = 0
        img_skip = 0
        img_no_url = 0

        for i, ad in enumerate(ads):
            ad_id = ad.id
            label = f"[{i + 1}/{total}] Ad {ad_id}"

            # ── Thumbnail ─────────────────────────────────────
            thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
            if ad.thumbnail_url:
                if os.path.exists(thumb_path):
                    # Already cached
                    if not ad.thumbnail_s3_key:
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                    thumb_ok += 1
                else:
                    print(f"  {label} thumbnail downloading...")
                    if download_file(ad.thumbnail_url, thumb_path):
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                        thumb_ok += 1
                        print(f"    OK ({os.path.getsize(thumb_path)} bytes)")
                    else:
                        thumb_skip += 1
                    time.sleep(REQUEST_DELAY)
            else:
                thumb_no_url += 1

            # ── Image ─────────────────────────────────────────
            img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
            if ad.image_url:
                if os.path.exists(img_path):
                    # Already cached
                    if not ad.image_s3_key:
                        ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                    img_ok += 1
                else:
                    print(f"  {label} image downloading...")
                    if download_file(ad.image_url, img_path):
                        ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                        img_ok += 1
                        print(f"    OK ({os.path.getsize(img_path)} bytes)")
                    else:
                        img_skip += 1
                    time.sleep(REQUEST_DELAY)
            else:
                img_no_url += 1

            # ── Update ad_metadata ────────────────────────────
            if ad.thumbnail_s3_key or ad.image_s3_key:
                meta = dict(ad.ad_metadata or {})
                meta["media_cached"] = True
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"  -- committed batch ({i + 1}/{total}) --")

        # Final commit
        session.commit()

        # ── Summary ───────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print(f"  DOWNLOAD COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Thumbnails: {thumb_ok} OK, {thumb_skip} skipped, {thumb_no_url} no URL")
        print(f"  Images:     {img_ok} OK, {img_skip} skipped, {img_no_url} no URL")
        print()

        # Verify DB state
        with_thumb_key = session.query(Ad).filter(Ad.thumbnail_s3_key.isnot(None)).count()
        with_img_key = session.query(Ad).filter(Ad.image_s3_key.isnot(None)).count()
        print(f"  DB thumbnail_s3_key set: {with_thumb_key}/{total}")
        print(f"  DB image_s3_key set:     {with_img_key}/{total}")
        print()

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
