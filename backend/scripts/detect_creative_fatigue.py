#!/usr/bin/env python3
"""Detect creative fatigue by analyzing performance decline of creative patterns.

For each creative pattern (fine_genre + hook_type + cta_type from ad_metadata),
tracks usage over time and detects whether performance is declining (fatigue),
still strong (fresh), or simply overused.

Fatigue detection:
  - Split ads chronologically into first half and second half
  - If second half avg score < first half avg score by >10 points -> fatigued
  - If >10 ads share the same pattern -> overused
  - If second half >= first half and not overused -> fresh

Outputs:
  - backend/exports/creative_fatigue.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/detect_creative_fatigue.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# -- Constants --------------------------------------------------------------

FATIGUE_DECLINE_THRESHOLD = 10  # second half avg must be >10 pts lower
OVERUSE_THRESHOLD = 10  # >10 ads with same structure = overused


# -- Helpers ----------------------------------------------------------------


def _get_score(ad: Ad) -> float:
    """Get the hit score for an ad, defaulting to 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _get_pattern_key(ad: Ad) -> str | None:
    """Build a pattern key from fine_genre + hook_type + cta_type in ad_metadata.

    Returns None if all three components are missing.
    """
    meta = ad.ad_metadata or {}
    fine_genre = meta.get("fine_genre")
    hook_type = meta.get("hook_type")
    cta_type = meta.get("cta_type")

    if not fine_genre and not hook_type and not cta_type:
        return None

    return f"{fine_genre or 'unknown'}|{hook_type or 'unknown'}|{cta_type or 'unknown'}"


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return mean(values) if values else 0.0


