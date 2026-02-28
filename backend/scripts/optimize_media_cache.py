"""Optimize media cache by removing duplicates, compressing oversized images,
and cleaning orphaned files.

Actions:
  1. Scan media_cache/ directory
  2. Remove duplicate files (same content hash)
  3. Compress oversized images (> 500KB) using Pillow if available
  4. Remove orphaned files (no matching ad in DB)
  5. Report savings: files removed, space saved

Run from the backend directory:
    cd backend
    python scripts/optimize_media_cache.py
"""

import hashlib
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────

MAX_IMAGE_SIZE = 500 * 1024  # 500KB threshold for compression
COMPRESS_QUALITY = 80        # JPEG quality for compressed images
COMPRESS_MAX_DIM = 1920      # Max dimension for resize

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")
DOWNLOAD_DIR = os.path.join(CACHE_DIR, "downloads")

# Pillow availability
_pillow_available = False
try:
    from PIL import Image
    _pillow_available = True
except ImportError:
    pass


def file_hash(path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(directory: str) -> list[tuple[str, str]]:
    """Find duplicate files in a directory by content hash.

    Returns list of (duplicate_path, original_path) pairs.
    """
    if not os.path.isdir(directory):
        return []

    hash_map: dict[str, str] = {}  # hash -> first file path
    duplicates = []

    for fname in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            fhash = file_hash(fpath)
            if fhash in hash_map:
                duplicates.append((fpath, hash_map[fhash]))
            else:
                hash_map[fhash] = fpath
        except Exception as e:
            logger.warning("Hash error for %s: %s", fpath, str(e))

    return duplicates


def compress_image(path: str) -> int:
    """Compress an oversized image. Returns bytes saved (0 if not compressed)."""
    if not _pillow_available:
        return 0

    try:
        original_size = os.path.getsize(path)
        if original_size <= MAX_IMAGE_SIZE:
            return 0

        with Image.open(path) as img:
            # Convert to RGB if necessary (e.g. RGBA PNG)
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            # Resize if too large
            w, h = img.size
            if max(w, h) > COMPRESS_MAX_DIM:
                ratio = COMPRESS_MAX_DIM / max(w, h)
                new_w = int(w * ratio)
                new_h = int(h * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)

            # Save with reduced quality
            img.save(path, "JPEG", quality=COMPRESS_QUALITY, optimize=True)

        new_size = os.path.getsize(path)
        saved = original_size - new_size
        return max(saved, 0)

    except Exception as e:
        logger.warning("Compress error for %s: %s", path, str(e))
        return 0


def find_orphaned_files(directory: str, ad_ids: set[int], extensions: list[str]) -> list[str]:
    """Find files in directory whose ID does not match any ad in DB."""
    if not os.path.isdir(directory):
        return []

    orphans = []
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue

        # Extract numeric ID from filename
        for ext in extensions:
            if fname.endswith(ext):
                try:
                    fid = int(fname.replace(ext, ""))
                    if fid not in ad_ids:
                        orphans.append(fpath)
                except ValueError:
                    # Non-numeric filename, consider orphan
                    orphans.append(fpath)
                break

    return orphans


def main():
    print("=" * 60)
    print("  MEDIA CACHE OPTIMIZER")
    print("=" * 60)
    print()

    if _pillow_available:
        print("  Pillow: available (image compression enabled)")
    else:
        print("  Pillow: NOT available (image compression skipped)")
    print()

    # Load ad IDs from DB
    session = SyncSessionLocal()
    try:
        ad_ids = {ad.id for ad in session.query(Ad.id).all()}
        print(f"  Total ads in DB: {len(ad_ids)}")
    finally:
        session.close()

    stats = {
        "duplicates_removed": 0,
        "duplicates_bytes_saved": 0,
        "images_compressed": 0,
        "compress_bytes_saved": 0,
        "orphans_removed": 0,
        "orphans_bytes_saved": 0,
        "downloads_cleaned": 0,
        "downloads_bytes_saved": 0,
    }

    # ── Step 1: Remove duplicates ────────────────────────────────────
    print("\n  Step 1: Scanning for duplicate files...")

    for dir_name, directory in [("thumbnails", THUMB_DIR), ("images", IMAGE_DIR)]:
        dupes = find_duplicates(directory)
        for dupe_path, orig_path in dupes:
            dupe_size = os.path.getsize(dupe_path)
            print(f"    DUPLICATE: {os.path.basename(dupe_path)} == {os.path.basename(orig_path)}")
            os.remove(dupe_path)
            stats["duplicates_removed"] += 1
            stats["duplicates_bytes_saved"] += dupe_size

    if stats["duplicates_removed"] == 0:
        print("    No duplicates found.")

    # ── Step 2: Compress oversized images ────────────────────────────
    print("\n  Step 2: Compressing oversized images...")

    if _pillow_available:
        for dir_name, directory in [("thumbnails", THUMB_DIR), ("images", IMAGE_DIR)]:
            if not os.path.isdir(directory):
                continue
            for fname in os.listdir(directory):
                fpath = os.path.join(directory, fname)
                if not os.path.isfile(fpath):
                    continue
                if not fname.endswith(".jpg"):
                    continue

                saved = compress_image(fpath)
                if saved > 0:
                    stats["images_compressed"] += 1
                    stats["compress_bytes_saved"] += saved
                    print(f"    COMPRESSED: {fname} (saved {saved / 1024:.1f} KB)")

        if stats["images_compressed"] == 0:
            print("    No oversized images found.")
    else:
        print("    Skipped (Pillow not available).")

    # ── Step 3: Remove orphaned files ────────────────────────────────
    print("\n  Step 3: Removing orphaned files...")

    # Thumbnails
    orphans = find_orphaned_files(THUMB_DIR, ad_ids, [".jpg"])
    for path in orphans:
        size = os.path.getsize(path)
        print(f"    ORPHAN thumbnail: {os.path.basename(path)}")
        os.remove(path)
        stats["orphans_removed"] += 1
        stats["orphans_bytes_saved"] += size

    # Images
    orphans = find_orphaned_files(IMAGE_DIR, ad_ids, [".jpg"])
    for path in orphans:
        size = os.path.getsize(path)
        print(f"    ORPHAN image: {os.path.basename(path)}")
        os.remove(path)
        stats["orphans_removed"] += 1
        stats["orphans_bytes_saved"] += size

    # Videos
    orphans = find_orphaned_files(VIDEO_DIR, ad_ids, [".mp4", ".webm", ".mov"])
    for path in orphans:
        size = os.path.getsize(path)
        print(f"    ORPHAN video: {os.path.basename(path)}")
        os.remove(path)
        stats["orphans_removed"] += 1
        stats["orphans_bytes_saved"] += size

    if stats["orphans_removed"] == 0:
        print("    No orphaned files found.")

    # ── Step 4: Clean old downloads ──────────────────────────────────
    print("\n  Step 4: Cleaning old download ZIPs...")

    if os.path.isdir(DOWNLOAD_DIR):
        for fname in os.listdir(DOWNLOAD_DIR):
            fpath = os.path.join(DOWNLOAD_DIR, fname)
            if os.path.isfile(fpath) and fname.endswith(".zip"):
                size = os.path.getsize(fpath)
                os.remove(fpath)
                stats["downloads_cleaned"] += 1
                stats["downloads_bytes_saved"] += size
                print(f"    REMOVED download: {fname}")

    if stats["downloads_cleaned"] == 0:
        print("    No old downloads found.")

    # ── Summary ──────────────────────────────────────────────────────
    total_saved = (
        stats["duplicates_bytes_saved"]
        + stats["compress_bytes_saved"]
        + stats["orphans_bytes_saved"]
        + stats["downloads_bytes_saved"]
    )

    print()
    print("=" * 60)
    print("  OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"  Duplicates removed:    {stats['duplicates_removed']} files ({stats['duplicates_bytes_saved'] / 1024:.1f} KB)")
    print(f"  Images compressed:     {stats['images_compressed']} files ({stats['compress_bytes_saved'] / 1024:.1f} KB saved)")
    print(f"  Orphaned files removed:{stats['orphans_removed']} files ({stats['orphans_bytes_saved'] / 1024:.1f} KB)")
    print(f"  Downloads cleaned:     {stats['downloads_cleaned']} files ({stats['downloads_bytes_saved'] / 1024:.1f} KB)")
    print(f"  --------------------------------")
    print(f"  Total space saved:     {total_saved / (1024 * 1024):.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
