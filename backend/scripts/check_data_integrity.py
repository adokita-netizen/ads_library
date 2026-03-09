"""A63 (CI-069): ad / ad_daily_metrics integrity checker.

Detects orphaned metrics, ads without metrics, and data inconsistencies.
Designed for daily cron or manual execution.

Usage:
    python -m scripts.check_data_integrity
    python -m scripts.check_data_integrity --fix  # auto-fix orphans
    python -m scripts.check_data_integrity --json-report exports/integrity.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SyncSessionLocal


def run_checks(session, fix: bool = False) -> dict:
    """Run all integrity checks and return results."""
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
        "total_issues": 0,
        "fixed": 0,
    }

    # 1. Orphaned metrics (ad_daily_metrics referencing non-existent ads)
    orphan_count = session.execute(text("""
        SELECT COUNT(*) FROM ad_daily_metrics m
        LEFT JOIN ads a ON m.ad_id = a.id
        WHERE a.id IS NULL
    """)).scalar()

    check1 = {"name": "orphaned_metrics", "count": orphan_count, "severity": "high" if orphan_count > 0 else "ok"}
    if orphan_count > 0 and fix:
        session.execute(text("""
            DELETE FROM ad_daily_metrics
            WHERE ad_id NOT IN (SELECT id FROM ads)
        """))
        session.commit()
        check1["fixed"] = orphan_count
        report["fixed"] += orphan_count
    report["checks"].append(check1)
    report["total_issues"] += orphan_count

    # 2. Ads without any metrics
    ads_no_metrics = session.execute(text("""
        SELECT COUNT(*) FROM ads a
        LEFT JOIN ad_daily_metrics m ON a.id = m.ad_id
        WHERE m.id IS NULL
    """)).scalar()
    total_ads = session.execute(text("SELECT COUNT(*) FROM ads")).scalar()
    check2 = {
        "name": "ads_without_metrics",
        "count": ads_no_metrics,
        "total_ads": total_ads,
        "pct": round(ads_no_metrics * 100 / total_ads, 1) if total_ads else 0,
        "severity": "medium" if ads_no_metrics > total_ads * 0.5 else "low",
    }
    report["checks"].append(check2)

    # 3. Duplicate metrics (same ad_id + metric_date)
    dup_count = session.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT ad_id, metric_date, COUNT(*) as cnt
            FROM ad_daily_metrics
            GROUP BY ad_id, metric_date
            HAVING COUNT(*) > 1
        ) dups
    """)).scalar()
    check3 = {"name": "duplicate_metrics", "count": dup_count, "severity": "high" if dup_count > 0 else "ok"}
    report["checks"].append(check3)
    report["total_issues"] += dup_count

    # 4. Negative view counts or spend
    neg_views = session.execute(text("""
        SELECT COUNT(*) FROM ad_daily_metrics WHERE view_count < 0 OR view_count_increase < 0
    """)).scalar()
    neg_spend = session.execute(text("""
        SELECT COUNT(*) FROM ad_daily_metrics WHERE estimated_spend < 0 OR estimated_spend_increase < 0
    """)).scalar()
    check4 = {
        "name": "negative_values",
        "negative_views": neg_views,
        "negative_spend": neg_spend,
        "severity": "medium" if (neg_views + neg_spend) > 0 else "ok",
    }
    report["checks"].append(check4)
    report["total_issues"] += neg_views + neg_spend

    # 5. Orphaned product_rankings
    orphan_pr = session.execute(text("""
        SELECT COUNT(*) FROM product_rankings p
        LEFT JOIN ads a ON p.ad_id = a.id
        WHERE a.id IS NULL
    """)).scalar()
    check5 = {"name": "orphaned_rankings", "count": orphan_pr, "severity": "medium" if orphan_pr > 0 else "ok"}
    if orphan_pr > 0 and fix:
        session.execute(text("""
            DELETE FROM product_rankings
            WHERE ad_id NOT IN (SELECT id FROM ads)
        """))
        session.commit()
        check5["fixed"] = orphan_pr
        report["fixed"] += orphan_pr
    report["checks"].append(check5)
    report["total_issues"] += orphan_pr

    # 6. Ads with NULL metadata
    null_meta = session.execute(text("""
        SELECT COUNT(*) FROM ads WHERE metadata IS NULL
    """)).scalar()
    check6 = {"name": "null_metadata", "count": null_meta, "severity": "low"}
    report["checks"].append(check6)

    # Grade
    if report["total_issues"] == 0:
        report["grade"] = "A"
    elif report["total_issues"] <= 5:
        report["grade"] = "B"
    elif report["total_issues"] <= 20:
        report["grade"] = "C"
    else:
        report["grade"] = "D"

    return report


def main():
    parser = argparse.ArgumentParser(description="Check ad/metrics data integrity")
    parser.add_argument("--fix", action="store_true", help="Auto-fix orphaned records")
    parser.add_argument("--json-report", type=str, help="Export report to JSON")
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        report = run_checks(session, fix=args.fix)

        print("=" * 60)
        print("  Data Integrity Report")
        print("  %s" % report["checked_at"])
        print("=" * 60)

        for check in report["checks"]:
            icon = "OK" if check["severity"] == "ok" else "!!"
            print("\n  [%s] %s" % (icon, check["name"]))
            for k, v in check.items():
                if k not in ("name", "severity"):
                    print("      %s: %s" % (k, v))

        print("\n  Total issues: %d" % report["total_issues"])
        if report["fixed"] > 0:
            print("  Fixed: %d" % report["fixed"])
        print("  Grade: %s" % report["grade"])

        if args.json_report:
            os.makedirs(os.path.dirname(args.json_report) or ".", exist_ok=True)
            with open(args.json_report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print("\n  Exported: %s" % args.json_report)

        print()
    finally:
        session.close()


if __name__ == "__main__":
    main()
