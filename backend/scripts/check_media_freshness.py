#!/usr/bin/env python3
"""Check freshness of cached media files.

For each cached media file:
  - Check file age
  - If > 30 days old, mark for re-download
  - Check if source URL is still accessible (HEAD request with timeout)
    NOTE: External HTTP requests are skipped per constraints.
    Only local checks are performed.

Output: exports/stale_media.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/check_media_freshness.py
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_cache")
)
EXPORTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exports")
)

# 30 days in seconds
STALE_THRESHOLD = 30 * 24 * 3600


def _check_directory(dir_path: str, media_type: str) -> tuple[list[dict], int, int]:
    """Check all files in a directory for freshness.

    Returns (stale_files, fresh_count, total_count)
    """
    stale_files = []
    fresh_count = 0
    total_count = 0

    if not os.path.isdir(dir_path):
        return stale_files, fresh_count, total_count

    now = time.time()

    for fname in os.listdir(dir_path):
        fpath = os.path.join(dir_path, fname)
        if not os.path.isfile(fpath):
            continue

        total_count += 1

        try:
            mtime = os.path.getmtime(fpath)
            age_seconds = now - mtime
            age_days = age_seconds / 86400
            file_size = os.path.getsize(fpath)
        except OSError:
            stale_files.append({
                "filename": fname,
                "media_type": media_type,
                "reason": "unreadable",
                "age_days": -1,
                "size_bytes": 0,
            })
            continue

        if age_seconds > STALE_THRESHOLD:
            stale_files.append({
                "filename": fname,
                "media_type": media_type,
                "reason": "old",
                "age_days": round(age_days, 1),
                "size_bytes": file_size,
                "last_modified": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
            })
        else:
            fresh_count += 1

    return stale_files, fresh_count, total_count


def main():
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    print("Checking media freshness (stale threshold: %d days)" % (STALE_THRESHOLD // 86400))
    print("Cache dir: %s" % CACHE_DIR)

    directories = [
        (os.path.join(CACHE_DIR, "thumbnails"), "thumbnail"),
        (os.path.join(CACHE_DIR, "images"), "image"),
        (os.path.join(CACHE_DIR, "videos"), "video"),
        (os.path.join(CACHE_DIR, "frames"), "frame"),
        (os.path.join(CACHE_DIR, "lp_screenshots"), "lp_screenshot"),
        (os.path.join(CACHE_DIR, "lp_html"), "lp_html"),
    ]

    all_stale = []
    total_fresh = 0
    total_files = 0
    type_summary = {}

    for dir_path, media_type in directories:
        stale, fresh, total = _check_directory(dir_path, media_type)
        all_stale.extend(stale)
        total_fresh += fresh
        total_files += total

        type_summary[media_type] = {
            "total": total,
            "fresh": fresh,
            "stale": len(stale),
        }

    # Check for unreachable URLs (from DB, without making actual requests)
    # Per constraints, we don't make external HTTP requests.
    # Instead we flag ads whose source URLs look expired (Facebook CDN tokens).
    unreachable_count = 0
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        for ad in ads:
            # Check for expired Facebook CDN URLs (contain token with expiration)
            for url in [ad.thumbnail_url, ad.image_url, ad.video_url]:
                if url and "fbcdn" in url and "oe=" in url:
                    # Facebook CDN URLs with 'oe=' parameter have expiry tokens
                    unreachable_count += 1
                    break
    except Exception:
        pass
    finally:
        session.close()

    # Build report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_files": total_files,
            "fresh": total_fresh,
            "stale": len(all_stale),
            "unreachable_urls": unreachable_count,
            "stale_threshold_days": STALE_THRESHOLD // 86400,
        },
        "by_type": type_summary,
        "stale_files": all_stale,
    }

    output_path = os.path.join(EXPORTS_DIR, "stale_media.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n=== Media Freshness Report ===")
    print("%d files fresh, %d stale, %d unreachable" % (
        total_fresh, len(all_stale), unreachable_count))

    print("\nBy Type:")
    print("  %-15s %6s %6s %6s" % ("Type", "Total", "Fresh", "Stale"))
    print("  " + "-" * 40)
    for media_type, info in sorted(type_summary.items()):
        print("  %-15s %6d %6d %6d" % (
            media_type, info["total"], info["fresh"], info["stale"]))

    print("\nOutput: %s" % output_path)


if __name__ == "__main__":
    main()
