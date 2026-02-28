#!/usr/bin/env python3
"""Take periodic snapshots of ad metrics (views, spend, likes).

Stores snapshots in ad_metadata["metrics_history"] (max 30 entries).
Computes daily and weekly deltas, stored in ad_metadata["current_deltas"].

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/snapshot_metrics.py
"""

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# Maximum number of snapshots to keep per ad
MAX_HISTORY = 30

# Default CPM (JPY per 1000 views) for spend estimation
DEFAULT_CPM_JPY = 800.0


def _get_current_metrics(ad: Ad) -> dict:
    """Extract current metrics from an ad record."""
    meta = ad.ad_metadata or {}
    est = meta.get("estimated_metrics", {})

    # Views: prefer view_count, then impressions, then estimated
    views = 0
    if ad.view_count and ad.view_count > 0:
        views = ad.view_count
    elif ad.impressions and ad.impressions > 0:
        views = ad.impressions
    elif est.get("total_views", 0) > 0:
        views = est["total_views"]

    # Spend: prefer spend field, then estimated
    spend_jpy = 0.0
    if ad.spend and ad.spend > 0:
        spend_jpy = float(ad.spend)
    elif est.get("estimated_total_spend_jpy", 0) > 0:
        spend_jpy = float(est["estimated_total_spend_jpy"])

    # Likes: prefer like_count field, then estimated
    likes = 0
    if ad.like_count and ad.like_count > 0:
        likes = ad.like_count

    return {
        "views": views,
        "spend_jpy": round(spend_jpy, 2),
        "likes": likes,
    }


def _compute_deltas(history: list) -> dict:
    """Compute daily and weekly deltas from metrics history.

    history is sorted newest-first.
    """
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if len(history) < 2:
        return {
            "view_increase_daily": 0,
            "spend_increase_daily_jpy": 0.0,
            "like_increase_daily": 0,
            "view_increase_weekly": 0,
            "spend_increase_weekly_jpy": 0.0,
            "snapshot_date": today_str,
        }

    latest = history[0]
    previous = history[1]

    # Daily delta (latest vs previous)
    view_increase_daily = max(0, latest["views"] - previous["views"])
    spend_increase_daily = max(0.0, latest["spend_jpy"] - previous["spend_jpy"])
    like_increase_daily = max(0, latest["likes"] - previous["likes"])

    # Weekly delta: find snapshot ~7 days ago
    view_increase_weekly = view_increase_daily
    spend_increase_weekly = spend_increase_daily

    if len(history) >= 7:
        week_ago = history[min(6, len(history) - 1)]
        view_increase_weekly = max(0, latest["views"] - week_ago["views"])
        spend_increase_weekly = max(0.0, latest["spend_jpy"] - week_ago["spend_jpy"])
    elif len(history) >= 2:
        oldest = history[-1]
        view_increase_weekly = max(0, latest["views"] - oldest["views"])
        spend_increase_weekly = max(0.0, latest["spend_jpy"] - oldest["spend_jpy"])

    return {
        "view_increase_daily": view_increase_daily,
        "spend_increase_daily_jpy": round(spend_increase_daily, 2),
        "like_increase_daily": like_increase_daily,
        "view_increase_weekly": view_increase_weekly,
        "spend_increase_weekly_jpy": round(spend_increase_weekly, 2),
        "snapshot_date": today_str,
    }


def main() -> None:
    print("=" * 60)
    print("Metrics Snapshot (views, spend, likes)")
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

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        updated = 0
        skipped_same_day = 0
        total_view_increase = 0
        total_spend_increase = 0.0

        for ad in ads:
            current = _get_current_metrics(ad)
            meta = dict(ad.ad_metadata or {})

            # Get existing history
            history = list(meta.get("metrics_history", []))

            # Skip if already snapshot today
            if history and history[0].get("date") == today_str:
                skipped_same_day += 1
                continue

            # Create new snapshot entry
            snapshot = {
                "date": today_str,
                "views": current["views"],
                "spend_jpy": current["spend_jpy"],
                "likes": current["likes"],
            }

            # Prepend new snapshot (newest first)
            history.insert(0, snapshot)

            # Cap at MAX_HISTORY
            if len(history) > MAX_HISTORY:
                history = history[:MAX_HISTORY]

            meta["metrics_history"] = history

            # Compute deltas
            deltas = _compute_deltas(history)
            meta["current_deltas"] = deltas

            total_view_increase += deltas["view_increase_daily"]
            total_spend_increase += deltas["spend_increase_daily_jpy"]

            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

        session.commit()

        # Summary
        print("\n--- Snapshot Results ---")
        print("  Ads updated with new snapshot: %d" % updated)
        print("  Skipped (already snapshot today): %d" % skipped_same_day)
        if updated > 0:
            avg_view_inc = total_view_increase / updated
            avg_spend_inc = total_spend_increase / updated
            print("  Avg daily view increase: %.0f" % avg_view_inc)
            print("  Avg daily spend increase: %.2f JPY" % avg_spend_inc)

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("ERROR: %s" % e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
