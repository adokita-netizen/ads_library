#!/usr/bin/env python3
"""Extract key frames from cached video files.

For each cached video in media_cache/videos/:
  - Extract 3 frames: at 0s, middle point, and 2/3 point
  - Save to media_cache/frames/{ad_id}_frame_{0,1,2}.jpg
  - If thumbnail is missing, use frame_0 as thumbnail
  - Update ad_metadata["frames_extracted"] = True

Uses ffmpeg (subprocess) if available, otherwise tries OpenCV (cv2).
If neither is available, prints a warning and skips.

Run from the backend directory:
    cd backend
    python scripts/extract_video_frames.py
"""

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
FRAMES_DIR = os.path.join(CACHE_DIR, "frames")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")

VIDEO_EXTENSIONS = ("mp4", "webm", "mov")


# ── Tool Detection ───────────────────────────────────────────────────

def detect_ffmpeg() -> str | None:
    """Check if ffmpeg is available. Returns path or None."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # Check common Windows locations
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
    ]
    for p in common_paths:
        if os.path.exists(p):
            return p

    return None


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


def get_video_duration_ffprobe(video_path: str, ffprobe_path: str) -> float | None:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def get_video_duration_cv2(video_path: str) -> float | None:
    """Get video duration using OpenCV."""
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0 and frame_count > 0:
            return frame_count / fps
    except Exception:
        pass
    return None


# ── Frame Extraction ─────────────────────────────────────────────────

def extract_frames_ffmpeg(
    video_path: str, ad_id: int, duration: float, ffmpeg_path: str
) -> list[str]:
    """Extract 3 frames using ffmpeg. Returns list of output paths."""
    timestamps = _compute_timestamps(duration)
    output_paths = []

    for i, ts in enumerate(timestamps):
        output_path = os.path.join(FRAMES_DIR, f"{ad_id}_frame_{i}.jpg")

        try:
            result = subprocess.run(
                [
                    ffmpeg_path,
                    "-y",               # overwrite output
                    "-ss", str(ts),     # seek to timestamp
                    "-i", video_path,   # input file
                    "-vframes", "1",    # extract 1 frame
                    "-q:v", "2",        # quality (2 = high)
                    output_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 100:
                    output_paths.append(output_path)
                else:
                    os.remove(output_path)
            else:
                if os.path.exists(output_path):
                    os.remove(output_path)

        except subprocess.TimeoutExpired:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            if os.path.exists(output_path):
                os.remove(output_path)

    return output_paths


def extract_frames_cv2(video_path: str, ad_id: int, duration: float) -> list[str]:
    """Extract 3 frames using OpenCV. Returns list of output paths."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    timestamps = _compute_timestamps(duration)
    output_paths = []

    for i, ts in enumerate(timestamps):
        output_path = os.path.join(FRAMES_DIR, f"{ad_id}_frame_{i}.jpg")

        frame_number = int(ts * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        ret, frame = cap.read()
        if ret:
            cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                output_paths.append(output_path)
            elif os.path.exists(output_path):
                os.remove(output_path)

    cap.release()
    return output_paths


def _compute_timestamps(duration: float) -> list[float]:
    """Compute 3 frame timestamps: 0s, middle, 2/3 point."""
    if duration <= 0:
        return [0.0]

    # Small safety margin to avoid seeking past end
    safe_duration = max(duration - 0.1, 0.1)

    timestamps = [
        0.0,                           # start
        safe_duration / 2.0,           # middle
        safe_duration * 2.0 / 3.0,     # 2/3 point
    ]

    # Deduplicate for very short videos
    seen = set()
    unique = []
    for ts in timestamps:
        rounded = round(ts, 1)
        if rounded not in seen:
            seen.add(rounded)
            unique.append(ts)

    return unique


# ── Main ──────────────────────────────────────────────────────────────

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


def has_existing_frames(ad_id: int) -> bool:
    """Check if frames have already been extracted for this ad."""
    frame_0 = os.path.join(FRAMES_DIR, f"{ad_id}_frame_0.jpg")
    return os.path.exists(frame_0)


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)

    # Detect available tools
    ffmpeg_path = detect_ffmpeg()
    ffprobe_path = detect_ffprobe()
    has_cv2 = detect_cv2()

    print("=" * 60)
    print("VIDEO FRAME EXTRACTION")
    print("=" * 60)
    print(f"ffmpeg:  {'YES (' + ffmpeg_path + ')' if ffmpeg_path else 'NOT FOUND'}")
    print(f"ffprobe: {'YES (' + ffprobe_path + ')' if ffprobe_path else 'NOT FOUND'}")
    print(f"OpenCV:  {'YES' if has_cv2 else 'NOT FOUND'}")

    if not ffmpeg_path and not has_cv2:
        print()
        print("WARNING: Neither ffmpeg nor OpenCV (cv2) is available.")
        print("Install ffmpeg or opencv-python to enable frame extraction.")
        print("Skipping frame extraction.")
        return

    use_ffmpeg = bool(ffmpeg_path)
    print(f"Using:   {'ffmpeg' if use_ffmpeg else 'OpenCV (cv2)'}")
    print()

    # Find cached videos
    cached_videos = find_cached_videos()
    print(f"Cached videos found: {len(cached_videos)}")

    if not cached_videos:
        print("No cached videos to process.")
        return

    # Filter to videos needing frame extraction
    to_process = [(aid, path) for aid, path in cached_videos
                   if not has_existing_frames(aid)]
    already_done = len(cached_videos) - len(to_process)
    print(f"Already extracted: {already_done}")
    print(f"To process: {len(to_process)}")
    print()

    if not to_process:
        print("All frames already extracted.")
        return

    session = SyncSessionLocal()
    stats = {"ok": 0, "failed": 0, "thumb_set": 0}

    try:
        for i, (ad_id, video_path) in enumerate(to_process):
            label = f"[{i+1}/{len(to_process)}] Ad {ad_id}"

            # Get duration
            duration = None
            if ffprobe_path:
                duration = get_video_duration_ffprobe(video_path, ffprobe_path)
            if duration is None and has_cv2:
                duration = get_video_duration_cv2(video_path)
            if duration is None:
                duration = 10.0  # fallback default

            # Extract frames
            if use_ffmpeg:
                frame_paths = extract_frames_ffmpeg(
                    video_path, ad_id, duration, ffmpeg_path
                )
            else:
                frame_paths = extract_frames_cv2(video_path, ad_id, duration)

            if frame_paths:
                print(f"  {label}: {len(frame_paths)} frames extracted (duration={duration:.1f}s)")
                stats["ok"] += 1

                # Update ad metadata
                ad = session.query(Ad).filter(Ad.id == ad_id).first()
                if ad:
                    meta = dict(ad.ad_metadata or {})
                    meta["frames_extracted"] = True
                    meta["frame_count"] = len(frame_paths)
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")

                    # If thumbnail is missing, use frame_0
                    frame_0_path = os.path.join(FRAMES_DIR, f"{ad_id}_frame_0.jpg")
                    if (not ad.thumbnail_s3_key) and os.path.exists(frame_0_path):
                        thumb_dest = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
                        shutil.copy2(frame_0_path, thumb_dest)
                        ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                        stats["thumb_set"] += 1
                        print(f"    -> Set frame_0 as thumbnail")
            else:
                print(f"  {label}: FAILED (no frames extracted)")
                stats["failed"] += 1

            # Batch commit
            if (i + 1) % 10 == 0:
                session.commit()

        session.commit()

        # Summary
        print()
        print("=" * 60)
        print("FRAME EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Videos processed:     {len(to_process)}")
        print(f"Frames extracted OK:  {stats['ok']}")
        print(f"Frames failed:        {stats['failed']}")
        print(f"Thumbnails set:       {stats['thumb_set']}")
        print(f"Already done:         {already_done}")
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
