#!/usr/bin/env python3
"""E2E test: Lambda -> SQS -> ECS -> Playwright -> DB update.

Tests the full media extraction pipeline by triggering a Lambda invocation
and polling the database for status updates.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/test_media_pipeline.py [AD_ID]
"""

import io
import json
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pipeline(ad_id: int = None, limit: int = 1):
    """Run E2E media extraction pipeline test.

    1. Find a pending ad from DB (or use specified ad_id)
    2. Invoke Lambda (action=extract_media)
    3. Poll DB for status changes (max 2 minutes)
    4. Report results
    """
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Install with: pip install boto3")
        return

    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()

    try:
        # Step 1: Find test target
        if ad_id:
            ad = session.query(Ad).filter(Ad.id == ad_id).first()
            if not ad:
                print(f"ERROR: Ad with id={ad_id} not found")
                return
        else:
            ad = session.query(Ad).filter(
                Ad.media_extraction_status == "pending",
                Ad.snapshot_url.isnot(None),
            ).first()
            if not ad:
                print("No pending ads with snapshot_url found")
                return

        snapshot_preview = (ad.snapshot_url or "")[:80]
        print(f"Testing with ad_id={ad.id}, snapshot_url={snapshot_preview}...")
        print(f"  Current status: {ad.media_extraction_status}")
        print(f"  Current image_url: {ad.image_url}")
        print(f"  Current video_url: {ad.video_url}")

        # Step 2: Invoke Lambda
        print("\nInvoking Lambda (action=extract_media)...")
        client = boto3.client("lambda", region_name="ap-northeast-1")
        response = client.invoke(
            FunctionName="vaap-production-api",
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "action": "extract_media",
                "limit": limit,
            }),
        )
        result = json.loads(response["Payload"].read())
        print(f"Lambda response: {json.dumps(result, indent=2, ensure_ascii=False)}")

        # Step 3: Poll for completion
        print("\nPolling for status changes...")
        for i in range(12):  # Max 2 minutes
            time.sleep(10)
            session.expire_all()
            ad = session.query(Ad).filter(Ad.id == ad.id).first()
            status = ad.media_extraction_status
            print(f"  [{(i + 1) * 10}s] status={status}")
            if status in ("completed", "enriched", "failed"):
                break

        # Step 4: Report results
        print(f"\n{'=' * 50}")
        print(f"  RESULT")
        print(f"{'=' * 50}")
        print(f"  status:        {ad.media_extraction_status}")
        print(f"  image_url:     {ad.image_url}")
        print(f"  video_url:     {ad.video_url}")
        print(f"  creative_type: {ad.creative_type}")
        print(f"  image_s3_key:  {ad.image_s3_key}")
        print(f"  thumbnail_url: {ad.thumbnail_url}")

        if ad.media_extraction_status in ("completed", "enriched"):
            print("\n  [OK] Pipeline test PASSED")
        elif ad.media_extraction_status == "failed":
            print("\n  [FAIL] Pipeline test FAILED - check CloudWatch logs")
        else:
            print(f"\n  [TIMEOUT] Status still '{ad.media_extraction_status}' after 2 min")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    target_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    test_pipeline(ad_id=target_id)
