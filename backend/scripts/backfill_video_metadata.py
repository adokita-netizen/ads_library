"""Backfill video metadata (duration, resolution, file_size) for existing ads.

For ads with video_url but no duration_seconds, downloads video to a
temp file, runs ffprobe, and updates the DB record.

Run from the backend directory:
    cd backend
    python scripts/backfill_video_metadata.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad


def extract_video_metadata(video_path: str) -> dict:
    """Extract video metadata using ffprobe."""
    import json
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        fps = 0.0
        rfr = vs.get("r_frame_rate", "")
        if rfr and "/" in rfr:
            n, d = rfr.split("/", 1)
            try:
                fps = float(n) / float(d) if float(d) != 0 else 0.0
            except (ValueError, ZeroDivisionError):
                pass
        return {
            "duration_seconds": float(data.get("format", {}).get("duration", 0)),
            "resolution_width": int(vs.get("width", 0)),
            "resolution_height": int(vs.get("height", 0)),
            "codec": vs.get("codec_name", ""),
            "file_size_bytes": int(data.get("format", {}).get("size", 0)),
            "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
            "fps": fps,
        }
    except Exception:
        return {}


def _get_session() -> Session:
    """Get a DB session, connecting to vaap_local.db if SQLite fallback is active."""
    if not is_in_memory_mode():
        return SyncSessionLocal()
    db_path = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return sessionmaker(bind=engine)()


BATCH_SIZE = 10
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
TIMEOUT = 60


def main():
    session = _get_session()

    try:
        # Find ads with video but no duration
        ads = (
            session.query(Ad)
            .filter(
                Ad.video_url.isnot(None),
                Ad.video_url != "",
                Ad.duration_seconds.is_(None),
            )
            .all()
        )

        total = len(ads)
        print(f"Found {total} videos without metadata")
        if total == 0:
            return

        # Check local cache first
        cache_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "media_cache", "videos")
        )

        updated = 0
        skipped = 0
        failed = 0

        for i, ad in enumerate(ads):
            label = f"[{i + 1}/{total}] Ad {ad.id}"

            # Check local cache
            local_path = None
            for ext in ("mp4", "webm", "mov"):
                p = os.path.join(cache_dir, f"{ad.id}.{ext}")
                if os.path.exists(p) and os.path.getsize(p) > 1000:
                    local_path = p
                    break

            if not local_path:
                # Download to temp file
                try:
                    import httpx
                    with httpx.Client(
                        timeout=TIMEOUT,
                        follow_redirects=True,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/121.0.0.0 Safari/537.36"
                            ),
                        },
                    ) as client:
                        resp = client.get(ad.video_url)
                        if resp.status_code != 200:
                            print(f"  {label}: HTTP {resp.status_code}, skipping")
                            skipped += 1
                            continue
                        data = resp.content
                        if len(data) > MAX_VIDEO_SIZE:
                            print(f"  {label}: too large ({len(data)} bytes), skipping")
                            skipped += 1
                            continue
                except Exception as e:
                    print(f"  {label}: download failed: {e}")
                    failed += 1
                    continue

                # Write to temp file
                suffix = ".mp4"
                if ".webm" in ad.video_url.lower():
                    suffix = ".webm"
                elif ".mov" in ad.video_url.lower():
                    suffix = ".mov"
                tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                tmp.write(data)
                tmp.close()
                local_path = tmp.name

            # Extract metadata
            video_meta = extract_video_metadata(local_path)

            # Clean up temp file (not cached ones)
            if local_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(local_path)
                except OSError:
                    pass

            if not video_meta:
                print(f"  {label}: ffprobe returned no data")
                failed += 1
                continue

            # Update ad
            if video_meta.get("duration_seconds"):
                ad.duration_seconds = video_meta["duration_seconds"]
            if video_meta.get("resolution_width"):
                ad.resolution_width = video_meta["resolution_width"]
            if video_meta.get("resolution_height"):
                ad.resolution_height = video_meta["resolution_height"]
            if video_meta.get("file_size_bytes"):
                ad.file_size_bytes = video_meta["file_size_bytes"]

            meta = dict(ad.ad_metadata or {})
            meta["video_codec"] = video_meta.get("codec", "")
            meta["video_bitrate"] = video_meta.get("bitrate", 0)
            meta["video_fps"] = video_meta.get("fps", 0)
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            dur = video_meta.get("duration_seconds", 0)
            res_w = video_meta.get("resolution_width", 0)
            res_h = video_meta.get("resolution_height", 0)
            print(f"  {label}: {dur:.1f}s {res_w}x{res_h}")
            updated += 1

            if (i + 1) % BATCH_SIZE == 0:
                session.commit()

        session.commit()

        print()
        print("=" * 50)
        print(f"Total:   {total}")
        print(f"Updated: {updated}")
        print(f"Skipped: {skipped}")
        print(f"Failed:  {failed}")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
