"""Media cleanup script for creative asset management.

Cleans up the media_cache directory:
  1. Remove orphaned files (files in media_cache/ that don't match any ad_id)
  2. Remove corrupt files (0 bytes, not valid image/video)
  3. Remove duplicates (same file hash)
  4. Print cleanup report

Run from the backend directory:
    cd backend
    python scripts/media_cleanup.py
"""

import os
import sys
import hashlib
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
MIN_IMAGE_SIZE = 100       # bytes - files smaller than this are corrupt
MIN_VIDEO_SIZE = 1000      # bytes - videos smaller than this are corrupt

# Magic bytes for valid image formats
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"
GIF_MAGIC = b"GIF"
WEBP_RIFF = b"RIFF"

# Magic bytes for valid video formats
MP4_FTYP = b"ftyp"
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"

# HTML detection patterns (error pages saved as images)
HTML_MARKERS = [b"<html", b"<!doctype", b"<!DOCTYPE", b"<HTML", b"<head", b"<?xml"]

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")
FRAMES_DIR = os.path.join(CACHE_DIR, "frames")
DOWNLOAD_DIR = os.path.join(CACHE_DIR, "downloads")


def _is_valid_image(path: str) -> bool:
    """Check if a file is a valid image by checking magic bytes and size."""
    try:
        size = os.path.getsize(path)
        if size < MIN_IMAGE_SIZE:
            return False
        with open(path, "rb") as f:
            header = f.read(32)
        if len(header) < 4:
            return False
        # Check for HTML masquerading as image
        header_lower = header.lower()
        for marker in HTML_MARKERS:
            if marker.lower() in header_lower:
                return False
        # Check for known image formats
        if header[:3] == JPEG_MAGIC:
            return True
        if header[:4] == PNG_MAGIC:
            return True
        if header[:3] == GIF_MAGIC:
            return True
        if header[:4] == WEBP_RIFF and len(header) >= 12 and header[8:12] == b"WEBP":
            return True
        return False
    except Exception:
        return False


def _is_valid_video(path: str) -> bool:
    """Check if a file is a valid video by checking magic bytes and size."""
    try:
        size = os.path.getsize(path)
        if size < MIN_VIDEO_SIZE:
            return False
        with open(path, "rb") as f:
            header = f.read(12)
        if len(header) < 4:
            return False
        # MP4/MOV (ftyp box)
        if MP4_FTYP in header[4:8]:
            return True
        # WebM (EBML header)
        if header[:4] == WEBM_MAGIC:
            return True
        # Large enough unknown format - probably OK
        if size > MIN_VIDEO_SIZE * 100:
            return True
        return False
    except Exception:
        return False


