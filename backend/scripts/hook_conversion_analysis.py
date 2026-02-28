#!/usr/bin/env python3
"""Hook-to-conversion analysis - which hook types lead to highest estimated spend.

Builds a Hook x CTA effectiveness matrix and finds the "golden combination"
per genre (highest hit_rate combo with count >= 3).

Output: exports/hook_cta_matrix.json

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/hook_conversion_analysis.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

HIT_THRESHOLD = 60


def _get_score(ad):
    """Extract latest_hit_score from ad_metadata."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _get_genre(ad):
    """Extract fine_genre from ad_metadata."""
    meta = ad.ad_metadata or {}
    return meta.get("fine_genre", meta.get("fine_genre_en", "other"))


def _is_hit(ad):
    """Check if ad is a hit or mega_hit via hit_level metadata."""
    meta = ad.ad_metadata or {}
    hit_level = meta.get("hit_level", "")
    return hit_level in ("hit", "mega_hit")


def _get_hook(ad):
    """Extract hook_type from ad_metadata or analysis relationship."""
    meta = ad.ad_metadata or {}
    hook = meta.get("hook_type", None)
    if hook:
        return str(hook).lower().strip()
    if ad.analysis and ad.analysis.hook_type:
        return ad.analysis.hook_type.lower().strip()
    return "none"


def _get_cta(ad):
    """Extract cta_type from ad_metadata or analysis relationship."""
    meta = ad.ad_metadata or {}
    cta = meta.get("cta_type", None)
    if cta:
        return str(cta).lower().strip()
    if ad.analysis and ad.analysis.cta_type:
        return ad.analysis.cta_type.lower().strip()
    return "none"


def safe_avg(values):
    """Compute average, returning 0 for empty lists."""
    return sum(values) / len(values) if values else 0


