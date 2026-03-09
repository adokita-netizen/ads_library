# D28: Media Quality Validation Pipeline

## Status: WAITING (Step 7 - after D26 + D27 verified)
## Depends on: D26 (extraction working), pipeline running

## Target Files
- `backend/scripts/validate_extracted_media.py` (NEW)
- `backend/app/tasks/media_tasks.py` (quality check addition)

---

## Task 1: validate_extracted_media.py (NEW SCRIPT)

Create `backend/scripts/validate_extracted_media.py`:

```python
"""Validate quality of extracted media and flag low-quality results."""

import io
from PIL import Image
from app.core.database import SyncSessionLocal
from app.core.storage import get_storage_client
from app.models.ad import Ad
from sqlalchemy.orm.attributes import flag_modified

def validate_all():
    session = SyncSessionLocal()
    storage = get_storage_client()

    ads = session.query(Ad).filter(
        Ad.media_extraction_status == "completed",
        Ad.image_s3_key.isnot(None),
    ).all()

    issues = []
    for ad in ads:
        try:
            data = storage.get_bytes(ad.image_s3_key)
            if not data:
                issues.append({"ad_id": ad.id, "issue": "s3_key_empty"})
                continue

            img = Image.open(io.BytesIO(data))
            w, h = img.size

            quality_issues = []

            # Check 1: Minimum resolution
            if w < 200 or h < 200:
                quality_issues.append(f"low_res_{w}x{h}")

            # Check 2: Aspect ratio (too extreme = likely icon/banner)
            ratio = max(w, h) / min(w, h)
            if ratio > 5:
                quality_issues.append(f"extreme_ratio_{ratio:.1f}")

            # Check 3: File size (too small = likely placeholder)
            if len(data) < 5000:  # 5KB
                quality_issues.append(f"tiny_file_{len(data)}B")

            # Check 4: Format
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

if __name__ == "__main__":
    validate_all()
```

---

## Task 2: Inline quality check in media_tasks.py

In `extract_media_task()`, add quality check AFTER image download + S3 upload (after the image upload try/except block, before "Auto-set thumbnail_url").

Insert after L138 (after image upload except block):

```python
# Inline quality check for downloaded image
if extracted.image_urls and ad.image_s3_key:
    try:
        from PIL import Image
        import io
        image_data_check = _download_sync(extracted.image_urls[0])
        if image_data_check:
            img = Image.open(io.BytesIO(image_data_check))
            w, h = img.size
            if w < 200 or h < 200 or len(image_data_check) < 5000:
                from sqlalchemy.orm.attributes import flag_modified
                meta = dict(ad.ad_metadata or {})
                meta["media_quality_issues"] = [f"low_quality_{w}x{h}_{len(image_data_check)}B"]
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                logger.warning("low_quality_image_detected", ad_id=ad_id, width=w, height=h)
    except Exception:
        pass
```

**NOTE:** To avoid downloading the image twice, consider reusing the `image_data` variable from the image download block above. Check if `image_data` is still in scope:

```python
# Better: reuse existing image_data (avoids double download)
if image_data:
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_data))
        w, h = img.size
        if w < 200 or h < 200 or len(image_data) < 5000:
            from sqlalchemy.orm.attributes import flag_modified
            meta = dict(ad.ad_metadata or {})
            meta["media_quality_issues"] = [f"low_quality_{w}x{h}_{len(image_data)}B"]
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            logger.warning("low_quality_image_detected", ad_id=ad_id, width=w, height=h)
    except Exception:
        pass
```

The issue: `image_data` is defined inside a try block at L127. Ensure it's accessible by defining `image_data = None` before the try block:

```python
# Before the existing image download try block (around L125):
image_data = None
if extracted.image_urls:
    try:
        image_data = _download_sync(extracted.image_urls[0])
        ...
```

---

## Constraints
- `validate_extracted_media.py`: New file in backend/scripts/ (Agent D scope)
- `media_tasks.py`: Quality check addition only
- Pillow (PIL) is already in requirements.txt
- ad_metadata keys used: `media_quality_issues` (Agent D scope)
- Print statements: English only
