"""Batch media revalidation.

Re-checks all cached media files for corruption and validity:
  1. Validates thumbnails, images, and videos
  2. Removes corrupted/broken files
  3. Updates cache manifest (ad DB fields)
  4. Prints summary of actions taken

Run from the backend directory:
    cd backend
    python scripts/revalidate_media.py
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")
BATCH_SIZE = 20

MIN_IMAGE_SIZE = 500       # bytes
MIN_VIDEO_SIZE = 5000      # bytes

# Magic bytes
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"
GIF_MAGIC = b"GIF"
WEBP_MAGIC = b"RIFF"
MP4_FTYP = b"ftyp"
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"

# HTML detection
HTML_MARKERS = [
    b"<html", b"<!doctype", b"<!DOCTYPE",
    b"<HTML", b"<head", b"<HEAD", b"<?xml", b"<svg",
]

# Pillow availability
_pillow_available = False
try:
    from PIL import Image
    _pillow_available = True
except ImportError:
    pass


def validate_image_file(path: str) -> tuple[bool, str]:
    """Validate an image file. Returns (is_valid, reason)."""
    if not os.path.exists(path):
        return False, "file does not exist"

    size = os.path.getsize(path)
    if size < MIN_IMAGE_SIZE:
        return False, f"too small ({size} bytes)"

    try:
        with open(path, "rb") as f:
            header = f.read(32)
    except Exception as e:
        return False, f"read error: {e}"

    if len(header) < 4:
        return False, "file too small to read header"

    # Check for HTML content masquerading as image
    header_lower = header.lower()
    for marker in HTML_MARKERS:
        if marker.lower() in header_lower:
            return False, "HTML content detected"

    # Check known image formats
    if header[:3] == JPEG_MAGIC:
        pass  # JPEG OK
    elif header[:4] == PNG_MAGIC:
        pass  # PNG OK
    elif header[:3] == GIF_MAGIC:
        pass  # GIF OK
    elif header[:4] == WEBP_MAGIC and len(header) >= 12 and header[8:12] == b"WEBP":
        pass  # WebP OK
    else:
        return False, f"unknown format (header: {header[:8].hex()})"

    # Pillow validation
    if _pillow_available:
        try:
            with Image.open(path) as img:
                img.verify()
        except Exception as e:
            return False, f"corrupt image: {e}"

    return True, "ok"


def validate_video_file(path: str) -> tuple[bool, str]:
    """Validate a video file. Returns (is_valid, reason)."""
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

    # If file is large enough, accept it
    if size > MIN_VIDEO_SIZE * 10:
        return True, "ok (unknown format, size acceptable)"

    return False, f"unrecognized video format (header: {header[:8].hex()})"


def main():
    print("=" * 60)
    print("  BATCH MEDIA REVALIDATION")
    print("=" * 60)
    print()

    if _pillow_available:
        print("  Pillow: available (deep image validation)")
    else:
        print("  Pillow: NOT available (header-only validation)")
    print()

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total_ads = len(ads)
        ad_ids = {ad.id for ad in ads}
        ad_map = {ad.id: ad for ad in ads}

        print(f"  Total ads in DB: {total_ads}")

        stats = {
            "thumb_checked": 0,
            "thumb_valid": 0,
            "thumb_removed": 0,
            "thumb_reasons": {},
            "img_checked": 0,
            "img_valid": 0,
            "img_removed": 0,
            "img_reasons": {},
            "video_checked": 0,
            "video_valid": 0,
            "video_removed": 0,
            "video_reasons": {},
            "orphans_removed": 0,
            "db_updated": 0,
        }

        # ── Validate thumbnails ──────────────────────────────────────
        print("\n  Validating thumbnails...")

        if os.path.isdir(THUMB_DIR):
            for fname in sorted(os.listdir(THUMB_DIR)):
                if not fname.endswith(".jpg"):
                    continue

                fpath = os.path.join(THUMB_DIR, fname)
                try:
                    fid = int(fname.replace(".jpg", ""))
                except ValueError:
                    # Orphaned file with non-numeric name
                    os.remove(fpath)
                    stats["orphans_removed"] += 1
                    print(f"    ORPHAN removed: {fname}")
                    continue

                if fid not in ad_ids:
                    os.remove(fpath)
                    stats["orphans_removed"] += 1
                    continue

                stats["thumb_checked"] += 1
                valid, reason = validate_image_file(fpath)

                if valid:
                    stats["thumb_valid"] += 1
                else:
                    stats["thumb_removed"] += 1
                    stats["thumb_reasons"][reason] = stats["thumb_reasons"].get(reason, 0) + 1
                    print(f"    INVALID thumbnail ad={fid}: {reason}")

                    # Remove file
                    os.remove(fpath)

                    # Update DB
                    if fid in ad_map:
                        ad = ad_map[fid]
                        ad.thumbnail_s3_key = None
                        meta = dict(ad.ad_metadata or {})
                        meta["revalidation_thumbnail_removed"] = True
                        ad.ad_metadata = meta
                        flag_modified(ad, "ad_metadata")
                        stats["db_updated"] += 1

        # ── Validate images ──────────────────────────────────────────
        print("  Validating images...")

        if os.path.isdir(IMAGE_DIR):
            for fname in sorted(os.listdir(IMAGE_DIR)):
                if not fname.endswith(".jpg"):
                    continue

                fpath = os.path.join(IMAGE_DIR, fname)
                try:
                    fid = int(fname.replace(".jpg", ""))
                except ValueError:
                    os.remove(fpath)
                    stats["orphans_removed"] += 1
                    continue

                if fid not in ad_ids:
                    os.remove(fpath)
                    stats["orphans_removed"] += 1
                    continue

                stats["img_checked"] += 1
                valid, reason = validate_image_file(fpath)

                if valid:
                    stats["img_valid"] += 1
                else:
                    stats["img_removed"] += 1
                    stats["img_reasons"][reason] = stats["img_reasons"].get(reason, 0) + 1
                    print(f"    INVALID image ad={fid}: {reason}")

                    os.remove(fpath)

                    if fid in ad_map:
                        ad = ad_map[fid]
                        ad.image_s3_key = None
                        meta = dict(ad.ad_metadata or {})
                        meta["revalidation_image_removed"] = True
                        ad.ad_metadata = meta
                        flag_modified(ad, "ad_metadata")
                        stats["db_updated"] += 1

        # ── Validate videos ──────────────────────────────────────────
        print("  Validating videos...")

        if os.path.isdir(VIDEO_DIR):
            for fname in sorted(os.listdir(VIDEO_DIR)):
                fpath = os.path.join(VIDEO_DIR, fname)
                ext_match = None
                for ext in (".mp4", ".webm", ".mov"):
                    if fname.endswith(ext):
                        ext_match = ext
                        break

                if not ext_match:
                    continue

                try:
                    fid = int(fname.replace(ext_match, ""))
                except ValueError:
                    os.remove(fpath)
                    stats["orphans_removed"] += 1
                    continue

                if fid not in ad_ids:
                    os.remove(fpath)
                    stats["orphans_removed"] += 1
                    continue

                stats["video_checked"] += 1
                valid, reason = validate_video_file(fpath)

                if valid:
                    stats["video_valid"] += 1
                else:
                    stats["video_removed"] += 1
                    stats["video_reasons"][reason] = stats["video_reasons"].get(reason, 0) + 1
                    print(f"    INVALID video ad={fid}: {reason}")
                    os.remove(fpath)

        # Commit all changes
        session.commit()

        # ── Summary ──────────────────────────────────────────────────
        total_checked = stats["thumb_checked"] + stats["img_checked"] + stats["video_checked"]
        total_valid = stats["thumb_valid"] + stats["img_valid"] + stats["video_valid"]
        total_removed = stats["thumb_removed"] + stats["img_removed"] + stats["video_removed"]

        print()
        print("=" * 60)
        print("  REVALIDATION RESULTS")
        print("=" * 60)
        print()
        print(f"  Total files checked: {total_checked}")
        print(f"  Valid:               {total_valid}")
        print(f"  Removed (invalid):   {total_removed}")
        print(f"  Orphans removed:     {stats['orphans_removed']}")
        print(f"  DB records updated:  {stats['db_updated']}")
        print()

        print(f"  Thumbnails:  {stats['thumb_checked']} checked, {stats['thumb_valid']} valid, {stats['thumb_removed']} removed")
        if stats["thumb_reasons"]:
            for reason, count in sorted(stats["thumb_reasons"].items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {count}")

        print(f"  Images:      {stats['img_checked']} checked, {stats['img_valid']} valid, {stats['img_removed']} removed")
        if stats["img_reasons"]:
            for reason, count in sorted(stats["img_reasons"].items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {count}")

        print(f"  Videos:      {stats['video_checked']} checked, {stats['video_valid']} valid, {stats['video_removed']} removed")
        if stats["video_reasons"]:
            for reason, count in sorted(stats["video_reasons"].items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {count}")

        print()
        health_pct = round(total_valid / total_checked * 100, 1) if total_checked > 0 else 0
        print(f"  Media health: {health_pct}%")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
