"""A90 (CI-124): Audit that top-30 ads are collected in daily metrics.

Verifies that the most important ads (by hit_score) have daily metrics
for today. Alerts if any top-30 ads are missing.

Usage:
    python -m scripts.audit_top30_collection
    python -m scripts.audit_top30_collection --date 2026-03-01
    python -m scripts.audit_top30_collection --top 50  # check top 50 instead
"""

import argparse
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics

import logging
logger = logging.getLogger(__name__)


def audit_top_n(session, target_date: date, top_n: int = 30) -> dict:
    """Check that top-N ads by hit_score have metrics for the given date."""
    # Dialect-agnostic top-N selection (works for PostgreSQL + SQLite fallback).
    ads = session.query(Ad.id, Ad.advertiser_name, Ad.ad_metadata).all()
    scored_ads = []
    for ad_id, advertiser_name, ad_metadata in ads:
        meta = ad_metadata or {}
        raw = meta.get("latest_hit_score", 0)
        try:
            score = float(raw)
        except (TypeError, ValueError):
            score = 0.0
        scored_ads.append((ad_id, advertiser_name, score))

    scored_ads.sort(key=lambda x: x[2], reverse=True)
    top_ads = scored_ads[:top_n]

    if not top_ads:
        return {
            "status": "warning",
            "message": "No ads found in database",
            "top_n": top_n,
            "date": str(target_date),
        }

    top_ids = [r[0] for r in top_ads]

    # Check which have metrics for target_date
    covered_rows = (
        session.query(AdDailyMetrics.ad_id)
        .filter(
            AdDailyMetrics.ad_id.in_(top_ids),
            AdDailyMetrics.metric_date == target_date,
        )
        .distinct()
        .all()
    )
    covered_ids = {r[0] for r in covered_rows}
    missing_ids = [aid for aid in top_ids if aid not in covered_ids]

    # Build missing details
    missing_details = []
    for r in top_ads:
        if r[0] in missing_ids:
            missing_details.append({
                "ad_id": r[0],
                "advertiser": r[1] or "",
                "hit_score": float(r[2]),
            })

    result = {
        "date": str(target_date),
        "top_n": top_n,
        "total_top_ads": len(top_ads),
        "covered": len(covered_ids),
        "missing": len(missing_ids),
        "coverage_pct": round(len(covered_ids) / len(top_ads) * 100, 1) if top_ads else 0,
    }

    if missing_ids:
        result["status"] = "ALERT"
        result["missing_ads"] = missing_details
        logger.warning(
            "top30_audit_missing date=%s missing=%d/%d",
            target_date, len(missing_ids), len(top_ads),
        )
    else:
        result["status"] = "PASS"

    return result


def main():
    parser = argparse.ArgumentParser(description="Audit top-30 ad metrics collection")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD, default: today)")
    parser.add_argument("--top", type=int, default=30, help="Number of top ads to check (default: 30)")
    args = parser.parse_args()

    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        target_date = date.today()

    print("=" * 60)
    print("  Top-%d Collection Audit" % args.top)
    print(f"  Date: {target_date}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        result = audit_top_n(session, target_date, top_n=args.top)

        icon = "OK" if result["status"] == "PASS" else "!!"
        print(f"\n  [{icon}] Coverage: {result['covered']}/{result['total_top_ads']} "
              f"({result['coverage_pct']}%)")

        if result["status"] == "ALERT":
            print(f"\n  MISSING {result['missing']} ads:")
            for ad in result.get("missing_ads", [])[:10]:
                print(f"    ad_id={ad['ad_id']} score={ad['hit_score']:.0f} {ad['advertiser'][:30]}")

            print("\n  Action:")
            print("    1. Check if daily metrics job ran: python -m scripts.ops_procedure_audit")
            print("    2. Run manually: python -c \"from app.tasks.metrics_tasks import *; "
                  "from app.core.database import SyncSessionLocal; "
                  "s=SyncSessionLocal(); collect_metrics_for_ads(s); s.commit()\"")
        else:
            print("  All top-%d ads have metrics for %s" % (args.top, target_date))

        print()

    finally:
        session.close()


if __name__ == "__main__":
    main()
