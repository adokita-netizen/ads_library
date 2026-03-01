#!/usr/bin/env python3
"""Aggregate metrics for the pro ranking table.

Computes final ranking_metrics per ad using the best available data
from metrics_history, current_deltas, and estimated_metrics.

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/aggregate_metrics.py
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.core.distributed_lock import acquire_distributed_lock, release_distributed_lock
from app.models.ad import Ad


def _best_total_views(ad):
    meta = ad.ad_metadata or {}
    history = meta.get("metrics_history", [])
    if history and history[0].get("views", 0) > 0:
        return history[0]["views"]
    est = meta.get("estimated_metrics", {})
    if est.get("total_views", 0) > 0:
        return est["total_views"]
    if ad.view_count and ad.view_count > 0:
        return ad.view_count
    if ad.impressions and ad.impressions > 0:
        return ad.impressions
    return 0


def _best_total_spend(ad):
    meta = ad.ad_metadata or {}
    history = meta.get("metrics_history", [])
    if history and history[0].get("spend_jpy", 0) > 0:
        return float(history[0]["spend_jpy"])
    est = meta.get("estimated_metrics", {})
    if est.get("estimated_total_spend_jpy", 0) > 0:
        return float(est["estimated_total_spend_jpy"])
    if ad.spend and ad.spend > 0:
        return float(ad.spend)
    return 0.0


def _best_view_increase(ad):
    meta = ad.ad_metadata or {}
    deltas = meta.get("current_deltas", {})
    if deltas.get("view_increase_daily", 0) > 0:
        return deltas["view_increase_daily"]
    est = meta.get("estimated_metrics", {})
    if est.get("view_increase_daily", 0) > 0:
        return int(est["view_increase_daily"])
    return 0


def _best_spend_increase(ad):
    meta = ad.ad_metadata or {}
    deltas = meta.get("current_deltas", {})
    if deltas.get("spend_increase_daily_jpy", 0) > 0:
        return float(deltas["spend_increase_daily_jpy"])
    est = meta.get("estimated_metrics", {})
    if est.get("spend_increase_daily_jpy", 0) > 0:
        return float(est["spend_increase_daily_jpy"])
    return 0.0


def _best_like_increase(ad):
    meta = ad.ad_metadata or {}
    deltas = meta.get("current_deltas", {})
    if deltas.get("like_increase_daily", 0) > 0:
        return deltas["like_increase_daily"]
    est = meta.get("estimated_metrics", {})
    if est.get("like_increase_daily", 0) > 0:
        return int(est["like_increase_daily"])
    return 0


def main():
    _lock_token = acquire_distributed_lock("aggregate_metrics", ttl=600)
    if _lock_token is None:
        print("SKIPPED: aggregate_metrics is already running.")
        return

    print("=" * 60)
    print("Metrics Aggregation for Ranking Table")
    print("Executed at: %s" % datetime.now(timezone.utc).isoformat())
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print("\nTotal ads in database: %d" % total)

        if total == 0:
            print("No ads found. Exiting.")
            return

        updated = 0
        total_views_sum = 0
        total_spend_sum = 0.0
        has_view_increase = 0
        has_spend_increase = 0

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        skipped_same_day = 0

        for ad in ads:
            # Idempotency guard: skip if already aggregated today
            existing_rm = (ad.ad_metadata or {}).get("ranking_metrics", {})
            existing_at = existing_rm.get("aggregated_at", "")
            if existing_at and existing_at[:10] == today_str:
                skipped_same_day += 1
                # Still count for stats
                total_views_sum += existing_rm.get("total_views", 0)
                total_spend_sum += existing_rm.get("total_spend_jpy", 0)
                if existing_rm.get("view_increase", 0) > 0:
                    has_view_increase += 1
                if existing_rm.get("spend_increase_jpy", 0) > 0:
                    has_spend_increase += 1
                continue

            tv = _best_total_views(ad)
            ts = _best_total_spend(ad)
            vi = _best_view_increase(ad)
            si = _best_spend_increase(ad)
            li = _best_like_increase(ad)

            ranking_metrics = {
                "total_views": tv,
                "view_increase": vi,
                "total_spend_jpy": round(ts, 2),
                "spend_increase_jpy": round(si, 2),
                "like_increase": li,
                "period": "daily",
                "aggregated_at": datetime.now(timezone.utc).isoformat(),
            }

            meta = dict(ad.ad_metadata or {})
            meta["ranking_metrics"] = ranking_metrics
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            total_views_sum += tv
            total_spend_sum += ts
            if vi > 0:
                has_view_increase += 1
            if si > 0:
                has_spend_increase += 1

        session.commit()
        print("\nUpdated %d/%d ads with ranking_metrics. Committed." % (updated, total))
        if skipped_same_day > 0:
            print("Skipped %d ads (already aggregated today %s)." % (skipped_same_day, today_str))

        avg_views = total_views_sum / total if total > 0 else 0
        avg_spend = total_spend_sum / total if total > 0 else 0

        print("\n--- Aggregate Statistics ---")
        print("  Total views (all ads):   %s" % "{:,}".format(total_views_sum))
        print("  Total spend (all ads):   %s JPY" % "{:,.0f}".format(total_spend_sum))
        print("  Avg views per ad:        %s" % "{:,.0f}".format(avg_views))
        print("  Avg spend per ad:        %s JPY" % "{:,.0f}".format(avg_spend))
        vi_pct = has_view_increase * 100 // total if total else 0
        si_pct = has_spend_increase * 100 // total if total else 0
        print("  Ads with view increase:  %d (%d%%)" % (has_view_increase, vi_pct))
        print("  Ads with spend increase: %d (%d%%)" % (has_spend_increase, si_pct))

        # View increase distribution
        print("\n--- View Increase Distribution ---")
        buckets = {"0": 0, "1-100": 0, "101-1K": 0, "1K-10K": 0, "10K-100K": 0, "100K+": 0}
        for ad in ads:
            v = (ad.ad_metadata or {}).get("ranking_metrics", {}).get("view_increase", 0)
            if v == 0:
                buckets["0"] += 1
            elif v <= 100:
                buckets["1-100"] += 1
            elif v <= 1000:
                buckets["101-1K"] += 1
            elif v <= 10000:
                buckets["1K-10K"] += 1
            elif v <= 100000:
                buckets["10K-100K"] += 1
            else:
                buckets["100K+"] += 1

        for bucket, count in buckets.items():
            pct = count / total * 100 if total else 0
            bar = "#" * int(pct / 2)
            print("  %10s: %4d (%5.1f%%) %s" % (bucket, count, pct, bar))

        # Top 10 by total views
        print("\n--- Top 10 Ads by Total Views ---")
        ranked = sorted(
            ads,
            key=lambda a: (a.ad_metadata or {}).get("ranking_metrics", {}).get("total_views", 0),
            reverse=True,
        )[:10]
        for i, ad in enumerate(ranked, 1):
            rm = (ad.ad_metadata or {}).get("ranking_metrics", {})
            title_safe = (ad.title or "").encode("ascii", "replace").decode("ascii")[:40]
            print("  %2d. [ID:%4d] views=%10s  vi=%8s  spend=%10s JPY" % (
                i, ad.id,
                "{:,}".format(rm.get("total_views", 0)),
                "{:,}".format(rm.get("view_increase", 0)),
                "{:,.0f}".format(rm.get("total_spend_jpy", 0)),
            ))
            print("      %s" % title_safe)

        # Export summary
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports"
        )
        os.makedirs(export_dir, exist_ok=True)
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "total_views_all": total_views_sum,
            "total_spend_all_jpy": round(total_spend_sum, 2),
            "avg_views_per_ad": round(avg_views),
            "avg_spend_per_ad_jpy": round(avg_spend, 2),
            "ads_with_view_increase": has_view_increase,
            "ads_with_spend_increase": has_spend_increase,
        }
        out_path = os.path.join(export_dir, "ranking_metrics_summary.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print("\n  Exported: %s" % out_path)
        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("ERROR: %s" % e)
        raise
    finally:
        session.close()
        release_distributed_lock("aggregate_metrics", _lock_token)


if __name__ == "__main__":
    main()
