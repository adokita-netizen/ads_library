#!/usr/bin/env python3
"""Calibrate hit scores and compute percentile ranks.

Analyzes current score distribution, checks for clustering issues,
and computes percentile-based rankings.

Outputs:
  - backend/exports/score_calibration.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/calibrate_hit_scores.py
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from statistics import mean, median, stdev

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_score(ad: Ad) -> float:
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _safe_stdev(vals: list[float]) -> float:
    return stdev(vals) if len(vals) >= 2 else 0.0


# ── Calibration ──────────────────────────────────────────────────────────


def analyze_distribution(scores: list[float]) -> dict:
    """Analyze score distribution for clustering and spread."""
    if not scores:
        return {"empty": True}

    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    # Percentiles
    p10 = sorted_scores[int(n * 0.1)]
    p25 = sorted_scores[int(n * 0.25)]
    p50 = sorted_scores[int(n * 0.5)]
    p75 = sorted_scores[int(n * 0.75)]
    p90 = sorted_scores[int(n * 0.9)]

    # Bucket distribution
    buckets = Counter()
    for s in scores:
        if s == 0:
            buckets["0"] += 1
        elif s <= 10:
            buckets["1-10"] += 1
        elif s <= 20:
            buckets["11-20"] += 1
        elif s <= 30:
            buckets["21-30"] += 1
        elif s <= 40:
            buckets["31-40"] += 1
        elif s <= 50:
            buckets["41-50"] += 1
        elif s <= 60:
            buckets["51-60"] += 1
        elif s <= 70:
            buckets["61-70"] += 1
        elif s <= 80:
            buckets["71-80"] += 1
        elif s <= 90:
            buckets["81-90"] += 1
        else:
            buckets["91-100"] += 1

    # Clustering check
    zero_count = sum(1 for s in scores if s == 0)
    max_count = sum(1 for s in scores if s >= 90)
    mid_range = sum(1 for s in scores if 30 <= s <= 70)

    issues = []
    if zero_count / n > 0.3:
        issues.append(f"Too many zero scores ({zero_count}/{n} = {zero_count/n*100:.1f}%)")
    if max_count / n > 0.3:
        issues.append(f"Too many max scores ({max_count}/{n} = {max_count/n*100:.1f}%)")
    if mid_range / n < 0.2:
        issues.append(f"Too few mid-range scores ({mid_range}/{n} = {mid_range/n*100:.1f}%)")

    return {
        "count": n,
        "mean": round(mean(scores), 1),
        "median": round(median(scores), 1),
        "stdev": round(_safe_stdev(scores), 1),
        "min": round(min(scores), 1),
        "max": round(max(scores), 1),
        "percentiles": {
            "p10": round(p10, 1),
            "p25": round(p25, 1),
            "p50": round(p50, 1),
            "p75": round(p75, 1),
            "p90": round(p90, 1),
        },
        "bucket_distribution": dict(sorted(buckets.items())),
        "zero_count": zero_count,
        "max_count": max_count,
        "issues": issues,
    }


def compute_percentile_rank(score: float, sorted_scores: list[float]) -> float:
    """Compute percentile rank for a score."""
    n = len(sorted_scores)
    if n == 0:
        return 0.0
    below = sum(1 for s in sorted_scores if s < score)
    return round(below / n * 100, 1)


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[calibrate_hit_scores] Total ads: {len(ads)}")

        scores = [_get_score(a) for a in ads]
        all_scores = sorted(scores)

        # 1. Analyze distribution
        dist = analyze_distribution(scores)
        print(f"\n  Score distribution:")
        print(f"    Mean: {dist['mean']}, Median: {dist['median']}, StDev: {dist['stdev']}")
        print(f"    Min: {dist['min']}, Max: {dist['max']}")
        print(f"    P10={dist['percentiles']['p10']}, P25={dist['percentiles']['p25']}, "
              f"P50={dist['percentiles']['p50']}, P75={dist['percentiles']['p75']}, "
              f"P90={dist['percentiles']['p90']}")

        print(f"\n  Bucket distribution:")
        for bucket, count in sorted(dist["bucket_distribution"].items()):
            pct = count / len(scores) * 100
            bar = "#" * int(pct / 2)
            print(f"    {bucket:>7s}: {count:>4d} ({pct:>5.1f}%) {bar}")

        if dist["issues"]:
            print(f"\n  Issues detected:")
            for issue in dist["issues"]:
                print(f"    - {issue}")
        else:
            print(f"\n  No distribution issues detected.")

        # 2. Compute percentile ranks and store
        updated = 0
        for ad in ads:
            score = _get_score(ad)
            percentile = compute_percentile_rank(score, all_scores)
            tier = "top_10" if percentile >= 90 else (
                "top_25" if percentile >= 75 else (
                    "top_50" if percentile >= 50 else "bottom_50"
                )
            )

            meta = dict(ad.ad_metadata or {})
            meta["score_calibration"] = {
                "percentile_rank": percentile,
                "tier": tier,
                "calibrated_at": datetime.now(timezone.utc).isoformat(),
            }
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

        session.commit()
        print(f"\n  Percentile ranks assigned: {updated} ads")

        # 3. Tier distribution
        tier_counts = Counter()
        for ad in ads:
            tier = (ad.ad_metadata or {}).get("score_calibration", {}).get("tier", "unknown")
            tier_counts[tier] += 1
        print(f"\n  Tier distribution:")
        for tier, count in tier_counts.most_common():
            print(f"    {tier}: {count}")

        # Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "distribution": dist,
            "tier_distribution": dict(tier_counts),
            "calibration_status": "no_issues" if not dist["issues"] else "issues_found",
        }

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "score_calibration.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
