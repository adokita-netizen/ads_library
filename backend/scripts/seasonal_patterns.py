#!/usr/bin/env python3
"""Analyze seasonal patterns in ad creative performance.

Groups ads by month and analyzes which genres, hooks, CTAs, and emotions
perform better in which months. Computes month-over-month changes.

Outputs:
  - backend/exports/seasonal_patterns.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/seasonal_patterns.py
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


def _month_key(dt: datetime) -> str:
    """Return month key like '2025-01'."""
    return f"{dt.year}-{dt.month:02d}"


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


def monthly_field_performance(ads: list[Ad], field: str) -> dict:
    """For a given creative field, compute hit_rate and avg_score per month per value."""
    monthly: dict[str, dict[str, list[Ad]]] = defaultdict(lambda: defaultdict(list))

    for ad in ads:
        dt = ad.first_seen_at or ad.created_at
        ca = _get_creative(ad)
        if dt and ca:
            mk = _month_key(dt)
            val = ca.get(field, "none")
            monthly[mk][val].append(ad)

    result = {}
    for month in sorted(monthly.keys()):
        month_data = {}
        for val, val_ads in monthly[month].items():
            scores = [_get_score(a) for a in val_ads]
            hits = sum(1 for a in val_ads if _is_hit(a))
            month_data[val] = {
                "count": len(val_ads),
                "avg_score": round(_safe_mean(scores), 1),
                "hit_rate": round(hits / len(val_ads) * 100, 1) if val_ads else 0,
            }
        result[month] = month_data

    return result


def genre_monthly_performance(ads: list[Ad]) -> dict:
    """Compute hit_rate and avg_score per genre per month."""
    monthly: dict[str, dict[str, list[Ad]]] = defaultdict(lambda: defaultdict(list))

    for ad in ads:
        dt = ad.first_seen_at or ad.created_at
        if dt:
            mk = _month_key(dt)
            genre = str(ad.category.value) if ad.category else "unknown"
            monthly[mk][genre].append(ad)

    result = {}
    for month in sorted(monthly.keys()):
        month_data = {}
        for genre, genre_ads in monthly[month].items():
            scores = [_get_score(a) for a in genre_ads]
            hits = sum(1 for a in genre_ads if _is_hit(a))
            month_data[genre] = {
                "count": len(genre_ads),
                "avg_score": round(_safe_mean(scores), 1),
                "hit_rate": round(hits / len(genre_ads) * 100, 1) if genre_ads else 0,
            }
        result[month] = month_data

    return result


def compute_mom_changes(monthly_data: dict) -> list[dict]:
    """Compute month-over-month changes for each value."""
    sorted_months = sorted(monthly_data.keys())
    if len(sorted_months) < 2:
        return []

    changes = []
    for i in range(1, len(sorted_months)):
        prev_month = sorted_months[i - 1]
        curr_month = sorted_months[i]
        prev_data = monthly_data[prev_month]
        curr_data = monthly_data[curr_month]

        all_values = set(list(prev_data.keys()) + list(curr_data.keys()))
        for val in all_values:
            prev_hr = prev_data.get(val, {}).get("hit_rate", 0)
            curr_hr = curr_data.get(val, {}).get("hit_rate", 0)
            prev_cnt = prev_data.get(val, {}).get("count", 0)
            curr_cnt = curr_data.get(val, {}).get("count", 0)

            if prev_cnt == 0 and curr_cnt == 0:
                continue

            changes.append({
                "from_month": prev_month,
                "to_month": curr_month,
                "value": val,
                "prev_hit_rate": prev_hr,
                "curr_hit_rate": curr_hr,
                "hit_rate_change": round(curr_hr - prev_hr, 1),
                "prev_count": prev_cnt,
                "curr_count": curr_cnt,
            })

    return sorted(changes, key=lambda x: abs(x["hit_rate_change"]), reverse=True)


def find_seasonal_winners(monthly_data: dict, min_count: int = 2) -> dict:
    """For each value, find the best-performing month."""
    # Collect all months' data per value
    value_months: dict[str, list[dict]] = defaultdict(list)
    for month, month_data in monthly_data.items():
        for val, stats in month_data.items():
            if stats["count"] >= min_count:
                value_months[val].append({"month": month, **stats})

    winners = {}
    for val, months in value_months.items():
        if len(months) < 2:
            continue
        best = max(months, key=lambda x: x["hit_rate"])
        worst = min(months, key=lambda x: x["hit_rate"])
        winners[val] = {
            "best_month": best["month"],
            "best_hit_rate": best["hit_rate"],
            "worst_month": worst["month"],
            "worst_hit_rate": worst["hit_rate"],
            "spread": round(best["hit_rate"] - worst["hit_rate"], 1),
            "data_points": len(months),
        }

    return dict(sorted(winners.items(), key=lambda x: x[1]["spread"], reverse=True))


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[seasonal_patterns] Loaded {len(ads)} ads")

        # 1. Monthly performance by field
        hook_monthly = monthly_field_performance(ads, "hook_type")
        cta_monthly = monthly_field_performance(ads, "cta_type")
        emotion_monthly = monthly_field_performance(ads, "emotion")

        # 2. Genre monthly
        genre_monthly = genre_monthly_performance(ads)

        # 3. Month-over-month changes
        hook_changes = compute_mom_changes(hook_monthly)
        cta_changes = compute_mom_changes(cta_monthly)
        genre_changes = compute_mom_changes(genre_monthly)

        # 4. Seasonal winners
        hook_winners = find_seasonal_winners(hook_monthly)
        cta_winners = find_seasonal_winners(cta_monthly)
        genre_winners = find_seasonal_winners(genre_monthly)

        # Print summary
        months = sorted(set(
            _month_key(a.first_seen_at or a.created_at)
            for a in ads if (a.first_seen_at or a.created_at)
        ))
        print(f"  Months covered: {len(months)} ({months[0] if months else '?'} to {months[-1] if months else '?'})")

        print(f"\n  Hook type seasonal winners (by spread):")
        for val, info in list(hook_winners.items())[:5]:
            print(f"    {val}: best={info['best_month']} ({info['best_hit_rate']}%), "
                  f"worst={info['worst_month']} ({info['worst_hit_rate']}%), spread={info['spread']}%")

        print(f"\n  CTA type seasonal winners:")
        for val, info in list(cta_winners.items())[:5]:
            print(f"    {val}: best={info['best_month']} ({info['best_hit_rate']}%), spread={info['spread']}%")

        print(f"\n  Genre seasonal winners:")
        for val, info in list(genre_winners.items())[:5]:
            print(f"    {val}: best={info['best_month']} ({info['best_hit_rate']}%), spread={info['spread']}%")

        # Notable MoM changes
        big_changes = [c for c in hook_changes if abs(c["hit_rate_change"]) > 20]
        print(f"\n  Big MoM changes (>20% hit rate shift): {len(big_changes)}")
        for c in big_changes[:5]:
            print(f"    {c['value']}: {c['prev_hit_rate']}% -> {c['curr_hit_rate']}% "
                  f"({c['from_month']} -> {c['to_month']})")

        # Build insights
        insights = []
        if hook_winners:
            top_hook = list(hook_winners.items())[0]
            insights.append(
                f"Most seasonal hook: '{top_hook[0]}' with {top_hook[1]['spread']}% hit rate spread "
                f"(best in {top_hook[1]['best_month']})"
            )
        if genre_winners:
            top_genre = list(genre_winners.items())[0]
            insights.append(
                f"Most seasonal genre: '{top_genre[0]}' with {top_genre[1]['spread']}% spread"
            )

        # Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": len(ads),
            "months_covered": months,
            "hook_monthly": hook_monthly,
            "cta_monthly": cta_monthly,
            "emotion_monthly": emotion_monthly,
            "genre_monthly": genre_monthly,
            "mom_changes": {
                "hook": hook_changes[:20],
                "cta": cta_changes[:20],
                "genre": genre_changes[:20],
            },
            "seasonal_winners": {
                "hook": hook_winners,
                "cta": cta_winners,
                "genre": genre_winners,
            },
            "insights": insights,
        }

        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "seasonal_patterns.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {out_path}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
