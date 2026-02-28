#!/usr/bin/env python3
"""Estimate total views, spend, and daily rates for all ads.

For ads WITH existing metrics (impressions, spend, reach), computes:
  - estimated_total_views, view_increase_daily
  - estimated_total_spend_jpy, spend_increase_daily_jpy
  - like_increase_daily

For ads WITHOUT metrics, estimates from:
  - duration_days * estimated_daily_impressions (from metadata)
  - estimated_cpm_jpy * impressions / 1000

Stores results in ad_metadata["estimated_metrics"].

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/estimate_metrics.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics


# Default CPM for estimation when no real data is available (JPY)
DEFAULT_CPM_JPY = 400.0
# Default daily impressions estimate when no data is available
DEFAULT_DAILY_IMPRESSIONS = 500


def _get_days_running(ad: Ad) -> int:
    """Compute total days an ad has been running."""
    meta = ad.ad_metadata or {}

    # Priority 1: days_running from metadata (computed by collect_delivery_dates.py)
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
        # Ensure timezone-aware
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        diff = (end_dt - start_dt).days
        return max(1, diff)

    return 1


def estimate_metrics(ad: Ad, ad_daily_metrics: list) -> dict:
    """Estimate metrics for a single ad.

    Returns a dict to be stored in ad_metadata["estimated_metrics"].
    """
    meta = ad.ad_metadata or {}
    days_running = _get_days_running(ad)

    # ── Gather existing data ──────────────────────────────────────
    total_views = 0
    total_spend = 0.0
    total_likes = 0
    has_real_views = False
    has_real_spend = False
    estimation_method = "inferred"

    # Option A: Use AdDailyMetrics (most accurate)
    if ad_daily_metrics:
        for m in ad_daily_metrics:
            total_views += (m.view_count or 0)
            total_spend += (m.estimated_spend or 0.0)
            total_likes += (m.like_count or 0)
        if total_views > 0:
            has_real_views = True
            estimation_method = "daily_metrics"
        if total_spend > 0:
            has_real_spend = True

    # Option B: Use ad-level fields
    if not has_real_views:
        if ad.view_count and ad.view_count > 0:
            total_views = ad.view_count
            has_real_views = True
            estimation_method = "ad_view_count"
        elif ad.impressions and ad.impressions > 0:
            total_views = ad.impressions
            has_real_views = True
            estimation_method = "ad_impressions"
        elif ad.reach and ad.reach > 0:
            total_views = ad.reach
            has_real_views = True
            estimation_method = "ad_reach"

    if not has_real_spend:
        if ad.spend and ad.spend > 0:
            total_spend = ad.spend
            has_real_spend = True

    # Option C: Use metadata estimates
    if not has_real_views:
        meta_impressions = meta.get("impressions_from_audience")
        if meta_impressions and isinstance(meta_impressions, (int, float)) and meta_impressions > 0:
            total_views = int(meta_impressions)
            has_real_views = True
            estimation_method = "audience_estimated"

    if not has_real_spend:
        meta_spend = meta.get("estimated_spend_jpy")
        if meta_spend and isinstance(meta_spend, (int, float)) and meta_spend > 0:
            total_spend = float(meta_spend)
            has_real_spend = True

    # ── Estimate missing values ───────────────────────────────────

    # If still no views, estimate from days_running
    if not has_real_views:
        daily_est = meta.get("estimated_daily_impressions")
        if daily_est and isinstance(daily_est, (int, float)):
            total_views = int(daily_est * days_running)
        else:
            total_views = DEFAULT_DAILY_IMPRESSIONS * days_running
        estimation_method = "default_estimated"

    # If still no spend, estimate from CPM
    if not has_real_spend:
        cpm = meta.get("estimated_cpm_jpy")
        if cpm and isinstance(cpm, (int, float)):
            total_spend = float(cpm * total_views / 1000.0)
        else:
            total_spend = float(DEFAULT_CPM_JPY * total_views / 1000.0)

    # ── Compute daily rates ───────────────────────────────────────
    view_increase_daily = round(total_views / days_running) if days_running > 0 else 0
    spend_increase_daily = round(total_spend / days_running, 2) if days_running > 0 else 0.0

    # Like increase daily
    if total_likes > 0 and days_running > 0:
        like_increase_daily = round(total_likes / days_running, 1)
    elif ad.like_count and ad.like_count > 0 and days_running > 0:
        like_increase_daily = round(ad.like_count / days_running, 1)
    else:
        like_increase_daily = 0

    return {
        "total_views": total_views,
        "view_increase_daily": view_increase_daily,
        "estimated_total_spend_jpy": round(total_spend, 2),
        "spend_increase_daily_jpy": spend_increase_daily,
        "like_increase_daily": like_increase_daily,
        "days_running": days_running,
        "estimation_method": estimation_method,
        "estimated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    print("=" * 60)
    print("Metrics Estimator (Views, Spend, Daily Rates)")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Pre-fetch all daily metrics
        all_metrics = session.query(AdDailyMetrics).all()
        metrics_by_ad: dict[int, list] = {}
        for m in all_metrics:
            metrics_by_ad.setdefault(m.ad_id, []).append(m)
        print(f"Loaded {len(all_metrics)} daily metric rows for {len(metrics_by_ad)} ads")

        # Process each ad
        updated = 0
        method_counter: dict[str, int] = {}
        total_views_sum = 0
        total_spend_sum = 0.0

        for ad in ads:
            ad_metrics = metrics_by_ad.get(ad.id, [])
            est = estimate_metrics(ad, ad_metrics)

            meta = dict(ad.ad_metadata or {})
            meta["estimated_metrics"] = est
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            method = est["estimation_method"]
            method_counter[method] = method_counter.get(method, 0) + 1
            total_views_sum += est["total_views"]
            total_spend_sum += est["estimated_total_spend_jpy"]

        session.commit()
        print(f"\nUpdated {updated}/{total} ads with estimated_metrics. Committed.")

        # Print estimation method distribution
        print(f"\n--- Estimation Method Distribution ---")
        for method, count in sorted(method_counter.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            print(f"  {method:<25s}: {count:>4d} ({pct:>5.1f}%)")

        # Print aggregate stats
        avg_views = total_views_sum / total if total > 0 else 0
        avg_spend = total_spend_sum / total if total > 0 else 0

        print(f"\n--- Aggregate Statistics ---")
        print(f"  Total estimated views:  {total_views_sum:>12,}")
        print(f"  Total estimated spend:  {total_spend_sum:>12,.0f} JPY")
        print(f"  Avg views per ad:       {avg_views:>12,.0f}")
        print(f"  Avg spend per ad:       {avg_spend:>12,.0f} JPY")

        # Print top 10 by estimated views
        print(f"\n--- Top 10 Ads by Estimated Total Views ---")
        top_ads = sorted(
            [(ad, (ad.ad_metadata or {}).get("estimated_metrics", {}))
             for ad in ads],
            key=lambda x: x[1].get("total_views", 0),
            reverse=True,
        )[:10]
        for i, (ad, est) in enumerate(top_ads, 1):
            title_safe = (ad.title or "")[:40].encode("ascii", "replace").decode("ascii")
            views = est.get("total_views", 0)
            spend = est.get("estimated_total_spend_jpy", 0)
            method = est.get("estimation_method", "?")
            print(f"  {i:>2d}. [ID:{ad.id:>4d}] views={views:>10,} spend={spend:>10,.0f} JPY ({method})")
            print(f"      {title_safe}")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
