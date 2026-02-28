#!/usr/bin/env python3
"""Trend velocity tracker - genre growth rates and trajectory classification.

For each genre (fine_genre from ad_metadata), calculates:
  - Ad growth rate (ads per week, trend direction via linear regression slope)
  - Score trajectory (improving / declining / stable)
  - Spend trajectory (increasing / decreasing / stable)
  - New entrant rate (new advertisers per week)

Classifies each genre: rapid_growth, stable, declining, emerging.

Exports to backend/exports/trend_velocity.json.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/track_trend_velocity.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_score(ad):
    """Extract latest_hit_score from ad_metadata, default 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _get_genre(ad):
    """Extract fine_genre from ad_metadata, default 'other'."""
    meta = ad.ad_metadata or {}
    return meta.get("fine_genre") or meta.get("fine_genre_en") or "other"


def _week_key(dt):
    """Return ISO week string like '2026-W09'.  None -> 'unknown'."""
    if dt is None:
        return "unknown"
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def linear_regression_slope(values):
    """Pure-Python simple linear regression slope.

    Given a list of y-values (indexed 0..n-1), returns the OLS slope.
    Positive = growing, negative = declining, 0 = flat or insufficient data.
    """
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def classify_genre(growth_slope, score_slope, total_ads):
    """Classify genre lifecycle status.

    - emerging:      very few ads (<=3), too early to judge
    - rapid_growth:  ad volume growing fast (slope > 0.5)
    - declining:     ad volume shrinking (slope < -0.5)
    - stable:        everything else
    """
    if total_ads <= 3:
        return "emerging"
    if growth_slope > 0.5:
        return "rapid_growth"
    if growth_slope < -0.5:
        return "declining"
    return "stable"


def _score_trend_label(slope):
    """Human-readable score trajectory label."""
    if slope > 1.0:
        return "improving"
    if slope < -1.0:
        return "declining"
    return "stable"


def _spend_trend_label(slope):
    """Human-readable spend trajectory label."""
    if slope > 100.0:
        return "increasing"
    if slope < -100.0:
        return "decreasing"
    return "stable"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Trend Velocity Tracker")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads loaded: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ------------------------------------------------------------------
        # 1. Group ads by genre and ISO week
        # ------------------------------------------------------------------
        genre_weekly = defaultdict(lambda: defaultdict(lambda: {
            "ad_count": 0,
            "scores": [],
            "spends": [],
            "advertisers": set(),
        }))

        # Track per-genre which advertisers first appear in each week
        genre_week_advertisers = defaultdict(lambda: defaultdict(set))

        for ad in ads:
            genre = _get_genre(ad)
            first_seen = ad.first_seen_at or ad.created_at
            week = _week_key(first_seen)

            bucket = genre_weekly[genre][week]
            bucket["ad_count"] += 1
            bucket["scores"].append(_get_score(ad))
            bucket["spends"].append(ad.spend or 0.0)

            adv = ad.advertiser_name or "unknown"
            bucket["advertisers"].add(adv)
            genre_week_advertisers[genre][week].add(adv)

        # ------------------------------------------------------------------
        # 2. Compute per-genre trend metrics
        # ------------------------------------------------------------------
        genres_output = []

        for genre in sorted(genre_weekly.keys()):
            weeks_data = genre_weekly[genre]
            sorted_weeks = sorted(w for w in weeks_data.keys() if w != "unknown")

            if not sorted_weeks:
                continue

            num_weeks = len(sorted_weeks)

            # Build weekly time-series
            weekly_ad_counts = []
            weekly_avg_scores = []
            weekly_total_spends = []
            new_entrant_counts = []
            seen_advertisers = set()

            for w in sorted_weeks:
                wd = weeks_data[w]
                weekly_ad_counts.append(wd["ad_count"])

                avg_score = (
                    sum(wd["scores"]) / len(wd["scores"])
                    if wd["scores"] else 0.0
                )
                weekly_avg_scores.append(avg_score)
                weekly_total_spends.append(sum(wd["spends"]))

                # New entrants = advertisers appearing this week for the first time
                new_in_week = genre_week_advertisers[genre][w] - seen_advertisers
                new_entrant_counts.append(len(new_in_week))
                seen_advertisers |= genre_week_advertisers[genre][w]

            # Slopes via linear regression
            growth_slope = linear_regression_slope(weekly_ad_counts)
            score_slope = linear_regression_slope(weekly_avg_scores)
            spend_slope = linear_regression_slope(weekly_total_spends)

            total_ads_genre = sum(weekly_ad_counts)
            ads_per_week = total_ads_genre / num_weeks if num_weeks else 0.0
            total_new_entrants = sum(new_entrant_counts)
            new_entrants_per_week = total_new_entrants / num_weeks if num_weeks else 0.0

            classification = classify_genre(growth_slope, score_slope, total_ads_genre)
            score_trend = _score_trend_label(score_slope)
            spend_trend = _spend_trend_label(spend_slope)

            genres_output.append({
                "genre": genre,
                "total_ads": total_ads_genre,
                "ads_per_week": round(ads_per_week, 1),
                "growth_slope": round(growth_slope, 3),
                "score_trend": score_trend,
                "spend_trend": spend_trend,
                "new_entrants_per_week": round(new_entrants_per_week, 1),
                "classification": classification,
                "weeks_active": num_weeks,
            })

        # Sort by total_ads descending for dashboard readability
        genres_output.sort(key=lambda g: g["total_ads"], reverse=True)

        # ------------------------------------------------------------------
        # 3. Print genre status dashboard
        # ------------------------------------------------------------------
        print(f"\n{'--- Genre Status Dashboard ---':^60}")
        header = (
            f"  {'Genre':<25s} {'Class':<14s} {'Ads':>5s} {'Ads/Wk':>7s} "
            f"{'ScoreTrend':<12s} {'SpendTrend':<12s} {'NewEnt/Wk':>9s} {'Weeks':>5s}"
        )
        print(header)
        print(
            f"  {'-'*25} {'-'*14} {'-'*5} {'-'*7} "
            f"{'-'*12} {'-'*12} {'-'*9} {'-'*5}"
        )

        for g in genres_output:
            print(
                f"  {g['genre']:<25s} {g['classification']:<14s} "
                f"{g['total_ads']:>5d} {g['ads_per_week']:>7.1f} "
                f"{g['score_trend']:<12s} {g['spend_trend']:<12s} "
                f"{g['new_entrants_per_week']:>9.1f} {g['weeks_active']:>5d}"
            )

        # Classification summary
        class_counts = defaultdict(int)
        for g in genres_output:
            class_counts[g["classification"]] += 1

        print(f"\n{'--- Classification Summary ---':^60}")
        for cls in ("rapid_growth", "stable", "declining", "emerging"):
            count = class_counts.get(cls, 0)
            if count:
                print(f"  {cls}: {count} genre(s)")

        print(f"\nTotal genres tracked: {len(genres_output)}")

        # ------------------------------------------------------------------
        # 4. Export to JSON
        # ------------------------------------------------------------------
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "genres": genres_output,
        }

        out_path = os.path.join(export_dir, "trend_velocity.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        print(f"\nExported: {out_path}")
        print("Done.")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
