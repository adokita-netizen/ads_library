"""Validate all cached media files for corruption and quality.

Checks ALL cached files in media_cache/:
  1. Magic bytes validation (JPEG: FF D8 FF, PNG: 89 50 4E 47)
  2. Minimum file size (>5KB for thumbnails/images)
  3. HTML-as-image detection (check for <html, <!DOCTYPE in first bytes)
  4. Image dimension check (>100x100 pixels, requires Pillow)

Invalid files are deleted and their s3_key is reset to NULL in DB.

Run from the backend directory:
    cd backend
    python scripts/validate_media_files.py
"""

import os
import sys
import struct
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# -- Config --
MIN_IMAGE_SIZE = 5120    # 5KB - smaller images are likely error pages
MIN_VIDEO_SIZE = 10240   # 10KB
MIN_IMAGE_DIMS = (100, 100)  # minimum width x height in pixels

# Magic bytes
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"
GIF_MAGIC = b"GIF"
WEBP_MAGIC = b"RIFF"
BMP_MAGIC = b"BM"

# HTML detection patterns (saved-as-jpg error pages)
HTML_MARKERS = [
    b"<html",
    b"<!doctype",
    b"<!DOCTYPE",
    b"<HTML",
    b"<head",
    b"<HEAD",
    b"<?xml",
    b"<svg",
]

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")


# -- Pillow availability check --
_pillow_available = False
try:
    from PIL import Image
    _pillow_available = True
except ImportError:
    pass


def check_magic_bytes(path: str) -> tuple[bool, str]:
    """Check if file has valid image magic bytes. Returns (valid, reason)."""
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
            return False, f"HTML content detected (found '{marker.decode(errors='replace')}')"

    # Check for known image formats
    if header[:3] == JPEG_MAGIC:
        return True, "JPEG"
    if header[:4] == PNG_MAGIC:
        return True, "PNG"
    if header[:3] == GIF_MAGIC:
        return True, "GIF"
    if header[:4] == WEBP_MAGIC and header[8:12] == b"WEBP":
        return True, "WebP"
    if header[:2] == BMP_MAGIC:
        return True, "BMP"

    return False, f"unknown format (header: {header[:8].hex()})"


def check_image_dimensions(path: str) -> tuple[bool, str, tuple[int, int] | None]:
    """Check image dimensions. Returns (valid, reason, (w, h) or None).

    Uses Pillow if available, otherwise attempts to read JPEG/PNG headers directly.
    """
    if _pillow_available:
        try:
            with Image.open(path) as img:
                w, h = img.size
            if w < MIN_IMAGE_DIMS[0] or h < MIN_IMAGE_DIMS[1]:
                return False, f"too small ({w}x{h}, min {MIN_IMAGE_DIMS[0]}x{MIN_IMAGE_DIMS[1]})", (w, h)
            return True, "ok", (w, h)
        except Exception as e:
            return False, f"Pillow cannot open: {e}", None

    # Fallback: read JPEG/PNG headers manually for dimensions
    try:
        with open(path, "rb") as f:
            header = f.read(32)

        # PNG: width at bytes 16-20, height at 20-24 (big-endian)
        if header[:4] == PNG_MAGIC and len(header) >= 24:
            w = struct.unpack(">I", header[16:20])[0]
            h = struct.unpack(">I", header[20:24])[0]
            if w < MIN_IMAGE_DIMS[0] or h < MIN_IMAGE_DIMS[1]:
                return False, f"too small ({w}x{h})", (w, h)
            return True, "ok", (w, h)

        # JPEG: dimensions are in SOF marker, harder to extract without Pillow
        # Skip dimension check for JPEG without Pillow
        return True, "ok (no Pillow, JPEG dims unchecked)", None

    except Exception:
        return True, "ok (dimension check skipped)", None


def validate_single_file(path: str, file_type: str = "image") -> tuple[bool, str]:
    """Full validation for a single file. Returns (valid, reason)."""
    if not os.path.exists(path):
        return False, "file does not exist"

    size = os.path.getsize(path)
    min_size = MIN_IMAGE_SIZE if file_type == "image" else MIN_VIDEO_SIZE

    if size < min_size:
        return False, f"too small ({size} bytes, min {min_size})"

    if file_type == "image":
        # Magic bytes check
        valid, reason = check_magic_bytes(path)
        if not valid:
            return False, reason

        # Dimension check
        dim_valid, dim_reason, dims = check_image_dimensions(path)
        if not dim_valid:
            return False, dim_reason

    return True, "ok"


