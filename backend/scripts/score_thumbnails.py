"""Thumbnail quality scorer.

For each cached thumbnail in media_cache/thumbnails/:
  1. Check image dimensions
  2. Check file size (too small = likely placeholder)
  3. Check if image is mostly single color (placeholder detection)
  4. Score 0-100 for quality
  5. Store in ad_metadata.thumbnail_quality
  6. Output summary to exports/thumbnail_quality_report.json

Run from the backend directory:
    cd backend
    python scripts/score_thumbnails.py
"""

import json
import os
import struct
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
BATCH_SIZE = 20

# Quality thresholds
MIN_GOOD_SIZE = 20 * 1024       # 20KB - decent quality
MIN_OK_SIZE = 5 * 1024          # 5KB - minimum acceptable
IDEAL_WIDTH = 1200              # Facebook recommended
IDEAL_HEIGHT = 628              # Facebook recommended
MIN_WIDTH = 200
MIN_HEIGHT = 200

# Pillow availability
_pillow_available = False
try:
    from PIL import Image
    _pillow_available = True
except ImportError:
    pass

# JPEG magic bytes
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"

# HTML detection
HTML_MARKERS = [b"<html", b"<!doctype", b"<!DOCTYPE", b"<head", b"<HEAD"]


def get_image_dimensions(path: str) -> tuple[int, int] | None:
    """Get image dimensions. Uses Pillow if available, else reads header."""
    if _pillow_available:
        try:
            with Image.open(path) as img:
                return img.size
        except Exception:
            return None

    # Fallback: read PNG header for dimensions
    try:
        with open(path, "rb") as f:
            header = f.read(32)

        if header[:4] == PNG_MAGIC and len(header) >= 24:
            w = struct.unpack(">I", header[16:20])[0]
            h = struct.unpack(">I", header[20:24])[0]
            return (w, h)
    except Exception:
        pass

    return None


def check_single_color(path: str) -> bool:
    """Check if image is mostly a single color (placeholder detection).

    Returns True if image appears to be a solid color / placeholder.
    Only works with Pillow.
    """
    if not _pillow_available:
        return False

    try:
        with Image.open(path) as img:
            # Resize to small size for quick analysis
            small = img.resize((10, 10), Image.NEAREST)
            pixels = list(small.getdata())

            if not pixels:
                return False

            # Check if all pixels are very similar
            first = pixels[0]
            if isinstance(first, int):
                # Grayscale
                values = pixels
                avg = sum(values) / len(values)
                variance = sum((p - avg) ** 2 for p in values) / len(values)
                return variance < 100  # Very low variance = single color
            elif isinstance(first, tuple) and len(first) >= 3:
                # RGB
                r_vals = [p[0] for p in pixels]
                g_vals = [p[1] for p in pixels]
                b_vals = [p[2] for p in pixels]

                r_var = sum((v - sum(r_vals) / len(r_vals)) ** 2 for v in r_vals) / len(r_vals)
                g_var = sum((v - sum(g_vals) / len(g_vals)) ** 2 for v in g_vals) / len(g_vals)
                b_var = sum((v - sum(b_vals) / len(b_vals)) ** 2 for v in b_vals) / len(b_vals)

                avg_var = (r_var + g_var + b_var) / 3
                return avg_var < 100
    except Exception:
        pass

    return False


def score_thumbnail(path: str) -> dict:
    """Score a thumbnail image quality 0-100.

    Returns dict with score, dimensions, and issues list.
    """
    result = {
        "score": 0,
        "dimensions": None,
        "issues": [],
    }

    if not os.path.exists(path):
        result["issues"].append("file_missing")
        return result

    file_size = os.path.getsize(path)

    # Check file header
    try:
        with open(path, "rb") as f:
            header = f.read(32)
    except Exception:
        result["issues"].append("read_error")
        return result

    # HTML detection
    header_lower = header.lower()
    for marker in HTML_MARKERS:
        if marker.lower() in header_lower:
            result["issues"].append("html_content")
            result["score"] = 0
            return result

    # Magic bytes check
    is_valid_image = (
        header[:3] == JPEG_MAGIC
        or header[:4] == PNG_MAGIC
        or header[:3] == b"GIF"
        or (header[:4] == b"RIFF" and len(header) >= 12 and header[8:12] == b"WEBP")
    )

    if not is_valid_image:
        result["issues"].append("invalid_format")
        result["score"] = 0
        return result

    # Start scoring
    score = 50  # Base score for valid image

    # File size scoring (0-20 points)
    if file_size >= MIN_GOOD_SIZE:
        score += 20
    elif file_size >= MIN_OK_SIZE:
        score += 10
    else:
        score -= 20
        result["issues"].append("too_small")

    # Dimension scoring (0-20 points)
    dims = get_image_dimensions(path)
    if dims:
        w, h = dims
        result["dimensions"] = f"{w}x{h}"

        if w >= IDEAL_WIDTH and h >= IDEAL_HEIGHT:
            score += 20
        elif w >= MIN_WIDTH and h >= MIN_HEIGHT:
            score += 10
        else:
            score -= 10
            result["issues"].append(f"low_resolution_{w}x{h}")

        # Aspect ratio check
        if w > 0 and h > 0:
            ratio = w / h
            if 1.5 <= ratio <= 2.0:
                score += 5  # Good landscape ratio
            elif 0.5 <= ratio <= 0.7:
                score += 3  # Acceptable portrait
    else:
        result["dimensions"] = "unknown"

    # Placeholder detection (0-10 points)
    is_single_color = check_single_color(path)
    if is_single_color:
        score -= 30
        result["issues"].append("single_color_placeholder")

    # Clamp score
    result["score"] = max(0, min(100, score))

    if not result["issues"]:
        result["issues"] = []

    return result


