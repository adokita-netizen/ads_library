"""Collect delivery date metrics for all ads.

Calculate days_running, estimated impressions, and estimated spend
based on first_seen_at / last_seen_at dates.  Ads still running
(last_seen_at is NULL) use today as the end date.

Estimation logic:
  - Base: 300 impressions/day
  - 30+ days: x1.5 (450/day) — advertiser sees ROI
  - 60+ days: x2.0 (600/day) — proven performer
  - 90+ days: x3.0 (900/day) — strong winner

Results are stored in ad_metadata and also update ad.impressions,
ad.spend, and ad.view_count columns.

Run from the backend directory:
    cd backend
    python scripts/collect_delivery_dates.py
"""

import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Config ────────────────────────────────────────────────────────

BATCH_SIZE = 10
CPM_JPY = 800  # Cost per 1000 impressions in JPY
BASE_DAILY_IMPRESSIONS = 300


# ── Estimation logic ──────────────────────────────────────────────

def estimate_daily_impressions(days_running: int) -> float:
    """Estimate daily impressions based on how long the ad has been running.

    Longer-running ads imply the advertiser is seeing positive ROI,
    so they likely have higher budgets and more impressions.
    """
    if days_running >= 90:
        return BASE_DAILY_IMPRESSIONS * 3.0   # 900/day
    elif days_running >= 60:
        return BASE_DAILY_IMPRESSIONS * 2.0   # 600/day
    elif days_running >= 30:
        return BASE_DAILY_IMPRESSIONS * 1.5   # 450/day
    else:
        return float(BASE_DAILY_IMPRESSIONS)  # 300/day


# ── Main ──────────────────────────────────────────────────────────

def main():
    session = SyncSessionLocal()
    now = datetime.now(timezone.utc)

    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Total ads: {total}")
        print()

        updated = 0
        skipped = 0

        # Accumulators for summary
        all_days = []
        still_running_count = 0
        days_30_plus = 0
        days_60_plus = 0
        days_90_plus = 0
        total_spend_jpy = 0.0

        for i, ad in enumerate(ads):
            # Determine date range
            start = ad.first_seen_at
            end = ad.last_seen_at

            if not start:
                # No first_seen_at — use created_at as fallback
                start = ad.created_at

            if not start:
                print(f"  [{i+1}/{total}] Ad {ad.id}: SKIP (no date info)")
                skipped += 1
                continue

            # Make timezone-aware if naive
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)

            is_still_running = end is None

            if end is None:
                end = now
            elif end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)

            # Calculate days running (minimum 1 day)
            delta = (end - start).days
            days_running = max(delta, 1)

            # Estimate metrics
            daily_impressions = estimate_daily_impressions(days_running)
            total_impressions = int(daily_impressions * days_running)
            total_spend = round(total_impressions * CPM_JPY / 1000)

            # Update ad_metadata
            meta = dict(ad.ad_metadata or {})
            meta["days_running"] = days_running
            meta["is_still_running"] = is_still_running
            meta["estimated_daily_impressions"] = int(daily_impressions)
            meta["estimated_total_impressions"] = total_impressions
            meta["estimated_total_spend_jpy"] = total_spend
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            # Update top-level columns
            ad.impressions = total_impressions
            ad.spend = float(total_spend)
            ad.view_count = total_impressions  # Use impressions as view_count proxy

            updated += 1

            # Accumulate stats
            all_days.append(days_running)
            if is_still_running:
                still_running_count += 1
            if days_running >= 30:
                days_30_plus += 1
            if days_running >= 60:
                days_60_plus += 1
            if days_running >= 90:
                days_90_plus += 1
            total_spend_jpy += total_spend

            status = "running" if is_still_running else "ended"
            print(f"  [{i+1}/{total}] Ad {ad.id}: {days_running}d ({status}) "
                  f"imp={total_impressions:,} spend={total_spend:,}JPY")

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                session.commit()

        # Final commit
        session.commit()

        # ── Summary ────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("  DELIVERY DATE METRICS - SUMMARY")
        print("=" * 60)
        print(f"  Total ads:                {total}")
        print(f"  Updated:                  {updated}")
        print(f"  Skipped (no date):        {skipped}")
        print()

        if all_days:
            avg_days = sum(all_days) / len(all_days)
            max_days = max(all_days)
            min_days = min(all_days)
            print(f"  Average days running:     {avg_days:.1f}")
            print(f"  Min days:                 {min_days}")
            print(f"  Max days:                 {max_days}")
        else:
            print(f"  Average days running:     N/A")

        print()
        print(f"  Still running:            {still_running_count}")
        print(f"  30+ days running:         {days_30_plus}")
        print(f"  60+ days running:         {days_60_plus}")
        print(f"  90+ days running:         {days_90_plus}")
        print()
        print(f"  Total estimated spend:    {total_spend_jpy:,.0f} JPY")
        print()

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
