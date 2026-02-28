#!/usr/bin/env python3
"""Detect trending ad patterns by grouping ads by week.

Groups ads by first_seen_at week, computes avg_score/hit_rate per week,
and identifies rising/declining creative patterns over time.

Outputs:
  - backend/exports/trend_report.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/detect_trends.py
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
    """Return ISO week key like '2025-W03'."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


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


# ── Weekly Aggregation ───────────────────────────────────────────────────


def aggregate_by_week(ads: list[Ad]) -> dict:
    """Group ads by week, compute stats per week."""
    weeks: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        dt = ad.first_seen_at or ad.created_at
        if dt:
            weeks[_week_key(dt)].append(ad)

    result = {}
    for week in sorted(weeks.keys()):
        week_ads = weeks[week]
        scores = [_get_score(a) for a in week_ads]
        hits = [a for a in week_ads if _is_hit(a)]

        # Dominant hooks/CTAs
        hooks = Counter()
        ctas = Counter()
        emotions = Counter()
        for a in week_ads:
            ca = _get_creative(a)
            if ca:
                h = ca.get("hook_type", "none")
                c = ca.get("cta_type", "none")
                e = ca.get("emotion", "none")
                hooks[h] += 1
                ctas[c] += 1
                emotions[e] += 1

        result[week] = {
            "ad_count": len(week_ads),
            "avg_score": round(_safe_mean(scores), 1),
            "hit_count": len(hits),
            "hit_rate": round(len(hits) / len(week_ads) * 100, 1) if week_ads else 0,
            "top_hooks": hooks.most_common(3),
            "top_ctas": ctas.most_common(3),
            "top_emotions": emotions.most_common(3),
        }

    return result


# ── Trend Detection ──────────────────────────────────────────────────────


def detect_pattern_trends(ads: list[Ad], field: str, min_count: int = 3) -> dict:
    """Track how a creative field's hit_rate changes over time.

    Returns patterns classified as 'rising', 'declining', or 'stable'.
    """
    # Group by (week, field_value)
    week_field: dict[str, dict[str, list[Ad]]] = defaultdict(lambda: defaultdict(list))
    for ad in ads:
        dt = ad.first_seen_at or ad.created_at
        ca = _get_creative(ad)
        if dt and ca:
            val = ca.get(field, "none")
            week_field[_week_key(dt)][val].append(ad)

    # Compute hit_rate per field_value per week
    sorted_weeks = sorted(week_field.keys())
    field_values = set()
    for wk in sorted_weeks:
        field_values.update(week_field[wk].keys())

    trends = {}
    for fv in field_values:
        weekly_rates = []
        for wk in sorted_weeks:
            ads_in = week_field[wk].get(fv, [])
            if len(ads_in) >= 1:
                hr = sum(1 for a in ads_in if _is_hit(a)) / len(ads_in) * 100
                weekly_rates.append({"week": wk, "count": len(ads_in), "hit_rate": round(hr, 1)})

        if len(weekly_rates) < 2:
            continue

        # Simple trend: compare first half avg vs second half avg
        mid = len(weekly_rates) // 2
        first_half = _safe_mean([r["hit_rate"] for r in weekly_rates[:mid]])
        second_half = _safe_mean([r["hit_rate"] for r in weekly_rates[mid:]])
        total_count = sum(r["count"] for r in weekly_rates)

        if total_count < min_count:
            continue

        diff = second_half - first_half
        if diff > 10:
            direction = "rising"
        elif diff < -10:
            direction = "declining"
        else:
            direction = "stable"

        trends[fv] = {
            "direction": direction,
            "first_half_hit_rate": round(first_half, 1),
            "second_half_hit_rate": round(second_half, 1),
            "change": round(diff, 1),
            "total_ads": total_count,
            "weekly_data": weekly_rates,
        }

    return trends


