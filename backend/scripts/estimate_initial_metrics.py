#!/usr/bin/env python3
"""Estimate initial metrics for ads without real-time tracking.

Estimates total_views from impressions/reach/estimated_daily_impressions.
Estimates total_spend_jpy from spend field or CPM calculation.
Estimates likes from like_count or engagement rate.

Stores results in ad_metadata["estimated_metrics"].
Sets ad_metadata["metrics_source"] = "estimated".

KEY FORMULA: spend = (views / 1000) * CPM_jpy

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/estimate_initial_metrics.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# Default CPM for Japanese market (JPY per 1000 impressions)
DEFAULT_CPM_JPY = 800.0

# Default daily impressions estimate when no data is available
DEFAULT_DAILY_IMPRESSIONS = 500

# Default engagement rate for estimating likes
DEFAULT_ENGAGEMENT_RATE = 0.005  # 0.5%


def _get_days_running(ad: Ad) -> int:
    """Compute total days an ad has been running."""
    meta = ad.ad_metadata or {}

    # Priority 1: days_running from metadata
    days = meta.get("days_running")
    if days and isinstance(days, (int, float)) and days > 0:
        return int(days)

    # Priority 2: estimated_days_running from metadata
    est_days = meta.get("estimated_days_running")
    if est_days and isinstance(est_days, (int, float)) and est_days > 0:
        return int(est_days)

    # Priority 3: Compute from first_seen_at / last_seen_at
    if ad.first_seen_at:
        end_dt = ad.last_seen_at or datetime.now(timezone.utc)
        start_dt = ad.first_seen_at
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        diff = (end_dt - start_dt).days
        return max(1, diff)

    return 1


def estimate_for_ad(ad: Ad) -> dict:
    """Estimate metrics for a single ad.

    Returns a dict to store in ad_metadata["estimated_metrics"].
    """
    meta = ad.ad_metadata or {}
    days_running = _get_days_running(ad)

    total_views = 0
    total_spend_jpy = 0.0
    total_likes = 0
    estimation_method = "default_estimated"

    # --- Estimate total_views ---
    # Priority 1: view_count field
    if ad.view_count and ad.view_count > 0:
        total_views = ad.view_count
        estimation_method = "view_count"
    # Priority 2: impressions field
    elif ad.impressions and ad.impressions > 0:
        total_views = ad.impressions
        estimation_method = "impressions"
    # Priority 3: reach field
    elif ad.reach and ad.reach > 0:
        total_views = ad.reach
        estimation_method = "reach"
    # Priority 4: estimated_daily_impressions * days_running
    else:
        daily_est = meta.get("estimated_daily_impressions")
        if daily_est and isinstance(daily_est, (int, float)) and daily_est > 0:
            total_views = int(daily_est * days_running)
            estimation_method = "daily_impressions_estimated"
        else:
            # Priority 5: audience-based estimation
            audience_imp = meta.get("impressions_from_audience")
            if audience_imp and isinstance(audience_imp, (int, float)) and audience_imp > 0:
                total_views = int(audience_imp)
                estimation_method = "audience_estimated"
            else:
                total_views = DEFAULT_DAILY_IMPRESSIONS * days_running
                estimation_method = "default_estimated"

    # --- Estimate total_spend_jpy ---
    # Priority 1: spend field directly
    if ad.spend and ad.spend > 0:
        total_spend_jpy = float(ad.spend)
    # Priority 2: estimated_spend_jpy from metadata
    elif meta.get("estimated_spend_jpy") and float(meta["estimated_spend_jpy"]) > 0:
        total_spend_jpy = float(meta["estimated_spend_jpy"])
    # Priority 3: CPM calculation: spend = (views / 1000) * CPM_jpy
    else:
        cpm = DEFAULT_CPM_JPY
        meta_cpm = meta.get("estimated_cpm_jpy")
        if meta_cpm and isinstance(meta_cpm, (int, float)) and meta_cpm > 0:
            cpm = float(meta_cpm)
        total_spend_jpy = (total_views / 1000.0) * cpm

    # --- Estimate likes ---
    if ad.like_count and ad.like_count > 0:
        total_likes = ad.like_count
    else:
        # Estimate at 0.5% engagement rate
        total_likes = int(total_views * DEFAULT_ENGAGEMENT_RATE)

    # --- Compute daily rates ---
    view_increase_daily = round(total_views / days_running) if days_running > 0 else 0
    spend_increase_daily_jpy = round(total_spend_jpy / days_running, 2) if days_running > 0 else 0.0
    like_increase_daily = round(total_likes / days_running, 1) if days_running > 0 else 0.0

    return {
        "total_views": total_views,
        "view_increase_daily": view_increase_daily,
        "estimated_total_spend_jpy": round(total_spend_jpy, 2),
        "spend_increase_daily_jpy": spend_increase_daily_jpy,
        "like_increase_daily": like_increase_daily,
        "total_likes": total_likes,
        "days_running": days_running,
        "estimation_method": estimation_method,
        "estimated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    print("=" * 60)
    print("Initial Metrics Estimator")
    print("KEY FORMULA: spend = (views / 1000) * CPM_jpy (default CPM=%d)" % int(DEFAULT_CPM_JPY))
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
        method_counter: dict[str, int] = {}
        total_views_sum = 0
        total_spend_sum = 0.0

        for ad in ads:
            est = estimate_for_ad(ad)

            meta = dict(ad.ad_metadata or {})
            meta["estimated_metrics"] = est
            meta["metrics_source"] = "estimated"
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            method = est["estimation_method"]
            method_counter[method] = method_counter.get(method, 0) + 1
            total_views_sum += est["total_views"]
            total_spend_sum += est["estimated_total_spend_jpy"]

        session.commit()
        print("\nUpdated %d/%d ads with estimated_metrics. Committed." % (updated, total))

        # Estimation method distribution
        print("\n--- Estimation Method Distribution ---")
        for method, count in sorted(method_counter.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            print("  %-28s: %4d (%5.1f%%)" % (method, count, pct))

        # Aggregate stats
        avg_views = total_views_sum / total if total > 0 else 0
        avg_spend = total_spend_sum / total if total > 0 else 0

        print("\n--- Aggregate Statistics ---")
        print("  Total estimated views:  %12s" % "{:,}".format(total_views_sum))
        print("  Total estimated spend:  %12s JPY" % "{:,.0f}".format(total_spend_sum))
        print("  Avg views per ad:       %12s" % "{:,.0f}".format(avg_views))
        print("  Avg spend per ad:       %12s JPY" % "{:,.0f}".format(avg_spend))

        # Top 10 by estimated views
        print("\n--- Top 10 Ads by Estimated Total Views ---")
        top_ads = sorted(
            [(ad, (ad.ad_metadata or {}).get("estimated_metrics", {}))
             for ad in ads],
            key=lambda x: x[1].get("total_views", 0),
            reverse=True,
        )[:10]
        for i, (ad, est) in enumerate(top_ads, 1):
            title_safe = (ad.title or "").encode("ascii", "replace").decode("ascii")[:40]
            views = est.get("total_views", 0)
            spend = est.get("estimated_total_spend_jpy", 0)
            method = est.get("estimation_method", "?")
            print("  %2d. [ID:%4d] views=%10s spend=%10s JPY (%s)" % (
                i, ad.id, "{:,}".format(views), "{:,.0f}".format(spend), method))
            print("      %s" % title_safe)

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("ERROR: %s" % e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
