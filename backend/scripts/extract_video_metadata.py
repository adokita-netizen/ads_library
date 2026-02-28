"""Extract video metadata and classify video format/type.

For each ad with video_url in DB:
  1. Extract duration from URL patterns, file metadata, or DB fields
  2. Classify format: vertical (9:16), horizontal (16:9), square (1:1)
  3. Detect if it's a slideshow vs real video (from file size/duration ratio)
  4. Store in ad_metadata.video_analysis

Run from the backend directory:
    cd backend
    python scripts/extract_video_metadata.py
"""

import os
import re
import struct
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
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")
BATCH_SIZE = 20

# Slideshow detection: if bitrate < threshold, likely slideshow
SLIDESHOW_BITRATE_THRESHOLD = 50_000  # 50 Kbps - very low bitrate suggests slideshow


def extract_duration_from_url(url: str) -> float | None:
    """Try to extract video duration from URL patterns."""
    if not url:
        return None

    # Pattern: duration=30, dur=15, t=10
    patterns = [
        r'duration[=_](\d+(?:\.\d+)?)',
        r'dur[=_](\d+(?:\.\d+)?)',
        r'[?&]t=(\d+(?:\.\d+)?)',
        r'_(\d+)s\.',  # filename like video_30s.mp4
    ]

    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1))
                if 1 <= val <= 600:  # Reasonable range: 1s to 10min
                    return val
            except ValueError:
                pass

    return None


def get_mp4_duration(filepath: str) -> float | None:
    """Try to extract duration from MP4 file header (mvhd atom)."""
    try:
        with open(filepath, "rb") as f:
            data = f.read(min(os.path.getsize(filepath), 2 * 1024 * 1024))  # First 2MB

        # Search for 'mvhd' atom
        pos = data.find(b"mvhd")
        if pos < 0:
            return None

        # mvhd atom structure (version 0):
        # 1 byte version, 3 bytes flags, 4 bytes creation_time,
        # 4 bytes modification_time, 4 bytes time_scale, 4 bytes duration
        mvhd_start = pos + 4  # skip 'mvhd'
        version = data[mvhd_start]

        if version == 0:
            # 32-bit fields
            if mvhd_start + 20 > len(data):
                return None
            time_scale = struct.unpack(">I", data[mvhd_start + 12:mvhd_start + 16])[0]
            duration = struct.unpack(">I", data[mvhd_start + 16:mvhd_start + 20])[0]
        elif version == 1:
            # 64-bit fields
            if mvhd_start + 28 > len(data):
                return None
            time_scale = struct.unpack(">I", data[mvhd_start + 20:mvhd_start + 24])[0]
            duration = struct.unpack(">Q", data[mvhd_start + 24:mvhd_start + 32])[0]
        else:
            return None

        if time_scale > 0:
            dur_sec = duration / time_scale
            if 0.1 <= dur_sec <= 3600:  # Reasonable range
                return round(dur_sec, 1)

    except Exception:
        pass

    return None


def classify_format(width: int | None, height: int | None) -> str:
    """Classify video format based on dimensions."""
    if not width or not height:
        return "unknown"

    ratio = width / height

    if ratio < 0.7:
        return "vertical"     # 9:16 or similar
    elif ratio > 1.4:
        return "horizontal"   # 16:9 or similar
    elif 0.9 <= ratio <= 1.1:
        return "square"       # 1:1
    else:
        return "other"


def detect_video_type(file_size: int | None, duration_sec: float | None) -> str:
    """Detect if video is a real video or slideshow based on bitrate."""
    if not file_size or not duration_sec or duration_sec <= 0:
        return "unknown"

    # Calculate bitrate in bits per second
    bitrate = (file_size * 8) / duration_sec

    if bitrate < SLIDESHOW_BITRATE_THRESHOLD:
        return "slideshow"
    else:
        return "real_video"


def main():
    print("=" * 60)
    print("  VIDEO METADATA EXTRACTOR")
    print("=" * 60)
    print()

    session = SyncSessionLocal()
    try:
        # Find all ads with video_url
        ads = session.query(Ad).filter(
            Ad.video_url.isnot(None)
        ).order_by(Ad.id).all()

        total = len(ads)
        print(f"  Ads with video_url: {total}")

        if total == 0:
            print("  No video ads to process.")
            return

        processed = 0
        updated = 0
        skipped = 0

        for i, ad in enumerate(ads):
            ad_id = ad.id
            meta = dict(ad.ad_metadata or {})

            # Skip if already analyzed
            existing = meta.get("video_analysis")
            if isinstance(existing, dict) and existing.get("duration_sec") is not None:
                skipped += 1
                continue

            processed += 1
            analysis: dict = {}

            # -- Duration extraction --
            duration_sec = None

            # 1. Try from DB field
            if ad.duration_seconds and ad.duration_seconds > 0:
                duration_sec = round(ad.duration_seconds, 1)

            # 2. Try from video file
            if duration_sec is None:
                for ext in ("mp4", "webm", "mov"):
                    video_path = os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")
                    if os.path.exists(video_path) and ext == "mp4":
                        duration_sec = get_mp4_duration(video_path)
                        if duration_sec:
                            break

            # 3. Try from URL patterns
            if duration_sec is None:
                duration_sec = extract_duration_from_url(ad.video_url)

            analysis["duration_sec"] = duration_sec

            # -- Format classification --
            width = ad.resolution_width
            height = ad.resolution_height
            analysis["format"] = classify_format(width, height)

            if width and height:
                analysis["resolution"] = f"{width}x{height}"

            # -- Video type detection --
            file_size = None
            for ext in ("mp4", "webm", "mov"):
                video_path = os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")
                if os.path.exists(video_path):
                    file_size = os.path.getsize(video_path)
                    analysis["file_size_bytes"] = file_size
                    analysis["cached"] = True
                    break

            if file_size is None:
                analysis["cached"] = False
                if ad.file_size_bytes:
                    file_size = ad.file_size_bytes

            analysis["type"] = detect_video_type(file_size, duration_sec)

            # Store in metadata
            meta["video_analysis"] = analysis
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"  Progress: {i + 1}/{total} processed")

        session.commit()

        # -- Summary --
        print()
        print("=" * 60)
        print("  EXTRACTION RESULTS")
        print("=" * 60)
        print(f"  Total video ads:     {total}")
        print(f"  Processed:           {processed}")
        print(f"  Updated metadata:    {updated}")
        print(f"  Skipped (existing):  {skipped}")

        # Count formats
        format_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        duration_count = 0

        for ad in ads:
            va = (ad.ad_metadata or {}).get("video_analysis", {})
            if isinstance(va, dict):
                fmt = va.get("format", "unknown")
                format_counts[fmt] = format_counts.get(fmt, 0) + 1
                vtype = va.get("type", "unknown")
                type_counts[vtype] = type_counts.get(vtype, 0) + 1
                if va.get("duration_sec") is not None:
                    duration_count += 1

        print(f"  With duration:       {duration_count}")
        print()
        print("  Format breakdown:")
        for fmt, count in sorted(format_counts.items(), key=lambda x: -x[1]):
            print(f"    {fmt}: {count}")
        print()
        print("  Type breakdown:")
        for vtype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {vtype}: {count}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
