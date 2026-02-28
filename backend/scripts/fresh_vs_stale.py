#!/usr/bin/env python3
"""Compare fresh (recent) ads vs stale (older) ads.

Analyzes whether newer ads use different creative patterns than older ads,
identifying what's changing in the market.

Outputs:
  - backend/exports/fresh_vs_stale.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/fresh_vs_stale.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_score(ad: Ad) -> float:
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_creative(ad: Ad) -> dict | None:
    meta = ad.ad_metadata or {}
    return meta.get("creative_analysis")


def _safe_mean(vals: list[float]) -> float:
    return mean(vals) if vals else 0.0


# ── Analysis Functions ───────────────────────────────────────────────────


def split_fresh_stale(ads: list[Ad], days: int = 7) -> tuple[list[Ad], list[Ad]]:
    """Split ads into fresh (last N days) and stale (older)."""
    # Use the most recent ad's date as reference to handle non-current data
    all_dates = [a.first_seen_at or a.created_at for a in ads if (a.first_seen_at or a.created_at)]
    if not all_dates:
        return [], ads

    # Find the latest date in data, use that as "now" reference
    latest_date = max(all_dates)
    cutoff = latest_date - timedelta(days=days)

    fresh = []
    stale = []
    for ad in ads:
        dt = ad.first_seen_at or ad.created_at
        if dt and dt >= cutoff:
            fresh.append(ad)
        else:
            stale.append(ad)

    return fresh, stale


def compute_group_stats(ads: list[Ad], label: str) -> dict:
    """Compute comprehensive stats for a group of ads."""
    if not ads:
        return {"label": label, "count": 0}

    scores = [_get_score(a) for a in ads]
    hits = sum(1 for a in ads if _is_hit(a))

    # Creative field distributions
    hooks = Counter()
    ctas = Counter()
    emotions = Counter()
    offers = Counter()
    types = Counter()

    for ad in ads:
        ca = _get_creative(ad)
        if ca:
            hooks[ca.get("hook_type", "none")] += 1
            ctas[ca.get("cta_type", "none")] += 1
            emotions[ca.get("emotion", "none")] += 1
            offers[ca.get("offer_type", "none")] += 1
        types[ad.creative_type or "unknown"] += 1

    # Genre distribution
    genres = Counter()
    for ad in ads:
        g = str(ad.category.value) if ad.category else "unknown"
        genres[g] += 1

    return {
        "label": label,
        "count": len(ads),
        "avg_score": round(_safe_mean(scores), 1),
        "hit_count": hits,
        "hit_rate": round(hits / len(ads) * 100, 1),
        "hooks": dict(hooks.most_common()),
        "ctas": dict(ctas.most_common()),
        "emotions": dict(emotions.most_common()),
        "offers": dict(offers.most_common()),
        "creative_types": dict(types.most_common()),
        "genres": dict(genres.most_common()),
    }


def compare_distributions(fresh_stats: dict, stale_stats: dict, field: str) -> list[dict]:
    """Compare a field's distribution between fresh and stale groups."""
    fresh_dist = fresh_stats.get(field, {})
    stale_dist = stale_stats.get(field, {})

    fresh_total = sum(fresh_dist.values()) or 1
    stale_total = sum(stale_dist.values()) or 1

    all_values = set(list(fresh_dist.keys()) + list(stale_dist.keys()))
    comparisons = []

    for val in all_values:
        fresh_pct = round(fresh_dist.get(val, 0) / fresh_total * 100, 1)
        stale_pct = round(stale_dist.get(val, 0) / stale_total * 100, 1)
        diff = round(fresh_pct - stale_pct, 1)

        comparisons.append({
            "value": val,
            "fresh_pct": fresh_pct,
            "stale_pct": stale_pct,
            "shift": diff,
            "direction": "increasing" if diff > 5 else ("decreasing" if diff < -5 else "stable"),
        })

    return sorted(comparisons, key=lambda x: abs(x["shift"]), reverse=True)


