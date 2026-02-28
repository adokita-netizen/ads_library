#!/usr/bin/env python3
"""Track competitor advertisers and analyze their strategies.

Identifies top advertisers by ad count and score, analyzes their creative
strategy, genre coverage, estimated spend, and win rate.

Outputs:
  - backend/exports/competitor_intelligence.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/track_competitors.py
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


# ── Competitor Analysis ──────────────────────────────────────────────────


def build_competitor_profiles(ads: list[Ad]) -> list[dict]:
    """Build detailed competitor profiles for each advertiser."""
    by_advertiser: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        name = ad.advertiser_name or "Unknown"
        by_advertiser[name].append(ad)

    profiles = []
    for name, adv_ads in by_advertiser.items():
        if len(adv_ads) < 1:
            continue

        scores = [_get_score(a) for a in adv_ads]
        hits = sum(1 for a in adv_ads if _is_hit(a))

        # Genre coverage
        genres = Counter(
            str(a.category.value) if a.category else "unknown"
            for a in adv_ads
        )

        # Creative strategy
        hooks = Counter()
        ctas = Counter()
        emotions = Counter()
        for a in adv_ads:
            ca = _get_creative(a)
            if ca:
                hooks[ca.get("hook_type", "none")] += 1
                ctas[ca.get("cta_type", "none")] += 1
                emotions[ca.get("emotion", "none")] += 1

        # Creative types
        types = Counter(a.creative_type or "unknown" for a in adv_ads)

        # Ad frequency (time span)
        dates = [a.first_seen_at or a.created_at for a in adv_ads if (a.first_seen_at or a.created_at)]
        if len(dates) >= 2:
            span_days = (max(dates) - min(dates)).days or 1
            frequency = len(adv_ads) / span_days * 30  # Ads per month
        else:
            span_days = 0
            frequency = 0

        # Estimated spend
        meta = adv_ads[0].ad_metadata or {} if adv_ads else {}
        total_spend = sum(
            float((a.ad_metadata or {}).get("estimated_spend_jpy", 0) or 0)
            for a in adv_ads
        )

        # Strategy shifts over time
        sorted_ads = sorted(adv_ads, key=lambda a: a.first_seen_at or a.created_at or datetime.min.replace(tzinfo=timezone.utc))
        if len(sorted_ads) >= 3:
            mid = len(sorted_ads) // 2
            early_hooks = Counter()
            late_hooks = Counter()
            for a in sorted_ads[:mid]:
                ca = _get_creative(a)
                if ca:
                    early_hooks[ca.get("hook_type", "none")] += 1
            for a in sorted_ads[mid:]:
                ca = _get_creative(a)
                if ca:
                    late_hooks[ca.get("hook_type", "none")] += 1
            strategy_shift = {
                "early_dominant_hook": early_hooks.most_common(1)[0][0] if early_hooks else "none",
                "late_dominant_hook": late_hooks.most_common(1)[0][0] if late_hooks else "none",
                "shifted": early_hooks.most_common(1)[0][0] != late_hooks.most_common(1)[0][0] if early_hooks and late_hooks else False,
            }
        else:
            strategy_shift = {"shifted": False}

        profiles.append({
            "advertiser": name,
            "total_ads": len(adv_ads),
            "hit_ads": hits,
            "win_rate": round(hits / len(adv_ads) * 100, 1),
            "avg_score": round(_safe_mean(scores), 1),
            "max_score": round(max(scores), 1) if scores else 0,
            "genres": dict(genres.most_common()),
            "genre_count": len(genres),
            "dominant_hook": hooks.most_common(1)[0][0] if hooks else "none",
            "dominant_cta": ctas.most_common(1)[0][0] if ctas else "none",
            "dominant_emotion": emotions.most_common(1)[0][0] if emotions else "none",
            "creative_types": dict(types.most_common()),
            "ads_per_month": round(frequency, 1),
            "active_span_days": span_days,
            "estimated_total_spend_jpy": round(total_spend),
            "strategy_shift": strategy_shift,
        })

    # Sort by total_ads descending
    profiles.sort(key=lambda x: x["total_ads"], reverse=True)
    return profiles


def compute_competitive_landscape(profiles: list[dict]) -> dict:
    """Summarize the competitive landscape."""
    if not profiles:
        return {}

    total_advertisers = len(profiles)
    top_by_ads = profiles[:10]
    top_by_win_rate = sorted(
        [p for p in profiles if p["total_ads"] >= 3],
        key=lambda x: x["win_rate"],
        reverse=True,
    )[:10]
    top_by_spend = sorted(profiles, key=lambda x: x["estimated_total_spend_jpy"], reverse=True)[:10]

    # Market concentration
    total_ads = sum(p["total_ads"] for p in profiles)
    top3_share = sum(p["total_ads"] for p in profiles[:3]) / total_ads * 100 if total_ads > 0 else 0

    return {
        "total_advertisers": total_advertisers,
        "total_ads": total_ads,
        "market_concentration_top3": round(top3_share, 1),
        "avg_ads_per_advertiser": round(total_ads / total_advertisers, 1) if total_advertisers > 0 else 0,
        "multi_genre_advertisers": sum(1 for p in profiles if p["genre_count"] >= 2),
        "top_by_volume": [
            {"advertiser": p["advertiser"], "ads": p["total_ads"], "win_rate": p["win_rate"]}
            for p in top_by_ads
        ],
        "top_by_win_rate": [
            {"advertiser": p["advertiser"], "ads": p["total_ads"], "win_rate": p["win_rate"]}
            for p in top_by_win_rate
        ],
        "top_by_spend": [
            {"advertiser": p["advertiser"], "spend_jpy": p["estimated_total_spend_jpy"]}
            for p in top_by_spend
        ],
    }


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[track_competitors] Loaded {len(ads)} ads")

        # Build profiles
        profiles = build_competitor_profiles(ads)
        landscape = compute_competitive_landscape(profiles)

        print(f"  Total advertisers: {landscape.get('total_advertisers', 0)}")
        print(f"  Market concentration (top 3): {landscape.get('market_concentration_top3', 0)}%")

        print(f"\n  Top 10 advertisers by ad count:")
        for p in profiles[:10]:
            print(f"    {p['advertiser']}: {p['total_ads']} ads, "
                  f"win_rate={p['win_rate']}%, avg_score={p['avg_score']}")

        top_winners = sorted(
            [p for p in profiles if p["total_ads"] >= 3],
            key=lambda x: x["win_rate"],
            reverse=True,
        )
        print(f"\n  Top 10 by win rate (min 3 ads):")
        for p in top_winners[:10]:
            print(f"    {p['advertiser']}: win_rate={p['win_rate']}%, "
                  f"n={p['total_ads']}, hook={p['dominant_hook']}, cta={p['dominant_cta']}")

        # Strategy shifts
        shifters = [p for p in profiles if p["strategy_shift"].get("shifted")]
        print(f"\n  Strategy shifters: {len(shifters)}")
        for p in shifters[:5]:
            s = p["strategy_shift"]
            print(f"    {p['advertiser']}: {s['early_dominant_hook']} -> {s['late_dominant_hook']}")

        # Insights
        insights = []
        if profiles:
            insights.append(f"Top advertiser: {profiles[0]['advertiser']} ({profiles[0]['total_ads']} ads)")
        if top_winners:
            insights.append(f"Highest win rate: {top_winners[0]['advertiser']} ({top_winners[0]['win_rate']}%)")
        insights.append(f"Market concentration top 3: {landscape.get('market_concentration_top3', 0)}%")

        # Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "landscape": landscape,
            "competitor_profiles": profiles,
            "insights": insights,
        }

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "competitor_intelligence.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
