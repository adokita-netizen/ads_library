#!/usr/bin/env python3
"""Download video files for ads with video_url.

Finds all ads that have a video_url but no cached video file,
downloads them to media_cache/videos/{ad_id}.mp4, and updates
ad_metadata["video_cached"] = True.

Skips files larger than 100MB.

Run from the backend directory:
    cd backend
    python scripts/download_videos.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# ── Config ────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.5
BATCH_SIZE = 10

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


# ── Helpers ───────────────────────────────────────────────────────────

def _find_existing_video(ad_id: int) -> str | None:
    """Check if a cached video file already exists for this ad."""
    for ext in ("mp4", "webm", "mov"):
        path = os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            return path
    return None


def _guess_extension(url: str, content_type: str = "") -> str:
    """Guess video file extension from URL or content-type."""
    url_lower = url.lower()
    if ".webm" in url_lower:
        return "webm"
    if ".mov" in url_lower:
        return "mov"
    if "webm" in content_type:
        return "webm"
    if "quicktime" in content_type:
        return "mov"
    return "mp4"


def download_video(ad_id: int, video_url: str) -> tuple[str, str]:
    """Download a video file.

    Returns (status, detail) where status is one of:
        "ok"        - downloaded successfully
        "too_large" - file exceeds MAX_FILE_SIZE_BYTES
        "exists"    - already cached
        "failed"    - download error
    """
    # Check if already cached
    existing = _find_existing_video(ad_id)
    if existing:
        return "exists", existing

    try:
        # HEAD request to check Content-Length before downloading
        try:
            head_resp = requests.head(
                video_url, timeout=10, allow_redirects=True,
                headers={"User-Agent": USER_AGENT}
            )
            content_length = int(head_resp.headers.get("Content-Length", 0))
            if content_length > MAX_FILE_SIZE_BYTES:
                return "too_large", f"{content_length / 1024 / 1024:.1f}MB"
        except Exception:
            # HEAD failed, proceed with GET anyway
            content_length = 0

        # Stream download
        resp = requests.get(
            video_url,
            timeout=REQUEST_TIMEOUT,
            stream=True,
            headers={"User-Agent": USER_AGENT},
        )

        if resp.status_code == 403:
            return "failed", "HTTP 403 (CDN expired)"
        if resp.status_code != 200:
            return "failed", f"HTTP {resp.status_code}"

        content_type = resp.headers.get("Content-Type", "")
        ext = _guess_extension(video_url, content_type)
        dest_path = os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")

        # Download with size check
        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                downloaded += len(chunk)
                if downloaded > MAX_FILE_SIZE_BYTES:
                    f.close()
                    os.remove(dest_path)
                    return "too_large", f"{downloaded / 1024 / 1024:.1f}MB+"

                f.write(chunk)

        # Verify minimum file size
        file_size = os.path.getsize(dest_path)
        if file_size < 1000:
            os.remove(dest_path)
            return "failed", f"too small ({file_size} bytes)"

        return "ok", dest_path

    except requests.exceptions.Timeout:
        return "failed", "timeout"
    except Exception as e:
        return "failed", str(e)[:100]


# ── Main ──────────────────────────────────────────────────────────────

def main():
    os.makedirs(VIDEO_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        # Find ads with video_url but no cached video
        ads_with_video = session.query(Ad).filter(
            Ad.video_url.isnot(None),
            Ad.video_url != "",
        ).order_by(Ad.id).all()

        total = len(ads_with_video)
        print("=" * 60)
        print("VIDEO DOWNLOAD")
        print("=" * 60)
        print(f"Ads with video_url: {total}")

        # Filter to only those without cached file
        to_download = []
        already_cached = 0
        for ad in ads_with_video:
            existing = _find_existing_video(ad.id)
            if existing:
                already_cached += 1
                # Ensure metadata is set
                meta = dict(ad.ad_metadata or {})
                if not meta.get("video_cached"):
                    meta["video_cached"] = True
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")
            else:
                to_download.append(ad)

        print(f"Already cached: {already_cached}")
        print(f"To download: {len(to_download)}")
        print()

        if not to_download:
            print("No videos to download.")
            session.commit()
            return

        stats = {"ok": 0, "too_large": 0, "failed": 0}

        for i, ad in enumerate(to_download):
            label = f"[{i+1}/{len(to_download)}] Ad {ad.id}"

            status, detail = download_video(ad.id, ad.video_url)
            stats[status] = stats.get(status, 0) + 1

            if status == "ok":
                print(f"  {label}: OK")
                meta = dict(ad.ad_metadata or {})
                meta["video_cached"] = True
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

                # Update file_size_bytes if we have the file
                try:
                    file_size = os.path.getsize(detail)
                    ad.file_size_bytes = file_size
                except Exception:
                    pass

            elif status == "too_large":
                print(f"  {label}: SKIPPED (too large: {detail})")
            elif status == "failed":
                print(f"  {label}: FAILED ({detail})")
            elif status == "exists":
                print(f"  {label}: EXISTS (already cached)")
                stats["ok"] = stats.get("ok", 0) + 1

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"  -- Committed batch {i + 1}/{len(to_download)}")

            time.sleep(REQUEST_DELAY)

        session.commit()

        # Summary
        print()
        print("=" * 60)
        print("VIDEO DOWNLOAD SUMMARY")
        print("=" * 60)
        print(f"Downloaded:   {stats.get('ok', 0)}")
        print(f"Skipped (>100MB): {stats.get('too_large', 0)}")
        print(f"Failed:       {stats.get('failed', 0)}")
        print(f"Total cached: {already_cached + stats.get('ok', 0)}")
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
