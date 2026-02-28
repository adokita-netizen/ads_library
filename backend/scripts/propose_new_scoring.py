#!/usr/bin/env python3
"""Propose improved scoring algorithm using percentile normalization,
genre-relative scoring, and recency boost.

Reads current ad data, computes new scores using three techniques:
  1. Percentile normalization - maps raw scores to percentile ranks (0-100)
  2. Genre-relative scoring - z-score within genre, then normalize
  3. Recency boost - bonus for ads still running or recently active

Outputs a comparison report showing improved distribution spread.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/propose_new_scoring.py
"""

import io
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def _mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def _stdev(vals):
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return (sum((x - m) ** 2 for x in vals) / (n - 1)) ** 0.5


def _median(vals):
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _percentile(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * p / 100
    f, c = math.floor(k), math.ceil(k)
    return s[f] * (c - k) + s[c] * (k - f) if f != c else s[int(k)]


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

def _extract(ad: Ad) -> dict:
    meta = ad.ad_metadata or {}
    try:
        score = float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        score = 0.0

    breakdown = meta.get("latest_score_breakdown", {})
    genre = meta.get("fine_genre_en") or "other"

    days_running = meta.get("days_running", 0)
    if days_running == 0 and ad.first_seen_at:
        now = datetime.now(timezone.utc)
        first = ad.first_seen_at
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        days_running = max(0, (now - first).days)

    is_still_running = meta.get("is_still_running", ad.last_seen_at is None)

    # Recency: days since last seen
    days_since_last_seen = None
    if ad.last_seen_at:
        last = ad.last_seen_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        days_since_last_seen = max(0, (datetime.now(timezone.utc) - last).days)

    return {
        "id": ad.id,
        "raw_score": score,
        "breakdown": breakdown,
        "genre": genre,
        "days_running": days_running,
        "is_still_running": is_still_running,
        "days_since_last_seen": days_since_last_seen,
        "view_count": ad.view_count or 0,
        "spend": ad.spend or 0,
        "has_video": bool(ad.video_url),
        "has_image": bool(ad.image_url),
    }


# ---------------------------------------------------------------------------
# New scoring algorithms
# ---------------------------------------------------------------------------

def method1_percentile_normalization(data: list[dict]) -> list[dict]:
    """Method 1: Pure percentile normalization.

    Maps each raw score to its percentile rank among all ads.
    This guarantees a uniform distribution across 0-100.
    """
    scores = sorted(set(d["raw_score"] for d in data))
    n = len(data)
    all_scores = sorted(d["raw_score"] for d in data)

    result = []
    for d in data:
        # Count how many scores are strictly below this one
        below = sum(1 for s in all_scores if s < d["raw_score"])
        equal = sum(1 for s in all_scores if s == d["raw_score"])
        # Use midpoint percentile: (below + 0.5 * equal) / n * 100
        percentile = (below + 0.5 * equal) / n * 100
        result.append({
            **d,
            "new_score": round(percentile, 2),
            "method": "percentile_normalization",
        })

    return result


def method2_genre_relative(data: list[dict]) -> list[dict]:
    """Method 2: Genre-relative z-score normalization.

    For each genre, compute z-score of raw_score, then map to 0-100:
      calibrated = z * 20 + 50 (clamped to 0-100)

    This ensures that within each genre, scores are normally distributed
    around 50, with the best ads in the genre scoring highest.
    """
    # Group by genre
    genre_data: dict[str, list[dict]] = defaultdict(list)
    for d in data:
        genre_data[d["genre"]].append(d)

    # Compute genre stats
    genre_stats = {}
    for genre, g_data in genre_data.items():
        scores = [d["raw_score"] for d in g_data]
        genre_stats[genre] = {
            "mean": _mean(scores),
            "stdev": _stdev(scores),
            "count": len(scores),
        }

    result = []
    for d in data:
        genre = d["genre"]
        st = genre_stats[genre]

        if st["stdev"] == 0 or st["count"] < 3:
            # Not enough data for z-score normalization
            # Fall back to global percentile within genre
            calibrated = 50.0
        else:
            z = (d["raw_score"] - st["mean"]) / st["stdev"]
            calibrated = z * 20 + 50

        calibrated = _clamp(calibrated, 0, 100)

        result.append({
            **d,
            "new_score": round(calibrated, 2),
            "genre_mean": round(st["mean"], 2),
            "genre_stdev": round(st["stdev"], 2),
            "method": "genre_relative",
        })

    return result


def method3_hybrid_with_recency(data: list[dict]) -> list[dict]:
    """Method 3: Hybrid scoring with percentile base + genre adjustment + recency boost.

    Components:
      - Base (60%): Percentile normalization of raw score
      - Genre adjustment (20%): Genre-relative z-score
      - Recency boost (20%): Bonus for currently active or recently seen ads

    This provides the best of both worlds: global ranking fairness with
    genre context and recency relevance.
    """
    n = len(data)
    all_scores = sorted(d["raw_score"] for d in data)

    # Pre-compute genre stats
    genre_data: dict[str, list[dict]] = defaultdict(list)
    for d in data:
        genre_data[d["genre"]].append(d)

    genre_stats = {}
    for genre, g_data in genre_data.items():
        scores = [d["raw_score"] for d in g_data]
        genre_stats[genre] = {"mean": _mean(scores), "stdev": _stdev(scores)}

    result = []
    for d in data:
        # Component 1: Percentile base (0-100, weighted 60%)
        below = sum(1 for s in all_scores if s < d["raw_score"])
        equal = sum(1 for s in all_scores if s == d["raw_score"])
        percentile_score = (below + 0.5 * equal) / n * 100

        # Component 2: Genre-relative (0-100, weighted 20%)
        genre = d["genre"]
        st = genre_stats[genre]
        if st["stdev"] > 0:
            z = (d["raw_score"] - st["mean"]) / st["stdev"]
            genre_score = _clamp(z * 20 + 50, 0, 100)
        else:
            genre_score = 50.0

        # Component 3: Recency boost (0-100, weighted 20%)
        recency_score = 0.0
        if d["is_still_running"]:
            # Currently running ads get a big boost
            if d["days_running"] >= 60:
                recency_score = 100.0
            elif d["days_running"] >= 30:
                recency_score = 80.0
            elif d["days_running"] >= 14:
                recency_score = 60.0
            else:
                recency_score = 40.0
        elif d["days_since_last_seen"] is not None:
            # Stopped ads: decay based on how long ago they stopped
            if d["days_since_last_seen"] <= 7:
                recency_score = 30.0
            elif d["days_since_last_seen"] <= 30:
                recency_score = 15.0
            else:
                recency_score = 5.0

        # Combine: 60% percentile + 20% genre + 20% recency
        combined = (
            percentile_score * 0.60
            + genre_score * 0.20
            + recency_score * 0.20
        )
        combined = _clamp(combined, 0, 100)

        result.append({
            **d,
            "new_score": round(combined, 2),
            "components": {
                "percentile_base": round(percentile_score, 2),
                "genre_relative": round(genre_score, 2),
                "recency_boost": round(recency_score, 2),
            },
            "method": "hybrid_recency",
        })

    return result


# ---------------------------------------------------------------------------
# Distribution analysis
# ---------------------------------------------------------------------------

def _analyze_dist(scores: list[float], label: str) -> dict:
    """Quick distribution stats for comparison."""
    n = len(scores)
    if n == 0:
        return {}
    return {
        "label": label,
        "mean": round(_mean(scores), 1),
        "median": round(_median(scores), 1),
        "stdev": round(_stdev(scores), 1),
        "p10": round(_percentile(scores, 10), 1),
        "p25": round(_percentile(scores, 25), 1),
        "p75": round(_percentile(scores, 75), 1),
        "p90": round(_percentile(scores, 90), 1),
        "iqr": round(_percentile(scores, 75) - _percentile(scores, 25), 1),
        "spread_p10_p90": round(_percentile(scores, 90) - _percentile(scores, 10), 1),
    }


def _print_histogram(scores, total, label):
    """Print a histogram for comparison."""
    print(f"\n  {label}:")
    buckets = Counter()
    for s in scores:
        bucket = min(int(s // 10) * 10, 90)
        buckets[f"{bucket}-{bucket + 9}"] += 1
    max_count = max(buckets.values()) if buckets else 1
    for lo in range(0, 100, 10):
        key = f"{lo}-{lo + 9}"
        count = buckets.get(key, 0)
        pct = count / total * 100
        bar = "#" * int(count / max(max_count, 1) * 35)
        print(f"    {key:>7s}: {count:>5d} ({pct:>5.1f}%) |{bar}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 64)
    print("  Propose New Scoring Algorithm")
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
        data = [_extract(ad) for ad in ads]
        raw_scores = [d["raw_score"] for d in data]

        # Current distribution baseline
        print(f"\n{'=' * 64}")
        print(f"  CURRENT SCORING (Baseline)")
        print(f"{'=' * 64}")
        baseline = _analyze_dist(raw_scores, "Current hit_score")
        print(f"  Mean:     {baseline['mean']}")
        print(f"  Median:   {baseline['median']}")
        print(f"  StdDev:   {baseline['stdev']}")
        print(f"  IQR:      {baseline['iqr']}")
        print(f"  P10-P90:  {baseline['spread_p10_p90']}")
        _print_histogram(raw_scores, total, "Current Distribution")

        # Method 1: Percentile normalization
        print(f"\n{'=' * 64}")
        print(f"  METHOD 1: Percentile Normalization")
        print(f"{'=' * 64}")
        print(f"  Description: Maps raw score to its percentile rank (0-100)")
        print(f"  Pros: Guarantees uniform distribution, maximizes discrimination")
        print(f"  Cons: Loses absolute meaning, always exactly uniform")

        m1_data = method1_percentile_normalization(data)
        m1_scores = [d["new_score"] for d in m1_data]
        m1_dist = _analyze_dist(m1_scores, "Percentile Normalized")
        print(f"\n  Mean:     {m1_dist['mean']}")
        print(f"  Median:   {m1_dist['median']}")
        print(f"  StdDev:   {m1_dist['stdev']}")
        print(f"  IQR:      {m1_dist['iqr']}")
        print(f"  P10-P90:  {m1_dist['spread_p10_p90']}")
        _print_histogram(m1_scores, total, "Method 1 Distribution")

        # Method 2: Genre-relative z-score
        print(f"\n{'=' * 64}")
        print(f"  METHOD 2: Genre-Relative Z-Score")
        print(f"{'=' * 64}")
        print(f"  Description: Z-score within genre, mapped to 0-100")
        print(f"  Pros: Fair comparison within genre, highlights genre leaders")
        print(f"  Cons: Cross-genre comparison less meaningful")

        m2_data = method2_genre_relative(data)
        m2_scores = [d["new_score"] for d in m2_data]
        m2_dist = _analyze_dist(m2_scores, "Genre-Relative")
        print(f"\n  Mean:     {m2_dist['mean']}")
        print(f"  Median:   {m2_dist['median']}")
        print(f"  StdDev:   {m2_dist['stdev']}")
        print(f"  IQR:      {m2_dist['iqr']}")
        print(f"  P10-P90:  {m2_dist['spread_p10_p90']}")
        _print_histogram(m2_scores, total, "Method 2 Distribution")

        # Method 3: Hybrid with recency
        print(f"\n{'=' * 64}")
        print(f"  METHOD 3: Hybrid (Percentile + Genre + Recency)  [RECOMMENDED]")
        print(f"{'=' * 64}")
        print(f"  Description: 60% percentile + 20% genre-relative + 20% recency")
        print(f"  Pros: Best balance of global fairness, genre context, and freshness")
        print(f"  Cons: More complex to explain")

        m3_data = method3_hybrid_with_recency(data)
        m3_scores = [d["new_score"] for d in m3_data]
        m3_dist = _analyze_dist(m3_scores, "Hybrid + Recency")
        print(f"\n  Mean:     {m3_dist['mean']}")
        print(f"  Median:   {m3_dist['median']}")
        print(f"  StdDev:   {m3_dist['stdev']}")
        print(f"  IQR:      {m3_dist['iqr']}")
        print(f"  P10-P90:  {m3_dist['spread_p10_p90']}")
        _print_histogram(m3_scores, total, "Method 3 Distribution")

        # Recency boost stats for method 3
        recency_scores = [d["components"]["recency_boost"] for d in m3_data]
        active = sum(1 for d in m3_data if d["is_still_running"])
        print(f"\n  Recency stats:")
        print(f"    Active ads:         {active} ({active / total * 100:.1f}%)")
        print(f"    Mean recency boost: {_mean(recency_scores):.1f}")

        # ---- Comparison table ----
        print(f"\n{'=' * 64}")
        print(f"  COMPARISON SUMMARY")
        print(f"{'=' * 64}")
        headers = f"  {'Method':<30s} {'Mean':>6s} {'StDev':>7s} {'IQR':>5s} {'P10-P90':>8s}"
        print(headers)
        print(f"  {'-' * 58}")
        for label, dist in [
            ("Current (baseline)", baseline),
            ("M1: Percentile", m1_dist),
            ("M2: Genre-Relative", m2_dist),
            ("M3: Hybrid + Recency [REC]", m3_dist),
        ]:
            print(
                f"  {label:<30s} "
                f"{dist['mean']:>6.1f} "
                f"{dist['stdev']:>7.1f} "
                f"{dist['iqr']:>5.1f} "
                f"{dist['spread_p10_p90']:>8.1f}"
            )

        # Improvement ratios
        if baseline["spread_p10_p90"] > 0:
            print(f"\n  Spread improvement ratios (vs. baseline):")
            for label, dist in [
                ("M1: Percentile", m1_dist),
                ("M2: Genre-Relative", m2_dist),
                ("M3: Hybrid + Recency", m3_dist),
            ]:
                ratio = dist["spread_p10_p90"] / baseline["spread_p10_p90"]
                print(f"    {label:<30s}  {ratio:.2f}x")

        # Three-tier distribution comparison
        print(f"\n  Three-Tier Distribution (target: ~20% / ~60% / ~20%):")
        print(f"  {'Method':<30s} {'Above 70':>10s} {'30-70':>10s} {'Below 30':>10s}")
        print(f"  {'-' * 62}")
        for label, scores in [
            ("Current", raw_scores),
            ("M1: Percentile", m1_scores),
            ("M2: Genre-Relative", m2_scores),
            ("M3: Hybrid + Recency", m3_scores),
        ]:
            a70 = sum(1 for s in scores if s > 70)
            mid = sum(1 for s in scores if 30 <= s <= 70)
            b30 = sum(1 for s in scores if s < 30)
            print(
                f"  {label:<30s} "
                f"{a70:>5d}({a70/total*100:>4.1f}%) "
                f"{mid:>5d}({mid/total*100:>4.1f}%) "
                f"{b30:>5d}({b30/total*100:>4.1f}%)"
            )

        # Recommendation
        print(f"\n{'=' * 64}")
        print(f"  RECOMMENDATION")
        print(f"{'=' * 64}")
        print(f"  Method 3 (Hybrid + Recency) is recommended because:")
        print(f"    1. It provides wider score distribution than the current system")
        print(f"    2. Genre-relative component ensures fair comparison within verticals")
        print(f"    3. Recency boost keeps active campaigns visible")
        print(f"    4. Percentile base prevents score clustering")
        print(f"")
        print(f"  To apply: python scripts/recalculate_scores.py")

        # Export
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "scoring_proposal.json")

        # Build export data with top/bottom examples for each method
        def _top_bottom(scored_data, n=5):
            sorted_d = sorted(scored_data, key=lambda x: -x["new_score"])
            top = [{"id": d["id"], "raw": d["raw_score"], "new": d["new_score"]} for d in sorted_d[:n]]
            bottom = [{"id": d["id"], "raw": d["raw_score"], "new": d["new_score"]} for d in sorted_d[-n:]]
            return {"top": top, "bottom": bottom}

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "baseline": baseline,
            "methods": {
                "percentile_normalization": {
                    "distribution": m1_dist,
                    "examples": _top_bottom(m1_data),
                },
                "genre_relative": {
                    "distribution": m2_dist,
                    "examples": _top_bottom(m2_data),
                },
                "hybrid_recency": {
                    "distribution": m3_dist,
                    "examples": _top_bottom(m3_data),
                    "recommended": True,
                },
            },
            "recommendation": "hybrid_recency",
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