def main():
    print("=" * 60)
    print("  MEDIA FILE VALIDATOR")
    print("=" * 60)

    if _pillow_available:
        print("  Pillow: available (full dimension checking enabled)")
    else:
        print("  Pillow: NOT available (dimension check limited)")
    print()

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total = len(ads)
        print(f"  Total ads: {total}")

        validated = 0
        deleted = 0
        details = {
            "thumb_valid": 0,
            "thumb_invalid": 0,
            "thumb_reasons": {},
            "img_valid": 0,
            "img_invalid": 0,
            "img_reasons": {},
        }

        for ad in ads:
            ad_id = ad.id

            # -- Validate thumbnail --
            thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
            if os.path.exists(thumb_path):
                valid, reason = validate_single_file(thumb_path, "image")
                if valid:
                    details["thumb_valid"] += 1
                    validated += 1
                else:
                    details["thumb_invalid"] += 1
                    details["thumb_reasons"][reason] = details["thumb_reasons"].get(reason, 0) + 1
                    print(f"  INVALID thumbnail ad={ad_id}: {reason}")

                    # Delete invalid file
                    os.remove(thumb_path)
                    deleted += 1

                    # Reset s3_key to NULL
                    if ad.thumbnail_s3_key:
                        ad.thumbnail_s3_key = None
                        meta = dict(ad.ad_metadata or {})
                        meta["media_health_fixed"] = True
                        meta["thumbnail_fixed"] = False
                        ad.ad_metadata = meta
                        flag_modified(ad, "ad_metadata")

            # -- Validate image --
            img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
            if os.path.exists(img_path):
                valid, reason = validate_single_file(img_path, "image")
                if valid:
                    details["img_valid"] += 1
                    validated += 1
                else:
                    details["img_invalid"] += 1
                    details["img_reasons"][reason] = details["img_reasons"].get(reason, 0) + 1
                    print(f"  INVALID image ad={ad_id}: {reason}")

                    # Delete invalid file
                    os.remove(img_path)
                    deleted += 1

                    # Reset s3_key to NULL
                    if ad.image_s3_key:
                        ad.image_s3_key = None
                        meta = dict(ad.ad_metadata or {})
                        meta["media_health_fixed"] = True
                        ad.ad_metadata = meta
                        flag_modified(ad, "ad_metadata")

        session.commit()

        # -- Final counts --
        after_thumb = session.query(Ad).filter(Ad.thumbnail_s3_key.isnot(None)).count()
        after_img = session.query(Ad).filter(Ad.image_s3_key.isnot(None)).count()

        # Count files on disk
        thumb_files = len([f for f in os.listdir(THUMB_DIR) if f.endswith(".jpg")]) if os.path.isdir(THUMB_DIR) else 0
        img_files = len([f for f in os.listdir(IMAGE_DIR) if f.endswith(".jpg")]) if os.path.isdir(IMAGE_DIR) else 0

        print()
        print("=" * 60)
        print("  VALIDATION RESULTS")
        print("=" * 60)
        print(f"  Validated: {validated} files OK")
        print(f"  Deleted:   {deleted} invalid files")
        print()
        print(f"  Thumbnails: {details['thumb_valid']} valid, {details['thumb_invalid']} invalid")
        if details["thumb_reasons"]:
            for reason, count in sorted(details["thumb_reasons"].items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {count}")
        print()
        print(f"  Images:     {details['img_valid']} valid, {details['img_invalid']} invalid")
        if details["img_reasons"]:
            for reason, count in sorted(details["img_reasons"].items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {count}")
        print()
        print(f"  Files on disk:   thumbnails={thumb_files}, images={img_files}")
        print(f"  DB s3_key set:   thumbnails={after_thumb}/{total}, images={after_img}/{total}")
        thumb_rate = after_thumb * 100 / total if total > 0 else 0
        img_rate = after_img * 100 / total if total > 0 else 0
        print(f"  Cache rate:      thumbnails={thumb_rate:.1f}%, images={img_rate:.1f}%")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
