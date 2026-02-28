#!/usr/bin/env python3
"""Check thumbnail quality for all ads in the database.

Validates every thumbnail_url by sending an HTTP HEAD request and reports:
  - Total ads with thumbnail_url
  - Valid (HTTP 200)
  - Broken (HTTP 404/403/other errors)
  - Missing (no thumbnail_url at all)

Generates a CSV report of broken thumbnails at:
    backend/reports/broken_thumbnails.csv

Usage:
    cd backend
    python -u scripts/check_thumbnail_quality.py
    python -u scripts/check_thumbnail_quality.py --timeout 15
    python -u scripts/check_thumbnail_quality.py --batch 50
"""

import sys
import io
import os
import csv
import time
import argparse
from datetime import datetime

# Windows cp932 compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
REPORT_FILE = os.path.join(REPORTS_DIR, "broken_thumbnails.csv")

DEFAULT_TIMEOUT = 10  # seconds per request
DEFAULT_BATCH = 20    # ads per progress update
REQUEST_DELAY = 0.2   # seconds between requests to avoid rate-limiting

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Core check
# ---------------------------------------------------------------------------

def check_url(url: str, timeout: int) -> dict:
    """Check a single URL via HTTP HEAD (falling back to GET).

    Returns dict with keys: status_code, ok, error, elapsed_ms.
    """
    result = {"status_code": None, "ok": False, "error": None, "elapsed_ms": 0}
    start = time.time()

    try:
        # Try HEAD first (lightweight)
        resp = requests.head(
            url, timeout=timeout, allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        result["status_code"] = resp.status_code

        # Some CDNs reject HEAD; fall back to GET on 405 or 403
        if resp.status_code in (405, 403):
            resp = requests.get(
                url, timeout=timeout, allow_redirects=True, stream=True,
                headers={"User-Agent": USER_AGENT},
            )
            resp.close()
            result["status_code"] = resp.status_code

        result["ok"] = (resp.status_code == 200)

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"connection_error: {str(e)[:80]}"
    except requests.exceptions.TooManyRedirects:
        result["error"] = "too_many_redirects"
    except Exception as e:
        result["error"] = f"unknown: {str(e)[:80]}"

    result["elapsed_ms"] = int((time.time() - start) * 1000)
    return result


def run_thumbnail_check(timeout: int, batch_size: int) -> dict:
    """Check all thumbnail URLs and return summary + broken list."""
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    stats = {
        "total_ads": 0,
        "with_thumbnail": 0,
        "missing_thumbnail": 0,
        "valid": 0,
        "broken": 0,
        "error": 0,
    }
    broken_records = []

    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        stats["total_ads"] = len(ads)

        # Separate into with/without thumbnail
        ads_with_thumb = [a for a in ads if a.thumbnail_url]
        ads_no_thumb = [a for a in ads if not a.thumbnail_url]
        stats["with_thumbnail"] = len(ads_with_thumb)
        stats["missing_thumbnail"] = len(ads_no_thumb)

        print(f"  Total ads:            {stats['total_ads']}")
        print(f"  With thumbnail_url:   {stats['with_thumbnail']}")
        print(f"  Missing thumbnail:    {stats['missing_thumbnail']}")
        print()

        if not ads_with_thumb:
            print("  No thumbnails to check.")
            return stats

        print(f"  Checking {len(ads_with_thumb)} thumbnail URLs ...")
        print()

        for i, ad in enumerate(ads_with_thumb):
            result = check_url(ad.thumbnail_url, timeout)

            if result["ok"]:
                stats["valid"] += 1
            elif result["error"]:
                stats["error"] += 1
                broken_records.append({
                    "ad_id": ad.id,
                    "external_id": ad.external_id or "",
                    "platform": str(ad.platform.value) if ad.platform else "",
                    "thumbnail_url": ad.thumbnail_url,
                    "status_code": result["status_code"] or "",
                    "error": result["error"] or "",
                    "advertiser_name": ad.advertiser_name or "",
                    "title": (ad.title or "")[:100],
                })
            else:
                stats["broken"] += 1
                broken_records.append({
                    "ad_id": ad.id,
                    "external_id": ad.external_id or "",
                    "platform": str(ad.platform.value) if ad.platform else "",
                    "thumbnail_url": ad.thumbnail_url,
                    "status_code": result["status_code"] or "",
                    "error": f"HTTP {result['status_code']}",
                    "advertiser_name": ad.advertiser_name or "",
                    "title": (ad.title or "")[:100],
                })

            # Progress update
            if (i + 1) % batch_size == 0 or (i + 1) == len(ads_with_thumb):
                pct = (i + 1) / len(ads_with_thumb) * 100
                print(
                    f"    [{i + 1}/{len(ads_with_thumb)}] ({pct:.0f}%)  "
                    f"valid={stats['valid']}  broken={stats['broken']}  "
                    f"error={stats['error']}"
                )
                sys.stdout.flush()

            time.sleep(REQUEST_DELAY)

    except Exception as e:
        print(f"  FATAL ERROR: {e}")
        raise
    finally:
        session.close()

    return stats, broken_records


def write_csv_report(broken_records: list):
    """Write the broken thumbnails CSV report."""
    os.makedirs(REPORTS_DIR, exist_ok=True)

    if not broken_records:
        print("  No broken thumbnails found. CSV report not generated.")
        return

    fieldnames = [
        "ad_id", "external_id", "platform", "thumbnail_url",
        "status_code", "error", "advertiser_name", "title",
    ]

    with open(REPORT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(broken_records)

    print(f"  CSV report written: {REPORT_FILE}")
    print(f"  Broken thumbnail records: {len(broken_records)}")


def print_report(stats: dict):
    """Print the final summary report."""
    print()
    print("=" * 70)
    print("  THUMBNAIL QUALITY CHECK REPORT")
    print("=" * 70)
    print()
    print(f"  Total ads:              {stats['total_ads']}")
    print(f"  With thumbnail_url:     {stats['with_thumbnail']}")
    print(f"  Missing thumbnail:      {stats['missing_thumbnail']}")
    print()

    if stats["with_thumbnail"] > 0:
        valid_pct = stats["valid"] / stats["with_thumbnail"] * 100
        broken_pct = stats["broken"] / stats["with_thumbnail"] * 100
        error_pct = stats["error"] / stats["with_thumbnail"] * 100

        print(f"  Valid (HTTP 200):       {stats['valid']:4d}  ({valid_pct:.1f}%)")
        print(f"  Broken (404/403/etc):   {stats['broken']:4d}  ({broken_pct:.1f}%)")
        print(f"  Error (timeout/conn):   {stats['error']:4d}  ({error_pct:.1f}%)")
        print()

        if valid_pct >= 95:
            print(f"  Status: HEALTHY")
        elif valid_pct >= 80:
            print(f"  Status: FAIR - consider running fix_bad_thumbnails.py")
        else:
            print(f"  Status: NEEDS ATTENTION - many thumbnails are broken")
    else:
        print("  No thumbnails to report on.")

    print()
    print("=" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check thumbnail quality for all ads"
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT,
        help=f"HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--batch", type=int, default=DEFAULT_BATCH,
        help=f"Progress report every N ads (default: {DEFAULT_BATCH})",
    )
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  THUMBNAIL QUALITY CHECK")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    result = run_thumbnail_check(args.timeout, args.batch)

    # Unpack result
    if isinstance(result, tuple):
        stats, broken_records = result
    else:
        stats = result
        broken_records = []

    # Write CSV report
    write_csv_report(broken_records)

    # Print summary
    print_report(stats)


if __name__ == "__main__":
    main()