def identify_market_shifts(comparisons: dict[str, list[dict]]) -> list[str]:
    """Generate human-readable insights from comparisons."""
    insights = []

    for field, comps in comparisons.items():
        increasing = [c for c in comps if c["direction"] == "increasing"]
        decreasing = [c for c in comps if c["direction"] == "decreasing"]

        if increasing:
            top = increasing[0]
            insights.append(
                f"Rising {field}: '{top['value']}' (+{top['shift']}% share in fresh ads)"
            )
        if decreasing:
            top = decreasing[0]
            insights.append(
                f"Declining {field}: '{top['value']}' ({top['shift']}% share in fresh ads)"
            )

    return insights


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[fresh_vs_stale] Loaded {len(ads)} ads")

        # Split into fresh (7 days) and stale
        fresh, stale = split_fresh_stale(ads, days=7)
        print(f"  Fresh (last 7 days): {len(fresh)}")
        print(f"  Stale (older): {len(stale)}")

        # Also do 30-day split for broader view
        fresh_30, stale_30 = split_fresh_stale(ads, days=30)

        # Compute stats
        fresh_stats = compute_group_stats(fresh, "fresh_7d")
        stale_stats = compute_group_stats(stale, "stale")
        fresh_30_stats = compute_group_stats(fresh_30, "fresh_30d")
        stale_30_stats = compute_group_stats(stale_30, "stale_30d")

        # Print score comparison
        print(f"\n  7-day comparison:")
        print(f"    Fresh avg score: {fresh_stats.get('avg_score', 'N/A')}, "
              f"hit rate: {fresh_stats.get('hit_rate', 'N/A')}%")
        print(f"    Stale avg score: {stale_stats.get('avg_score', 'N/A')}, "
              f"hit rate: {stale_stats.get('hit_rate', 'N/A')}%")

        print(f"\n  30-day comparison:")
        print(f"    Fresh avg score: {fresh_30_stats.get('avg_score', 'N/A')}, "
              f"hit rate: {fresh_30_stats.get('hit_rate', 'N/A')}%")
        print(f"    Stale avg score: {stale_30_stats.get('avg_score', 'N/A')}, "
              f"hit rate: {stale_30_stats.get('hit_rate', 'N/A')}%")

        # Compare distributions (use 30-day for more data)
        comparisons_30 = {
            "hooks": compare_distributions(fresh_30_stats, stale_30_stats, "hooks"),
            "ctas": compare_distributions(fresh_30_stats, stale_30_stats, "ctas"),
            "emotions": compare_distributions(fresh_30_stats, stale_30_stats, "emotions"),
            "offers": compare_distributions(fresh_30_stats, stale_30_stats, "offers"),
            "creative_types": compare_distributions(fresh_30_stats, stale_30_stats, "creative_types"),
            "genres": compare_distributions(fresh_30_stats, stale_30_stats, "genres"),
        }

        comparisons_7 = {
            "hooks": compare_distributions(fresh_stats, stale_stats, "hooks"),
            "ctas": compare_distributions(fresh_stats, stale_stats, "ctas"),
            "emotions": compare_distributions(fresh_stats, stale_stats, "emotions"),
        }

        # Print shifts
        print(f"\n  Market shifts (30-day fresh vs stale):")
        for field, comps in comparisons_30.items():
            shifts = [c for c in comps if c["direction"] != "stable"]
            if shifts:
                print(f"    {field}:")
                for s in shifts[:3]:
                    arrow = "^" if s["direction"] == "increasing" else "v"
                    print(f"      {arrow} {s['value']}: {s['stale_pct']}% -> {s['fresh_pct']}% ({s['shift']:+.1f}%)")

        # Insights
        insights = identify_market_shifts(comparisons_30)
        print(f"\n  Key insights:")
        for i in insights:
            print(f"    - {i}")

        # Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "splits": {
                "7_day": {
                    "fresh_count": len(fresh),
                    "stale_count": len(stale),
                    "fresh_stats": fresh_stats,
                    "stale_stats": stale_stats,
                    "comparisons": comparisons_7,
                },
                "30_day": {
                    "fresh_count": len(fresh_30),
                    "stale_count": len(stale_30),
                    "fresh_stats": fresh_30_stats,
                    "stale_stats": stale_30_stats,
                    "comparisons": comparisons_30,
                },
            },
            "insights": insights,
        }

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "fresh_vs_stale.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
