#!/usr/bin/env python3
"""Analyze optimal ad description length vs hit rate.

Buckets ads by description character count (0-50, 50-100, 100-200,
200-500, 500+) and computes hit rate, avg score, and other metrics
per bucket to find the "sweet spot" for ad copy length.

Outputs:
  - backend/exports/optimal_length.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/optimal_length.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Length Buckets ───────────────────────────────────────────────────────

LENGTH_BUCKETS = [
    ("0-50", 0, 50),
    ("50-100", 50, 100),
    ("100-200", 100, 200),
    ("200-500", 200, 500),
    ("500+", 500, float("inf")),
]

TITLE_LENGTH_BUCKETS = [
    ("0-20", 0, 20),
    ("20-40", 20, 40),
    ("40-60", 40, 60),
    ("60-100", 60, 100),
    ("100+", 100, float("inf")),
]


# ── Helpers ──────────────────────────────────────────────────────────────


def _is_hit(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _safe_mean(vals: list[float]) -> float:
    return mean(vals) if vals else 0.0


def _safe_median(vals: list[float]) -> float:
    return median(vals) if vals else 0.0


def _bucket_label(length: int, buckets: list[tuple[str, int, float]]) -> str:
    """Assign a length to its bucket label."""
    for label, low, high in buckets:
        if low <= length < high:
            return label
    return buckets[-1][0]  # fallback to last bucket


# ── Analysis Functions ──────────────────────────────────────────────────


def analyze_description_length(ads: list[Ad]) -> dict:
    """Analyze hit rate and avg score by description length bucket."""
    buckets: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        desc = ad.description or ""
        length = len(desc)
        bucket = _bucket_label(length, LENGTH_BUCKETS)
        buckets[bucket].append(ad)

    results = {}
    for label, low, high in LENGTH_BUCKETS:
        bucket_ads = buckets.get(label, [])
        if not bucket_ads:
            results[label] = {
                "count": 0, "hit_count": 0, "hit_rate": 0,
                "avg_score": 0, "median_score": 0,
                "avg_length": 0,
            }
            continue

        scores = [_get_score(a) for a in bucket_ads]
        hits = sum(1 for a in bucket_ads if _is_hit(a))
        lengths = [len(a.description or "") for a in bucket_ads]

        results[label] = {
            "count": len(bucket_ads),
            "hit_count": hits,
            "hit_rate": round(hits / len(bucket_ads) * 100, 1),
            "avg_score": round(_safe_mean(scores), 1),
            "median_score": round(_safe_median(scores), 1),
            "avg_length": round(_safe_mean([float(l) for l in lengths]), 1),
            "min_length": min(lengths),
            "max_length": max(lengths),
        }

    return results


def analyze_title_length(ads: list[Ad]) -> dict:
    """Analyze hit rate and avg score by title length bucket."""
    buckets: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        title = ad.title or ""
        length = len(title)
        bucket = _bucket_label(length, TITLE_LENGTH_BUCKETS)
        buckets[bucket].append(ad)

    results = {}
    for label, low, high in TITLE_LENGTH_BUCKETS:
        bucket_ads = buckets.get(label, [])
        if not bucket_ads:
            results[label] = {
                "count": 0, "hit_count": 0, "hit_rate": 0,
                "avg_score": 0, "avg_length": 0,
            }
            continue

        scores = [_get_score(a) for a in bucket_ads]
        hits = sum(1 for a in bucket_ads if _is_hit(a))
        lengths = [len(a.title or "") for a in bucket_ads]

        results[label] = {
            "count": len(bucket_ads),
            "hit_count": hits,
            "hit_rate": round(hits / len(bucket_ads) * 100, 1),
            "avg_score": round(_safe_mean(scores), 1),
            "avg_length": round(_safe_mean([float(l) for l in lengths]), 1),
        }

    return results


def analyze_combined_length(ads: list[Ad]) -> dict:
    """Analyze total text length (title + description) vs performance."""
    # Use 100-char-wide buckets
    combined_buckets = [
        ("0-100", 0, 100),
        ("100-200", 100, 200),
        ("200-400", 200, 400),
        ("400-700", 400, 700),
        ("700+", 700, float("inf")),
    ]

    buckets: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        total_len = len(ad.title or "") + len(ad.description or "")
        bucket = _bucket_label(total_len, combined_buckets)
        buckets[bucket].append(ad)

    results = {}
    for label, low, high in combined_buckets:
        bucket_ads = buckets.get(label, [])
        if not bucket_ads:
            results[label] = {"count": 0, "hit_rate": 0, "avg_score": 0}
            continue

        scores = [_get_score(a) for a in bucket_ads]
        hits = sum(1 for a in bucket_ads if _is_hit(a))

        results[label] = {
            "count": len(bucket_ads),
            "hit_count": hits,
            "hit_rate": round(hits / len(bucket_ads) * 100, 1),
            "avg_score": round(_safe_mean(scores), 1),
        }

    return results


def analyze_length_by_genre(ads: list[Ad]) -> dict:
    """Find optimal description length per genre."""
    genre_lengths: dict[str, list[dict]] = defaultdict(list)

    for ad in ads:
        genre = str(ad.category.value) if ad.category else "unknown"
        desc = ad.description or ""
        genre_lengths[genre].append({
            "length": len(desc),
            "score": _get_score(ad),
            "is_hit": _is_hit(ad),
        })

    results = {}
    for genre, entries in genre_lengths.items():
        if len(entries) < 3:
            continue

        # Find the sweet spot: what's the avg length of hit ads vs non-hit
        hit_lengths = [e["length"] for e in entries if e["is_hit"]]
        non_hit_lengths = [e["length"] for e in entries if not e["is_hit"]]

        results[genre] = {
            "total_ads": len(entries),
            "hit_ads": len(hit_lengths),
            "avg_length_hit": round(_safe_mean([float(l) for l in hit_lengths]), 1) if hit_lengths else None,
            "avg_length_non_hit": round(_safe_mean([float(l) for l in non_hit_lengths]), 1) if non_hit_lengths else None,
            "median_length_hit": round(_safe_median([float(l) for l in hit_lengths]), 1) if hit_lengths else None,
            "median_length_non_hit": round(_safe_median([float(l) for l in non_hit_lengths]), 1) if non_hit_lengths else None,
        }

    return results


def analyze_line_count_vs_performance(ads: list[Ad]) -> dict:
    """Analyze number of lines in description vs performance."""
    line_groups: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        desc = ad.description or ""
        if not desc.strip():
            line_groups["0 lines"].append(ad)
            continue
        line_count = len([l for l in desc.split("\n") if l.strip()])
        if line_count <= 1:
            line_groups["1 line"].append(ad)
        elif line_count <= 3:
            line_groups["2-3 lines"].append(ad)
        elif line_count <= 5:
            line_groups["4-5 lines"].append(ad)
        elif line_count <= 10:
            line_groups["6-10 lines"].append(ad)
        else:
            line_groups["11+ lines"].append(ad)

    results = {}
    for label in ["0 lines", "1 line", "2-3 lines", "4-5 lines", "6-10 lines", "11+ lines"]:
        group_ads = line_groups.get(label, [])
        if not group_ads:
            continue
        scores = [_get_score(a) for a in group_ads]
        hits = sum(1 for a in group_ads if _is_hit(a))
        results[label] = {
            "count": len(group_ads),
            "hit_count": hits,
            "hit_rate": round(hits / len(group_ads) * 100, 1),
            "avg_score": round(_safe_mean(scores), 1),
        }

    return results


def find_sweet_spot(desc_stats: dict) -> dict:
    """Identify the optimal description length bucket."""
    # Filter buckets with at least 3 ads
    valid = {
        k: v for k, v in desc_stats.items()
        if v["count"] >= 3
    }
    if not valid:
        return {"sweet_spot": "insufficient data"}

    # Sweet spot by hit rate
    best_hr = max(valid.items(), key=lambda x: x[1]["hit_rate"])
    # Sweet spot by avg score
    best_score = max(valid.items(), key=lambda x: x[1]["avg_score"])

    return {
        "best_by_hit_rate": {
            "bucket": best_hr[0],
            "hit_rate": best_hr[1]["hit_rate"],
            "avg_score": best_hr[1]["avg_score"],
            "count": best_hr[1]["count"],
        },
        "best_by_avg_score": {
            "bucket": best_score[0],
            "hit_rate": best_score[1]["hit_rate"],
            "avg_score": best_score[1]["avg_score"],
            "count": best_score[1]["count"],
        },
    }


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Optimal Length Analysis Script")
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

        total_hits = sum(1 for a in ads if _is_hit(a))
        baseline_hr = round(total_hits / total * 100, 1) if total > 0 else 0
        print(f"Baseline hit rate: {baseline_hr}%")

        # 1. Description length analysis
        print("\n--- Description Length vs Performance ---")
        desc_stats = analyze_description_length(ads)
        print(f"  {'Bucket':<12s} {'Count':>6s} {'Hits':>5s} {'HitRate':>8s} {'AvgScore':>9s} {'AvgLen':>7s}")
        print(f"  {'-' * 55}")
        for bucket, stats in desc_stats.items():
            print(
                f"  {bucket:<12s} {stats['count']:>6d} {stats['hit_count']:>5d} "
                f"{stats['hit_rate']:>7.1f}% {stats['avg_score']:>8.1f} "
                f"{stats['avg_length']:>6.0f}"
            )

        # 2. Title length analysis
        print(f"\n--- Title Length vs Performance ---")
        title_stats = analyze_title_length(ads)
        print(f"  {'Bucket':<12s} {'Count':>6s} {'Hits':>5s} {'HitRate':>8s} {'AvgScore':>9s}")
        print(f"  {'-' * 45}")
        for bucket, stats in title_stats.items():
            print(
                f"  {bucket:<12s} {stats['count']:>6d} {stats['hit_count']:>5d} "
                f"{stats['hit_rate']:>7.1f}% {stats['avg_score']:>8.1f}"
            )

        # 3. Combined length
        print(f"\n--- Combined Length (title + desc) vs Performance ---")
        combined_stats = analyze_combined_length(ads)
        for bucket, stats in combined_stats.items():
            print(
                f"  {bucket:<12s} n={stats['count']:>4d}  "
                f"hit_rate={stats['hit_rate']:>5.1f}%  "
                f"avg_score={stats['avg_score']:.1f}"
            )

        # 4. Line count analysis
        print(f"\n--- Line Count vs Performance ---")
        line_stats = analyze_line_count_vs_performance(ads)
        for label, stats in line_stats.items():
            print(
                f"  {label:<12s} n={stats['count']:>4d}  "
                f"hit_rate={stats['hit_rate']:>5.1f}%  "
                f"avg_score={stats['avg_score']:.1f}"
            )

        # 5. Genre-specific optimal length
        print(f"\n--- Optimal Length by Genre ---")
        genre_stats = analyze_length_by_genre(ads)
        for genre, info in sorted(genre_stats.items(), key=lambda x: x[1]["total_ads"], reverse=True):
            hit_len = info.get("avg_length_hit")
            non_hit_len = info.get("avg_length_non_hit")
            hit_str = f"{hit_len:.0f}" if hit_len is not None else "N/A"
            non_hit_str = f"{non_hit_len:.0f}" if non_hit_len is not None else "N/A"
            print(f"  {genre:<16s} n={info['total_ads']:>3d}  "
                  f"hit_avg_len={hit_str:>5s}  non_hit_avg_len={non_hit_str:>5s}")

        # 6. Sweet spot
        sweet_spot = find_sweet_spot(desc_stats)
        print(f"\n--- Sweet Spot ---")
        if "sweet_spot" in sweet_spot:
            print(f"  {sweet_spot['sweet_spot']}")
        else:
            hr_best = sweet_spot["best_by_hit_rate"]
            sc_best = sweet_spot["best_by_avg_score"]
            print(f"  By hit rate: {hr_best['bucket']} "
                  f"({hr_best['hit_rate']}%, avg_score={hr_best['avg_score']}, n={hr_best['count']})")
            print(f"  By avg score: {sc_best['bucket']} "
                  f"(avg_score={sc_best['avg_score']}, hit_rate={sc_best['hit_rate']}%, n={sc_best['count']})")

        sweet_spot_title = find_sweet_spot(title_stats)
        if "sweet_spot" not in sweet_spot_title:
            hr_best = sweet_spot_title["best_by_hit_rate"]
            print(f"  Title sweet spot: {hr_best['bucket']} "
                  f"({hr_best['hit_rate']}% hit rate, n={hr_best['count']})")

        # 7. Build insights
        insights = []

        # Description sweet spot insight
        if "sweet_spot" not in sweet_spot:
            hr_best = sweet_spot["best_by_hit_rate"]
            insights.append(
                f"Optimal description length: {hr_best['bucket']} chars "
                f"({hr_best['hit_rate']}% hit rate, n={hr_best['count']})"
            )

        # Title insight
        if "sweet_spot" not in sweet_spot_title:
            hr_best = sweet_spot_title["best_by_hit_rate"]
            insights.append(
                f"Optimal title length: {hr_best['bucket']} chars "
                f"({hr_best['hit_rate']}% hit rate)"
            )

        # Short vs long comparison
        short_bucket = desc_stats.get("0-50", {})
        long_bucket = desc_stats.get("500+", {})
        if short_bucket.get("count", 0) >= 3 and long_bucket.get("count", 0) >= 3:
            if short_bucket["hit_rate"] > long_bucket["hit_rate"]:
                insights.append(
                    f"Shorter descriptions outperform longer ones: "
                    f"0-50 chars ({short_bucket['hit_rate']}%) vs 500+ chars ({long_bucket['hit_rate']}%)"
                )
            else:
                insights.append(
                    f"Longer descriptions outperform shorter ones: "
                    f"500+ chars ({long_bucket['hit_rate']}%) vs 0-50 chars ({short_bucket['hit_rate']}%)"
                )

        # Line count insight
        if line_stats:
            valid_lines = {k: v for k, v in line_stats.items() if v["count"] >= 3}
            if valid_lines:
                best_lines = max(valid_lines.items(), key=lambda x: x[1]["hit_rate"])
                insights.append(
                    f"Best line count: {best_lines[0]} "
                    f"({best_lines[1]['hit_rate']}% hit rate, n={best_lines[1]['count']})"
                )

        print(f"\n--- Key Insights ---")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        # 8. Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "baseline_hit_rate": baseline_hr,
            "description_length": desc_stats,
            "title_length": title_stats,
            "combined_length": combined_stats,
            "line_count": line_stats,
            "genre_optimal_length": genre_stats,
            "sweet_spot": {
                "description": sweet_spot,
                "title": sweet_spot_title,
            },
            "insights": insights,
        }

        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "optimal_length.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\nReport saved to: {out_path}")
        print("Done!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
