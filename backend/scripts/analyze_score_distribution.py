#!/usr/bin/env python3
"""Analyze hit_score distribution and identify clustering issues.

Examines the current hit_score distribution across all ads, identifies
that most ads cluster at 89-93 (or similar narrow ranges), and computes
correlation with actual engagement metrics (views, spend, days running).

Outputs:
  - Detailed console report with statistics and histograms
  - backend/exports/score_distribution_analysis.json

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_score_distribution.py
"""

import io
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Statistics helpers (no external deps)
# ---------------------------------------------------------------------------

def _safe_mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _safe_median(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _safe_stdev(vals: list[float]) -> float:
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    variance = sum((x - m) ** 2 for x in vals) / (n - 1)
    return variance ** 0.5 if variance > 0 else 0.0


def _percentile(vals: list[float], p: float) -> float:
    """Compute the p-th percentile (0-100)."""
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation coefficient between two lists."""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return 0.0

    mx = sum(xs) / n
    my = sum(ys) / n

    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs)
    dy = sum((y - my) ** 2 for y in ys)

    denom = (dx * dy) ** 0.5
    if denom == 0:
        return 0.0
    return num / denom


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_ad_data(ad: Ad) -> dict:
    """Extract scoring and metric data from an ad."""
    meta = ad.ad_metadata or {}

    # Hit score
    try:
        score = float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        score = 0.0

    # Score breakdown
    breakdown = meta.get("latest_score_breakdown", {})

    # Days running
    days_running = meta.get("days_running", 0)
    if days_running == 0 and ad.first_seen_at:
        now = datetime.now(timezone.utc)
        first = ad.first_seen_at
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        days_running = max(0, (now - first).days)

    # Genre
    genre = meta.get("fine_genre_en") or "other"

    # Is still running
    is_still_running = meta.get("is_still_running", ad.last_seen_at is None)

    return {
        "id": ad.id,
        "score": score,
        "breakdown": breakdown,
        "days_running": days_running,
        "genre": genre,
        "is_still_running": is_still_running,
        "view_count": ad.view_count or 0,
        "like_count": ad.like_count or 0,
        "spend": ad.spend or 0,
        "has_video": bool(ad.video_url),
        "has_image": bool(ad.image_url),
        "has_thumbnail": bool(ad.thumbnail_url),
        "hit_level": meta.get("hit_level", "none"),
    }


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_distribution(scores: list[float]) -> dict:
    """Comprehensive distribution analysis."""
    if not scores:
        return {"empty": True}

    n = len(scores)
    result = {
        "count": n,
        "mean": round(_safe_mean(scores), 2),
        "median": round(_safe_median(scores), 2),
        "stdev": round(_safe_stdev(scores), 2),
        "min": round(min(scores), 2),
        "max": round(max(scores), 2),
        "percentiles": {
            "p5": round(_percentile(scores, 5), 2),
            "p10": round(_percentile(scores, 10), 2),
            "p25": round(_percentile(scores, 25), 2),
            "p50": round(_percentile(scores, 50), 2),
            "p75": round(_percentile(scores, 75), 2),
            "p90": round(_percentile(scores, 90), 2),
            "p95": round(_percentile(scores, 95), 2),
        },
    }

    # Bucket distribution (1-point resolution)
    fine_buckets: Counter = Counter()
    for s in scores:
        fine_buckets[int(s)] += 1

    result["fine_buckets"] = dict(sorted(fine_buckets.items()))

    # 10-wide bucket distribution
    wide_buckets: Counter = Counter()
    for s in scores:
        bucket = min(int(s // 10) * 10, 90)
        wide_buckets[f"{bucket}-{bucket + 9}"] += 1
    result["wide_buckets"] = dict(sorted(wide_buckets.items()))

    # Clustering analysis: find the most crowded 5-point range
    best_range_start = 0
    best_range_count = 0
    for start in range(0, 96):
        count = sum(1 for s in scores if start <= s < start + 5)
        if count > best_range_count:
            best_range_count = count
            best_range_start = start

    result["most_crowded_range"] = {
        "start": best_range_start,
        "end": best_range_start + 5,
        "count": best_range_count,
        "pct": round(best_range_count / n * 100, 1),
    }

    # Effective range (where 80% of scores fall)
    p10 = _percentile(scores, 10)
    p90 = _percentile(scores, 90)
    result["effective_range"] = {
        "p10": round(p10, 1),
        "p90": round(p90, 1),
        "spread": round(p90 - p10, 1),
    }

    # Clustering issues
    issues = []
    iqr = result["percentiles"]["p75"] - result["percentiles"]["p25"]
    if iqr < 10:
        issues.append(f"Very narrow IQR ({iqr:.1f}) - scores are highly clustered")
    if result["stdev"] < 10:
        issues.append(f"Low standard deviation ({result['stdev']:.1f}) - poor discriminating power")
    if best_range_count / n > 0.4:
        issues.append(
            f"Over 40% of ads in {best_range_start}-{best_range_start + 5} range "
            f"({best_range_count}/{n})"
        )
    if p90 - p10 < 20:
        issues.append(f"80% of scores fall in just {p90 - p10:.1f} point range ({p10:.0f}-{p90:.0f})")

    result["issues"] = issues
    return result


def analyze_correlations(data: list[dict]) -> dict:
    """Analyze correlation between hit_score and actual metrics."""
    scores = [d["score"] for d in data]
    views = [d["view_count"] for d in data]
    likes = [d["like_count"] for d in data]
    days = [d["days_running"] for d in data]
    spends = [d["spend"] for d in data]

    # Only use ads with nonzero metrics for meaningful correlation
    score_view_pairs = [(d["score"], d["view_count"]) for d in data if d["view_count"] > 0]
    score_spend_pairs = [(d["score"], d["spend"]) for d in data if d["spend"] > 0]
    score_days_pairs = [(d["score"], d["days_running"]) for d in data if d["days_running"] > 0]
    score_like_pairs = [(d["score"], d["like_count"]) for d in data if d["like_count"] > 0]

    correlations = {}

    if len(score_view_pairs) >= 3:
        xs, ys = zip(*score_view_pairs)
        correlations["score_vs_views"] = {
            "r": round(_pearson_correlation(list(xs), list(ys)), 4),
            "n": len(score_view_pairs),
        }

    if len(score_spend_pairs) >= 3:
        xs, ys = zip(*score_spend_pairs)
        correlations["score_vs_spend"] = {
            "r": round(_pearson_correlation(list(xs), list(ys)), 4),
            "n": len(score_spend_pairs),
        }

    if len(score_days_pairs) >= 3:
        xs, ys = zip(*score_days_pairs)
        correlations["score_vs_days_running"] = {
            "r": round(_pearson_correlation(list(xs), list(ys)), 4),
            "n": len(score_days_pairs),
        }

    if len(score_like_pairs) >= 3:
        xs, ys = zip(*score_like_pairs)
        correlations["score_vs_likes"] = {
            "r": round(_pearson_correlation(list(xs), list(ys)), 4),
            "n": len(score_like_pairs),
        }

    # Also compute correlation between individual signal components
    signal_names = ["longevity", "spend", "active_bonus", "creative", "trend"]
    for sig in signal_names:
        sig_values = [d["breakdown"].get(sig, 0) for d in data if d["breakdown"]]
        if len(sig_values) >= 3 and len(views) == len(sig_values):
            nonzero_pairs = [
                (s, v) for s, v in zip(sig_values, views) if v > 0
            ]
            if len(nonzero_pairs) >= 3:
                xs, ys = zip(*nonzero_pairs)
                correlations[f"{sig}_vs_views"] = {
                    "r": round(_pearson_correlation(list(xs), list(ys)), 4),
                    "n": len(nonzero_pairs),
                }

    return correlations


def analyze_by_genre(data: list[dict]) -> dict:
    """Break down score distribution by genre."""
    genre_data: dict[str, list[float]] = defaultdict(list)
    for d in data:
        genre_data[d["genre"]].append(d["score"])

    result = {}
    for genre, scores in sorted(genre_data.items(), key=lambda x: -len(x[1])):
        if len(scores) < 2:
            continue
        result[genre] = {
            "count": len(scores),
            "mean": round(_safe_mean(scores), 1),
            "median": round(_safe_median(scores), 1),
            "stdev": round(_safe_stdev(scores), 1),
            "min": round(min(scores), 1),
            "max": round(max(scores), 1),
        }

    return result


def analyze_signal_contribution(data: list[dict]) -> dict:
    """Analyze how each signal contributes to the total score."""
    signal_names = ["longevity", "spend", "active_bonus", "creative", "trend"]
    signal_max = {"longevity": 40, "spend": 20, "active_bonus": 20, "creative": 10, "trend": 10}

    results = {}
    for sig in signal_names:
        values = [d["breakdown"].get(sig, 0) for d in data if d["breakdown"]]
        if not values:
            continue
        max_possible = signal_max.get(sig, 10)
        results[sig] = {
            "max_possible": max_possible,
            "mean": round(_safe_mean(values), 1),
            "median": round(_safe_median(values), 1),
            "stdev": round(_safe_stdev(values), 1),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "utilization": round(_safe_mean(values) / max_possible * 100, 1) if max_possible > 0 else 0,
            "at_zero_pct": round(sum(1 for v in values if v == 0) / len(values) * 100, 1),
            "at_max_pct": round(sum(1 for v in values if v >= max_possible * 0.9) / len(values) * 100, 1),
        }

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 64)
    print("  Hit Score Distribution Analysis")
    print(f"  Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 64)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads loaded: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Extract data
        data = [extract_ad_data(ad) for ad in ads]
        scores = [d["score"] for d in data]
        nonzero_scores = [s for s in scores if s > 0]

        # ---- 1. Overall distribution ----
        dist = analyze_distribution(scores)
        print(f"\n{'=' * 64}")
        print(f"  1. OVERALL SCORE DISTRIBUTION")
        print(f"{'=' * 64}")
        print(f"  Count:  {dist['count']}")
        print(f"  Mean:   {dist['mean']}")
        print(f"  Median: {dist['median']}")
        print(f"  StdDev: {dist['stdev']}")
        print(f"  Min:    {dist['min']}")
        print(f"  Max:    {dist['max']}")

        print(f"\n  Percentiles:")
        for label, value in dist["percentiles"].items():
            print(f"    {label}: {value}")

        print(f"\n  Most crowded 5-point range: "
              f"{dist['most_crowded_range']['start']}-{dist['most_crowded_range']['end']} "
              f"({dist['most_crowded_range']['count']} ads, "
              f"{dist['most_crowded_range']['pct']}%)")

        print(f"\n  Effective range (P10-P90): "
              f"{dist['effective_range']['p10']}-{dist['effective_range']['p90']} "
              f"(spread: {dist['effective_range']['spread']} points)")

        # Histogram
        print(f"\n  10-point Bucket Histogram:")
        max_count = max(dist["wide_buckets"].values()) if dist["wide_buckets"] else 1
        for lo in range(0, 100, 10):
            key = f"{lo}-{lo + 9}"
            count = dist["wide_buckets"].get(key, 0)
            pct = count / total * 100
            bar_len = int(count / max(max_count, 1) * 40)
            bar = "#" * bar_len
            print(f"    {key:>7s}: {count:>5d} ({pct:>5.1f}%) |{bar}")

        # Fine-grained histogram for the clustered region
        crowded_start = max(0, dist["most_crowded_range"]["start"] - 5)
        crowded_end = min(100, dist["most_crowded_range"]["end"] + 5)
        print(f"\n  Fine-grained histogram ({crowded_start}-{crowded_end}):")
        for score_val in range(crowded_start, crowded_end + 1):
            count = dist["fine_buckets"].get(score_val, 0)
            if count > 0:
                pct = count / total * 100
                bar = "#" * min(int(pct * 2), 60)
                print(f"    score={score_val:>3d}: {count:>5d} ({pct:>5.1f}%) {bar}")

        # Issues
        if dist["issues"]:
            print(f"\n  ISSUES DETECTED:")
            for issue in dist["issues"]:
                print(f"    [!] {issue}")
        else:
            print(f"\n  No major distribution issues detected.")

        # ---- 2. Non-zero scores only ----
        if nonzero_scores:
            nz_dist = analyze_distribution(nonzero_scores)
            print(f"\n{'=' * 64}")
            print(f"  2. NON-ZERO SCORES ONLY ({len(nonzero_scores)} ads)")
            print(f"{'=' * 64}")
            print(f"  Mean:   {nz_dist['mean']}")
            print(f"  Median: {nz_dist['median']}")
            print(f"  StdDev: {nz_dist['stdev']}")
            zero_count = sum(1 for s in scores if s == 0)
            print(f"  Ads with score=0: {zero_count} ({zero_count / total * 100:.1f}%)")

        # ---- 3. Signal contribution analysis ----
        signal_analysis = analyze_signal_contribution(data)
        if signal_analysis:
            print(f"\n{'=' * 64}")
            print(f"  3. SIGNAL CONTRIBUTION ANALYSIS")
            print(f"{'=' * 64}")
            print(f"  {'Signal':<20s} {'Max':>4s} {'Mean':>6s} {'Util%':>6s} {'Zero%':>6s} {'Max%':>6s}")
            print(f"  {'-' * 50}")
            for sig, info in signal_analysis.items():
                print(
                    f"  {sig:<20s} "
                    f"{info['max_possible']:>4d} "
                    f"{info['mean']:>6.1f} "
                    f"{info['utilization']:>5.1f}% "
                    f"{info['at_zero_pct']:>5.1f}% "
                    f"{info['at_max_pct']:>5.1f}%"
                )

        # ---- 4. Correlation analysis ----
        correlations = analyze_correlations(data)
        if correlations:
            print(f"\n{'=' * 64}")
            print(f"  4. CORRELATION ANALYSIS (Pearson r)")
            print(f"{'=' * 64}")
            for label, info in correlations.items():
                r = info["r"]
                n = info["n"]
                strength = (
                    "strong" if abs(r) > 0.7
                    else "moderate" if abs(r) > 0.4
                    else "weak" if abs(r) > 0.2
                    else "negligible"
                )
                print(f"  {label:<30s}  r={r:>7.4f}  n={n:>5d}  ({strength})")

        # ---- 5. Genre breakdown ----
        genre_breakdown = analyze_by_genre(data)
        if genre_breakdown:
            print(f"\n{'=' * 64}")
            print(f"  5. SCORE DISTRIBUTION BY GENRE")
            print(f"{'=' * 64}")
            print(f"  {'Genre':<25s} {'Count':>6s} {'Mean':>6s} {'Median':>7s} {'StdDev':>7s} {'Range':>12s}")
            print(f"  {'-' * 67}")
            for genre, info in genre_breakdown.items():
                range_str = f"{info['min']:.0f}-{info['max']:.0f}"
                print(
                    f"  {genre:<25s} "
                    f"{info['count']:>6d} "
                    f"{info['mean']:>6.1f} "
                    f"{info['median']:>7.1f} "
                    f"{info['stdev']:>7.1f} "
                    f"{range_str:>12s}"
                )

        # ---- 6. Hit level distribution ----
        hit_counter: Counter = Counter()
        for d in data:
            hit_counter[d["hit_level"]] += 1

        print(f"\n{'=' * 64}")
        print(f"  6. HIT LEVEL DISTRIBUTION")
        print(f"{'=' * 64}")
        for level in ["mega_hit", "hit", "none"]:
            count = hit_counter.get(level, 0)
            pct = count / total * 100
            print(f"  {level:<15s} {count:>6d} ({pct:>5.1f}%)")

        # ---- 7. Diagnosis and recommendations ----
        print(f"\n{'=' * 64}")
        print(f"  7. DIAGNOSIS & RECOMMENDATIONS")
        print(f"{'=' * 64}")

        iqr = dist["percentiles"]["p75"] - dist["percentiles"]["p25"]
        effective_spread = dist["effective_range"]["spread"]

        if effective_spread < 20:
            print(f"  [CRITICAL] Score clustering detected.")
            print(f"    - 80% of ads fall within a {effective_spread:.0f}-point range")
            print(f"    - IQR is only {iqr:.1f} points")
            print(f"    - Scoring algorithm lacks discriminating power")
            print(f"  Recommended actions:")
            print(f"    1. Apply percentile normalization to spread scores across 0-100")
            print(f"    2. Use genre-relative scoring (z-score within genre)")
            print(f"    3. Add recency boost for recently active ads")
            print(f"    4. Increase weight differentiation between signals")
        elif effective_spread < 40:
            print(f"  [WARNING] Moderate score clustering.")
            print(f"    - 80% of ads in a {effective_spread:.0f}-point range")
            print(f"    - Consider percentile normalization for better discrimination")
        else:
            print(f"  [OK] Score distribution has adequate spread ({effective_spread:.0f} points)")

        # Export
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "score_distribution_analysis.json")

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "distribution": dist,
            "signal_analysis": signal_analysis,
            "correlations": correlations,
            "genre_breakdown": genre_breakdown,
            "hit_level_distribution": dict(hit_counter),
            "diagnosis": {
                "effective_spread": effective_spread,
                "iqr": iqr,
                "most_crowded_range": dist["most_crowded_range"],
                "issues": dist["issues"],
            },
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")
        print("\nDone.")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
