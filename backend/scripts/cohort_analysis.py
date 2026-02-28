#!/usr/bin/env python3
"""Cohort analysis - group ads by first_seen week and track metrics.

Groups ads by the ISO week of first_seen_at, computes cohort metrics,
and determines whether newer ads perform better or worse than older ones
using Pearson correlation between cohort index and avg_score.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/cohort_analysis.py
"""

import json
import math
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

def _ensure_utc(dt):
    """Return a timezone-aware datetime in UTC. If naive, assume UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _week_key(dt):
    """Return ISO year-week string like '2026-W05' for a datetime."""
    if dt is None:
        return None
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _get_score(ad):
    """Extract the hit score from ad metadata."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _pearson_correlation(xs, ys):
    """Compute Pearson correlation coefficient between two sequences.

    Returns 0.0 when computation is not possible (e.g. constant values,
    fewer than 2 data points).  Uses no external libraries.
    """
    n = len(xs)
    if n < 2:
        return 0.0

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return 0.0

    return cov / denom


def _classify_trend(correlation):
    """Classify a correlation value into a human-readable direction."""
    if correlation > 0.15:
        return "improving"
    elif correlation < -0.15:
        return "declining"
    else:
        return "flat"


def _generate_insights(cohort_data, trend_direction, correlation):
    """Generate human-readable insight strings from cohort data and trend."""
    insights = []

    if not cohort_data:
        insights.append("No cohort data available for analysis.")
        return insights

    total_ads = sum(c["count"] for c in cohort_data)
    insights.append(f"Analyzed {total_ads} ads across {len(cohort_data)} weekly cohorts.")

    # Overall trend insight
    if trend_direction == "improving":
        insights.append(
            f"Newer cohorts tend to score higher (r={correlation:.2f}). "
            "Ad quality or targeting appears to be improving over time."
        )
    elif trend_direction == "declining":
        insights.append(
            f"Newer cohorts tend to score lower (r={correlation:.2f}). "
            "Recent ads may need creative or targeting adjustments."
        )
    else:
        insights.append(
            f"No significant trend in scores across cohorts (r={correlation:.2f}). "
            "Performance is relatively stable over time."
        )

    # Best and worst cohorts
    best = max(cohort_data, key=lambda c: c["avg_score"])
    worst = min(cohort_data, key=lambda c: c["avg_score"])
    if best["week"] != worst["week"]:
        insights.append(
            f"Best performing cohort: {best['week']} "
            f"(avg_score={best['avg_score']}, count={best['count']})."
        )
        insights.append(
            f"Worst performing cohort: {worst['week']} "
            f"(avg_score={worst['avg_score']}, count={worst['count']})."
        )

    # Hit rate insights
    hit_rates = [c["hit_rate"] for c in cohort_data]
    avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0
    insights.append(f"Average hit rate across cohorts: {avg_hit_rate:.1f}%.")

    # Volume insights
    largest = max(cohort_data, key=lambda c: c["count"])
    insights.append(
        f"Largest cohort: {largest['week']} with {largest['count']} ads."
    )

    # View insights
    views_list = [c["avg_views"] for c in cohort_data if c["avg_views"] > 0]
    if views_list:
        overall_avg_views = sum(views_list) / len(views_list)
        insights.append(
            f"Average views per ad across cohorts: {overall_avg_views:,.0f}."
        )

    return insights


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Cohort Analysis - Ads by First-Seen Week")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads loaded: {total}")

        if total == 0:
            print("No ads found. Writing empty result and exiting.")
            _export({
                "cohorts": [],
                "trend": {"direction": "flat", "correlation": 0.0},
                "insights": ["No ads found in database."],
            })
            return

        # ------------------------------------------------------------------
        # 1. Group by ISO week of first_seen_at (fallback to created_at)
        # ------------------------------------------------------------------
        cohorts = defaultdict(list)
        skipped = 0
        for ad in ads:
            dt = ad.first_seen_at or ad.created_at
            dt = _ensure_utc(dt)
            week = _week_key(dt)
            if week is None:
                skipped += 1
                continue
            cohorts[week].append(ad)

        if skipped:
            print(f"  Skipped {skipped} ads with no usable date.")

        # ------------------------------------------------------------------
        # 2. Compute metrics per weekly cohort
        # ------------------------------------------------------------------
        cohort_data = []
        for week in sorted(cohorts.keys()):
            ads_in_cohort = cohorts[week]
            n = len(ads_in_cohort)

            scores = [_get_score(ad) for ad in ads_in_cohort]
            avg_score = sum(scores) / n if n > 0 else 0.0
            hit_count = sum(1 for s in scores if s >= 60)
            hit_rate = (hit_count / n * 100) if n > 0 else 0.0

            views = [ad.view_count or 0 for ad in ads_in_cohort]
            avg_views = sum(views) / n if n > 0 else 0

            cohort_data.append({
                "week": week,
                "count": n,
                "avg_score": round(avg_score, 1),
                "hit_rate": round(hit_rate, 1),
                "avg_views": round(avg_views, 0),
            })

        # ------------------------------------------------------------------
        # 3. Print cohort table
        # ------------------------------------------------------------------
        print(f"\n{'--- Cohort Metrics by Week ---':^60}")
        header = (
            f"  {'Week':<12s} {'Count':>6s} {'AvgScore':>9s} "
            f"{'HitRate':>8s} {'AvgViews':>10s}"
        )
        print(header)
        print(f"  {'-'*12} {'-'*6} {'-'*9} {'-'*8} {'-'*10}")

        for c in cohort_data:
            print(
                f"  {c['week']:<12s} {c['count']:>6d} {c['avg_score']:>9.1f} "
                f"{c['hit_rate']:>7.1f}% {c['avg_views']:>10.0f}"
            )

        # ------------------------------------------------------------------
        # 4. Trend analysis: correlation between cohort index and avg_score
        # ------------------------------------------------------------------
        print(f"\n--- Trend Analysis ---")

        if len(cohort_data) >= 2:
            indices = list(range(len(cohort_data)))
            avg_scores = [c["avg_score"] for c in cohort_data]

            correlation = _pearson_correlation(indices, avg_scores)
            correlation = round(correlation, 4)
            direction = _classify_trend(correlation)

            print(f"  Cohorts analyzed:     {len(cohort_data)}")
            print(f"  Pearson correlation:  {correlation}")
            print(f"  Trend direction:      {direction}")

            # Also show first-half vs second-half comparison
            mid = len(cohort_data) // 2
            early_avg = sum(c["avg_score"] for c in cohort_data[:mid]) / mid
            late_avg = sum(c["avg_score"] for c in cohort_data[mid:]) / len(cohort_data[mid:])
            print(f"  Early cohorts avg:    {early_avg:.1f}")
            print(f"  Late cohorts avg:     {late_avg:.1f}")
        else:
            correlation = 0.0
            direction = "flat"
            print("  Not enough cohorts (need >= 2) for trend analysis.")

        # ------------------------------------------------------------------
        # 5. Generate insights
        # ------------------------------------------------------------------
        insights = _generate_insights(cohort_data, direction, correlation)

        print(f"\n--- Insights ---")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        # ------------------------------------------------------------------
        # 6. Export to JSON
        # ------------------------------------------------------------------
        output = {
            "cohorts": cohort_data,
            "trend": {
                "direction": direction,
                "correlation": correlation,
            },
            "insights": insights,
        }
        out_path = _export(output)
        print(f"\nExported: {out_path}")
        print("Done!")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


def _export(data):
    """Write data dict to exports/cohort_analysis.json and return the path."""
    export_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports"
    )
    os.makedirs(export_dir, exist_ok=True)
    out_path = os.path.join(export_dir, "cohort_analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path


if __name__ == "__main__":
    main()