def identify_emerging_patterns(ads: list[Ad]) -> list[dict]:
    """Find patterns that appear only in recent weeks with high hit rates."""
    sorted_weeks = sorted(set(
        _week_key(a.first_seen_at or a.created_at)
        for a in ads if (a.first_seen_at or a.created_at)
    ))
    if len(sorted_weeks) < 4:
        return []

    recent_weeks = set(sorted_weeks[-4:])  # last 4 weeks
    older_weeks = set(sorted_weeks[:-4])

    # Find hook+CTA combos in recent weeks not in older weeks
    recent_combos: dict[str, list[Ad]] = defaultdict(list)
    older_combos: set[str] = set()

    for ad in ads:
        dt = ad.first_seen_at or ad.created_at
        ca = _get_creative(ad)
        if not dt or not ca:
            continue
        wk = _week_key(dt)
        combo = f"{ca.get('hook_type', 'none')}+{ca.get('cta_type', 'none')}"
        if wk in recent_weeks:
            recent_combos[combo].append(ad)
        elif wk in older_weeks:
            older_combos.add(combo)

    emerging = []
    for combo, combo_ads in recent_combos.items():
        if combo in older_combos:
            continue
        if len(combo_ads) < 2:
            continue
        hr = sum(1 for a in combo_ads if _is_hit(a)) / len(combo_ads) * 100
        avg = _safe_mean([_get_score(a) for a in combo_ads])
        emerging.append({
            "pattern": combo,
            "ad_count": len(combo_ads),
            "hit_rate": round(hr, 1),
            "avg_score": round(avg, 1),
            "status": "new_pattern",
        })

    return sorted(emerging, key=lambda x: x["hit_rate"], reverse=True)


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[detect_trends] Loaded {len(ads)} ads")

        # 1. Weekly aggregation
        weekly = aggregate_by_week(ads)
        print(f"  Weeks with data: {len(weekly)}")

        # 2. Pattern trends per field
        hook_trends = detect_pattern_trends(ads, "hook_type")
        cta_trends = detect_pattern_trends(ads, "cta_type")
        emotion_trends = detect_pattern_trends(ads, "emotion")

        rising = []
        declining = []
        for field_name, trends in [("hook", hook_trends), ("cta", cta_trends), ("emotion", emotion_trends)]:
            for val, info in trends.items():
                entry = {"field": field_name, "value": val, **info}
                if info["direction"] == "rising":
                    rising.append(entry)
                elif info["direction"] == "declining":
                    declining.append(entry)

        rising.sort(key=lambda x: x["change"], reverse=True)
        declining.sort(key=lambda x: x["change"])

        print(f"  Rising trends: {len(rising)}")
        for t in rising[:5]:
            print(f"    {t['field']}={t['value']}: {t['first_half_hit_rate']}% -> {t['second_half_hit_rate']}% (+{t['change']})")
        print(f"  Declining trends: {len(declining)}")
        for t in declining[:5]:
            print(f"    {t['field']}={t['value']}: {t['first_half_hit_rate']}% -> {t['second_half_hit_rate']}% ({t['change']})")

        # 3. Emerging patterns
        emerging = identify_emerging_patterns(ads)
        print(f"  Emerging patterns: {len(emerging)}")
        for e in emerging[:5]:
            print(f"    {e['pattern']}: {e['ad_count']} ads, {e['hit_rate']}% hit rate")

        # 4. Overall trend summary
        sorted_weeks = sorted(weekly.keys())
        if len(sorted_weeks) >= 2:
            first_wk = weekly[sorted_weeks[0]]
            last_wk = weekly[sorted_weeks[-1]]
            score_trend = last_wk["avg_score"] - first_wk["avg_score"]
            hit_trend = last_wk["hit_rate"] - first_wk["hit_rate"]
        else:
            score_trend = 0
            hit_trend = 0

        # Serialize
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "total_weeks": len(weekly),
            "weekly_summary": {
                k: {
                    **v,
                    "top_hooks": [{"value": h, "count": c} for h, c in v["top_hooks"]],
                    "top_ctas": [{"value": h, "count": c} for h, c in v["top_ctas"]],
                    "top_emotions": [{"value": h, "count": c} for h, c in v["top_emotions"]],
                }
                for k, v in weekly.items()
            },
            "rising_trends": rising,
            "declining_trends": declining,
            "emerging_patterns": emerging,
            "overall": {
                "score_trend": round(score_trend, 1),
                "hit_rate_trend": round(hit_trend, 1),
                "market_direction": "improving" if score_trend > 5 else ("declining" if score_trend < -5 else "stable"),
            },
            "insights": [],
        }

        # Generate insights
        if rising:
            report["insights"].append(
                f"Top rising pattern: {rising[0]['field']}={rising[0]['value']} "
                f"(+{rising[0]['change']}% hit rate change)"
            )
        if declining:
            report["insights"].append(
                f"Top declining pattern: {declining[0]['field']}={declining[0]['value']} "
                f"({declining[0]['change']}% hit rate change)"
            )
        if emerging:
            report["insights"].append(
                f"{len(emerging)} new patterns detected in recent weeks"
            )

        # Export
        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "trend_report.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