def _file_hash(path: str) -> str:
    """Compute MD5 hash of a file for duplicate detection."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _extract_ad_id_from_filename(filename: str) -> int | None:
    """Try to extract ad_id from a filename like '123.jpg' or '123_frame_0.jpg'."""
    base = filename.split(".")[0]
    # Handle frame filenames: {ad_id}_frame_{idx}
    if "_frame_" in base:
        base = base.split("_frame_")[0]
    try:
        return int(base)
    except (ValueError, IndexError):
        return None


def run_cleanup(dry_run: bool = False) -> dict:
    """Run the full media cleanup.

    Args:
        dry_run: If True, only report what would be done without deleting.

    Returns:
        Cleanup statistics dict.
    """
    stats = {
        "orphaned_removed": 0,
        "orphaned_size_mb": 0.0,
        "corrupt_removed": 0,
        "corrupt_size_mb": 0.0,
        "duplicates_removed": 0,
        "duplicates_size_mb": 0.0,
        "total_freed_mb": 0.0,
        "files_scanned": 0,
        "files_kept": 0,
    }

    session = SyncSessionLocal()
    try:
        # Get all valid ad IDs from database
        ad_ids = {row[0] for row in session.query(Ad.id).all()}
        print(f"Database has {len(ad_ids)} ads")

        # Track file hashes for duplicate detection (hash -> first path seen)
        seen_hashes: dict[str, str] = {}

        # Directories to scan: (dir_path, file_type, extension_filter)
        scan_dirs = []
        if os.path.isdir(THUMB_DIR):
            scan_dirs.append((THUMB_DIR, "image", ".jpg"))
        if os.path.isdir(IMAGE_DIR):
            scan_dirs.append((IMAGE_DIR, "image", ".jpg"))
        if os.path.isdir(VIDEO_DIR):
            scan_dirs.append((VIDEO_DIR, "video", None))
        if os.path.isdir(FRAMES_DIR):
            scan_dirs.append((FRAMES_DIR, "image", ".jpg"))
        if os.path.isdir(DOWNLOAD_DIR):
            scan_dirs.append((DOWNLOAD_DIR, "other", ".zip"))

        for dir_path, file_type, ext_filter in scan_dirs:
            dir_name = os.path.basename(dir_path)
            print(f"\nScanning {dir_name}/...")

            for filename in os.listdir(dir_path):
                filepath = os.path.join(dir_path, filename)
                if not os.path.isfile(filepath):
                    continue

                # Apply extension filter if specified
                if ext_filter and not filename.lower().endswith(ext_filter):
                    # For video dir, accept multiple extensions
                    if file_type == "video":
                        if not any(filename.lower().endswith(e) for e in (".mp4", ".webm", ".mov")):
                            continue
                    else:
                        continue

                stats["files_scanned"] += 1
                file_size = os.path.getsize(filepath)
                file_size_mb = file_size / (1024 * 1024)

                # Skip downloads dir from orphan/corrupt checks (temp files)
                if dir_path == DOWNLOAD_DIR:
                    stats["files_kept"] += 1
                    continue

                # ── Check 1: Orphaned file (no matching ad_id in DB) ──
                ad_id = _extract_ad_id_from_filename(filename)
                if ad_id is not None and ad_id not in ad_ids:
                    stats["orphaned_removed"] += 1
                    stats["orphaned_size_mb"] += file_size_mb
                    print(f"  ORPHAN: {dir_name}/{filename} (ad_id={ad_id} not in DB)")
                    if not dry_run:
                        os.remove(filepath)
                    continue

                # ── Check 2: Corrupt file ──
                is_valid = True
                if file_type == "image":
                    is_valid = _is_valid_image(filepath)
                elif file_type == "video":
                    is_valid = _is_valid_video(filepath)

                if not is_valid:
                    stats["corrupt_removed"] += 1
                    stats["corrupt_size_mb"] += file_size_mb
                    print(f"  CORRUPT: {dir_name}/{filename} ({file_size} bytes)")
                    if not dry_run:
                        os.remove(filepath)
                    continue

                # ── Check 3: Duplicate file (same hash) ──
                fhash = _file_hash(filepath)
                if fhash and fhash in seen_hashes:
                    # Keep the first one, remove subsequent duplicates
                    original = seen_hashes[fhash]
                    # Only remove if in different directories (same ad in thumb+image is OK)
                    orig_dir = os.path.dirname(original)
                    if orig_dir == dir_path:
                        stats["duplicates_removed"] += 1
                        stats["duplicates_size_mb"] += file_size_mb
                        print(f"  DUPLICATE: {dir_name}/{filename} == {os.path.basename(original)}")
                        if not dry_run:
                            os.remove(filepath)
                        continue

                # File is valid and unique
                if fhash:
                    seen_hashes[fhash] = filepath
                stats["files_kept"] += 1

        stats["total_freed_mb"] = (
            stats["orphaned_size_mb"]
            + stats["corrupt_size_mb"]
            + stats["duplicates_size_mb"]
        )

        return stats

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        logger.exception("media_cleanup failed")
        raise
    finally:
        session.close()


def print_report(stats: dict, dry_run: bool = False):
    """Print a formatted cleanup report."""
    mode = "DRY RUN" if dry_run else "CLEANUP"
    print(f"\n{'=' * 60}")
    print(f"  MEDIA {mode} REPORT")
    print(f"{'=' * 60}")
    print()
    print(f"  Files scanned:        {stats['files_scanned']}")
    print(f"  Files kept:           {stats['files_kept']}")
    print()
    print(f"  Orphaned removed:     {stats['orphaned_removed']}  ({stats['orphaned_size_mb']:.2f} MB)")
    print(f"  Corrupt removed:      {stats['corrupt_removed']}  ({stats['corrupt_size_mb']:.2f} MB)")
    print(f"  Duplicates removed:   {stats['duplicates_removed']}  ({stats['duplicates_size_mb']:.2f} MB)")
    print()
    print(f"  Total freed:          {stats['total_freed_mb']:.2f} MB")
    print(f"{'=' * 60}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Media cache cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Report only, do not delete")
    args = parser.parse_args()

    print("=" * 60)
    print("  Media Cleanup")
    if args.dry_run:
        print("  MODE: DRY RUN (no files will be deleted)")
    print("=" * 60)

    stats = run_cleanup(dry_run=args.dry_run)
    print_report(stats, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
