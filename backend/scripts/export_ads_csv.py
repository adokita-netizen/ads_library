"""Export all ad data to CSV and/or JSON file.

Outputs a comprehensive export with:
  - Core ad fields (id, title, advertiser, platform, etc.)
  - Score fields (hit_score, hit_level, score_breakdown signals)
  - Creative analysis fields (hook_type, cta_type, offer_type, emotion, etc.)
  - Delivery info (days_running, is_still_running, estimated_spend)
  - Media status (has_cached_thumbnail, has_cached_image, has_cached_video)
  - URLs (destination_url, snapshot_url)

Output: backend/exports/ads_export_YYYYMMDD.csv / .json
Creates the exports/ directory if it does not exist.

Usage:
    cd backend
    python scripts/export_ads_csv.py                          # CSV only (default)
    python scripts/export_ads_csv.py --format json            # JSON only
    python scripts/export_ads_csv.py --format both            # CSV + JSON
    python scripts/export_ads_csv.py --output-dir /path/to    # Custom output dir
    python scripts/export_ads_csv.py --mask-pii               # Mask PII fields
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Config ────────────────────────────────────────────────────────

DEFAULT_EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")

# Score breakdown signal keys (from ranking_service.compute_hit_score)
SCORE_SIGNAL_KEYS = ["longevity", "spend", "active_bonus", "creative", "trend"]

# Creative analysis field keys
CREATIVE_FIELDS = [
    "hook_type", "cta_type", "offer_type", "offer_detail", "emotion",
    "has_emoji", "has_numbers", "has_testimonial", "has_before_after",
    "text_length", "line_count", "destination_type",
]

# CSV columns
CSV_COLUMNS = [
    "id",
    "external_id",
    "title",
    "advertiser_name",
    "brand_name",
    "platform",
    "category",
    "status",
    "creative_type",
    "hit_score",
    "hit_level",
    "is_hit",
    "hit_pattern_rank",
    "days_running",
    "is_still_running",
    "longevity_class",
    "estimated_spend",
    "destination_url",
    "snapshot_url",
    "video_url",
    "image_url",
    "thumbnail_url",
    "first_seen_at",
    "last_seen_at",
    "view_count",
    "like_count",
    "created_at",
    "updated_at",
    # Creative analysis fields
    "hook_type",
    "cta_type",
    "offer_type",
    "offer_detail",
    "emotion",
    "has_emoji",
    "has_numbers",
    "has_testimonial",
    "has_before_after",
    "text_length",
    "line_count",
    "destination_type",
    # Media cache status
    "has_cached_thumbnail",
    "has_cached_image",
    "has_cached_video",
    # Score breakdown signals (flattened)
    "signal_longevity",
    "signal_spend",
    "signal_active_bonus",
    "signal_creative",
    "signal_trend",
]


# ── Helper Functions ─────────────────────────────────────────────


def safe_str(value) -> str:
    """Convert value to string safely, returning empty string for None."""
    if value is None:
        return ""
    return str(value)


def format_datetime(dt) -> str:
    """Format datetime to ISO string, or empty if None."""
    if dt is None:
        return ""
    try:
        return dt.isoformat()
    except (AttributeError, ValueError):
        return str(dt)


# ── PII Masking (CI-085) ─────────────────────────────────────────

# Fields that contain personally identifiable or commercially sensitive info
_PII_NAME_FIELDS = {"advertiser_name", "brand_name"}
_PII_URL_FIELDS = {"destination_url", "snapshot_url", "video_url", "image_url", "thumbnail_url"}
_PII_ID_FIELDS = {"external_id"}


def _mask_name(value: str) -> str:
    """Mask a name: keep first 2 chars + hash suffix. '山田太郎' → '山田***_a3f2'."""
    if not value:
        return value
    prefix = value[:2]
    h = hashlib.sha256(value.encode()).hexdigest()[:4]
    return f"{prefix}***_{h}"


def _mask_url(value: str) -> str:
    """Mask URL to domain only. 'https://example.com/path?id=123' → 'https://example.com/***'."""
    if not value:
        return value
    try:
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/***"
        return "***"
    except Exception:
        return "***"


def _mask_id(value: str) -> str:
    """Replace external ID with a one-way hash."""
    if not value:
        return value
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def mask_row(row: dict) -> dict:
    """Apply PII masking to a single export row."""
    masked = dict(row)
    for field in _PII_NAME_FIELDS:
        if field in masked and masked[field]:
            masked[field] = _mask_name(str(masked[field]))
    for field in _PII_URL_FIELDS:
        if field in masked and masked[field]:
            masked[field] = _mask_url(str(masked[field]))
    for field in _PII_ID_FIELDS:
        if field in masked and masked[field]:
            masked[field] = _mask_id(str(masked[field]))
    return masked


def extract_row(ad: Ad) -> dict:
    """Extract a flat dict of export values from an Ad record."""
    meta = ad.ad_metadata or {}
    score_breakdown = meta.get("latest_score_breakdown", {})
    creative = meta.get("creative_analysis", {})
    media_cache = meta.get("media_cache_status", {})

    # Compute estimated spend from metadata or direct field
    estimated_spend = meta.get("estimated_total_spend_jpy") or ad.spend or ""

    row = {
        "id": ad.id,
        "external_id": safe_str(ad.external_id),
        "title": safe_str(ad.title),
        "advertiser_name": safe_str(ad.advertiser_name),
        "brand_name": safe_str(ad.brand_name),
        "platform": safe_str(ad.platform.value if ad.platform else ""),
        "category": safe_str(ad.category.value if ad.category else ""),
        "status": safe_str(ad.status.value if ad.status else ""),
        "creative_type": safe_str(ad.creative_type),
        "hit_score": safe_str(meta.get("latest_hit_score", "")),
        "hit_level": safe_str(meta.get("hit_level", "")),
        "is_hit": safe_str(meta.get("is_hit", "")),
        "hit_pattern_rank": safe_str(meta.get("hit_pattern_rank", "")),
        "days_running": safe_str(meta.get("days_running", "")),
        "is_still_running": safe_str(meta.get("is_still_running", "")),
        "longevity_class": safe_str(meta.get("longevity_class", "")),
        "estimated_spend": safe_str(estimated_spend),
        "destination_url": safe_str(ad.destination_url),
        "snapshot_url": safe_str(ad.snapshot_url),
        "video_url": safe_str(ad.video_url),
        "image_url": safe_str(ad.image_url),
        "thumbnail_url": safe_str(ad.thumbnail_url),
        "first_seen_at": format_datetime(ad.first_seen_at),
        "last_seen_at": format_datetime(ad.last_seen_at),
        "view_count": safe_str(ad.view_count),
        "like_count": safe_str(ad.like_count),
        "created_at": format_datetime(ad.created_at),
        "updated_at": format_datetime(ad.updated_at),
    }

    # Creative analysis fields
    for field in CREATIVE_FIELDS:
        row[field] = safe_str(creative.get(field, ""))

    # Media cache status
    row["has_cached_thumbnail"] = safe_str(media_cache.get("has_cached_thumbnail", ""))
    row["has_cached_image"] = safe_str(media_cache.get("has_cached_image", ""))
    row["has_cached_video"] = safe_str(media_cache.get("has_cached_video", ""))

    # Flatten score breakdown signals
    for key in SCORE_SIGNAL_KEYS:
        row[f"signal_{key}"] = safe_str(score_breakdown.get(key, ""))

    return row


# ── Main ──────────────────────────────────────────────────────────


def write_csv(ads: list[Ad], filepath: str, mask_pii: bool = False) -> int:
    """Write ads to CSV file. Returns count exported."""
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        exported = 0
        for ad in ads:
            try:
                row = extract_row(ad)
                if mask_pii:
                    row = mask_row(row)
                writer.writerow(row)
                exported += 1
            except Exception as e:
                print(f"  Error exporting ad ID {ad.id}: {e}")
    return exported


def write_json(ads: list[Ad], filepath: str, mask_pii: bool = False) -> int:
    """Write ads to JSON file. Returns count exported."""
    records = []
    for ad in ads:
        try:
            row = extract_row(ad)
            if mask_pii:
                row = mask_row(row)
            # Convert numeric strings back to numbers for JSON
            for key in ["id", "hit_score", "days_running", "view_count",
                         "like_count", "line_count", "hit_pattern_rank",
                         "signal_longevity", "signal_spend",
                         "signal_active_bonus", "signal_creative", "signal_trend"]:
                val = row.get(key, "")
                if val != "" and val is not None:
                    try:
                        row[key] = float(val) if "." in str(val) else int(val)
                    except (ValueError, TypeError):
                        pass
            # Convert boolean strings
            for key in ["is_hit", "is_still_running", "has_emoji", "has_numbers",
                         "has_testimonial", "has_before_after",
                         "has_cached_thumbnail", "has_cached_image", "has_cached_video"]:
                val = row.get(key, "")
                if val == "True":
                    row[key] = True
                elif val == "False":
                    row[key] = False
            records.append(row)
        except Exception as e:
            print(f"  Error exporting ad ID {ad.id}: {e}")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return len(records)


def main():
    parser = argparse.ArgumentParser(description="Export ad data to CSV/JSON")
    parser.add_argument("--format", choices=["csv", "json", "both"],
                        default="csv", help="Output format (default: csv)")
    parser.add_argument("--output-dir", default=DEFAULT_EXPORTS_DIR,
                        help=f"Output directory (default: {DEFAULT_EXPORTS_DIR})")
    parser.add_argument("--mask-pii", action="store_true",
                        help="Mask PII fields (names, URLs, IDs) in output")
    args = parser.parse_args()

    export_format = args.format
    exports_dir = args.output_dir
    mask_pii = args.mask_pii

    print("=" * 60)
    print("Ad Data Export")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print(f"Format: {export_format}")
    if mask_pii:
        print("PII masking: ENABLED")
    print("=" * 60)

    os.makedirs(exports_dir, exist_ok=True)
    print(f"Export directory: {exports_dir}")

    today = datetime.now(timezone.utc).strftime("%Y%m%d")

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total_ads = len(ads)
        print(f"Total ads to export: {total_ads}")

        if total_ads == 0:
            print("No ads found. Exiting without creating file.")
            return

        files_created = []

        # CSV export
        if export_format in ("csv", "both"):
            suffix = "_masked" if mask_pii else ""
            csv_path = os.path.join(exports_dir, f"ads_export_{today}{suffix}.csv")
            csv_count = write_csv(ads, csv_path, mask_pii=mask_pii)
            csv_size = os.path.getsize(csv_path) / 1024
            files_created.append(("CSV", csv_path, csv_count, csv_size))

        # JSON export
        if export_format in ("json", "both"):
            suffix = "_masked" if mask_pii else ""
            json_path = os.path.join(exports_dir, f"ads_export_{today}{suffix}.json")
            json_count = write_json(ads, json_path, mask_pii=mask_pii)
            json_size = os.path.getsize(json_path) / 1024
            files_created.append(("JSON", json_path, json_count, json_size))

        print()
        print("=" * 60)
        print("EXPORT COMPLETE")
        print("=" * 60)
        for fmt, path, count, size in files_created:
            print(f"  {fmt}:")
            print(f"    File:    {path}")
            print(f"    Rows:    {count}")
            print(f"    Size:    {size:.1f} KB")
        print(f"  Columns:   {len(CSV_COLUMNS)}")
        print()

        # Summary statistics
        hit_count = sum(1 for a in ads if (a.ad_metadata or {}).get("is_hit"))
        running_count = sum(
            1 for a in ads if (a.ad_metadata or {}).get("is_still_running") is True
        )
        with_score = sum(
            1 for a in ads if (a.ad_metadata or {}).get("latest_hit_score") is not None
        )
        with_creative = sum(
            1 for a in ads if (a.ad_metadata or {}).get("creative_analysis")
        )

        print("Data summary:")
        print(f"  Ads with hit_score:        {with_score}/{total_ads}")
        print(f"  Ads with creative_analysis: {with_creative}/{total_ads}")
        print(f"  Hit ads:                   {hit_count}")
        print(f"  Currently running:         {running_count}")

        print()
        print("Done!")

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
