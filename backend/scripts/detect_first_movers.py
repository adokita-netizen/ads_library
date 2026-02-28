#!/usr/bin/env python3
"""Detect first movers: who adopts new creative patterns first?

Tracks when new creative patterns appear for the first time, whether
early adopters get higher hit rates, and identifies emerging patterns.

Outputs:
  - backend/exports/first_movers.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/detect_first_movers.py
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


def _week_key(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


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


def find_pattern_first_appearances(ads: list[Ad]) -> list[dict]:
    """Track when each creative combo first appeared and who used it."""
    # Sort by date
    sorted_ads = sorted(
        ads,
        key=lambda a: a.first_seen_at or a.created_at or datetime.min.replace(tzinfo=timezone.utc),
    )

    # Track first appearance of each combo
    seen_combos: dict[str, dict] = {}

    for ad in sorted_ads:
        ca = _get_creative(ad)
        if not ca:
            continue
        dt = ad.first_seen_at or ad.created_at
        if not dt:
            continue

        hook = ca.get("hook_type", "none")
        cta = ca.get("cta_type", "none")
        emotion = ca.get("emotion", "none")
        combo = f"{hook}+{cta}+{emotion}"

        if combo not in seen_combos:
            seen_combos[combo] = {
                "combo": combo,
                "first_seen": dt.isoformat(),
                "first_week": _week_key(dt),
                "first_mover_advertiser": ad.advertiser_name or "Unknown",
                "first_mover_ad_id": ad.id,
                "first_mover_is_hit": _is_hit(ad),
                "first_mover_score": _get_score(ad),
                "total_users": 0,
                "total_hits": 0,
                "avg_score": 0,
                "adopter_list": [],
            }

    # Count total usage
    combo_ads: dict[str, list[Ad]] = defaultdict(list)
    for ad in sorted_ads:
        ca = _get_creative(ad)
        if not ca:
            continue
        hook = ca.get("hook_type", "none")
        cta = ca.get("cta_type", "none")
        emotion = ca.get("emotion", "none")
        combo = f"{hook}+{cta}+{emotion}"
        combo_ads[combo].append(ad)

    for combo, c_ads in combo_ads.items():
        if combo in seen_combos:
            scores = [_get_score(a) for a in c_ads]
            hits = sum(1 for a in c_ads if _is_hit(a))
            seen_combos[combo]["total_users"] = len(c_ads)
            seen_combos[combo]["total_hits"] = hits
            seen_combos[combo]["avg_score"] = round(_safe_mean(scores), 1)
            seen_combos[combo]["hit_rate"] = round(hits / len(c_ads) * 100, 1) if c_ads else 0

            # List unique adopters
            adopters = set()
            for a in c_ads:
                name = a.advertiser_name or "Unknown"
                if name not in adopters:
                    adopters.add(name)
            seen_combos[combo]["adopter_count"] = len(adopters)

    results = list(seen_combos.values())
    results.sort(key=lambda x: x["first_seen"])
    return results


def analyze_first_mover_advantage(patterns: list[dict]) -> dict:
    """Do first movers of new patterns get higher hit rates?"""
    first_mover_hits = sum(1 for p in patterns if p["first_mover_is_hit"])
    first_mover_scores = [p["first_mover_score"] for p in patterns]
    avg_pattern_scores = [p["avg_score"] for p in patterns if p["total_users"] > 1]

    # Patterns where first mover outperformed average
    first_beats_avg = sum(
        1 for p in patterns
        if p["total_users"] > 1 and p["first_mover_score"] > p["avg_score"]
    )

    multi_user = [p for p in patterns if p["total_users"] > 1]

    return {
        "total_patterns": len(patterns),
        "first_mover_hit_rate": round(first_mover_hits / len(patterns) * 100, 1) if patterns else 0,
        "first_mover_avg_score": round(_safe_mean(first_mover_scores), 1),
        "overall_avg_score": round(_safe_mean(avg_pattern_scores), 1),
        "first_beats_average": first_beats_avg,
        "multi_user_patterns": len(multi_user),
        "advantage_rate": round(
            first_beats_avg / len(multi_user) * 100, 1
        ) if multi_user else 0,
    }


def find_emerging_patterns(patterns: list[dict], recent_weeks: int = 8) -> list[dict]:
    """Identify patterns that appeared recently and show promise."""
    # Get all weeks
    all_weeks = sorted(set(p["first_week"] for p in patterns))
    if len(all_weeks) < recent_weeks:
        recent_threshold = all_weeks[0] if all_weeks else ""
    else:
        recent_threshold = all_weeks[-recent_weeks]

    emerging = [
        p for p in patterns
        if p["first_week"] >= recent_threshold
        and p["total_users"] >= 2
    ]

    return sorted(emerging, key=lambda x: x["avg_score"], reverse=True)


def find_top_first_movers(ads: list[Ad], patterns: list[dict]) -> list[dict]:
    """Find advertisers who are most frequently first movers."""
    first_mover_counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "hits": 0, "scores": []})

    for p in patterns:
        adv = p["first_mover_advertiser"]
        first_mover_counts[adv]["count"] += 1
        if p["first_mover_is_hit"]:
            first_mover_counts[adv]["hits"] += 1
        first_mover_counts[adv]["scores"].append(p["first_mover_score"])

    results = []
    for adv, data in first_mover_counts.items():
        if data["count"] >= 2:
            results.append({
                "advertiser": adv,
                "first_mover_count": data["count"],
                "hit_count": data["hits"],
                "hit_rate": round(data["hits"] / data["count"] * 100, 1),
                "avg_score": round(_safe_mean(data["scores"]), 1),
            })

    return sorted(results, key=lambda x: x["first_mover_count"], reverse=True)


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[detect_first_movers] Loaded {len(ads)} ads")

        # 1. Pattern first appearances
        patterns = find_pattern_first_appearances(ads)
        print(f"  Unique creative combos: {len(patterns)}")

        # 2. First mover advantage analysis
        advantage = analyze_first_mover_advantage(patterns)
        print(f"\n  First mover advantage:")
        print(f"    First mover hit rate: {advantage['first_mover_hit_rate']}%")
        print(f"    First mover avg score: {advantage['first_mover_avg_score']}")
        print(f"    Overall avg score: {advantage['overall_avg_score']}")
        print(f"    First beats average: {advantage['first_beats_average']}/{advantage['multi_user_patterns']} "
              f"({advantage['advantage_rate']}%)")

        # 3. Emerging patterns
        emerging = find_emerging_patterns(patterns)
        print(f"\n  Emerging patterns (recent 8 weeks, 2+ users): {len(emerging)}")
        for e in emerging[:5]:
            print(f"    {e['combo']}: {e['total_users']} users, "
                  f"avg_score={e['avg_score']}, hit_rate={e.get('hit_rate', 0)}%")

        # 4. Top first movers
        top_movers = find_top_first_movers(ads, patterns)
        print(f"\n  Top first mover advertisers:")
        for m in top_movers[:5]:
            print(f"    {m['advertiser']}: {m['first_mover_count']} patterns first, "
                  f"hit_rate={m['hit_rate']}%")

        # Insights
        insights = []
        if advantage["advantage_rate"] > 50:
            insights.append("First movers tend to outperform later adopters")
        elif advantage["advantage_rate"] < 30:
            insights.append("First mover advantage is weak - later adopters often do better")
        else:
            insights.append("Mixed first mover advantage - context dependent")

        if emerging:
            insights.append(f"Top emerging pattern: {emerging[0]['combo']} "
                          f"(avg score {emerging[0]['avg_score']})")
        if top_movers:
            insights.append(f"Most innovative advertiser: {top_movers[0]['advertiser']} "
                          f"({top_movers[0]['first_mover_count']} patterns first)")

        # Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "total_patterns": len(patterns),
            "first_mover_advantage": advantage,
            "pattern_history": patterns[:50],  # Top 50 by date
            "emerging_patterns": emerging[:20],
            "top_first_movers": top_movers,
            "insights": insights,
        }

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "first_movers.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
