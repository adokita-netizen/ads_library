"""A83 (CI-099): Prioritized data enrichment queue.

Identifies ads that need data enrichment and processes them in priority
order: higher-scoring ads and ads missing critical fields first.

Priority factors:
  1. Missing critical fields (no metrics, no creative_analysis) = highest
  2. Hit ads without full analysis = high
  3. Recent ads (last 7 days) = medium
  4. Remaining ads = low

Usage:
    python -m scripts.prioritized_enrichment --dry-run       # show queue only
    python -m scripts.prioritized_enrichment --limit 20      # process top 20
    python -m scripts.prioritized_enrichment                  # process all
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SyncSessionLocal


def build_priority_queue(session, limit: int | None = None) -> list[dict]:
    """Build a prioritized list of ads needing enrichment."""
    rows = session.execute(text("""
        WITH enrichment_status AS (
            SELECT
                a.id,
                a.advertiser_name,
                a.title,
                a.created_at,
                a.first_seen_at,
                CASE WHEN a.ad_metadata IS NULL THEN TRUE ELSE FALSE END as no_metadata,
                CASE WHEN a.ad_metadata->>'creative_analysis' IS NULL THEN TRUE ELSE FALSE END as no_creative,
                CASE WHEN a.ad_metadata->>'latest_hit_score' IS NULL THEN TRUE ELSE FALSE END as no_score,
                CASE WHEN a.ad_metadata->>'ranking_metrics' IS NULL THEN TRUE ELSE FALSE END as no_ranking,
                COALESCE((a.ad_metadata->>'latest_hit_score')::float, 0) as hit_score,
                COALESCE((a.ad_metadata->>'is_hit')::boolean, FALSE) as is_hit,
                (SELECT COUNT(*) FROM ad_daily_metrics m WHERE m.ad_id = a.id) as metric_count
            FROM ads a
        )
        SELECT id, advertiser_name, title, created_at, first_seen_at,
               no_metadata, no_creative, no_score, no_ranking,
               hit_score, is_hit, metric_count,
               CASE
                   WHEN no_metadata OR metric_count = 0 THEN 100
                   WHEN is_hit AND (no_creative OR no_ranking) THEN 80
                   WHEN no_creative OR no_score THEN 60
                   WHEN first_seen_at > NOW() - INTERVAL '7 days' THEN 40
                   ELSE 20
               END as priority
        FROM enrichment_status
        WHERE no_metadata OR no_creative OR no_score OR no_ranking OR metric_count = 0
        ORDER BY priority DESC, hit_score DESC, id
    """)).fetchall()

    queue = []
    for r in rows:
        missing = []
        if r[5]:
            missing.append("metadata")
        if r[6]:
            missing.append("creative_analysis")
        if r[7]:
            missing.append("hit_score")
        if r[8]:
            missing.append("ranking_metrics")
        if r[11] == 0:
            missing.append("daily_metrics")

        queue.append({
            "ad_id": r[0],
            "advertiser": r[1] or "",
            "title": (r[2] or "")[:40],
            "priority": r[12],
            "hit_score": float(r[9]),
            "metric_count": r[11],
            "missing": missing,
        })

    if limit:
        queue = queue[:limit]
    return queue


def process_enrichment(session, ad_id: int) -> dict:
    """Run enrichment for a single ad. Returns what was enriched."""
    from app.models.ad import Ad
    from sqlalchemy.orm.attributes import flag_modified

    ad = session.query(Ad).filter(Ad.id == ad_id).first()
    if not ad:
        return {"ad_id": ad_id, "status": "not_found"}

    enriched = []
    meta = dict(ad.ad_metadata or {})

    # Ensure ranking_metrics exists
    if "ranking_metrics" not in meta:
        meta["ranking_metrics"] = {
            "total_views": ad.view_count or 0,
            "view_increase": 0,
            "total_spend_jpy": float(ad.spend or 0),
            "spend_increase_jpy": 0,
            "like_increase": 0,
            "period": "daily",
            "aggregated_at": datetime.now(timezone.utc).isoformat(),
        }
        enriched.append("ranking_metrics")

    # Ensure basic metadata fields
    if "days_running" not in meta:
        if ad.first_seen_at and ad.last_seen_at:
            first = ad.first_seen_at if ad.first_seen_at.tzinfo else ad.first_seen_at.replace(tzinfo=timezone.utc)
            last = ad.last_seen_at if ad.last_seen_at.tzinfo else ad.last_seen_at.replace(tzinfo=timezone.utc)
            meta["days_running"] = max(1, (last - first).days)
        else:
            meta["days_running"] = 1
        enriched.append("days_running")

    if enriched:
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

    return {"ad_id": ad_id, "enriched": enriched}


def main():
    parser = argparse.ArgumentParser(description="Prioritized data enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Show queue without processing")
    parser.add_argument("--limit", type=int, help="Process only top N ads")
    args = parser.parse_args()

    print("=" * 60)
    print("  Prioritized Data Enrichment Queue")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        queue = build_priority_queue(session, limit=args.limit)

        print(f"\n  Ads needing enrichment: {len(queue)}")
        if not queue:
            print("  All ads are fully enriched!")
            return

        # Show priority distribution
        by_priority = {}
        for item in queue:
            p = item["priority"]
            by_priority[p] = by_priority.get(p, 0) + 1
        print("\n  Priority distribution:")
        for p in sorted(by_priority.keys(), reverse=True):
            label = {100: "CRITICAL", 80: "HIGH", 60: "MEDIUM", 40: "RECENT", 20: "LOW"}.get(p, str(p))
            print(f"    {label} ({p}): {by_priority[p]} ads")

        # Show top entries
        print(f"\n  Top {min(10, len(queue))} in queue:")
        for item in queue[:10]:
            print(f"    [P{item['priority']}] ad_id={item['ad_id']} "
                  f"score={item['hit_score']:.0f} missing={','.join(item['missing'])}")

        if args.dry_run:
            print("\n  DRY-RUN: No changes made.")
            return

        # Process
        print(f"\n  Processing {len(queue)} ads...")
        processed = 0
        enriched_total = 0
        for item in queue:
            result = process_enrichment(session, item["ad_id"])
            if result.get("enriched"):
                enriched_total += len(result["enriched"])
                processed += 1

        if processed > 0:
            session.commit()

        print(f"  Processed: {processed} ads")
        print(f"  Fields enriched: {enriched_total}")
        print("  Done!")

    except Exception as e:
        session.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
