#!/usr/bin/env python3
"""Bulk upload media_cache/ files to S3 and update DB s3 keys.

Usage:
    python -m scripts.upload_to_s3                  # upload all
    python -m scripts.upload_to_s3 --type thumbnails # upload only thumbnails
    python -m scripts.upload_to_s3 --dry-run         # preview without uploading

Bucket structure: s3://{bucket}/{thumbnails,images,videos}/{ad_id}.{ext}
"""

import argparse
import mimetypes
import os
import sys
import time

# -- Path setup ---------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "media_cache")
)

MEDIA_TYPES = {
    "thumbnails": {
        "s3_col": "thumbnail_s3_key",
        "extensions": (".jpg", ".jpeg", ".png", ".webp"),
    },
    "images": {
        "s3_col": "image_s3_key",
        "extensions": (".jpg", ".jpeg", ".png", ".webp"),
    },
    "videos": {
        "s3_col": "s3_key",
        "extensions": (".mp4", ".webm", ".mov"),
    },
}


def _guess_content_type(filename: str) -> str:
    """Guess MIME type from file extension."""
    ext = os.path.splitext(filename)[1].lower()
    mapping = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }
    return mapping.get(ext, mimetypes.guess_type(filename)[0] or "application/octet-stream")


def _extract_ad_id(filename: str) -> int | None:
    """Extract ad_id from filename like '123.jpg'."""
    name = os.path.splitext(filename)[0]
    try:
        return int(name)
    except ValueError:
        return None


def upload_media(media_type: str | None = None, dry_run: bool = False) -> dict:
    """Upload media files to S3 and update DB.

    Args:
        media_type: 'thumbnails', 'images', or 'videos'. None = all.
        dry_run: If True, only preview what would be uploaded.

    Returns:
        Summary dict with counts.
    """
    import boto3

    types_to_process = [media_type] if media_type else list(MEDIA_TYPES.keys())
    total_uploaded = 0
    total_skipped = 0
    total_errors = 0
    total_updated_db = 0

    # Get S3 client
    s3_client = None
    bucket = None
    if not dry_run:
        try:
            from app.core.config import get_settings
            settings = get_settings()
            bucket = settings.aws_s3_bucket
            if not bucket:
                print("ERROR: AWS_S3_BUCKET not set in config/.env")
                return {"error": "no_bucket"}
            s3_client = boto3.client("s3", region_name=settings.aws_region)
            # Test access
            s3_client.head_bucket(Bucket=bucket)
            print(f"S3 bucket verified: {bucket}")
        except Exception as e:
            print(f"ERROR: Cannot access S3 bucket: {e}")
            return {"error": str(e)}

    session = SyncSessionLocal()
    try:
        for mtype in types_to_process:
            info = MEDIA_TYPES[mtype]
            s3_col = info["s3_col"]
            local_dir = os.path.join(CACHE_DIR, mtype)

            if not os.path.isdir(local_dir):
                print(f"  [{mtype}] Directory not found: {local_dir}")
                continue

            files = sorted(os.listdir(local_dir))
            valid_files = [
                f for f in files
                if os.path.splitext(f)[1].lower() in info["extensions"]
                and _extract_ad_id(f) is not None
            ]

            print(f"\n== {mtype.upper()} == ({len(valid_files)} files)")

            for i, filename in enumerate(valid_files, 1):
                ad_id = _extract_ad_id(filename)
                local_path = os.path.join(local_dir, filename)
                file_size = os.path.getsize(local_path)
                s3_key = f"{mtype}/{filename}"
                content_type = _guess_content_type(filename)

                # Check if already in DB
                ad = session.query(Ad).filter(Ad.id == ad_id).first()
                if not ad:
                    total_skipped += 1
                    continue

                existing_key = getattr(ad, s3_col, None)
                if existing_key and not dry_run:
                    # Already has S3 key, skip unless local file is newer
                    total_skipped += 1
                    continue

                if dry_run:
                    print(f"  [{i}/{len(valid_files)}] WOULD upload {filename} "
                          f"({file_size/1024:.1f} KB) -> s3://{bucket or 'BUCKET'}/{s3_key}")
                    total_uploaded += 1
                    continue

                # Upload to S3
                try:
                    # Use multipart for files > 8MB
                    if file_size > 8 * 1024 * 1024:
                        from boto3.s3.transfer import TransferConfig
                        config = TransferConfig(
                            multipart_threshold=8 * 1024 * 1024,
                            multipart_chunksize=8 * 1024 * 1024,
                        )
                        s3_client.upload_file(
                            local_path, bucket, s3_key,
                            ExtraArgs={"ContentType": content_type},
                            Config=config,
                        )
                    else:
                        s3_client.upload_file(
                            local_path, bucket, s3_key,
                            ExtraArgs={"ContentType": content_type},
                        )

                    # Update DB
                    setattr(ad, s3_col, s3_key)
                    session.commit()
                    total_uploaded += 1
                    total_updated_db += 1

                    if i % 20 == 0 or i == len(valid_files):
                        print(f"  [{i}/{len(valid_files)}] Uploaded {filename} "
                              f"({file_size/1024:.1f} KB)")
                        sys.stdout.flush()

                except Exception as e:
                    print(f"  ERROR uploading {filename}: {e}")
                    session.rollback()
                    total_errors += 1

    finally:
        session.close()

    summary = {
        "uploaded": total_uploaded,
        "skipped": total_skipped,
        "errors": total_errors,
        "db_updated": total_updated_db,
    }
    print(f"\n=== Summary ===")
    print(f"  Uploaded:   {total_uploaded}")
    print(f"  Skipped:    {total_skipped}")
    print(f"  Errors:     {total_errors}")
    print(f"  DB updated: {total_updated_db}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Upload media_cache to S3")
    parser.add_argument("--type", choices=list(MEDIA_TYPES.keys()),
                        help="Upload only this media type")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without uploading")
    args = parser.parse_args()

    print("=== S3 Media Upload ===")
    print(f"  Cache dir: {CACHE_DIR}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE UPLOAD'}")
    print(f"  Type: {args.type or 'all'}")
    sys.stdout.flush()

    start = time.time()
    result = upload_media(media_type=args.type, dry_run=args.dry_run)
    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
