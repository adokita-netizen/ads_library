#!/usr/bin/env python3
"""Batch processor for AWS Rekognition analysis.

Processes all unanalyzed ads in one run:
  1. Image analysis (detect_labels, detect_text, detect_faces, detect_moderation)
  2. Video analysis (label, text, face detection via async API)

Features:
  - Resume capability (skips already processed ads)
  - Cost estimation before running
  - Rate limiting (max 5 calls/sec for images)
  - Progress reporting

Usage:
    python -m scripts.batch_rekognition                 # process all
    python -m scripts.batch_rekognition --images-only   # images only
    python -m scripts.batch_rekognition --videos-only   # videos only
    python -m scripts.batch_rekognition --cost-estimate  # cost estimate only
    python -m scripts.batch_rekognition --limit 50       # limit batch size
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "media_cache")
)

# Pricing
IMAGE_PRICE_PER_CALL = 0.001
IMAGE_CALLS_PER_AD = 4
VIDEO_PRICE_PER_MIN = 0.10
VIDEO_ANALYSES = 3
AVG_VIDEO_DURATION_MIN = 0.5


def _count_pending(session) -> dict:
    """Count ads pending analysis."""
    all_ads = session.query(Ad).all()

    images_pending = 0
    videos_pending = 0

    for ad in all_ads:
        meta = ad.ad_metadata or {}

        # Check image
        if "rekognition" not in meta:
            for subdir in ("images", "thumbnails"):
                path = os.path.join(CACHE_DIR, subdir, f"{ad.id}.jpg")
                if os.path.exists(path):
                    images_pending += 1
                    break

        # Check video
        if "rekognition_video" not in meta:
            for ext in ("mp4", "webm", "mov"):
                path = os.path.join(CACHE_DIR, "videos", f"{ad.id}.{ext}")
                if os.path.exists(path):
                    videos_pending += 1
                    break

    return {"images": images_pending, "videos": videos_pending}


def main():
    parser = argparse.ArgumentParser(description="Batch Rekognition analysis")
    parser.add_argument("--images-only", action="store_true")
    parser.add_argument("--videos-only", action="store_true")
    parser.add_argument("--cost-estimate", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    print("=== Batch AWS Rekognition Processing ===\n")

    session = SyncSessionLocal()
    try:
        counts = _count_pending(session)
    finally:
        session.close()

    img_limit = args.limit if args.limit > 0 else counts["images"]
    vid_limit = args.limit if args.limit > 0 else counts["videos"]

    img_count = min(counts["images"], img_limit) if not args.videos_only else 0
    vid_count = min(counts["videos"], vid_limit) if not args.images_only else 0

    img_cost = img_count * IMAGE_PRICE_PER_CALL * IMAGE_CALLS_PER_AD
    vid_cost = vid_count * AVG_VIDEO_DURATION_MIN * VIDEO_PRICE_PER_MIN * VIDEO_ANALYSES
    total_cost = img_cost + vid_cost

    print(f"Pending analysis:")
    print(f"  Images: {counts['images']} total, {img_count} to process -> ${img_cost:.2f}")
    print(f"  Videos: {counts['videos']} total, {vid_count} to process -> ${vid_cost:.2f}")
    print(f"  TOTAL ESTIMATED COST: ${total_cost:.2f}")
    print()

    if args.cost_estimate:
        return

    if total_cost > 10.0:
        print(f"WARNING: Estimated cost exceeds $10. Use --limit to reduce batch size.")
        print(f"Example: python -m scripts.batch_rekognition --limit 50")
        return

    start = time.time()

    # Process images
    if img_count > 0:
        print("\n--- Phase 1: Image Analysis ---")
        from scripts.rekognition_analyze import analyze_ads
        analyze_ads(limit=img_count)

    # Process videos
    if vid_count > 0:
        print("\n--- Phase 2: Video Analysis ---")
        from scripts.rekognition_video import analyze_videos
        analyze_videos(limit=vid_count)

    elapsed = time.time() - start
    print(f"\n=== Batch Complete in {elapsed:.0f}s ===")
    print(f"  Images processed: {img_count}")
    print(f"  Videos processed: {vid_count}")
    print(f"  Estimated cost:   ${total_cost:.2f}")


if __name__ == "__main__":
    main()