def _iso_week_label(dt: datetime) -> str:
    """Return an ISO week label like '2025-W03'."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _get_sort_dt(ad: Ad) -> datetime:
    """Return the best available datetime for chronological sorting."""
    return ad.first_seen_at or ad.created_at


# -- Analysis Functions -----------------------------------------------------


def group_ads_by_pattern(ads: list[Ad]) -> dict[str, list[Ad]]:
    """Group ads by their creative pattern key (fine_genre|hook_type|cta_type).

    Ads without any pattern components are skipped.
    """
    groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        key = _get_pattern_key(ad)
        if key:
            groups[key].append(ad)
    return dict(groups)


def analyze_pattern(key: str, ads: list[Ad]) -> dict:
    """Analyze a single creative pattern for fatigue signals.

    Sorts ads chronologically by first_seen_at, splits into first half and
    second half, then compares average scores.
    """
    parts = key.split("|")
    fine_genre = parts[0]
    hook_type = parts[1]
    cta_type = parts[2]

    # Sort chronologically
    sorted_ads = sorted(ads, key=_get_sort_dt)

    # Compute scores
    all_scores = [_get_score(a) for a in sorted_ads]
    avg_score = round(_safe_mean(all_scores), 1)

    # Weekly usage breakdown
    weekly_usage: dict[str, int] = defaultdict(int)
    for ad in sorted_ads:
        dt = ad.first_seen_at or ad.created_at
        if dt:
            weekly_usage[_iso_week_label(dt)] += 1

    # Split into first half and second half for fatigue detection
    mid = len(sorted_ads) // 2
    if mid == 0:
        # Only 1 ad, cannot meaningfully split
        first_half_scores = all_scores
        second_half_scores = all_scores
    else:
        first_half_scores = [_get_score(a) for a in sorted_ads[:mid]]
        second_half_scores = [_get_score(a) for a in sorted_ads[mid:]]

    first_half_avg = round(_safe_mean(first_half_scores), 1)
    second_half_avg = round(_safe_mean(second_half_scores), 1)
    score_decline = round(first_half_avg - second_half_avg, 1)

    # Determine fatigue status
    count = len(ads)
    is_fatigued = (
        count >= 2
        and first_half_avg > 0
        and score_decline > FATIGUE_DECLINE_THRESHOLD
    )
    is_overused = count > OVERUSE_THRESHOLD
    is_fresh = (
        count >= 2
        and second_half_avg >= first_half_avg
        and not is_overused
    )

    # Date range
    first_date = _get_sort_dt(sorted_ads[0])
    last_date = _get_sort_dt(sorted_ads[-1])

    return {
        "pattern_key": key,
        "fine_genre": fine_genre,
        "hook_type": hook_type,
        "cta_type": cta_type,
        "ad_count": count,
        "avg_score": avg_score,
        "first_half_avg_score": first_half_avg,
        "second_half_avg_score": second_half_avg,
        "score_decline": score_decline,
        "is_fatigued": is_fatigued,
        "is_overused": is_overused,
        "is_fresh": is_fresh,
        "first_seen": first_date.isoformat() if first_date else None,
        "last_seen": last_date.isoformat() if last_date else None,
        "weekly_usage": dict(sorted(weekly_usage.items())),
        "sample_titles": [
            ad.title for ad in sorted_ads[:5] if ad.title
        ],
    }


def generate_insights(
    fatigued: list[dict],
    fresh: list[dict],
    overused: list[dict],
    total_patterns: int,
) -> list[str]:
    """Generate human-readable insights from the analysis results."""
    insights = []

    if fatigued:
        worst = max(fatigued, key=lambda p: p["score_decline"])
        insights.append(
            f"Most fatigued pattern: {worst['fine_genre']} + {worst['hook_type']} + "
            f"{worst['cta_type']} (score declined {worst['score_decline']} points, "
            f"from {worst['first_half_avg_score']} to {worst['second_half_avg_score']})"
        )

    if fresh:
        best = max(fresh, key=lambda p: p["avg_score"])
        insights.append(
            f"Strongest fresh pattern: {best['fine_genre']} + {best['hook_type']} + "
            f"{best['cta_type']} (avg score {best['avg_score']}, "
            f"n={best['ad_count']})"
        )

    if overused:
        most_used = max(overused, key=lambda p: p["ad_count"])
        insights.append(
            f"Most overused pattern: {most_used['fine_genre']} + {most_used['hook_type']} + "
            f"{most_used['cta_type']} ({most_used['ad_count']} ads)"
        )

    # Overlap: patterns that are both fatigued AND overused
    fatigued_keys = {p["pattern_key"] for p in fatigued}
    overused_keys = {p["pattern_key"] for p in overused}
    overlap = fatigued_keys & overused_keys
    if overlap:
        insights.append(
            f"{len(overlap)} pattern(s) are both fatigued and overused -- "
            f"consider retiring these creative structures"
        )

    # Fatigue rate
    if total_patterns > 0:
        fatigue_rate = round(len(fatigued) / total_patterns * 100, 1)
        insights.append(
            f"Fatigue rate: {fatigue_rate}% of patterns show performance decline"
        )

    # Fresh patterns recommendation
    fresh_not_overused = [p for p in fresh if not p["is_overused"]]
    if fresh_not_overused:
        insights.append(
            f"{len(fresh_not_overused)} pattern(s) are fresh and not overused -- "
            f"good candidates for scaling"
        )

    return insights


# -- Main -------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("Creative Fatigue Detection")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total_ads = len(ads)
        print(f"\nTotal ads in database: {total_ads}")

        if total_ads == 0:
            print("No ads found. Exiting.")
            return

        # Group by pattern
        pattern_groups = group_ads_by_pattern(ads)
        total_patterns = len(pattern_groups)
        print(f"Unique creative patterns (fine_genre + hook_type + cta_type): {total_patterns}")

        if total_patterns == 0:
            print("No ads with pattern metadata found. Exiting.")
            return

        # Analyze each pattern
        all_results = []
        for key, group_ads in pattern_groups.items():
            result = analyze_pattern(key, group_ads)
            all_results.append(result)

        # Categorize
        fatigued = [r for r in all_results if r["is_fatigued"]]
        overused = [r for r in all_results if r["is_overused"]]
        fresh = [r for r in all_results if r["is_fresh"]]

        # Sort each category for readability
        fatigued.sort(key=lambda x: x["score_decline"], reverse=True)
        overused.sort(key=lambda x: x["ad_count"], reverse=True)
        fresh.sort(key=lambda x: x["avg_score"], reverse=True)

        # Generate insights
        insights = generate_insights(fatigued, fresh, overused, total_patterns)

        # Print required summary line
        print(
            f"\n{len(fatigued)} patterns showing fatigue, "
            f"{len(fresh)} patterns still fresh, "
            f"{len(overused)} patterns overused"
        )

        # Print top fatigued patterns
        if fatigued:
            print(f"\n--- Top Fatigued Patterns ---")
            print(f"  {'Pattern':<50s} {'Count':>5s} {'1stHalf':>8s} {'2ndHalf':>8s} {'Decline':>8s}")
            print(f"  {'-' * 80}")
            for p in fatigued[:10]:
                label = f"{p['fine_genre']} + {p['hook_type']} + {p['cta_type']}"
                if len(label) > 48:
                    label = label[:45] + "..."
                print(
                    f"  {label:<50s} {p['ad_count']:>5d} "
                    f"{p['first_half_avg_score']:>7.1f} {p['second_half_avg_score']:>7.1f} "
                    f"{p['score_decline']:>7.1f}"
                )

        # Print top fresh patterns
        if fresh:
            print(f"\n--- Top Fresh Patterns ---")
            print(f"  {'Pattern':<50s} {'Count':>5s} {'AvgScore':>9s}")
            print(f"  {'-' * 65}")
            for p in fresh[:10]:
                label = f"{p['fine_genre']} + {p['hook_type']} + {p['cta_type']}"
                if len(label) > 48:
                    label = label[:45] + "..."
                print(f"  {label:<50s} {p['ad_count']:>5d} {p['avg_score']:>8.1f}")

        # Print overused patterns
        if overused:
            print(f"\n--- Overused Patterns (>10 ads) ---")
            print(f"  {'Pattern':<50s} {'Count':>5s} {'AvgScore':>9s} {'Fatigued?':>10s}")
            print(f"  {'-' * 75}")
            for p in overused[:10]:
                label = f"{p['fine_genre']} + {p['hook_type']} + {p['cta_type']}"
                if len(label) > 48:
                    label = label[:45] + "..."
                fatigued_flag = "YES" if p["is_fatigued"] else "no"
                print(
                    f"  {label:<50s} {p['ad_count']:>5d} "
                    f"{p['avg_score']:>8.1f} {fatigued_flag:>10s}"
                )

        # Print insights
        if insights:
            print(f"\n--- Insights ---")
            for i, insight in enumerate(insights, 1):
                print(f"  {i}. {insight}")

        # Build export report
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_patterns": total_patterns,
            "fatigued_patterns": fatigued,
            "overused_patterns": overused,
            "fresh_patterns": fresh,
            "insights": insights,
        }

        # Export to JSON
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "creative_fatigue.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\nExported: {out_path}")
        print("Done!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
