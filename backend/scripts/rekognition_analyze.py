#!/usr/bin/env python3
"""Analyze cached images/thumbnails with AWS Rekognition.

For each cached thumbnail/image, calls:
  - detect_labels()       -> objects in image (product, person, food, etc.)
  - detect_text()         -> OCR text overlays on creative
  - detect_faces()        -> face count, emotions
  - detect_moderation_labels() -> content safety check

Results stored in ad_metadata["rekognition"].

Usage:
    python -m scripts.rekognition_analyze                  # analyze all unprocessed
    python -m scripts.rekognition_analyze --ad-id 123      # analyze specific ad
    python -m scripts.rekognition_analyze --limit 50       # limit batch size
    python -m scripts.rekognition_analyze --cost-estimate   # show cost estimate only
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "media_cache")
)

# Rekognition pricing (us-east-1, per image)
PRICE_PER_IMAGE = 0.001  # $0.001 per image for detect_labels
CALLS_PER_IMAGE = 4  # labels + text + faces + moderation


def _get_rekognition_client():
    """Get boto3 Rekognition client."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    return boto3.client("rekognition", region_name=settings.aws_region)


def _find_image_path(ad_id: int) -> str | None:
    """Find cached image for an ad. Prefers images/ over thumbnails/."""
    for subdir in ("images", "thumbnails"):
        path = os.path.join(CACHE_DIR, subdir, f"{ad_id}.jpg")
        if os.path.exists(path):
            return path
    return None


def _analyze_image(client, image_bytes: bytes) -> dict:
    """Run all 4 Rekognition analyses on an image."""
    result = {}

    # 1. Detect labels (objects, scenes)
    try:
        resp = client.detect_labels(
            Image={"Bytes": image_bytes},
            MaxLabels=20,
            MinConfidence=70.0,
        )
        result["labels"] = [
            {"name": lbl["Name"], "confidence": round(lbl["Confidence"], 1)}
            for lbl in resp.get("Labels", [])
        ]
    except Exception as e:
        result["labels"] = []
        result["labels_error"] = str(e)

    # 2. Detect text (OCR)
    try:
        resp = client.detect_text(Image={"Bytes": image_bytes})
        # Only keep LINE detections (not WORD) for cleaner output
        result["text_detections"] = [
            det["DetectedText"]
            for det in resp.get("TextDetections", [])
            if det["Type"] == "LINE" and det["Confidence"] > 70.0
        ]
    except Exception as e:
        result["text_detections"] = []
        result["text_error"] = str(e)

    # 3. Detect faces
    try:
        resp = client.detect_faces(
            Image={"Bytes": image_bytes},
            Attributes=["ALL"],
        )
        faces = []
        for face in resp.get("FaceDetails", []):
            emotions = {}
            for emo in face.get("Emotions", []):
                if emo["Confidence"] > 50.0:
                    emotions[emo["Type"].lower()] = round(emo["Confidence"], 1)
            age = face.get("AgeRange", {})
            faces.append({
                "emotions": emotions,
                "age_range": [age.get("Low", 0), age.get("High", 0)],
                "gender": face.get("Gender", {}).get("Value", "Unknown"),
                "smile": face.get("Smile", {}).get("Value", False),
            })
        result["faces"] = faces
    except Exception as e:
        result["faces"] = []
        result["faces_error"] = str(e)

    # 4. Content moderation
    try:
        resp = client.detect_moderation_labels(
            Image={"Bytes": image_bytes},
            MinConfidence=70.0,
        )
        result["moderation"] = [
            {"name": lbl["Name"], "confidence": round(lbl["Confidence"], 1)}
            for lbl in resp.get("ModerationLabels", [])
        ]
    except Exception as e:
        result["moderation"] = []
        result["moderation_error"] = str(e)

    return result


def analyze_ads(ad_id: int | None = None, limit: int = 0, cost_only: bool = False) -> dict:
    """Analyze ads with Rekognition.

    Args:
        ad_id: Specific ad to analyze. None = all unprocessed.
        limit: Max ads to process. 0 = unlimited.
        cost_only: Only show cost estimate.
    """
    session = SyncSessionLocal()
    try:
        if ad_id:
            ads = [session.query(Ad).filter(Ad.id == ad_id).first()]
            ads = [a for a in ads if a]
        else:
            all_ads = session.query(Ad).all()
            ads = []
            for ad in all_ads:
                meta = ad.ad_metadata or {}
                if "rekognition" in meta:
                    continue  # already analyzed
                if _find_image_path(ad.id):
                    ads.append(ad)

        if limit > 0:
            ads = ads[:limit]

        print(f"Ads to analyze: {len(ads)}")
        est_cost = len(ads) * PRICE_PER_IMAGE * CALLS_PER_IMAGE
        print(f"Estimated cost: ${est_cost:.2f} ({len(ads)} images x {CALLS_PER_IMAGE} API calls)")

        if cost_only or len(ads) == 0:
            return {"total": len(ads), "estimated_cost": est_cost}

        client = _get_rekognition_client()
        processed = 0
        errors = 0

        for i, ad in enumerate(ads, 1):
            img_path = _find_image_path(ad.id)
            if not img_path:
                continue

            try:
                with open(img_path, "rb") as f:
                    image_bytes = f.read()

                # Rekognition max image size: 5MB
                if len(image_bytes) > 5 * 1024 * 1024:
                    print(f"  [{i}/{len(ads)}] Ad {ad.id}: image too large ({len(image_bytes)/1024/1024:.1f}MB), skipping")
                    continue

                analysis = _analyze_image(client, image_bytes)

                # Store in ad_metadata
                meta = ad.ad_metadata or {}
                meta["rekognition"] = analysis
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                session.commit()

                processed += 1
                if i % 10 == 0 or i == len(ads):
                    labels_count = len(analysis.get("labels", []))
                    text_count = len(analysis.get("text_detections", []))
                    face_count = len(analysis.get("faces", []))
                    print(f"  [{i}/{len(ads)}] Ad {ad.id}: {labels_count} labels, "
                          f"{text_count} text, {face_count} faces")
                    sys.stdout.flush()

                # Rate limit: max 5 calls/sec -> 4 calls per image -> 0.8s sleep
                time.sleep(0.8)

            except Exception as e:
                print(f"  [{i}/{len(ads)}] Ad {ad.id}: ERROR - {e}")
                session.rollback()
                errors += 1
                time.sleep(1)

        summary = {"processed": processed, "errors": errors, "total": len(ads)}
        print(f"\n=== Summary ===")
        print(f"  Processed: {processed}")
        print(f"  Errors:    {errors}")
        print(f"  Cost:      ~${processed * PRICE_PER_IMAGE * CALLS_PER_IMAGE:.2f}")
        return summary

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Analyze images with AWS Rekognition")
    parser.add_argument("--ad-id", type=int, help="Analyze specific ad")
    parser.add_argument("--limit", type=int, default=0, help="Max ads to process")
    parser.add_argument("--cost-estimate", action="store_true", help="Show cost estimate only")
    args = parser.parse_args()

    print("=== AWS Rekognition Image Analysis ===")
    sys.stdout.flush()
    analyze_ads(ad_id=args.ad_id, limit=args.limit, cost_only=args.cost_estimate)


if __name__ == "__main__":
    main()
