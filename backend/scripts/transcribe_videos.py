#!/usr/bin/env python3
"""Transcribe video ad audio using AWS Transcribe.

For each cached video:
  1. Upload to S3 (if not already there)
  2. Start transcription job (ja-JP)
  3. Poll for completion
  4. Download and parse transcript
  5. Store in ad_metadata["transcript"]

Usage:
    python -m scripts.transcribe_videos                  # all unprocessed
    python -m scripts.transcribe_videos --ad-id 123      # specific ad
    python -m scripts.transcribe_videos --limit 20       # limit batch
    python -m scripts.transcribe_videos --cost-estimate   # cost preview
"""

import argparse
import json
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

# AWS Transcribe pricing
PRICE_PER_SECOND = 0.00040  # $0.024/min = $0.0004/sec
POLL_INTERVAL = 15  # seconds
MAX_WAIT = 600  # 10 minutes max per job


def _get_clients():
    """Get boto3 clients."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    region = settings.aws_region
    bucket = settings.aws_s3_bucket
    transcribe = boto3.client("transcribe", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    return transcribe, s3, bucket, region


def _find_video_path(ad_id: int) -> str | None:
    """Find cached video file."""
    for ext in ("mp4", "webm", "mov"):
        path = os.path.join(CACHE_DIR, "videos", f"{ad_id}.{ext}")
        if os.path.exists(path):
            return path
    return None


def _ensure_on_s3(s3_client, bucket: str, video_path: str, ad_id: int) -> str:
    """Ensure video is on S3 for Transcribe."""
    s3_key = f"videos/{ad_id}{os.path.splitext(video_path)[1]}"
    try:
        s3_client.head_object(Bucket=bucket, Key=s3_key)
    except Exception:
        s3_client.upload_file(video_path, bucket, s3_key)
    return s3_key


def _transcribe_video(transcribe_client, s3_uri: str, job_name: str) -> dict | None:
    """Start and wait for transcription job."""
    try:
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": s3_uri},
            MediaFormat="mp4",
            LanguageCode="ja-JP",
            Settings={
                "ShowSpeakerLabels": False,
            },
        )
    except transcribe_client.exceptions.ConflictException:
        print(f"    Job {job_name} already exists, checking status...")

    # Poll for completion
    elapsed = 0
    while elapsed < MAX_WAIT:
        resp = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        status = resp["TranscriptionJob"]["TranscriptionJobStatus"]

        if status == "COMPLETED":
            transcript_uri = resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            return _download_transcript(transcript_uri)
        elif status == "FAILED":
            reason = resp["TranscriptionJob"].get("FailureReason", "unknown")
            print(f"    Transcription FAILED: {reason}")
            return None

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    print(f"    Transcription timed out after {MAX_WAIT}s")
    return None


def _download_transcript(uri: str) -> dict | None:
    """Download and parse transcript JSON from the URI."""
    import httpx
    try:
        resp = httpx.get(uri, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", {})
        transcripts = results.get("transcripts", [])
        full_text = transcripts[0]["transcript"] if transcripts else ""

        # Parse segments from items
        segments = []
        current_segment = {"start": 0.0, "end": 0.0, "text": ""}
        for item in results.get("items", []):
            if item["type"] == "pronunciation":
                start = float(item.get("start_time", 0))
                end = float(item.get("end_time", 0))
                word = item["alternatives"][0]["content"]
                confidence = float(item["alternatives"][0].get("confidence", 0))

                if not current_segment["text"]:
                    current_segment["start"] = start
                current_segment["end"] = end
                current_segment["text"] += word

                # Split segments at ~5s intervals
                if end - current_segment["start"] > 5.0:
                    segments.append({
                        "start": round(current_segment["start"], 2),
                        "end": round(end, 2),
                        "text": current_segment["text"].strip(),
                    })
                    current_segment = {"start": 0.0, "end": 0.0, "text": ""}

            elif item["type"] == "punctuation":
                current_segment["text"] += item["alternatives"][0]["content"]

        # Flush last segment
        if current_segment["text"].strip():
            segments.append({
                "start": round(current_segment["start"], 2),
                "end": round(current_segment["end"], 2),
                "text": current_segment["text"].strip(),
            })

        # Overall confidence
        confidences = [
            float(item["alternatives"][0].get("confidence", 0))
            for item in results.get("items", [])
            if item["type"] == "pronunciation" and item.get("alternatives")
        ]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "full_text": full_text,
            "segments": segments,
            "language": "ja-JP",
            "confidence": round(avg_confidence, 3),
        }

    except Exception as e:
        print(f"    Failed to download transcript: {e}")
        return None


def transcribe_ads(ad_id: int | None = None, limit: int = 0, cost_only: bool = False) -> dict:
    """Transcribe video ads."""
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
                if "transcript" in meta:
                    continue
                if _find_video_path(ad.id):
                    ads.append(ad)

        if limit > 0:
            ads = ads[:limit]

        # Cost estimate (assume avg 30s per video)
        est_cost = len(ads) * 30 * PRICE_PER_SECOND
        print(f"Videos to transcribe: {len(ads)}")
        print(f"Estimated cost: ${est_cost:.2f} (assuming ~30s avg)")

        if cost_only or len(ads) == 0:
            return {"total": len(ads), "estimated_cost": est_cost}

        transcribe, s3, bucket, region = _get_clients()
        if not bucket:
            print("ERROR: AWS_S3_BUCKET not set")
            return {"error": "no_bucket"}

        processed = 0
        errors = 0

        for i, ad in enumerate(ads, 1):
            video_path = _find_video_path(ad.id)
            if not video_path:
                continue

            print(f"\n[{i}/{len(ads)}] Ad {ad.id}: {os.path.basename(video_path)}")
            sys.stdout.flush()

            try:
                # Ensure on S3
                s3_key = _ensure_on_s3(s3, bucket, video_path, ad.id)
                s3_uri = f"s3://{bucket}/{s3_key}"

                # Start transcription
                import uuid
                job_name = f"vaap-ad-{ad.id}-{uuid.uuid4().hex[:8]}"
                print(f"  Starting transcription job: {job_name}")

                transcript = _transcribe_video(transcribe, s3_uri, job_name)
                if transcript:
                    meta = ad.ad_metadata or {}
                    meta["transcript"] = transcript
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")
                    session.commit()
                    processed += 1

                    text_preview = transcript["full_text"][:80]
                    print(f"  Done: confidence={transcript['confidence']:.2f}, "
                          f"segments={len(transcript['segments'])}")
                    print(f"  Text: {text_preview}...")
                else:
                    errors += 1

                # Clean up job
                try:
                    transcribe.delete_transcription_job(TranscriptionJobName=job_name)
                except Exception:
                    pass

            except Exception as e:
                print(f"  ERROR: {e}")
                session.rollback()
                errors += 1

        summary = {"processed": processed, "errors": errors, "total": len(ads)}
        print(f"\n=== Summary ===")
        print(f"  Transcribed: {processed}")
        print(f"  Errors:      {errors}")
        return summary

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Transcribe video ads with AWS Transcribe")
    parser.add_argument("--ad-id", type=int, help="Transcribe specific ad")
    parser.add_argument("--limit", type=int, default=0, help="Max ads to process")
    parser.add_argument("--cost-estimate", action="store_true", help="Show cost estimate only")
    args = parser.parse_args()

    print("=== AWS Transcribe Video Transcription ===")
    sys.stdout.flush()
    transcribe_ads(ad_id=args.ad_id, limit=args.limit, cost_only=args.cost_estimate)


if __name__ == "__main__":
    main()
