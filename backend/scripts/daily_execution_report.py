"""A91 (CI-127): Unified daily execution report.

Consolidates key daily metrics into a single report:
  - Collection: how many ads/metrics were collected today
  - Key extraction: metadata quality (creative analysis, keywords)
  - Hit determination: hit scores and hit/non-hit breakdown
  - Data quality: integrity check summary

Usage:
    python -m scripts.daily_execution_report
    python -m scripts.daily_execution_report --date 2026-03-01
    python -m scripts.daily_execution_report --json exports/daily_report.json
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SyncSessionLocal
from app.services.data_quality_report import build_japanese_inventory_audit, build_numeric_truth_audit


def build_report(session, target_date: date) -> dict:
    """Build a comprehensive daily execution report."""
    report = {
        "report_date": str(target_date),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": {},
    }

    # ── 1. Collection Summary ────────────────────────────────────
    collection = {}
    collection["total_ads"] = session.execute(text("SELECT COUNT(*) FROM ads")).scalar()
    collection["metrics_today"] = session.execute(text(
        "SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = :d"
    ), {"d": target_date}).scalar()
    collection["metrics_yesterday"] = session.execute(text(
        "SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = :d - 1"
    ), {"d": target_date}).scalar()

    # New ads today
    collection["new_ads_today"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE DATE(created_at) = :d"
    ), {"d": target_date}).scalar()

    # Coverage
    collection["coverage_pct"] = round(
        collection["metrics_today"] / collection["total_ads"] * 100, 1
    ) if collection["total_ads"] else 0

    report["sections"]["collection"] = collection

    # ── 2. Key Extraction Quality ────────────────────────────────
    extraction = {}
    extraction["with_creative_analysis"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE ad_metadata->>'creative_analysis' IS NOT NULL"
    )).scalar()
    extraction["with_keywords"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE ad_metadata->>'keywords' IS NOT NULL"
    )).scalar()
    extraction["with_ranking_metrics"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE ad_metadata->>'ranking_metrics' IS NOT NULL"
    )).scalar()
    extraction["with_destination_url"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE destination_url IS NOT NULL AND destination_url != ''"
    )).scalar()

    total = collection["total_ads"]
    extraction["creative_pct"] = round(extraction["with_creative_analysis"] / total * 100, 1) if total else 0
    extraction["keywords_pct"] = round(extraction["with_keywords"] / total * 100, 1) if total else 0

    report["sections"]["extraction"] = extraction

    # ── 3. Hit Determination ─────────────────────────────────────
    hit_det = {}
    hit_det["with_score"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE ad_metadata->>'latest_hit_score' IS NOT NULL"
    )).scalar()
    hit_det["hit_ads"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE (ad_metadata->>'is_hit')::boolean = true"
    )).scalar()
    hit_det["non_hit"] = hit_det["with_score"] - hit_det["hit_ads"]
    hit_det["hit_rate_pct"] = round(
        hit_det["hit_ads"] / hit_det["with_score"] * 100, 1
    ) if hit_det["with_score"] else 0

    # Score distribution
    score_dist = session.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE (ad_metadata->>'latest_hit_score')::float >= 80) as excellent,
            COUNT(*) FILTER (WHERE (ad_metadata->>'latest_hit_score')::float >= 60
                                AND (ad_metadata->>'latest_hit_score')::float < 80) as good,
            COUNT(*) FILTER (WHERE (ad_metadata->>'latest_hit_score')::float >= 40
                                AND (ad_metadata->>'latest_hit_score')::float < 60) as average,
            COUNT(*) FILTER (WHERE (ad_metadata->>'latest_hit_score')::float < 40) as low
        FROM ads
        WHERE ad_metadata->>'latest_hit_score' IS NOT NULL
    """)).fetchone()

    hit_det["score_distribution"] = {
        "excellent_80+": score_dist[0],
        "good_60_79": score_dist[1],
        "average_40_59": score_dist[2],
        "low_under_40": score_dist[3],
    }

    # Top 5 by score today
    top5 = session.execute(text("""
        SELECT a.id, a.advertiser_name,
               (a.ad_metadata->>'latest_hit_score')::float as score,
               m.view_count_increase, m.estimated_spend_increase
        FROM ads a
        LEFT JOIN ad_daily_metrics m ON a.id = m.ad_id AND m.metric_date = :d
        WHERE a.ad_metadata->>'latest_hit_score' IS NOT NULL
        ORDER BY score DESC
        LIMIT 5
    """), {"d": target_date}).fetchall()

    hit_det["top5_today"] = [{
        "ad_id": r[0], "advertiser": r[1] or "",
        "score": float(r[2]),
        "view_increase": r[3] or 0,
        "spend_increase": float(r[4]) if r[4] else 0,
    } for r in top5]

    report["sections"]["hit_determination"] = hit_det

    # ── 4. Data Quality Summary ──────────────────────────────────
    quality = {}
    quality["orphaned_metrics"] = session.execute(text("""
        SELECT COUNT(*) FROM ad_daily_metrics m
        LEFT JOIN ads a ON m.ad_id = a.id WHERE a.id IS NULL
    """)).scalar()
    quality["negative_values"] = session.execute(text("""
        SELECT COUNT(*) FROM ad_daily_metrics
        WHERE view_count < 0 OR estimated_spend < 0
    """)).scalar()
    quality["null_metadata"] = session.execute(text(
        "SELECT COUNT(*) FROM ads WHERE ad_metadata IS NULL"
    )).scalar()

    issues = quality["orphaned_metrics"] + quality["negative_values"]
    quality["grade"] = "A" if issues == 0 else "B" if issues <= 5 else "C" if issues <= 20 else "D"

    report["sections"]["data_quality"] = quality

    numeric_truth = build_numeric_truth_audit(session, target_date=target_date, top_n=5)
    japanese_inventory = build_japanese_inventory_audit(session, target_date=target_date, top_n=5)
    report["sections"]["numeric_truth"] = {
        "estimated_only_count": numeric_truth["summary"]["estimated_only_count"],
        "missing_numeric_count": numeric_truth["summary"]["missing_numeric_count"],
        "stale_real_metrics_count": numeric_truth["summary"]["stale_real_metrics_count"],
        "spend": numeric_truth["summary"]["fields"]["spend"],
        "view_count": numeric_truth["summary"]["fields"]["view_count"],
        "lp_score": numeric_truth["summary"]["fields"]["lp_score"],
        "priority_backfill_targets": numeric_truth["priority_backfill_targets"][:5],
    }
    report["sections"]["japanese_inventory"] = {
        "jp_rate": japanese_inventory["summary"]["jp_rate"],
        "non_jp_rate": japanese_inventory["summary"]["non_jp_rate"],
        "unknown_rate": japanese_inventory["summary"]["unknown_rate"],
        "manual_review_count": japanese_inventory["summary"]["manual_review_count"],
        "coverage": japanese_inventory["summary"]["coverage"],
        "manual_review_queue": japanese_inventory["manual_review_queue"][:5],
    }

    return report


