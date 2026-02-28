#!/usr/bin/env python3
"""Monitor competitor advertisers for changes and new ads.

Reads watched advertisers from data/user_preferences.json (or uses top 20
by ad count). For each watched advertiser:
  - Count current ads, calculate avg score
  - Detect new ads in last 7 days
  - Detect score changes
Stores monitoring results in data/competitor_monitor.json.

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/monitor_competitors.py
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
)
PREFS_PATH = os.path.join(DATA_DIR, "user_preferences.json")
MONITOR_PATH = os.path.join(DATA_DIR, "competitor_monitor.json")


def _load_watched_advertisers() -> list[str] | None:
    """Load watched advertisers from user_preferences.json."""
    if not os.path.exists(PREFS_PATH):
        return None
    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        watched = prefs.get("watched_advertisers", [])
        if watched and isinstance(watched, list):
            return watched
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _load_previous_monitor() -> dict:
    """Load previous monitoring data for change detection."""
    if not os.path.exists(MONITOR_PATH):
        return {}
    try:
        with open(MONITOR_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print("Loaded %d ads" % len(ads))

        # Group ads by advertiser
        by_advertiser: dict[str, list[Ad]] = {}
        for ad in ads:
            name = ad.advertiser_name or "Unknown"
            if name not in by_advertiser:
                by_advertiser[name] = []
            by_advertiser[name].append(ad)

        # Determine watched advertisers
        watched = _load_watched_advertisers()
        if not watched:
            # Use top 20 by ad count
            sorted_advertisers = sorted(
                by_advertiser.items(), key=lambda x: len(x[1]), reverse=True
            )
            watched = [name for name, _ in sorted_advertisers[:20]]
            print("No watched advertisers configured, using top %d by ad count" % len(watched))
        else:
            print("Loaded %d watched advertisers from preferences" % len(watched))

        # Load previous data for change detection
        previous = _load_previous_monitor()
        prev_advertisers = {}
        if isinstance(previous, dict):
            for entry in previous.get("advertisers", []):
                if isinstance(entry, dict) and "name" in entry:
                    prev_advertisers[entry["name"]] = entry

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        results = []
        alerts = []

        for name in watched:
            ad_list = by_advertiser.get(name, [])
            if not ad_list:
                continue

            # Current stats
            total_ads = len(ad_list)
            scores = []
            new_ads_7d = 0

            for ad in ad_list:
                meta = ad.ad_metadata or {}
                try:
                    score = float(meta.get("latest_hit_score", 0) or 0)
                    if score > 0:
                        scores.append(score)
                except (ValueError, TypeError):
                    pass

                if ad.created_at and ad.created_at.replace(tzinfo=timezone.utc if ad.created_at.tzinfo is None else ad.created_at.tzinfo) >= seven_days_ago:
                    new_ads_7d += 1

            avg_score = round(sum(scores) / len(scores), 1) if scores else 0

            # Genre distribution
            genre_counts: dict[str, int] = {}
            for ad in ad_list:
                meta = ad.ad_metadata or {}
                genre = meta.get("fine_genre_en", "unknown")
                genre_counts[genre] = genre_counts.get(genre, 0) + 1

            # Compare with previous
            prev = prev_advertisers.get(name, {})
            prev_total = prev.get("total_ads", 0)
            prev_avg = prev.get("avg_score", 0)

            ad_count_change = total_ads - prev_total
            score_change = round(avg_score - prev_avg, 1) if prev_avg else 0

            # Generate alerts
            if new_ads_7d >= 5:
                alerts.append({
                    "type": "high_activity",
                    "advertiser": name,
                    "message": "%s launched %d new ads in the last 7 days" % (name, new_ads_7d),
                    "severity": "high" if new_ads_7d >= 10 else "medium",
                })

            if score_change >= 10:
                alerts.append({
                    "type": "score_increase",
                    "advertiser": name,
                    "message": "%s avg score increased by %.1f points" % (name, score_change),
                    "severity": "medium",
                })
            elif score_change <= -10:
                alerts.append({
                    "type": "score_decrease",
                    "advertiser": name,
                    "message": "%s avg score decreased by %.1f points" % (name, abs(score_change)),
                    "severity": "low",
                })

            entry = {
                "name": name,
                "total_ads": total_ads,
                "new_ads_7d": new_ads_7d,
                "avg_score": avg_score,
                "top_genres": dict(sorted(genre_counts.items(), key=lambda x: -x[1])[:5]),
                "ad_count_change": ad_count_change,
                "score_change": score_change,
            }
            results.append(entry)

        # Sort by total ads descending
        results.sort(key=lambda x: x["total_ads"], reverse=True)

        # Build output
        monitor_data = {
            "generated_at": now.isoformat(),
            "total_watched": len(watched),
            "total_with_ads": len(results),
            "alerts": alerts,
            "advertisers": results,
        }

        with open(MONITOR_PATH, "w", encoding="utf-8") as f:
            json.dump(monitor_data, f, ensure_ascii=False, indent=2)

        # Print summary
        print("\n=== Competitor Monitor Summary ===")
        print("Watched: %d advertisers" % len(watched))
        print("With ads: %d" % len(results))
        print("Alerts:   %d" % len(alerts))

        if alerts:
            print("\nAlerts:")
            for alert in alerts:
                severity_marker = {"high": "!!!", "medium": "!!", "low": "!"}.get(alert["severity"], "?")
                print("  [%s] %s" % (severity_marker, alert["message"]))

        print("\nTop Advertisers:")
        print("  %-30s %6s %6s %8s %8s" % ("Name", "Total", "New7d", "AvgScore", "Change"))
        print("  " + "-" * 68)
        for entry in results[:15]:
            name_display = entry["name"][:30] if entry["name"] else "Unknown"
            print("  %-30s %6d %6d %8.1f %+8.1f" % (
                name_display, entry["total_ads"], entry["new_ads_7d"],
                entry["avg_score"], entry["score_change"]
            ))

        print("\nOutput: %s" % MONITOR_PATH)

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
