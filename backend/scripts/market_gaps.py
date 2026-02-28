#!/usr/bin/env python3
"""Market gap analysis: find under-served and over-saturated segments.

Identifies:
  - Under-served genres (few ads but high hit rate)
  - Over-saturated genres (many ads, low hit rate)
  - Hook/CTA combinations NOT being used but likely effective

Outputs:
  - backend/exports/market_gaps.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/market_gaps.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


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


def _get_creative(ad: Ad) -> dict | None:
    meta = ad.ad_metadata or {}
    return meta.get("creative_analysis")


def _safe_mean(vals: list[float]) -> float:
    return mean(vals) if vals else 0.0


# ── Analysis Functions ───────────────────────────────────────────────────


def analyze_genre_saturation(ads: list[Ad]) -> list[dict]:
    """Classify genres by saturation level."""
    genre_ads: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        genre = str(ad.category.value) if ad.category else "unknown"
        genre_ads[genre].append(ad)

    total = len(ads)
    results = []

    for genre, g_ads in genre_ads.items():
        scores = [_get_score(a) for a in g_ads]
        hits = sum(1 for a in g_ads if _is_hit(a))
        hr = hits / len(g_ads) * 100 if g_ads else 0
        share = len(g_ads) / total * 100 if total > 0 else 0

        # Classification
        if share < 5 and hr > 50:
            status = "under_served"
        elif share > 20 and hr < 30:
            status = "over_saturated"
        elif share > 20 and hr > 50:
            status = "competitive_but_viable"
        elif share < 5 and hr < 30:
            status = "niche_struggling"
        else:
            status = "balanced"

        results.append({
            "genre": genre,
            "ad_count": len(g_ads),
            "market_share": round(share, 1),
            "hit_count": hits,
            "hit_rate": round(hr, 1),
            "avg_score": round(_safe_mean(scores), 1),
            "saturation_status": status,
        })

    return sorted(results, key=lambda x: x["hit_rate"], reverse=True)


def find_unused_combos(ads: list[Ad]) -> list[dict]:
    """Find hook+CTA combinations NOT being used but likely effective.

    Strategy: find combos where each component has high hit rate individually
    but the combo itself has few or no ads.
    """
    # Compute individual field hit rates
    field_hit_rates: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"total": 0, "hits": 0}))

    for ad in ads:
        ca = _get_creative(ad)
        if not ca:
            continue
        is_hit = _is_hit(ad)
        for field in ["hook_type", "cta_type", "offer_type", "emotion"]:
            val = ca.get(field, "none")
            field_hit_rates[field][val]["total"] += 1
            if is_hit:
                field_hit_rates[field][val]["hits"] += 1

    # Compute hit rates
    field_hrs: dict[str, dict[str, float]] = {}
    for field, values in field_hit_rates.items():
        field_hrs[field] = {}
        for val, data in values.items():
            if data["total"] >= 2:
                field_hrs[field][val] = data["hits"] / data["total"] * 100

    # Count existing combos
    combo_counts: Counter = Counter()
    combo_hit_rates: dict[str, dict] = defaultdict(lambda: {"total": 0, "hits": 0})

    for ad in ads:
        ca = _get_creative(ad)
        if not ca:
            continue
        hook = ca.get("hook_type", "none")
        cta = ca.get("cta_type", "none")
        combo = f"{hook}+{cta}"
        combo_counts[combo] += 1
        combo_hit_rates[combo]["total"] += 1
        if _is_hit(ad):
            combo_hit_rates[combo]["hits"] += 1

    # Find unused/rare combos with high-performing components
    hooks_hr = field_hrs.get("hook_type", {})
    ctas_hr = field_hrs.get("cta_type", {})

    opportunities = []
    for hook, hook_hr in hooks_hr.items():
        if hook_hr < 40:
            continue
        for cta, cta_hr in ctas_hr.items():
            if cta_hr < 40:
                continue
            combo = f"{hook}+{cta}"
            count = combo_counts.get(combo, 0)

            if count <= 1:  # Unused or very rare
                expected_hr = (hook_hr + cta_hr) / 2
                opportunities.append({
                    "combo": combo,
                    "hook": hook,
                    "cta": cta,
                    "hook_hit_rate": round(hook_hr, 1),
                    "cta_hit_rate": round(cta_hr, 1),
                    "expected_hit_rate": round(expected_hr, 1),
                    "current_usage": count,
                    "opportunity": "untested" if count == 0 else "underexplored",
                })

    return sorted(opportunities, key=lambda x: x["expected_hit_rate"], reverse=True)


def find_genre_gaps(ads: list[Ad]) -> list[dict]:
    """Find genre+creative combos that are underrepresented."""
    genre_creative: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"total": 0, "hits": 0}))

    for ad in ads:
        genre = str(ad.category.value) if ad.category else "unknown"
        ca = _get_creative(ad)
        if ca:
            hook = ca.get("hook_type", "none")
            genre_creative[genre][hook]["total"] += 1
            if _is_hit(ad):
                genre_creative[genre][hook]["hits"] += 1

    # Find hooks that work well in one genre but aren't used in another
    hook_global_hr: dict[str, float] = {}
    for field_data in genre_creative.values():
        for hook, data in field_data.items():
            if hook not in hook_global_hr and data["total"] >= 3:
                total_h = sum(
                    gd.get(hook, {}).get("total", 0)
                    for gd in genre_creative.values()
                )
                hits_h = sum(
                    gd.get(hook, {}).get("hits", 0)
                    for gd in genre_creative.values()
                )
                if total_h >= 3:
                    hook_global_hr[hook] = hits_h / total_h * 100

    gaps = []
    for genre, hooks in genre_creative.items():
        used_hooks = set(hooks.keys())
        for hook, hr in hook_global_hr.items():
            if hook not in used_hooks and hr > 50:
                gaps.append({
                    "genre": genre,
                    "missing_hook": hook,
                    "global_hit_rate": round(hr, 1),
                    "suggestion": f"Try '{hook}' hook in '{genre}' genre (global hit rate: {hr:.0f}%)",
                })

    return sorted(gaps, key=lambda x: x["global_hit_rate"], reverse=True)


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[market_gaps] Loaded {len(ads)} ads")

        # 1. Genre saturation
        saturation = analyze_genre_saturation(ads)
        under_served = [s for s in saturation if s["saturation_status"] == "under_served"]
        over_saturated = [s for s in saturation if s["saturation_status"] == "over_saturated"]

        print(f"\n  Genre saturation analysis:")
        for s in saturation:
            print(f"    {s['genre']}: {s['ad_count']} ads ({s['market_share']}% share), "
                  f"hit_rate={s['hit_rate']}% -> {s['saturation_status']}")

        print(f"\n  Under-served genres: {len(under_served)}")
        for u in under_served:
            print(f"    {u['genre']}: only {u['ad_count']} ads but {u['hit_rate']}% hit rate")

        print(f"  Over-saturated genres: {len(over_saturated)}")
        for o in over_saturated:
            print(f"    {o['genre']}: {o['ad_count']} ads but only {o['hit_rate']}% hit rate")

        # 2. Unused combos
        opportunities = find_unused_combos(ads)
        print(f"\n  Untested/underexplored creative combos: {len(opportunities)}")
        for opp in opportunities[:10]:
            print(f"    {opp['combo']}: expected HR={opp['expected_hit_rate']}% "
                  f"(hook={opp['hook_hit_rate']}%, cta={opp['cta_hit_rate']}%) "
                  f"[{opp['opportunity']}]")

        # 3. Genre gaps
        genre_gaps = find_genre_gaps(ads)
        print(f"\n  Genre-hook gaps: {len(genre_gaps)}")
        for g in genre_gaps[:10]:
            print(f"    {g['suggestion']}")

        # Insights
        insights = []
        if under_served:
            insights.append(f"{len(under_served)} under-served genres with high potential")
        if over_saturated:
            insights.append(f"{len(over_saturated)} over-saturated genres (consider differentiation)")
        if opportunities:
            top_opp = opportunities[0]
            insights.append(f"Top untested combo: {top_opp['combo']} "
                          f"(expected {top_opp['expected_hit_rate']}% hit rate)")

        # Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "genre_saturation": saturation,
            "under_served_genres": under_served,
            "over_saturated_genres": over_saturated,
            "creative_opportunities": opportunities[:30],
            "genre_gaps": genre_gaps,
            "insights": insights,
        }

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "market_gaps.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