def main():
    print("=" * 60)
    print("Hook-to-Conversion Analysis")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ── Collect data per hook type ────────────────────────────
        hook_data = defaultdict(lambda: {"scores": [], "spends": [], "hits": 0, "count": 0})

        # ── Hook x CTA combination matrix ────────────────────────
        combo_data = defaultdict(lambda: {"scores": [], "spends": [], "hits": 0, "count": 0})

        # ── Genre-specific combos for golden combination ─────────
        genre_combo_data = defaultdict(lambda: defaultdict(
            lambda: {"scores": [], "hits": 0, "count": 0}
        ))

        for ad in ads:
            hook = _get_hook(ad)
            cta = _get_cta(ad)
            genre = _get_genre(ad)
            score = _get_score(ad)
            spend = ad.spend or 0
            hit = 1 if _is_hit(ad) else 0

            # Hook effectiveness
            hook_data[hook]["scores"].append(score)
            hook_data[hook]["spends"].append(spend)
            hook_data[hook]["hits"] += hit
            hook_data[hook]["count"] += 1

            # Combo matrix
            combo_key = f"{hook}|{cta}"
            combo_data[combo_key]["scores"].append(score)
            combo_data[combo_key]["spends"].append(spend)
            combo_data[combo_key]["hits"] += hit
            combo_data[combo_key]["count"] += 1

            # Genre-level combo
            genre_combo_data[genre][combo_key]["scores"].append(score)
            genre_combo_data[genre][combo_key]["hits"] += hit
            genre_combo_data[genre][combo_key]["count"] += 1

        # ── 1. Hook effectiveness ranking ─────────────────────────
        print("\n--- Hook Type Effectiveness (sorted by avg spend) ---")
        print(f"  {'Hook':<25s} {'Count':>6s} {'AvgScore':>9s} {'HitRate':>8s} {'AvgSpend':>10s}")
        print(f"  {'-'*25} {'-'*6} {'-'*9} {'-'*8} {'-'*10}")

        hook_effectiveness = []
        for hook, data in hook_data.items():
            count = data["count"]
            avg_score = safe_avg(data["scores"])
            hit_rate = data["hits"] / count * 100 if count > 0 else 0
            avg_spend = safe_avg(data["spends"])

            hook_effectiveness.append({
                "hook_type": hook,
                "count": count,
                "avg_score": round(avg_score, 2),
                "hit_rate": round(hit_rate, 2),
                "avg_spend": round(avg_spend, 2),
            })

        hook_effectiveness.sort(key=lambda x: x["avg_spend"], reverse=True)
        for h in hook_effectiveness:
            print(f"  {h['hook_type']:<25s} {h['count']:>6d} {h['avg_score']:>9.1f} "
                  f"{h['hit_rate']:>7.1f}% {h['avg_spend']:>10.1f}")

        # ── 2. Hook x CTA combination matrix ─────────────────────
        print("\n--- Top 20 Hook + CTA Combinations (by hit rate) ---")
        print(f"  {'Hook':<20s} {'CTA':<20s} {'Count':>6s} {'AvgScore':>9s} {'HitRate':>8s}")
        print(f"  {'-'*20} {'-'*20} {'-'*6} {'-'*9} {'-'*8}")

        combo_matrix = []
        for combo_key, data in combo_data.items():
            parts = combo_key.split("|", 1)
            hook = parts[0]
            cta = parts[1] if len(parts) > 1 else "none"
            count = data["count"]
            avg_score = safe_avg(data["scores"])
            hit_rate = data["hits"] / count * 100 if count > 0 else 0

            combo_matrix.append({
                "hook_type": hook,
                "cta_type": cta,
                "count": count,
                "avg_score": round(avg_score, 2),
                "hit_rate": round(hit_rate, 2),
            })

        combo_matrix.sort(key=lambda x: x["hit_rate"], reverse=True)
        for c in combo_matrix[:20]:
            print(f"  {c['hook_type']:<20s} {c['cta_type']:<20s} {c['count']:>6d} "
                  f"{c['avg_score']:>9.1f} {c['hit_rate']:>7.1f}%")

        # ── 3. Golden combination per genre ───────────────────────
        print("\n--- Golden Combination per Genre (min count >= 3) ---")
        golden_combos_by_genre = {}

        for genre in sorted(genre_combo_data.keys()):
            combos = genre_combo_data[genre]
            best_combo = None
            best_hit_rate = -1

            for combo_key, data in combos.items():
                if data["count"] >= 3:
                    hit_rate = data["hits"] / data["count"] * 100 if data["count"] > 0 else 0
                    if hit_rate > best_hit_rate:
                        best_hit_rate = hit_rate
                        best_combo = combo_key

            if best_combo:
                parts = best_combo.split("|", 1)
                hook = parts[0]
                cta = parts[1] if len(parts) > 1 else "none"
                combo_count = combos[best_combo]["count"]

                golden_combos_by_genre[genre] = {
                    "hook_type": hook,
                    "cta_type": cta,
                    "hit_rate": round(best_hit_rate, 2),
                    "count": combo_count,
                }

                print(f"  Best combination for {genre}: {hook} + {cta} "
                      f"(hit rate: {best_hit_rate:.0f}%)")

        if not golden_combos_by_genre:
            print("  No genre had a combo with count >= 3.")

        # ── 4. Generate insights ──────────────────────────────────
        insights = _generate_insights(hook_effectiveness, combo_matrix, golden_combos_by_genre)

        print("\n--- Insights ---")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        # ── Export ────────────────────────────────────────────────
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports"
        )
        os.makedirs(export_dir, exist_ok=True)

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hook_effectiveness": hook_effectiveness,
            "combo_matrix": combo_matrix,
            "golden_combos_by_genre": golden_combos_by_genre,
            "insights": insights,
        }

        out_path = os.path.join(export_dir, "hook_cta_matrix.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        print(f"\nExported: {out_path}")
        print("Done!")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


def _generate_insights(hook_effectiveness, combo_matrix, golden_combos):
    """Generate plain-English insight strings from the analysis data."""
    insights = []

    # Insight 1: Top hook type by spend
    if hook_effectiveness:
        top_hook = hook_effectiveness[0]
        insights.append(
            f"Highest-spend hook type is '{top_hook['hook_type']}' "
            f"with avg spend {top_hook['avg_spend']:.0f} across {top_hook['count']} ads."
        )

    # Insight 2: Top hook type by hit rate (with minimum count)
    qualified_hooks = [h for h in hook_effectiveness if h["count"] >= 3]
    if qualified_hooks:
        top_hit_hook = max(qualified_hooks, key=lambda x: x["hit_rate"])
        insights.append(
            f"Hook type '{top_hit_hook['hook_type']}' has the highest hit rate "
            f"at {top_hit_hook['hit_rate']:.1f}% (n={top_hit_hook['count']})."
        )

    # Insight 3: Best combo overall by hit rate (min count 3)
    qualified_combos = [c for c in combo_matrix if c["count"] >= 3]
    if qualified_combos:
        best_combo = max(qualified_combos, key=lambda x: x["hit_rate"])
        insights.append(
            f"Best hook+CTA combo overall: '{best_combo['hook_type']}' + '{best_combo['cta_type']}' "
            f"with {best_combo['hit_rate']:.1f}% hit rate (n={best_combo['count']})."
        )

    # Insight 4: Number of genres with golden combos
    if golden_combos:
        genre_count = len(golden_combos)
        avg_golden_hit = safe_avg([v["hit_rate"] for v in golden_combos.values()])
        insights.append(
            f"Found golden combos for {genre_count} genres "
            f"with average hit rate of {avg_golden_hit:.1f}%."
        )

    # Insight 5: Lowest performing hook type
    if len(qualified_hooks) >= 2:
        worst_hook = min(qualified_hooks, key=lambda x: x["hit_rate"])
        insights.append(
            f"Lowest-performing hook type is '{worst_hook['hook_type']}' "
            f"with only {worst_hook['hit_rate']:.1f}% hit rate (n={worst_hook['count']})."
        )

    return insights


if __name__ == "__main__":
    main()
