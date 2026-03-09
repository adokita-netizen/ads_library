#!/usr/bin/env python3
"""Validate quality of extracted media and flag low-quality results.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/validate_extracted_media.py
"""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def validate_all():
    from PIL import Image
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad
    from sqlalchemy.orm.attributes import flag_modified

    session = SyncSessionLocal()

    ads = session.query(Ad).filter(
        Ad.media_extraction_status.in_(["completed", "enriched"]),
        Ad.image_s3_key.isnot(None),
    ).all()

    print(f"Validating {len(ads)} ads with image_s3_key...")

    issues = []
    for ad in ads:
        try:
            # Try local cache first, then S3
            local_path = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "..", "media_cache", "images", f"{ad.id}.jpg")
            )
            data = None
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    data = f.read()
            else:
                try:
                    from app.core.storage import get_storage_client
                    storage = get_storage_client()
                    data = storage.get_bytes(ad.image_s3_key)
                except Exception:
                    pass

            if not data:
                issues.append({"ad_id": ad.id, "issue": "s3_key_empty"})
                continue

            img = Image.open(io.BytesIO(data))
            w, h = img.size

            quality_issues = []

            # Check 1: Minimum resolution
            if w < 200 or h < 200:
                quality_issues.append(f"low_res_{w}x{h}")

            # Check 2: Extreme aspect ratio (likely icon/banner)
            ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 99
            if ratio > 5:
                quality_issues.append(f"extreme_ratio_{ratio:.1f}")

            # Check 3: File size too small (likely placeholder)
            if len(data) < 5000:
                quality_issues.append(f"tiny_file_{len(data)}B")

            # Check 4: Unusual format
            if img.format not in ("JPEG", "PNG", "WEBP"):
                quality_issues.append(f"unusual_format_{img.format}")

            if quality_issues:
                meta = dict(ad.ad_metadata or {})
                meta["media_quality_issues"] = quality_issues
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                issues.append({"ad_id": ad.id, "issues": quality_issues})

        except Exception as e:
            issues.append({"ad_id": ad.id, "issue": f"error: {str(e)}"})

    session.commit()
    session.close()

    print(f"Validated {len(ads)} ads, {len(issues)} with issues")
    for i in issues[:20]:
        print(f"  ad_id={i['ad_id']}: {i.get('issues') or i.get('issue')}")

    return {"total": len(ads), "issues": len(issues), "details": issues[:50]}


if __name__ == "__main__":
    validate_all()