def main():
    print("=" * 60)
    print("  THUMBNAIL QUALITY SCORER")
    print("=" * 60)
    print()

    if _pillow_available:
        print("  Pillow: available (full analysis enabled)")
    else:
        print("  Pillow: NOT available (limited analysis)")
    print()

    if not os.path.isdir(THUMB_DIR):
        print("  No thumbnails directory found.")
        return

    os.makedirs(EXPORTS_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        # Load all ads
        ads = session.query(Ad).order_by(Ad.id).all()
        ad_map = {ad.id: ad for ad in ads}

        # Find thumbnail files
        thumb_files = [f for f in os.listdir(THUMB_DIR) if f.endswith(".jpg")]
        total = len(thumb_files)
        print(f"  Cached thumbnails: {total}")
        print()

        if total == 0:
            print("  No thumbnails to score.")
            return

        scored = 0
        updated = 0
        scores: list[int] = []
        quality_report: dict = {
            "total_scored": 0,
            "average_score": 0,
            "score_distribution": {},
            "common_issues": {},
            "details": [],
        }

        for i, fname in enumerate(thumb_files):
            fpath = os.path.join(THUMB_DIR, fname)

            # Extract ad_id from filename
            try:
                ad_id = int(fname.replace(".jpg", ""))
            except ValueError:
                continue

            # Score the thumbnail
            result = score_thumbnail(fpath)
            scored += 1
            scores.append(result["score"])

            # Track issues
            for issue in result.get("issues", []):
                quality_report["common_issues"][issue] = quality_report["common_issues"].get(issue, 0) + 1

            # Score distribution buckets
            bucket = f"{(result['score'] // 10) * 10}-{(result['score'] // 10) * 10 + 9}"
            quality_report["score_distribution"][bucket] = quality_report["score_distribution"].get(bucket, 0) + 1

            # Add to details (limited)
            if len(quality_report["details"]) < 500:
                quality_report["details"].append({
                    "ad_id": ad_id,
                    "score": result["score"],
                    "dimensions": result["dimensions"],
                    "issues": result["issues"],
                })

            # Update DB if ad exists
            if ad_id in ad_map:
                ad = ad_map[ad_id]
                meta = dict(ad.ad_metadata or {})
                meta["thumbnail_quality"] = {
                    "score": result["score"],
                    "dimensions": result["dimensions"],
                    "issues": result["issues"],
                }
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1

            if (i + 1) % BATCH_SIZE == 0:
                session.commit()

            if (i + 1) % 50 == 0:
                print(f"  Progress: {i + 1}/{total}")

        session.commit()

        # Compute summary stats
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        quality_report["total_scored"] = scored
        quality_report["average_score"] = avg_score

        # Save report
        report_path = os.path.join(EXPORTS_DIR, "thumbnail_quality_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2, ensure_ascii=True)

        # Print summary
        print()
        print("=" * 60)
        print("  SCORING RESULTS")
        print("=" * 60)
        print(f"  Thumbnails scored:   {scored}")
        print(f"  DB records updated:  {updated}")
        print(f"  Average score:       {avg_score}")
        print()
        print("  Score distribution:")
        for bucket in sorted(quality_report["score_distribution"].keys()):
            count = quality_report["score_distribution"][bucket]
            bar = "#" * min(count, 40)
            print(f"    {bucket:>5}: {count:4d} {bar}")
        print()
        print("  Common issues:")
        for issue, count in sorted(quality_report["common_issues"].items(), key=lambda x: -x[1]):
            print(f"    {issue}: {count}")
        print()
        print(f"  Report saved to: {report_path}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
