"""Media health check script.

Scans all ads and validates cached media files:
  1. Reports cached vs uncached counts for thumbnails/images/videos
  2. Validates cached files (not corrupt, not too small)
  3. Deletes invalid cached files and resets s3_key to NULL
  4. Prints summary report

Run from the backend directory:
    cd backend
    python scripts/media_health_check.py
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
MIN_JPEG_SIZE = 500       # bytes - smaller JPEG is likely corrupt
MIN_VIDEO_SIZE = 5000     # bytes - smaller video is likely corrupt

# JPEG magic bytes: FF D8 FF
JPEG_MAGIC = b"\xff\xd8\xff"

# MP4 ftyp header (bytes 4-8)
MP4_FTYP = b"ftyp"

# WebM magic bytes (EBML header)
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")
DOWNLOAD_DIR = os.path.join(CACHE_DIR, "downloads")


def validate_jpeg(path: str) -> tuple[bool, str]:
    """Validate a JPEG file. Returns (is_valid, reason)."""
    if not os.path.exists(path):
        return False, "file does not exist"

    size = os.path.getsize(path)
    if size < MIN_JPEG_SIZE:
        return False, f"too small ({size} bytes)"

    try:
        with open(path, "rb") as f:
            header = f.read(3)
        if header != JPEG_MAGIC:
            return False, f"invalid JPEG header (got {header.hex()})"
    except Exception as e:
        return False, f"read error: {e}"

    return True, "ok"


def validate_video(path: str) -> tuple[bool, str]:
    """Validate a video file (MP4/WebM/MOV). Returns (is_valid, reason)."""
    if not os.path.exists(path):
        return False, "file does not exist"

    size = os.path.getsize(path)
    if size < MIN_VIDEO_SIZE:
        return False, f"too small ({size} bytes)"

    try:
        with open(path, "rb") as f:
            header = f.read(12)
    except Exception as e:
        return False, f"read error: {e}"

    # Check MP4/MOV (ftyp box)
    if MP4_FTYP in header[4:8]:
        return True, "ok (mp4/mov)"

    # Check WebM (EBML header)
    if header[:4] == WEBM_MAGIC:
        return True, "ok (webm)"

    # If we can't identify the format but the file is large enough, accept it
    if size > MIN_VIDEO_SIZE * 10:
        return True, "ok (unknown format, size acceptable)"

    return False, f"unrecognized video format (header: {header[:8].hex()})"


def run_health_check(fix: bool = True) -> dict:
    """Run media health check on all ads.

    Args:
        fix: If True, delete invalid files and reset DB keys to NULL.

    Returns:
        Summary statistics dict.
    """
    session = SyncSessionLocal()
    stats = {
        "total_ads": 0,
        # Thumbnails
        "thumb_cached": 0,
        "thumb_uncached": 0,
        "thumb_no_url": 0,
        "thumb_invalid": 0,
        "thumb_fixed": 0,
        # Images
        "img_cached": 0,
        "img_uncached": 0,
        "img_no_url": 0,
        "img_invalid": 0,
        "img_fixed": 0,
        # Videos
        "video_cached": 0,
        "video_uncached": 0,
        "video_no_url": 0,
        "video_invalid": 0,
        "video_fixed": 0,
        # Orphan files (on disk but not in DB)
        "orphan_thumbs": 0,
        "orphan_images": 0,
        "orphan_videos": 0,
        # Downloads cleanup
        "download_files": 0,
        "download_size_mb": 0.0,
    }

    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        stats["total_ads"] = len(ads)
        ad_ids_set = {ad.id for ad in ads}

        print(f"Scanning {stats['total_ads']} ads...\n")

        invalid_files = []  # (path, ad_id, field_name) tuples for fixing

        for ad in ads:
            ad_id = ad.id

            # ── Thumbnail check ───────────────────────────────────
            thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
            if ad.thumbnail_url:
                if os.path.exists(thumb_path):
                    valid, reason = validate_jpeg(thumb_path)
                    if valid:
                        stats["thumb_cached"] += 1
                    else:
                        stats["thumb_invalid"] += 1
                        invalid_files.append((thumb_path, ad, "thumbnail_s3_key"))
                        print(f"  INVALID thumbnail ad={ad_id}: {reason}")
                else:
                    stats["thumb_uncached"] += 1
            else:
                stats["thumb_no_url"] += 1

            # ── Image check ───────────────────────────────────────
            img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
            if ad.image_url:
                if os.path.exists(img_path):
                    valid, reason = validate_jpeg(img_path)
                    if valid:
                        stats["img_cached"] += 1
                    else:
                        stats["img_invalid"] += 1
                        invalid_files.append((img_path, ad, "image_s3_key"))
                        print(f"  INVALID image ad={ad_id}: {reason}")
                else:
                    stats["img_uncached"] += 1
            else:
                stats["img_no_url"] += 1

            # ── Video check ───────────────────────────────────────
            if ad.video_url and ad.creative_type == "video":
                video_found = False
                for ext in ("mp4", "webm", "mov"):
                    video_path = os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")
                    if os.path.exists(video_path):
                        valid, reason = validate_video(video_path)
                        if valid:
                            stats["video_cached"] += 1
                            video_found = True
                        else:
                            stats["video_invalid"] += 1
                            invalid_files.append((video_path, ad, None))
                            print(f"  INVALID video ad={ad_id}: {reason}")
                            video_found = True
                        break
                if not video_found:
                    stats["video_uncached"] += 1
            else:
                stats["video_no_url"] += 1

        # ── Check for orphan files ────────────────────────────────
        if os.path.exists(THUMB_DIR):
            for fname in os.listdir(THUMB_DIR):
                if fname.endswith(".jpg"):
                    try:
                        file_id = int(fname.replace(".jpg", ""))
                        if file_id not in ad_ids_set:
                            stats["orphan_thumbs"] += 1
                    except ValueError:
                        stats["orphan_thumbs"] += 1

        if os.path.exists(IMAGE_DIR):
            for fname in os.listdir(IMAGE_DIR):
                if fname.endswith(".jpg"):
                    try:
                        file_id = int(fname.replace(".jpg", ""))
                        if file_id not in ad_ids_set:
                            stats["orphan_images"] += 1
                    except ValueError:
                        stats["orphan_images"] += 1

        if os.path.exists(VIDEO_DIR):
            for fname in os.listdir(VIDEO_DIR):
                for ext in (".mp4", ".webm", ".mov"):
                    if fname.endswith(ext):
                        try:
                            file_id = int(fname.replace(ext, ""))
                            if file_id not in ad_ids_set:
                                stats["orphan_videos"] += 1
                        except ValueError:
                            stats["orphan_videos"] += 1

        # ── Check downloads directory ─────────────────────────────
        if os.path.exists(DOWNLOAD_DIR):
            for fname in os.listdir(DOWNLOAD_DIR):
                fpath = os.path.join(DOWNLOAD_DIR, fname)
                if os.path.isfile(fpath):
                    stats["download_files"] += 1
                    stats["download_size_mb"] += os.path.getsize(fpath) / (1024 * 1024)

        # ── Fix invalid files ─────────────────────────────────────
        if fix and invalid_files:
            print(f"\nFixing {len(invalid_files)} invalid files...")
            for path, ad, field_name in invalid_files:
                # Delete the corrupt file
                if os.path.exists(path):
                    os.remove(path)
                    print(f"  DELETED: {os.path.basename(path)}")

                # Reset DB field to NULL
                if field_name:
                    setattr(ad, field_name, None)
                    meta = dict(ad.ad_metadata or {})
                    meta["media_health_fixed"] = True
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")

                    if "thumb" in field_name:
                        stats["thumb_fixed"] += 1
                    elif "image" in field_name:
                        stats["img_fixed"] += 1
                else:
                    stats["video_fixed"] += 1

            session.commit()
            print(f"  DB updated: {stats['thumb_fixed']} thumbnails, "
                  f"{stats['img_fixed']} images, {stats['video_fixed']} videos reset to NULL")

        return stats

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        logger.exception("media_health_check failed")
        raise
    finally:
        session.close()


def print_report(stats: dict):
    """Print a formatted health check report."""
    total = stats["total_ads"]

    print(f"\n{'=' * 70}")
    print(f"  MEDIA HEALTH CHECK REPORT")
    print(f"{'=' * 70}")
    print()

    # Thumbnails
    thumb_total = stats["thumb_cached"] + stats["thumb_uncached"] + stats["thumb_invalid"]
    thumb_pct = (stats["thumb_cached"] / thumb_total * 100) if thumb_total > 0 else 0
    print(f"  THUMBNAILS:")
    print(f"    Cached (valid):   {stats['thumb_cached']:4d}  ({thumb_pct:.1f}%)")
    print(f"    Uncached:         {stats['thumb_uncached']:4d}")
    print(f"    Invalid/corrupt:  {stats['thumb_invalid']:4d}  (fixed: {stats['thumb_fixed']})")
    print(f"    No URL:           {stats['thumb_no_url']:4d}")
    print()

    # Images
    img_total = stats["img_cached"] + stats["img_uncached"] + stats["img_invalid"]
    img_pct = (stats["img_cached"] / img_total * 100) if img_total > 0 else 0
    print(f"  IMAGES:")
    print(f"    Cached (valid):   {stats['img_cached']:4d}  ({img_pct:.1f}%)")
    print(f"    Uncached:         {stats['img_uncached']:4d}")
    print(f"    Invalid/corrupt:  {stats['img_invalid']:4d}  (fixed: {stats['img_fixed']})")
    print(f"    No URL:           {stats['img_no_url']:4d}")
    print()

    # Videos
    video_total = stats["video_cached"] + stats["video_uncached"] + stats["video_invalid"]
    video_pct = (stats["video_cached"] / video_total * 100) if video_total > 0 else 0
    print(f"  VIDEOS:")
    print(f"    Cached (valid):   {stats['video_cached']:4d}  ({video_pct:.1f}%)")
    print(f"    Uncached:         {stats['video_uncached']:4d}")
    print(f"    Invalid/corrupt:  {stats['video_invalid']:4d}  (fixed: {stats['video_fixed']})")
    print(f"    No URL / image:   {stats['video_no_url']:4d}")
    print()

    # Orphans
    total_orphans = stats["orphan_thumbs"] + stats["orphan_images"] + stats["orphan_videos"]
    if total_orphans > 0:
        print(f"  ORPHAN FILES (on disk, no matching ad in DB):")
        print(f"    Thumbnails:  {stats['orphan_thumbs']}")
        print(f"    Images:      {stats['orphan_images']}")
        print(f"    Videos:      {stats['orphan_videos']}")
        print()

    # Downloads
    if stats["download_files"] > 0:
        print(f"  DOWNLOADS (temp ZIP files):")
        print(f"    Files:     {stats['download_files']}")
        print(f"    Size:      {stats['download_size_mb']:.1f} MB")
        print()

    # Overall health score
    all_media = thumb_total + img_total + video_total
    all_cached = stats["thumb_cached"] + stats["img_cached"] + stats["video_cached"]
    all_invalid = stats["thumb_invalid"] + stats["img_invalid"] + stats["video_invalid"]
    health_pct = (all_cached / all_media * 100) if all_media > 0 else 0

    print(f"  OVERALL:")
    print(f"    Total ads:        {total}")
    print(f"    Media items:      {all_media}")
    print(f"    Cached (valid):   {all_cached}")
    print(f"    Invalid:          {all_invalid}")
    print(f"    Health score:     {health_pct:.1f}%")

    if health_pct >= 90:
        print(f"    Status:           HEALTHY")
    elif health_pct >= 70:
        print(f"    Status:           FAIR - consider running auto_media_cache.py")
    else:
        print(f"    Status:           NEEDS ATTENTION - run auto_media_cache.py")

    print(f"{'=' * 70}")


def main():
    """Run the full health check."""
    print("=" * 70)
    print("  Media Health Check")
    print("=" * 70)

    stats = run_health_check(fix=True)
    print_report(stats)


if __name__ == "__main__":
    main()
