#!/usr/bin/env python3
"""Analyze seasonal patterns in ad performance by genre.

Groups ads by month/season, finds genre x season correlations,
identifies seasonal peaks per genre.

Output: exports/seasonal_patterns.json
Format:
  {
    "skincare": {
      "peak_months": [6, 7, 8],
      "low_months": [12, 1],
      "seasonal_index": {"spring": 1.2, "summer": 1.5, ...},
      "monthly_stats": {
        "1": {"count": 10, "hit_rate": 25.0, "avg_score": 42.5}, ...
      }
    },
    ...
  }

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_seasonal_patterns.py
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

SEASONS = {
    "spring": [3, 4, 5],
    "summer": [6, 7, 8],
    "autumn": [9, 10, 11],
    "winter": [12, 1, 2],
}

# Reverse lookup: month -> season
MONTH_TO_SEASON = {}
for _season, _months in SEASONS.items():
    for _m in _months:
        MONTH_TO_SEASON[_m] = _season


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_utc(dt: datetime) -> datetime:
    """Handle timezone-naive datetimes by adding UTC if needed."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_month(ad: Ad) -> int | None:
    """Get the month number from first_seen_at, falling back to created_at."""
    dt = ad.first_seen_at or ad.created_at
    if dt is None:
        return None
    dt = _ensure_utc(dt)
    return dt.month


def _get_genre(ad: Ad) -> str | None:
    """Get fine_genre_en from ad_metadata. Returns None if missing."""
    meta = ad.ad_metadata or {}
    fg = meta.get("fine_genre_en")
    if fg and isinstance(fg, str) and fg.strip():
        return fg.strip()
    return None


def _get_score(ad: Ad) -> float:
    """Get the latest hit score from metadata, defaulting to 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    """Check if an ad qualifies as a hit."""
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0.0 if empty."""
    return round(mean(values), 2) if values else 0.0


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def build_genre_monthly_data(ads: list[Ad]) -> dict[str, dict[int, list[Ad]]]:
    """Group ads by (genre, month). Only includes ads with fine_genre_en.

    Returns: {genre: {month_int: [ad, ...]}}
    """
    data: dict[str, dict[int, list[Ad]]] = defaultdict(lambda: defaultdict(list))

    for ad in ads:
        genre = _get_genre(ad)
        month = _get_month(ad)
        if genre is None or month is None:
            continue
        data[genre][month].append(ad)

    return data


def compute_monthly_stats(genre_data: dict[int, list[Ad]]) -> dict[str, dict]:
    """Compute count, hit_rate, avg_score for each month of a single genre.

    Returns: {"1": {"count": N, "hit_rate": P, "avg_score": S}, ...}
    All 12 months are included, even if count is 0.
    """
    stats = {}
    for month in range(1, 13):
        month_ads = genre_data.get(month, [])
        count = len(month_ads)
        if count == 0:
            stats[str(month)] = {"count": 0, "hit_rate": 0.0, "avg_score": 0.0}
            continue

        hits = sum(1 for a in month_ads if _is_hit(a))
        scores = [_get_score(a) for a in month_ads]
        stats[str(month)] = {
            "count": count,
            "hit_rate": round(hits / count * 100, 1),
            "avg_score": _safe_mean(scores),
        }

    return stats


def compute_seasonal_index(genre_data: dict[int, list[Ad]]) -> dict[str, float]:
    """Compute seasonal_index for a single genre.

    seasonal_index = ads_in_season / expected_if_uniform
    where expected_if_uniform = total_ads / 4
    A value of 1.0 means exactly average; >1 = over-represented; <1 = under-represented.

    Returns: {"spring": 1.2, "summer": 1.5, "autumn": 0.8, "winter": 0.5}
    """
    total = sum(len(ads) for ads in genre_data.values())
    if total == 0:
        return {s: 0.0 for s in SEASONS}

    expected = total / 4.0  # uniform distribution across 4 seasons

    index = {}
    for season_name, season_months in SEASONS.items():
        season_count = sum(len(genre_data.get(m, [])) for m in season_months)
        index[season_name] = round(season_count / expected, 2) if expected > 0 else 0.0

    return index


