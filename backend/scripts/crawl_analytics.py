#!/usr/bin/env python3
"""Analyze crawl history from DB.

Produces analytics:
  - Ads per day/week/month
  - New ads discovery rate
  - Genre distribution over time
  - Advertiser entry/exit tracking

Output: exports/crawl_analytics.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/crawl_analytics.py
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

EXPORTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exports")
)


def _ascii_bar(value: int, max_value: int, width: int = 40) -> str:
    """Generate an ASCII bar of given width."""
    if max_value <= 0:
        return ""
    filled = int(value / max_value * width)
    return "#" * filled


def main():
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.created_at).all()
        print("Loaded %d ads" % len(ads))

        if not ads:
            print("No ads found. Nothing to analyze.")
            return

        now = datetime.now(timezone.utc)

        # ── Daily counts ────────────────────────────────────────
        daily_counts: dict[str, int] = defaultdict(int)
        weekly_counts: dict[str, int] = defaultdict(int)
        monthly_counts: dict[str, int] = defaultdict(int)

        genre_by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        advertiser_first_seen: dict[str, str] = {}
        advertiser_last_seen: dict[str, str] = {}

        for ad in ads:
            if not ad.created_at:
                continue

            day_str = ad.created_at.strftime("%Y-%m-%d")
            week_str = ad.created_at.strftime("%Y-W%W")
            month_str = ad.created_at.strftime("%Y-%m")

            daily_counts[day_str] += 1
            weekly_counts[week_str] += 1
            monthly_counts[month_str] += 1

            # Genre distribution by month
            meta = ad.ad_metadata or {}
            genre = meta.get("fine_genre_en", "unknown")
            genre_by_month[month_str][genre] += 1

            # Advertiser tracking
            adv = ad.advertiser_name or "Unknown"
            if adv not in advertiser_first_seen or day_str < advertiser_first_seen[adv]:
                advertiser_first_seen[adv] = day_str
            if adv not in advertiser_last_seen or day_str > advertiser_last_seen[adv]:
                advertiser_last_seen[adv] = day_str

        # ── Discovery rate ──────────────────────────────────────
        # Last 7 days vs previous 7 days
        seven_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        fourteen_days_ago = (now - timedelta(days=14)).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")

        recent_7d = sum(v for k, v in daily_counts.items() if k >= seven_days_ago)
        previous_7d = sum(v for k, v in daily_counts.items()
                          if fourteen_days_ago <= k < seven_days_ago)
        discovery_trend = "increasing" if recent_7d > previous_7d else (
            "decreasing" if recent_7d < previous_7d else "stable"
        )

        # ── Advertiser entry/exit ───────────────────────────────
        new_advertisers_30d = []
        exited_advertisers = []
        thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

        for adv, first_seen in advertiser_first_seen.items():
            if first_seen >= thirty_days_ago:
                new_advertisers_30d.append({
                    "name": adv,
                    "first_seen": first_seen,
                })

        for adv, last_seen in advertiser_last_seen.items():
            if last_seen < thirty_days_ago:
                exited_advertisers.append({
                    "name": adv,
                    "last_seen": last_seen,
                })

        # ── Build output ────────────────────────────────────────
        # Sort daily counts for last 30 days
        recent_daily = sorted(
            [(k, v) for k, v in daily_counts.items() if k >= thirty_days_ago],
            key=lambda x: x[0]
        )

        report = {
            "generated_at": now.isoformat(),
            "summary": {
                "total_ads": len(ads),
                "total_days": len(daily_counts),
                "total_advertisers": len(advertiser_first_seen),
                "recent_7d_ads": recent_7d,
                "previous_7d_ads": previous_7d,
                "discovery_trend": discovery_trend,
                "new_advertisers_30d": len(new_advertisers_30d),
                "exited_advertisers": len(exited_advertisers),
            },
            "daily_counts": dict(sorted(daily_counts.items())),
            "weekly_counts": dict(sorted(weekly_counts.items())),
            "monthly_counts": dict(sorted(monthly_counts.items())),
            "genre_by_month": {k: dict(v) for k, v in sorted(genre_by_month.items())},
            "advertiser_tracking": {
                "new_30d": sorted(new_advertisers_30d, key=lambda x: x["first_seen"]),
                "exited": sorted(exited_advertisers, key=lambda x: x["last_seen"], reverse=True)[:50],
            },
        }

        output_path = os.path.join(EXPORTS_DIR, "crawl_analytics.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # ── Print summary with ASCII charts ─────────────────────
        print("\n=== Crawl Analytics Summary ===")
        print("Total ads: %d" % len(ads))
        print("Total days with data: %d" % len(daily_counts))
        print("Total advertisers: %d" % len(advertiser_first_seen))
        print("Discovery trend: %s (last 7d: %d, prev 7d: %d)" % (
            discovery_trend, recent_7d, previous_7d))

        # Daily chart (last 14 days)
        print("\nDaily Ads (last 14 days):")
        last_14 = recent_daily[-14:] if len(recent_daily) >= 14 else recent_daily
        if last_14:
            max_daily = max(v for _, v in last_14)
            for day_str, count in last_14:
                bar = _ascii_bar(count, max_daily, 40)
                print("  %s  %4d  %s" % (day_str, count, bar))

        # Monthly chart
        if monthly_counts:
            print("\nMonthly Ads:")
            sorted_monthly = sorted(monthly_counts.items())
            max_monthly = max(monthly_counts.values())
            for month_str, count in sorted_monthly[-6:]:
                bar = _ascii_bar(count, max_monthly, 40)
                print("  %s  %5d  %s" % (month_str, count, bar))

        # New advertisers
        if new_advertisers_30d:
            print("\nNew Advertisers (last 30 days): %d" % len(new_advertisers_30d))
            for entry in new_advertisers_30d[:10]:
                print("  + %s (since %s)" % (entry["name"][:40], entry["first_seen"]))

        print("\nOutput: %s" % output_path)

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
