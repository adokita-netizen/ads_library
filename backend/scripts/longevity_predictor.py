#!/usr/bin/env python3
"""Predict ad longevity based on creative features.

Analyzes which creative features (hook, CTA, emotion, creative_type)
correlate with long-running ads. Scores each feature by its correlation
with longevity_class.

Outputs:
  - backend/exports/longevity_factors.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/longevity_predictor.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, stdev

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Constants ────────────────────────────────────────────────────────────

# Longevity class to numeric score for correlation
LONGEVITY_SCORES = {
    "flash": 1,
    "short": 2,
    "medium": 3,
    "long": 4,
}

CREATIVE_FIELDS = ["hook_type", "cta_type", "offer_type", "emotion", "creative_type"]


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_longevity_score(ad: Ad) -> int | None:
    """Get numeric longevity score (1-4) from ad_metadata."""
    meta = ad.ad_metadata or {}
    lc = meta.get("longevity_class")
    if lc:
        return LONGEVITY_SCORES.get(lc)
    return None


def _get_days_running(ad: Ad) -> float | None:
    """Get days_running from ad_metadata."""
    meta = ad.ad_metadata or {}
    dr = meta.get("days_running") or meta.get("estimated_days_running")
    if dr is not None:
        try:
            return float(dr)
        except (ValueError, TypeError):
            pass
    return None


def _get_creative(ad: Ad) -> dict | None:
    meta = ad.ad_metadata or {}
    return meta.get("creative_analysis")


def _get_score(ad: Ad) -> float:
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _safe_mean(vals: list[float]) -> float:
    return mean(vals) if vals else 0.0


def _safe_stdev(vals: list[float]) -> float:
    return stdev(vals) if len(vals) >= 2 else 0.0


# ── Analysis Functions ───────────────────────────────────────────────────


def compute_feature_longevity_correlation(ads: list[Ad]) -> dict:
    """For each creative field value, compute avg longevity score and days_running."""
    field_stats: dict[str, dict[str, list]] = {}

    for field in CREATIVE_FIELDS:
        field_stats[field] = defaultdict(lambda: {"longevity_scores": [], "days_running": [], "hit_scores": []})

    for ad in ads:
        ca = _get_creative(ad)
        ls = _get_longevity_score(ad)
        dr = _get_days_running(ad)
        hs = _get_score(ad)

        if not ca:
            continue

        for field in CREATIVE_FIELDS:
            if field == "creative_type":
                val = ad.creative_type or "unknown"
            else:
                val = ca.get(field, "none")

            bucket = field_stats[field][val]
            if ls is not None:
                bucket["longevity_scores"].append(ls)
            if dr is not None:
                bucket["days_running"].append(dr)
            bucket["hit_scores"].append(hs)

    # Compute summary stats
    results = {}
    for field in CREATIVE_FIELDS:
        field_result = {}
        for val, data in field_stats[field].items():
            if not data["longevity_scores"]:
                continue
            field_result[val] = {
                "count": len(data["longevity_scores"]),
                "avg_longevity_score": round(_safe_mean(data["longevity_scores"]), 2),
                "avg_days_running": round(_safe_mean(data["days_running"]), 1) if data["days_running"] else None,
                "stdev_days": round(_safe_stdev(data["days_running"]), 1) if len(data["days_running"]) >= 2 else None,
                "avg_hit_score": round(_safe_mean(data["hit_scores"]), 1),
                "long_rate": round(
                    sum(1 for s in data["longevity_scores"] if s == 4) / len(data["longevity_scores"]) * 100, 1
                ),
            }
        # Sort by avg_longevity_score descending
        results[field] = dict(sorted(
            field_result.items(),
            key=lambda x: x[1]["avg_longevity_score"],
            reverse=True,
        ))

    return results


def compute_longevity_prediction_rules(correlations: dict, min_count: int = 3) -> list[dict]:
    """Generate simple prediction rules from correlation data."""
    rules = []

    for field, values in correlations.items():
        for val, stats in values.items():
            if stats["count"] < min_count:
                continue

            # Predict "long" if avg longevity score >= 3.0
            if stats["avg_longevity_score"] >= 3.0:
                rules.append({
                    "rule": f"{field}={val} -> likely LONG-RUNNING",
                    "field": field,
                    "value": val,
                    "avg_longevity": stats["avg_longevity_score"],
                    "long_rate": stats["long_rate"],
                    "confidence": "high" if stats["count"] >= 10 else "medium",
                    "sample_size": stats["count"],
                })
            elif stats["avg_longevity_score"] <= 2.0:
                rules.append({
                    "rule": f"{field}={val} -> likely SHORT-LIVED",
                    "field": field,
                    "value": val,
                    "avg_longevity": stats["avg_longevity_score"],
                    "long_rate": stats["long_rate"],
                    "confidence": "high" if stats["count"] >= 10 else "medium",
                    "sample_size": stats["count"],
                })

    return sorted(rules, key=lambda x: abs(x["avg_longevity"] - 2.5), reverse=True)


def compute_combo_longevity(ads: list[Ad], min_count: int = 2) -> list[dict]:
    """Find feature combinations that predict longevity."""
    combos: dict[str, list] = defaultdict(lambda: {"longevity": [], "days": [], "scores": []})

    for ad in ads:
        ca = _get_creative(ad)
        ls = _get_longevity_score(ad)
        dr = _get_days_running(ad)
        hs = _get_score(ad)

        if not ca or ls is None:
            continue

        hook = ca.get("hook_type", "none")
        cta = ca.get("cta_type", "none")
        ct = ad.creative_type or "unknown"
        combo_key = f"{hook}+{cta}+{ct}"

        combos[combo_key]["longevity"].append(ls)
        if dr is not None:
            combos[combo_key]["days"].append(dr)
        combos[combo_key]["scores"].append(hs)

    results = []
    for combo, data in combos.items():
        if len(data["longevity"]) < min_count:
            continue
        results.append({
            "combo": combo,
            "count": len(data["longevity"]),
            "avg_longevity": round(_safe_mean(data["longevity"]), 2),
            "avg_days": round(_safe_mean(data["days"]), 1) if data["days"] else None,
            "avg_score": round(_safe_mean(data["scores"]), 1),
            "long_rate": round(sum(1 for s in data["longevity"] if s == 4) / len(data["longevity"]) * 100, 1),
        })

    return sorted(results, key=lambda x: x["avg_longevity"], reverse=True)


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[longevity_predictor] Loaded {len(ads)} ads")

        # Count longevity distribution
        longevity_dist = defaultdict(int)
        for ad in ads:
            meta = ad.ad_metadata or {}
            lc = meta.get("longevity_class", "unknown")
            longevity_dist[lc] += 1
        print(f"  Longevity distribution: {dict(longevity_dist)}")

        # 1. Feature-longevity correlation
        correlations = compute_feature_longevity_correlation(ads)
        print(f"\n  Feature importance (by longevity prediction):")
        for field, values in correlations.items():
            if values:
                best_val = list(values.keys())[0]
                best_stats = values[best_val]
                worst_val = list(values.keys())[-1]
                worst_stats = values[worst_val]
                print(f"    {field}: best={best_val} (avg {best_stats['avg_longevity_score']}, "
                      f"long_rate {best_stats['long_rate']}%), "
                      f"worst={worst_val} ({worst_stats['avg_longevity_score']})")

        # 2. Prediction rules
        rules = compute_longevity_prediction_rules(correlations)
        long_rules = [r for r in rules if "LONG" in r["rule"]]
        short_rules = [r for r in rules if "SHORT" in r["rule"]]
        print(f"\n  Prediction rules: {len(long_rules)} LONG, {len(short_rules)} SHORT")
        for r in long_rules[:5]:
            print(f"    {r['rule']} (long_rate={r['long_rate']}%, n={r['sample_size']})")

        # 3. Combo longevity
        combos = compute_combo_longevity(ads)
        print(f"\n  Top combos for longevity (hook+cta+type):")
        for c in combos[:5]:
            print(f"    {c['combo']}: avg_longevity={c['avg_longevity']}, "
                  f"avg_days={c['avg_days']}, n={c['count']}")

        # Build insights
        insights = []
        if long_rules:
            insights.append(f"Strongest longevity predictor: {long_rules[0]['rule']}")
        if combos:
            insights.append(f"Best combo for longevity: {combos[0]['combo']} "
                          f"(avg {combos[0]['avg_longevity']} longevity score)")

        # Compute overall feature importance ranking
        feature_importance = []
        for field, values in correlations.items():
            scores = [v["avg_longevity_score"] for v in values.values() if v["count"] >= 3]
            if len(scores) >= 2:
                spread = max(scores) - min(scores)
                feature_importance.append({
                    "field": field,
                    "spread": round(spread, 2),
                    "max_longevity": round(max(scores), 2),
                    "min_longevity": round(min(scores), 2),
                })
        feature_importance.sort(key=lambda x: x["spread"], reverse=True)
        print(f"\n  Feature importance ranking (by longevity spread):")
        for fi in feature_importance:
            print(f"    {fi['field']}: spread={fi['spread']} "
                  f"(range {fi['min_longevity']}-{fi['max_longevity']})")

        # Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "longevity_distribution": dict(longevity_dist),
            "feature_correlations": correlations,
            "prediction_rules": rules,
            "combo_longevity": combos[:30],
            "feature_importance": feature_importance,
            "insights": insights,
        }

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "longevity_factors.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
