"""Auto-download media after crawl completion.

After any crawl completes, this script automatically:
  1. Downloads thumbnail_url -> media_cache/thumbnails/{ad_id}.jpg
  2. Downloads image_url -> media_cache/images/{ad_id}.jpg
  3. For video ads: downloads video_url -> media_cache/videos/{ad_id}.mp4 (if size < 50MB)
  4. Updates thumbnail_s3_key, image_s3_key in the database
  5. Skips already-cached ads

Run from the backend directory:
    cd backend
    python scripts/auto_media_cache.py

Can also be imported and called as a post-crawl hook:
    from scripts.auto_media_cache import cache_new_ads
    cache_new_ads()
"""

import os
import sys
import time
import logging
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
REQUEST_DELAY = 0.3       # seconds between downloads
REQUEST_TIMEOUT = 15      # seconds per download
VIDEO_TIMEOUT = 60        # seconds for video downloads
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 MB limit for video downloads
BATCH_SIZE = 20           # commit every N rows
MIN_FILE_SIZE = 100       # bytes - files smaller than this are considered corrupt

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
    print(f"Cache directories ready: {CACHE_DIR}")


def download_file(url: str, dest_path: str, timeout: int = REQUEST_TIMEOUT) -> bool:
    """Download a single file. Returns True on success, False on failure."""
    if not url or not url.startswith(("http://", "https://")):
        return False

    try:
        resp = requests.get(
            url, timeout=timeout, stream=True, headers=HEADERS
        )
        if resp.status_code == 403:
            print(f"    SKIP (403 Forbidden): {url[:80]}...")
            return False
        if resp.status_code != 200:
            print(f"    SKIP (HTTP {resp.status_code}): {url[:80]}...")
            return False

        # For videos, check Content-Length before downloading
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_VIDEO_SIZE:
            print(f"    SKIP (too large: {int(content_length) // 1024 // 1024}MB): {url[:80]}...")
            return False

        total_bytes = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                total_bytes += len(chunk)
                if total_bytes > MAX_VIDEO_SIZE:
                    break

        if total_bytes > MAX_VIDEO_SIZE:
            os.remove(dest_path)
            print(f"    SKIP (exceeded 50MB during download): {url[:80]}...")
            return False

        file_size = os.path.getsize(dest_path)
        if file_size < MIN_FILE_SIZE:
            os.remove(dest_path)
            print(f"    SKIP (too small: {file_size}B): {url[:80]}...")
            return False

        return True

    except requests.exceptions.Timeout:
        print(f"    SKIP (timeout): {url[:80]}...")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False
    except requests.exceptions.ConnectionError:
        print(f"    SKIP (connection error): {url[:80]}...")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False
    except Exception as e:
        print(f"    SKIP (error: {e}): {url[:80]}...")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


