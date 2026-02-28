#!/usr/bin/env python3
"""Analyze cached videos with AWS Rekognition Video.

Uses asynchronous Rekognition Video APIs:
  - start_label_detection()  -> objects throughout video
  - start_text_detection()   -> text overlays at each timestamp
  - start_face_detection()   -> faces and emotions over time

Results stored in ad_metadata["rekognition_video"].

Usage:
    python -m scripts.rekognition_video                 # analyze all unprocessed
    python -m scripts.rekognition_video --ad-id 123     # analyze specific ad
    python -m scripts.rekognition_video --limit 10      # limit batch size
    python -m scripts.rekognition_video --cost-estimate  # show cost estimate only

Note: Videos must be uploaded to S3 first (uses upload_to_s3.py or uploads temporarily).
"""

import argparse
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "media_cache")
)

# Rekognition Video pricing (per minute of video)
PRICE_PER_MINUTE = 0.10  # $0.10 per minute
POLL_INTERVAL = 10  # seconds between status checks
MAX_WAIT = 600  # max seconds to wait for a job


def _get_clients():
    """Get boto3 Rekognition and S3 clients."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    region = settings.aws_region
    bucket = settings.aws_s3_bucket
    rek = boto3.client("rekognition", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    return rek, s3, bucket


def _find_video_path(ad_id: int) -> str | None:
    """Find cached video file."""
    for ext in ("mp4", "webm", "mov"):
        path = os.path.join(CACHE_DIR, "videos", f"{ad_id}.{ext}")
        if os.path.exists(path):
            return path
    return None


def _upload_video_to_s3(s3_client, bucket: str, video_path: str, ad_id: int) -> str:
    """Upload video to S3 for Rekognition processing."""
    s3_key = f"videos/{ad_id}{os.path.splitext(video_path)[1]}"
    s3_client.upload_file(video_path, bucket, s3_key)
    return s3_key


def _wait_for_job(rek_client, job_id: str, get_fn_name: str) -> dict | None:
    """Poll for Rekognition Video job completion."""
    get_fn = getattr(rek_client, get_fn_name)
    elapsed = 0
    while elapsed < MAX_WAIT:
        resp = get_fn(JobId=job_id)
        status = resp.get("JobStatus")
        if status == "SUCCEEDED":
            return resp
        elif status == "FAILED":
            print(f"    Job {job_id} FAILED: {resp.get('StatusMessage', 'unknown')}")
            return None
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    print(f"    Job {job_id} timed out after {MAX_WAIT}s")
    return None


def _analyze_video(rek_client, bucket: str, s3_key: str) -> dict:
    """Run Rekognition Video analyses (label, text, face detection)."""
    video_ref = {"S3Object": {"Bucket": bucket, "Name": s3_key}}
    result = {}

    # 1. Label detection
    try:
        resp = rek_client.start_label_detection(Video=video_ref, MinConfidence=70.0)
        job_id = resp["JobId"]
        print(f"    Label detection started: {job_id}")
        job_result = _wait_for_job(rek_client, job_id, "get_label_detection")
        if job_result:
            # Aggregate labels across all timestamps
            label_map = {}
            for lbl in job_result.get("Labels", []):
                name = lbl["Label"]["Name"]
                conf = lbl["Label"]["Confidence"]
                ts = lbl.get("Timestamp", 0) / 1000.0  # ms to seconds
                if name not in label_map or conf > label_map[name]["confidence"]:
                    label_map[name] = {
                        "name": name,
                        "confidence": round(conf, 1),
                        "first_seen_sec": round(ts, 1),
                    }
            result["labels"] = sorted(label_map.values(), key=lambda x: -x["confidence"])[:30]
        else:
            result["labels"] = []
    except Exception as e:
        result["labels"] = []
        result["labels_error"] = str(e)

    # 2. Text detection
    try:
        resp = rek_client.start_text_detection(Video=video_ref)
        job_id = resp["JobId"]
        print(f"    Text detection started: {job_id}")
        job_result = _wait_for_job(rek_client, job_id, "get_text_detection")
        if job_result:
            text_by_time = []
            seen_texts = set()
            for det in job_result.get("TextDetections", []):
                td = det["TextDetection"]
                if td["Type"] != "LINE" or td["Confidence"] < 70.0:
                    continue
                text = td["DetectedText"]
                ts = det.get("Timestamp", 0) / 1000.0
                if text not in seen_texts:
                    seen_texts.add(text)
                    text_by_time.append({
                        "text": text,
                        "timestamp_sec": round(ts, 1),
                        "confidence": round(td["Confidence"], 1),
                    })
            result["text_detections"] = text_by_time[:30]
        else:
            result["text_detections"] = []
    except Exception as e:
        result["text_detections"] = []
        result["text_error"] = str(e)

    # 3. Face detection
    try:
        resp = rek_client.start_face_detection(
            Video=video_ref,
            FaceAttributes="ALL",
        )
        job_id = resp["JobId"]
        print(f"    Face detection started: {job_id}")
        job_result = _wait_for_job(rek_client, job_id, "get_face_detection")
        if job_result:
            key_moments = []
            for det in job_result.get("Faces", []):
                face = det["Face"]
                ts = det.get("Timestamp", 0) / 1000.0
                emotions = {}
                for emo in face.get("Emotions", []):
                    if emo["Confidence"] > 50.0:
                        emotions[emo["Type"].lower()] = round(emo["Confidence"], 1)
                if emotions:
                    key_moments.append({
                        "timestamp_sec": round(ts, 1),
                        "emotions": emotions,
                        "smile": face.get("Smile", {}).get("Value", False),
                    })
            # Keep only distinct moments (>2s apart)
            filtered = []
            last_ts = -3
            for m in key_moments:
                if m["timestamp_sec"] - last_ts >= 2:
                    filtered.append(m)
                    last_ts = m["timestamp_sec"]
            result["face_moments"] = filtered[:20]
            result["total_face_detections"] = len(job_result.get("Faces", []))
        else:
            result["face_moments"] = []
    except Exception as e:
        result["face_moments"] = []
        result["faces_error"] = str(e)

    return result


def analyze_videos(ad_id: int | None = None, limit: int = 0, cost_only: bool = False) -> dict:
    """Analyze videos with Rekognition Video."""
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
                if "rekognition_video" in meta:
                    continue
                if _find_video_path(ad.id):
                    ads.append(ad)

        if limit > 0:
            ads = ads[:limit]

        # Estimate duration (assume avg 30s per video)
        avg_duration_min = 0.5
        est_cost = len(ads) * avg_duration_min * PRICE_PER_MINUTE * 3  # 3 analyses
        print(f"Videos to analyze: {len(ads)}")
        print(f"Estimated cost: ${est_cost:.2f} (assuming ~30s avg video, 3 analyses each)")

        if cost_only or len(ads) == 0:
            return {"total": len(ads), "estimated_cost": est_cost}

        rek, s3, bucket = _get_clients()
        if not bucket:
            print("ERROR: AWS_S3_BUCKET not set")
            return {"error": "no_bucket"}

        processed = 0
        errors = 0

        for i, ad in enumerate(ads, 1):
            video_path = _find_video_path(ad.id)
            if not video_path:
                continue

            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            print(f"\n[{i}/{len(ads)}] Ad {ad.id}: {os.path.basename(video_path)} ({file_size_mb:.1f}MB)")
            sys.stdout.flush()

            try:
                # Check if already on S3
                s3_key = ad.s3_key
                if not s3_key:
                    print(f"  Uploading to S3...")
                    s3_key = _upload_video_to_s3(s3, bucket, video_path, ad.id)

                analysis = _analyze_video(rek, bucket, s3_key)

                meta = ad.ad_metadata or {}
                meta["rekognition_video"] = analysis
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                session.commit()
                processed += 1

                label_count = len(analysis.get("labels", []))
                text_count = len(analysis.get("text_detections", []))
                face_count = len(analysis.get("face_moments", []))
                print(f"  Done: {label_count} labels, {text_count} text, {face_count} face moments")

            except Exception as e:
                print(f"  ERROR: {e}")
                session.rollback()
                errors += 1

        summary = {"processed": processed, "errors": errors, "total": len(ads)}
        print(f"\n=== Summary ===")
        print(f"  Processed: {processed}")
        print(f"  Errors:    {errors}")
        return summary

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Analyze videos with AWS Rekognition Video")
    parser.add_argument("--ad-id", type=int, help="Analyze specific ad")
    parser.add_argument("--limit", type=int, default=0, help="Max ads to process")
    parser.add_argument("--cost-estimate", action="store_true", help="Show cost estimate only")
    args = parser.parse_args()

    print("=== AWS Rekognition Video Analysis ===")
    sys.stdout.flush()
    analyze_videos(ad_id=args.ad_id, limit=args.limit, cost_only=args.cost_estimate)


if __name__ == "__main__":
    main()