def print_report(report: dict):
    """Pretty-print the daily report."""
    c = report["sections"]["collection"]
    e = report["sections"]["extraction"]
    h = report["sections"]["hit_determination"]
    q = report["sections"]["data_quality"]
    n = report["sections"]["numeric_truth"]
    j = report["sections"]["japanese_inventory"]

    print(f"\n  1. COLLECTION")
    print(f"     Total ads:        {c['total_ads']}")
    print(f"     Metrics today:    {c['metrics_today']} ({c['coverage_pct']}% coverage)")
    print(f"     Metrics yesterday:{c['metrics_yesterday']}")
    print(f"     New ads today:    {c['new_ads_today']}")

    print(f"\n  2. KEY EXTRACTION")
    print(f"     Creative analysis: {e['with_creative_analysis']}/{c['total_ads']} ({e['creative_pct']}%)")
    print(f"     Keywords:          {e['with_keywords']}/{c['total_ads']} ({e['keywords_pct']}%)")
    print(f"     Ranking metrics:   {e['with_ranking_metrics']}/{c['total_ads']}")
    print(f"     Destination URL:   {e['with_destination_url']}/{c['total_ads']}")

    print(f"\n  3. HIT DETERMINATION")
    print(f"     Scored ads:  {h['with_score']}")
    print(f"     Hit ads:     {h['hit_ads']} ({h['hit_rate_pct']}%)")
    dist = h["score_distribution"]
    print(f"     Score dist:  80+={dist['excellent_80+']}  60-79={dist['good_60_79']}  "
          f"40-59={dist['average_40_59']}  <40={dist['low_under_40']}")
    if h["top5_today"]:
        print(f"     Top 5 today:")
        for t in h["top5_today"]:
            print(f"       #{t['ad_id']} score={t['score']:.0f} vi={t['view_increase']} "
                  f"{t['advertiser'][:25]}")

    print(f"\n  4. DATA QUALITY: Grade {q['grade']}")
    print(f"     Orphaned metrics: {q['orphaned_metrics']}")
    print(f"     Negative values:  {q['negative_values']}")
    print(f"     NULL metadata:    {q['null_metadata']}")

    print(f"\n  5. NUMERIC TRUTH")
    print(f"     Estimated only:   {n['estimated_only_count']}")
    print(f"     Missing numeric:  {n['missing_numeric_count']}")
    print(f"     Stale real:       {n['stale_real_metrics_count']}")
    print(f"     Spend coverage:   real={n['spend']['real_count']} est={n['spend']['estimated_count']} miss={n['spend']['missing_count']}")
    print(f"     View coverage:    real={n['view_count']['real_count']} est={n['view_count']['estimated_count']} miss={n['view_count']['missing_count']}")
    print(f"     LP score cover.:  real={n['lp_score']['real_count']} miss={n['lp_score']['missing_count']}")

    print(f"\n  6. JAPANESE INVENTORY")
    print(f"     JP rate:          {j['jp_rate']:.1%}")
    print(f"     Non-JP rate:      {j['non_jp_rate']:.1%}")
    print(f"     Unknown rate:     {j['unknown_rate']:.1%}")
    print(f"     Manual review:    {j['manual_review_count']}")


def main():
    parser = argparse.ArgumentParser(description="Daily execution report")
    parser.add_argument("--date", type=str, help="Report date (YYYY-MM-DD, default: today)")
    parser.add_argument("--json", type=str, help="Export report to JSON file")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()

    print("=" * 60)
    print("  Daily Execution Report")
    print(f"  Date: {target_date}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        report = build_report(session, target_date)
        print_report(report)

        if args.json:
            os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n  Exported: {args.json}")

        print()

    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