def cache_new_ads(ad_ids: list[int] | None = None):
    """Download and cache media for ads that are not yet cached.

    Args:
        ad_ids: Optional list of specific ad IDs to process.
                If None, processes all ads missing cached media.

    Returns:
        dict with counts of results.
    """
    ensure_dirs()

    session = SyncSessionLocal()
    stats = {
        "thumb_ok": 0, "thumb_skip": 0, "thumb_already": 0, "thumb_no_url": 0,
        "img_ok": 0, "img_skip": 0, "img_already": 0, "img_no_url": 0,
        "video_ok": 0, "video_skip": 0, "video_already": 0, "video_no_url": 0,
        "total_processed": 0,
    }

    try:
        query = session.query(Ad).order_by(Ad.id)

        if ad_ids:
            query = query.filter(Ad.id.in_(ad_ids))
        else:
            # Only process ads that are missing at least one cached media file
            query = query.filter(
                or_(
                    Ad.thumbnail_s3_key.is_(None),
                    Ad.image_s3_key.is_(None),
                    # Video ads without cached video
                    (Ad.video_url.isnot(None)) & (Ad.creative_type == "video"),
                )
            )

        ads = query.all()
        total = len(ads)
        print(f"\nAds to process: {total}")

        if total == 0:
            print("All ads already cached. Nothing to do.")
            return stats

        for i, ad in enumerate(ads):
            ad_id = ad.id
            label = f"[{i + 1}/{total}] Ad {ad_id}"
            stats["total_processed"] += 1

            # ── Thumbnail ─────────────────────────────────────────
            thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
            if ad.thumbnail_url:
                if os.path.exists(thumb_path) and os.path.getsize(thumb_path) >= MIN_FILE_SIZE:
                    if not ad.thumbnail_s3_key:
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                    stats["thumb_already"] += 1
                else:
                    print(f"  {label} thumbnail downloading...")
                    if download_file(ad.thumbnail_url, thumb_path):
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                        stats["thumb_ok"] += 1
                        print(f"    OK ({os.path.getsize(thumb_path)} bytes)")
                    else:
                        stats["thumb_skip"] += 1
                    time.sleep(REQUEST_DELAY)
            else:
                stats["thumb_no_url"] += 1

            # ── Image ─────────────────────────────────────────────
            img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
            if ad.image_url:
                if os.path.exists(img_path) and os.path.getsize(img_path) >= MIN_FILE_SIZE:
                    if not ad.image_s3_key:
                        ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                    stats["img_already"] += 1
                else:
                    print(f"  {label} image downloading...")
                    if download_file(ad.image_url, img_path):
                        ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                        stats["img_ok"] += 1
                        print(f"    OK ({os.path.getsize(img_path)} bytes)")
                    else:
                        stats["img_skip"] += 1
                    time.sleep(REQUEST_DELAY)
            else:
                stats["img_no_url"] += 1

            # ── Video ─────────────────────────────────────────────
            video_path = os.path.join(VIDEO_DIR, f"{ad_id}.mp4")
            if ad.video_url and ad.creative_type == "video":
                if os.path.exists(video_path) and os.path.getsize(video_path) >= MIN_FILE_SIZE:
                    stats["video_already"] += 1
                else:
                    print(f"  {label} video downloading...")
                    if download_file(ad.video_url, video_path, timeout=VIDEO_TIMEOUT):
                        stats["video_ok"] += 1
                        fsize = os.path.getsize(video_path)
                        print(f"    OK ({fsize // 1024}KB)")
                        # Update file_size_bytes if not set
                        if not ad.file_size_bytes:
                            ad.file_size_bytes = fsize
                    else:
                        stats["video_skip"] += 1
                    time.sleep(REQUEST_DELAY)
            else:
                stats["video_no_url"] += 1

            # ── Update ad_metadata ────────────────────────────────
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

        # ── Summary ───────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print(f"  AUTO MEDIA CACHE COMPLETE")
        print(f"{'=' * 60}")
        print(f"  Thumbnails: {stats['thumb_ok']} new, {stats['thumb_already']} already cached, "
              f"{stats['thumb_skip']} failed, {stats['thumb_no_url']} no URL")
        print(f"  Images:     {stats['img_ok']} new, {stats['img_already']} already cached, "
              f"{stats['img_skip']} failed, {stats['img_no_url']} no URL")
        print(f"  Videos:     {stats['video_ok']} new, {stats['video_already']} already cached, "
              f"{stats['video_skip']} failed, {stats['video_no_url']} no URL/not video")
        print()

        return stats

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        logger.exception("auto_media_cache failed")
        raise
    finally:
        session.close()


def main():
    """Run auto media cache for all uncached ads."""
    print("=" * 60)
    print("  Auto Media Cache - Post-Crawl Hook")
    print("=" * 60)

    stats = cache_new_ads()

    # Print final DB state
    session = SyncSessionLocal()
    try:
        total = session.query(Ad).count()
        with_thumb = session.query(Ad).filter(Ad.thumbnail_s3_key.isnot(None)).count()
        with_img = session.query(Ad).filter(Ad.image_s3_key.isnot(None)).count()
        with_video_url = session.query(Ad).filter(Ad.video_url.isnot(None)).count()

        # Count cached video files on disk
        video_files = 0
        if os.path.exists(VIDEO_DIR):
            video_files = len([f for f in os.listdir(VIDEO_DIR) if f.endswith((".mp4", ".webm", ".mov"))])

        print(f"  DB State:")
        print(f"    Total ads:           {total}")
        print(f"    thumbnail_s3_key:    {with_thumb}/{total}")
        print(f"    image_s3_key:        {with_img}/{total}")
        print(f"    video_url set:       {with_video_url}/{total}")
        print(f"    video files cached:  {video_files}")
        print()
    finally:
        session.close()


if __name__ == "__main__":
    main()
