#!/usr/bin/env python3
"""Extract video metadata (duration, resolution, file size, codec) from cached videos.

For each cached video in media_cache/videos/:
  - Extract duration, resolution (width x height), file size, codec
  - Update Ad model: duration_seconds, resolution_width, resolution_height, file_size_bytes
  - Update ad_metadata with codec info

Uses ffprobe (subprocess) if available, otherwise tries OpenCV (cv2).
If neither is available, only updates file_size_bytes.

Run from the backend directory:
    cd backend
    python scripts/extract_video_info.py
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# ── Config ────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")

VIDEO_EXTENSIONS = ("mp4", "webm", "mov")


# ── Tool Detection ───────────────────────────────────────────────────

def detect_ffprobe() -> str | None:
    """Check if ffprobe is available. Returns path or None."""
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        return ffprobe_path

    common_paths = [
        r"C:\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffprobe.exe"),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p

    return None


def detect_cv2() -> bool:
    """Check if OpenCV (cv2) is available."""
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


# ── Info Extraction ──────────────────────────────────────────────────

def extract_info_ffprobe(video_path: str, ffprobe_path: str) -> dict:
    """Extract video info using ffprobe. Returns dict with duration, width, height, codec."""
    info = {}

    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            return info

        data = json.loads(result.stdout)

        # Duration from format
        fmt = data.get("format", {})
        if fmt.get("duration"):
            try:
                info["duration"] = float(fmt["duration"])
            except (ValueError, TypeError):
                pass

        # Find video stream for resolution and codec
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                if stream.get("width"):
                    info["width"] = int(stream["width"])
                if stream.get("height"):
                    info["height"] = int(stream["height"])
                if stream.get("codec_name"):
                    info["codec"] = stream["codec_name"]
                if stream.get("bit_rate"):
                    try:
                        info["bitrate"] = int(stream["bit_rate"])
                    except (ValueError, TypeError):
                        pass
                # Get fps
                r_frame_rate = stream.get("r_frame_rate", "")
                if "/" in r_frame_rate:
                    parts = r_frame_rate.split("/")
                    try:
                        num, den = int(parts[0]), int(parts[1])
                        if den > 0:
                            info["fps"] = round(num / den, 2)
                    except (ValueError, IndexError):
                        pass
                break

    except subprocess.TimeoutExpired:
        pass
    except json.JSONDecodeError:
        pass
    except Exception:
        pass

    return info


def extract_info_cv2(video_path: str) -> dict:
    """Extract video info using OpenCV. Returns dict with duration, width, height."""
    info = {}

    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return info

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if fps > 0 and frame_count > 0:
            info["duration"] = frame_count / fps
        if width > 0:
            info["width"] = width
        if height > 0:
            info["height"] = height
        if fps > 0:
            info["fps"] = round(fps, 2)

        # Try to get codec fourcc
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        if fourcc > 0:
            codec_chars = [chr((fourcc >> (8 * i)) & 0xFF) for i in range(4)]
            info["codec"] = "".join(codec_chars).strip()

        cap.release()

    except Exception:
        pass

    return info


# ── Helpers ──────────────────────────────────────────────────────────

def find_cached_videos() -> list[tuple[int, str]]:
    """Find all cached video files. Returns list of (ad_id, path)."""
    if not os.path.isdir(VIDEO_DIR):
        return []

    videos = []
    for filename in os.listdir(VIDEO_DIR):
        for ext in VIDEO_EXTENSIONS:
            if filename.endswith(f".{ext}"):
                try:
                    ad_id = int(filename.replace(f".{ext}", ""))
                    path = os.path.join(VIDEO_DIR, filename)
                    if os.path.getsize(path) > 1000:
                        videos.append((ad_id, path))
                except ValueError:
                    continue
    return sorted(videos, key=lambda x: x[0])


# ── Main ──────────────────────────────────────────────────────────────

def main():
    ffprobe_path = detect_ffprobe()
    has_cv2 = detect_cv2()

    print("=" * 60)
    print("VIDEO INFO EXTRACTION")
    print("=" * 60)
    print(f"ffprobe: {'YES (' + ffprobe_path + ')' if ffprobe_path else 'NOT FOUND'}")
    print(f"OpenCV:  {'YES' if has_cv2 else 'NOT FOUND'}")

    if not ffprobe_path and not has_cv2:
        print()
        print("WARNING: Neither ffprobe nor OpenCV is available.")
        print("Only file_size_bytes will be updated.")

    use_ffprobe = bool(ffprobe_path)
    print(f"Using:   {'ffprobe' if use_ffprobe else ('OpenCV' if has_cv2 else 'file size only')}")
    print()

    # Find cached videos
    cached_videos = find_cached_videos()
    print(f"Cached videos found: {len(cached_videos)}")

    if not cached_videos:
        print("No cached videos to process.")
        return

    session = SyncSessionLocal()
    stats = {"updated": 0, "skipped": 0, "failed": 0}

    try:
        for i, (ad_id, video_path) in enumerate(cached_videos):
            label = f"[{i+1}/{len(cached_videos)}] Ad {ad_id}"

            ad = session.query(Ad).filter(Ad.id == ad_id).first()
            if not ad:
                print(f"  {label}: SKIPPED (ad not found in DB)")
                stats["skipped"] += 1
                continue

            # Get file size (always available)
            try:
                file_size = os.path.getsize(video_path)
            except OSError:
                print(f"  {label}: FAILED (could not read file)")
                stats["failed"] += 1
                continue

            # Extract info using available tool
            info = {}
            if use_ffprobe:
                info = extract_info_ffprobe(video_path, ffprobe_path)
            elif has_cv2:
                info = extract_info_cv2(video_path)

            # Update Ad model fields
            changed = False

            if file_size and (ad.file_size_bytes is None or ad.file_size_bytes != file_size):
                ad.file_size_bytes = file_size
                changed = True

            if info.get("duration") and (ad.duration_seconds is None):
                ad.duration_seconds = round(info["duration"], 2)
                changed = True

            if info.get("width") and (ad.resolution_width is None):
                ad.resolution_width = info["width"]
                changed = True

            if info.get("height") and (ad.resolution_height is None):
                ad.resolution_height = info["height"]
                changed = True

            # Update metadata with extended info
            meta = dict(ad.ad_metadata or {})
            video_info_meta = {}
            if info.get("codec"):
                video_info_meta["codec"] = info["codec"]
            if info.get("fps"):
                video_info_meta["fps"] = info["fps"]
            if info.get("bitrate"):
                video_info_meta["bitrate"] = info["bitrate"]
            if file_size:
                video_info_meta["file_size_mb"] = round(file_size / 1024 / 1024, 2)

            if video_info_meta:
                meta["video_info"] = video_info_meta
                meta["video_info_extracted"] = True
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                changed = True

            if changed:
                stats["updated"] += 1
                duration_str = f"{info.get('duration', '?'):.1f}s" if isinstance(info.get('duration'), (int, float)) else "?"
                res_str = f"{info.get('width', '?')}x{info.get('height', '?')}"
                codec_str = info.get("codec", "?")
                size_mb = file_size / 1024 / 1024
                print(f"  {label}: {duration_str}, {res_str}, {codec_str}, {size_mb:.1f}MB")
            else:
                stats["skipped"] += 1
                print(f"  {label}: already up to date")

            # Batch commit
            if (i + 1) % 20 == 0:
                session.commit()

        session.commit()

        # Summary
        print()
        print("=" * 60)
        print("VIDEO INFO SUMMARY")
        print("=" * 60)
        print(f"Total cached videos: {len(cached_videos)}")
        print(f"Updated:             {stats['updated']}")
        print(f"Already up to date:  {stats['skipped']}")
        print(f"Failed:              {stats['failed']}")

        # Print aggregate stats
        ads_with_duration = session.query(Ad).filter(
            Ad.duration_seconds.isnot(None)
        ).count()
        ads_with_resolution = session.query(Ad).filter(
            Ad.resolution_width.isnot(None)
        ).count()
        ads_with_filesize = session.query(Ad).filter(
            Ad.file_size_bytes.isnot(None)
        ).count()

        print()
        print("Database video metadata coverage:")
        print(f"  duration_seconds:   {ads_with_duration}")
        print(f"  resolution:         {ads_with_resolution}")
        print(f"  file_size_bytes:    {ads_with_filesize}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        err_str = str(e).encode("unicode_escape").decode("ascii")
        print(f"FATAL ERROR: {err_str}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
