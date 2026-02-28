#!/usr/bin/env python3
"""Winning formula report: find the EXACT creative combinations that produce hits.

Combines all analysis to determine what combination of:
  hook_type + cta_type + offer_type + emotion + creative_type
produces the highest hit rate.

Ranks top 20 formulas and lists example ads for each.
Exports to backend/exports/winning_formulas.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/winning_formula.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    """Check if ad is a hit or mega_hit."""
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return round(mean(values), 1) if values else 0.0


def _safe_median(values: list[float]) -> float:
    """Return median or 0 if empty."""
    return round(median(values), 1) if values else 0.0


def _hit_rate(hits: int, total: int) -> float:
    """Calculate hit rate percentage."""
    if total == 0:
        return 0.0
    return round(hits / total * 100, 1)


def _build_formula_key(ad: Ad) -> str | None:
    """Build a formula key from ad's creative_analysis + creative_type.

    Returns None if creative_analysis is missing.
    """
    ca = (ad.ad_metadata or {}).get("creative_analysis")
    if not ca:
        return None

    hook = ca.get("hook_type", "none")
    cta = ca.get("cta_type", "none")
    offer = ca.get("offer_type", "none")
    emotion = ca.get("emotion", "neutral")
    creative_type = ad.creative_type or "unknown"

    return f"{hook}|{cta}|{offer}|{emotion}|{creative_type}"


def _parse_formula_key(key: str) -> dict:
    """Parse a formula key back into component fields."""
    parts = key.split("|")
    return {
        "hook_type": parts[0] if len(parts) > 0 else "none",
        "cta_type": parts[1] if len(parts) > 1 else "none",
        "offer_type": parts[2] if len(parts) > 2 else "none",
        "emotion": parts[3] if len(parts) > 3 else "neutral",
        "creative_type": parts[4] if len(parts) > 4 else "unknown",
    }


def main() -> None:
    print("=" * 60)
    print("WINNING FORMULA REPORT")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Total ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ── Step 1: Group ads by formula key ──────────────────────────
        formula_groups: dict[str, list[Ad]] = defaultdict(list)
        skipped = 0

        for ad in ads:
            key = _build_formula_key(ad)
            if key is None:
                skipped += 1
                continue
            formula_groups[key].append(ad)

        print(f"Ads with creative_analysis: {total - skipped}")
        print(f"Unique formulas found: {len(formula_groups)}")
        if skipped > 0:
            print(f"Ads skipped (no creative_analysis): {skipped}")

        # ── Step 2: Score each formula ────────────────────────────────
        formulas = []

        for key, group_ads in formula_groups.items():
            components = _parse_formula_key(key)
            group_total = len(group_ads)
            hits = sum(1 for a in group_ads if _is_hit(a))
            scores = [_get_score(a) for a in group_ads]

            # Build example ads list (top 3 by score)
            sorted_by_score = sorted(group_ads, key=_get_score, reverse=True)
            examples = []
            for ad in sorted_by_score[:3]:
                title_safe = (ad.title or "")[:60]
                adv_safe = (ad.advertiser_name or "")[:40]
                examples.append({
                    "ad_id": ad.id,
                    "title": title_safe,
                    "advertiser": adv_safe,
                    "score": _get_score(ad),
                    "is_hit": _is_hit(ad),
                })

            formula = {
                **components,
                "formula_key": key,
                "total_ads": group_total,
                "hit_ads": hits,
                "hit_rate": _hit_rate(hits, group_total),
                "avg_score": _safe_mean(scores),
                "median_score": _safe_median(scores),
                "max_score": round(max(scores), 1) if scores else 0.0,
                "min_score": round(min(scores), 1) if scores else 0.0,
                "examples": examples,
            }
            formulas.append(formula)

        # ── Step 3: Rank formulas ─────────────────────────────────────
        # Primary sort: hit_rate desc, secondary: avg_score desc
        # Only include formulas with >= 2 ads for statistical significance
        significant_formulas = [f for f in formulas if f["total_ads"] >= 2]
        all_formulas_sorted = sorted(formulas, key=lambda f: (f["hit_rate"], f["avg_score"]), reverse=True)

        # Top 20 with significance filter
        top_formulas = sorted(
            significant_formulas,
            key=lambda f: (f["hit_rate"], f["avg_score"]),
            reverse=True,
        )[:20]

        # ── Step 4: Component-level analysis ──────────────────────────
        # Which individual component values produce the best results?
        component_analysis = {}
        for comp in ["hook_type", "cta_type", "offer_type", "emotion", "creative_type"]:
            comp_groups: dict[str, list[Ad]] = defaultdict(list)
            for ad in ads:
                ca = (ad.ad_metadata or {}).get("creative_analysis")
                if not ca and comp != "creative_type":
                    continue
                if comp == "creative_type":
                    val = ad.creative_type or "unknown"
                else:
                    val = ca.get(comp, "none")
                comp_groups[val].append(ad)

            comp_stats = {}
            for val, group in comp_groups.items():
                gt = len(group)
                gh = sum(1 for a in group if _is_hit(a))
                gs = [_get_score(a) for a in group]
                comp_stats[val] = {
                    "total": gt,
                    "hits": gh,
                    "hit_rate": _hit_rate(gh, gt),
                    "avg_score": _safe_mean(gs),
                }

            # Sort by avg_score desc
            component_analysis[comp] = dict(
                sorted(comp_stats.items(), key=lambda x: -x[1]["avg_score"])
            )

        # ── Step 5: Generate overall insights ─────────────────────────
        insights = []

        # Best overall formula
        if top_formulas:
            best = top_formulas[0]
            insights.append(
                f"Best formula: hook={best['hook_type']}, cta={best['cta_type']}, "
                f"offer={best['offer_type']}, emotion={best['emotion']}, "
                f"type={best['creative_type']} "
                f"(hit_rate={best['hit_rate']}%, avg_score={best['avg_score']}, n={best['total_ads']})"
            )

        # Best per component
        for comp in ["hook_type", "cta_type", "offer_type", "emotion", "creative_type"]:
            stats = component_analysis.get(comp, {})
            # Filter for significance (>= 3 ads)
            sig_stats = {k: v for k, v in stats.items() if v["total"] >= 3}
            if sig_stats:
                best_key = max(sig_stats, key=lambda k: sig_stats[k]["avg_score"])
                best_val = sig_stats[best_key]
                insights.append(
                    f"Best {comp}: '{best_key}' "
                    f"(avg_score={best_val['avg_score']}, "
                    f"hit_rate={best_val['hit_rate']}%, n={best_val['total']})"
                )

        # Hit formula density
        formulas_with_hits = sum(1 for f in formulas if f["hit_ads"] > 0)
        insights.append(
            f"Formulas containing hits: {formulas_with_hits}/{len(formulas)} "
            f"({_hit_rate(formulas_with_hits, len(formulas))}%)"
        )

        # ── Step 6: Build & export report ─────────────────────────────
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads_analyzed": total - skipped,
            "total_unique_formulas": len(formulas),
            "significant_formulas": len(significant_formulas),
            "top_20_formulas": top_formulas,
            "all_formulas": all_formulas_sorted,
            "component_analysis": component_analysis,
            "insights": insights,
        }

        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "winning_formulas.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nExported to: {export_path}")

        # ── Print Results ─────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print("TOP 20 WINNING FORMULAS")
        print(f"{'=' * 60}")
        print(f"  {'#':>2s} {'Hook':<14s} {'CTA':<14s} {'Offer':<14s} {'Emotion':<12s} {'Type':<8s} {'N':>3s} {'Hits':>4s} {'Rate':>6s} {'AvgSc':>6s}")
        print(f"  {'-' * 95}")

        for i, f in enumerate(top_formulas, 1):
            print(
                f"  {i:>2d} {f['hook_type']:<14s} {f['cta_type']:<14s} "
                f"{f['offer_type']:<14s} {f['emotion']:<12s} {f['creative_type']:<8s} "
                f"{f['total_ads']:>3d} {f['hit_ads']:>4d} "
                f"{f['hit_rate']:>5.1f}% {f['avg_score']:>5.1f}"
            )

            # Print example ads for top 5
            if i <= 5 and f["examples"]:
                for ex in f["examples"][:2]:
                    title_safe = ex["title"][:40].encode("ascii", "replace").decode("ascii")
                    hit_mark = "HIT" if ex["is_hit"] else "   "
                    print(f"       [{hit_mark}] ID:{ex['ad_id']:>4d} score={ex['score']:>5.1f} {title_safe}")

        # Component analysis summary
        print(f"\n{'=' * 60}")
        print("COMPONENT ANALYSIS (best values per field)")
        print(f"{'=' * 60}")

        for comp in ["hook_type", "cta_type", "offer_type", "emotion", "creative_type"]:
            stats = component_analysis.get(comp, {})
            print(f"\n  --- {comp} ---")
            print(f"  {'Value':<16s} {'Total':>5s} {'Hits':>5s} {'Rate':>6s} {'AvgSc':>6s}")
            for val, data in list(stats.items())[:8]:
                print(
                    f"  {val:<16s} {data['total']:>5d} {data['hits']:>5d} "
                    f"{data['hit_rate']:>5.1f}% {data['avg_score']:>5.1f}"
                )

        # Key insights
        print(f"\n{'=' * 60}")
        print("KEY INSIGHTS")
        print(f"{'=' * 60}")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