def find_peak_and_low_months(monthly_stats: dict[str, dict]) -> tuple[list[int], list[int]]:
    """Identify peak months (highest activity) and low months for a genre.

    Peak months: months with count > 1.3x the average monthly count.
    Low months: months with count < 0.7x the average monthly count.

    Returns: (peak_months, low_months) as sorted lists of month ints.
    """
    counts = [(int(m), monthly_stats[m]["count"]) for m in monthly_stats]
    total = sum(c for _, c in counts)
    if total == 0:
        return [], []

    avg = total / 12.0

    peak_months = sorted(
        [m for m, c in counts if c > avg * 1.3],
        key=lambda m: -monthly_stats[str(m)]["count"],
    )
    low_months = sorted(
        [m for m, c in counts if 0 < avg and c < avg * 0.7],
    )

    return peak_months, low_months


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary_table(genre_results: dict) -> None:
    """Print a summary table showing genre vs season distribution."""
    print("\n" + "=" * 80)
    print("GENRE vs SEASON DISTRIBUTION (seasonal_index, 1.0 = uniform)")
    print("=" * 80)

    header = "%-30s %10s %10s %10s %10s" % ("Genre", "Spring", "Summer", "Autumn", "Winter")
    print(header)
    print("-" * 80)

    for genre in sorted(genre_results.keys()):
        si = genre_results[genre]["seasonal_index"]
        total_count = sum(
            genre_results[genre]["monthly_stats"][str(m)]["count"]
            for m in range(1, 13)
        )
        if total_count == 0:
            continue

        vals = []
        for s in ["spring", "summer", "autumn", "winter"]:
            idx = si.get(s, 0.0)
            # Highlight peaks with asterisk
            marker = " *" if idx >= 1.3 else ""
            vals.append("%8.2f%s" % (idx, marker))

        label = genre[:30]
        print("%-30s %10s %10s %10s %10s" % (label, *vals))

    print("-" * 80)
    print("(* = seasonal_index >= 1.3, indicating strong seasonal concentration)")

    # Peak months summary
    print("\n" + "=" * 80)
    print("GENRE PEAK & LOW MONTHS")
    print("=" * 80)
    print("%-30s %-30s %-30s" % ("Genre", "Peak Months", "Low Months"))
    print("-" * 80)

    for genre in sorted(genre_results.keys()):
        gr = genre_results[genre]
        total_count = sum(
            gr["monthly_stats"][str(m)]["count"]
            for m in range(1, 13)
        )
        if total_count == 0:
            continue

        peak_str = ", ".join(MONTH_NAMES[m] for m in gr["peak_months"]) if gr["peak_months"] else "(none)"
        low_str = ", ".join(MONTH_NAMES[m] for m in gr["low_months"]) if gr["low_months"] else "(none)"
        print("%-30s %-30s %-30s" % (genre[:30], peak_str, low_str))

    print("-" * 80)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("SEASONAL PATTERN ANALYSIS")
    print("Executed at: %s" % datetime.now(timezone.utc).isoformat())
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print("Total ads loaded: %d" % total)

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Filter to ads that have both a genre and a date
        eligible = [
            a for a in ads
            if _get_genre(a) is not None and _get_month(a) is not None
        ]
        print("Ads with fine_genre_en and date: %d / %d" % (len(eligible), total))

        if not eligible:
            print("No eligible ads found (need fine_genre_en in ad_metadata). Exiting.")
            return

        # Genre distribution
        genre_counts: dict[str, int] = defaultdict(int)
        for a in eligible:
            genre_counts[_get_genre(a)] += 1
        print("Distinct genres: %d" % len(genre_counts))

        # Build per-genre monthly data
        genre_monthly = build_genre_monthly_data(eligible)

        # Compute results for each genre
        genre_results: dict[str, dict] = {}
        for genre in sorted(genre_monthly.keys()):
            gdata = genre_monthly[genre]

            monthly_stats = compute_monthly_stats(gdata)
            seasonal_index = compute_seasonal_index(gdata)
            peak_months, low_months = find_peak_and_low_months(monthly_stats)

            genre_results[genre] = {
                "peak_months": peak_months,
                "low_months": low_months,
                "seasonal_index": seasonal_index,
                "monthly_stats": monthly_stats,
            }

        # Print summary table
        print_summary_table(genre_results)

        # Overall season stats
        print("\n" + "=" * 60)
        print("OVERALL SEASON PERFORMANCE")
        print("=" * 60)
        for season_name, season_months in SEASONS.items():
            season_ads = [
                a for a in eligible
                if _get_month(a) in season_months
            ]
            count = len(season_ads)
            if count == 0:
                print("  %-8s  count=0" % season_name)
                continue

            scores = [_get_score(a) for a in season_ads]
            hits = sum(1 for a in season_ads if _is_hit(a))
            print("  %-8s  count=%5d  avg_score=%.2f  hit_rate=%.1f%%" % (
                season_name, count, _safe_mean(scores),
                round(hits / count * 100, 1),
            ))

        # Top seasonal genres (highest seasonal_index in any season)
        print("\nTop seasonally concentrated genres:")
        seasonal_peaks = []
        for genre, gr in genre_results.items():
            total_count = sum(gr["monthly_stats"][str(m)]["count"] for m in range(1, 13))
            if total_count < 5:
                continue
            for season_name, idx in gr["seasonal_index"].items():
                if idx >= 1.3:
                    seasonal_peaks.append((genre, season_name, idx, total_count))

        seasonal_peaks.sort(key=lambda x: x[2], reverse=True)
        for genre, season_name, idx, count in seasonal_peaks[:15]:
            print("  %-30s  %-8s  index=%.2f  (n=%d)" % (genre[:30], season_name, idx, count))

        if not seasonal_peaks:
            print("  (no genres with seasonal_index >= 1.3 found)")

        # Export
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "seasonal_patterns.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(genre_results, f, ensure_ascii=False, indent=2)

        print("\nExported to: %s" % export_path)
        print("Genres in output: %d" % len(genre_results))
        print("Done!")

    except Exception as e:
        session.rollback()
        print("FATAL ERROR: %s" % e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
