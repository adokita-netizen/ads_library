#!/usr/bin/env python3
"""CI-068: Detect duplicate media files via content hash comparison.

Scans media_cache/images and media_cache/videos, computes MD5 hashes,
and reports duplicate groups. Optionally marks duplicates in ad_metadata.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/detect_media_duplicates.py [--mark] [--delete-dupes]
"""

import hashlib
import io
import os
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = os.path.normpath(os.path.join(BASE_DIR, "media_cache", "images"))
VIDEO_DIR = os.path.normpath(os.path.join(BASE_DIR, "media_cache", "videos"))


def _get_session():
    """Get DB session with SQLite fallback."""
    try:
        from app.core.database import SyncSessionLocal
        session = SyncSessionLocal()
        session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return session
    except Exception:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        db_path = os.path.join(BASE_DIR, "vaap_local.db")
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        return Session()


def file_md5(path: str) -> str:
    """Compute MD5 hash of file contents."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_directory(directory: str) -> dict[str, list[str]]:
    """Scan directory and group files by content hash."""
    hash_to_files: dict[str, list[str]] = defaultdict(list)
    if not os.path.isdir(directory):
        return hash_to_files

    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath) or os.path.getsize(fpath) < 100:
            continue
        try:
            h = file_md5(fpath)
            hash_to_files[h].append(fpath)
        except Exception:
            pass

    return hash_to_files


def extract_ad_id(filepath: str) -> int | None:
    """Extract ad ID from filename like '123.jpg' or '123.mp4'."""
    basename = os.path.splitext(os.path.basename(filepath))[0]
    try:
        return int(basename)
    except ValueError:
        return None


def detect_and_report(mark: bool = False, delete_dupes: bool = False):
    print("Scanning media directories for duplicates...")

    image_groups = scan_directory(IMAGE_DIR)
    video_groups = scan_directory(VIDEO_DIR)

    image_dupes = {h: files for h, files in image_groups.items() if len(files) > 1}
    video_dupes = {h: files for h, files in video_groups.items() if len(files) > 1}

    total_image_dupes = sum(len(f) - 1 for f in image_dupes.values())
    total_video_dupes = sum(len(f) - 1 for f in video_dupes.values())

    print(f"\nImage files scanned: {sum(len(f) for f in image_groups.values())}")
    print(f"Image duplicate groups: {len(image_dupes)} ({total_image_dupes} extra files)")
    print(f"Video files scanned: {sum(len(f) for f in video_groups.values())}")
    print(f"Video duplicate groups: {len(video_dupes)} ({total_video_dupes} extra files)")

    if image_dupes:
        print("\n=== Image Duplicate Groups ===")
        for h, files in sorted(image_dupes.items()):
            ids = [extract_ad_id(f) for f in files]
            size = os.path.getsize(files[0])
            print(f"  Hash {h[:12]}: {len(files)} files, {size/1024:.0f}KB, ad_ids={ids}")

    if video_dupes:
        print("\n=== Video Duplicate Groups ===")
        for h, files in sorted(video_dupes.items()):
            ids = [extract_ad_id(f) for f in files]
            size = os.path.getsize(files[0])
            print(f"  Hash {h[:12]}: {len(files)} files, {size/1024/1024:.1f}MB, ad_ids={ids}")

    if not mark and not delete_dupes:
        return

    # Mark duplicates in DB
    if mark:
        from app.models.ad import Ad
        from sqlalchemy.orm.attributes import flag_modified

        session = _get_session()
        marked = 0

        all_dupes = {**image_dupes, **video_dupes}
        for h, files in all_dupes.items():
            ad_ids = [extract_ad_id(f) for f in files]
            ad_ids = [i for i in ad_ids if i is not None]
            if len(ad_ids) < 2:
                continue
            # Keep first (lowest ID), mark rest as duplicates
            primary_id = min(ad_ids)
            for aid in ad_ids:
                if aid == primary_id:
                    continue
                ad = session.query(Ad).filter(Ad.id == aid).first()
                if not ad:
                    continue
                meta = dict(ad.ad_metadata or {})
                meta["media_duplicate_of"] = primary_id
                meta["media_hash"] = h
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                marked += 1

        try:
            session.commit()
        except Exception:
            session.rollback()
        session.close()
        print(f"\nMarked {marked} ads as media duplicates in DB")

    # Delete duplicate files (keep first/smallest ID)
    if delete_dupes:
        deleted = 0
        all_dupes = {**image_dupes, **video_dupes}
        for h, files in all_dupes.items():
            # Sort by ad ID, keep lowest
            sorted_files = sorted(files, key=lambda f: extract_ad_id(f) or 999999)
            for f in sorted_files[1:]:
                try:
                    os.remove(f)
                    deleted += 1
                except Exception:
                    pass
        print(f"\nDeleted {deleted} duplicate media files")


if __name__ == "__main__":
    mark_mode = "--mark" in sys.argv
    delete_mode = "--delete-dupes" in sys.argv
    detect_and_report(mark=mark_mode, delete_dupes=delete_mode)
