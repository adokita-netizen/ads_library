#!/usr/bin/env python3
"""Generate creative recommendations per genre based on hit predictor insights.

Uses the trained model's feature importance and per-genre hit patterns to
produce actionable recommendations: ideal creative formula, elements to include,
and elements to avoid.

Outputs:
  - backend/exports/creative_recommendations.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_recommendations.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _is_hit(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _safe_mean(vals: list[float]) -> float:
    return round(mean(vals), 1) if vals else 0.0


def _hit_rate(hits: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(hits / total * 100, 1)


def _best_value_by_hit_rate(
    ads: list[Ad], field: str, min_count: int = 2
) -> tuple[str | None, float]:
    """Find the value of a creative field with the highest hit rate."""
    groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        ca = (ad.ad_metadata or {}).get("creative_analysis", {})
        val = ca.get(field, "none") or "none"
        groups[str(val)].append(ad)

    best_val = None
    best_rate = -1.0
    for val, group in groups.items():
        if len(group) < min_count:
            continue
        hits = sum(1 for a in group if _is_hit(a))
        rate = hits / len(group) * 100
        if rate > best_rate:
            best_rate = rate
            best_val = val

    return best_val, best_rate


def _worst_value_by_hit_rate(
    ads: list[Ad], field: str, min_count: int = 2
) -> tuple[str | None, float]:
    """Find the value of a creative field with the lowest hit rate."""
    groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        ca = (ad.ad_metadata or {}).get("creative_analysis", {})
        val = ca.get(field, "none") or "none"
        groups[str(val)].append(ad)

    worst_val = None
    worst_rate = 101.0
    for val, group in groups.items():
        if len(group) < min_count:
            continue
        hits = sum(1 for a in group if _is_hit(a))
        rate = hits / len(group) * 100
        if rate < worst_rate:
            worst_rate = rate
            worst_val = val

    return worst_val, worst_rate


def _boolean_impact(ads: list[Ad], field: str) -> dict:
    """Measure the impact of a boolean feature on hit rate."""
    present_ads = []
    absent_ads = []
    for ad in ads:
        ca = (ad.ad_metadata or {}).get("creative_analysis", {})
        if ca.get(field):
            present_ads.append(ad)
        else:
            absent_ads.append(ad)

    present_hits = sum(1 for a in present_ads if _is_hit(a))
    absent_hits = sum(1 for a in absent_ads if _is_hit(a))

    return {
        "present_count": len(present_ads),
        "present_hit_rate": _hit_rate(present_hits, len(present_ads)),
        "absent_count": len(absent_ads),
        "absent_hit_rate": _hit_rate(absent_hits, len(absent_ads)),
        "lift": round(
            _hit_rate(present_hits, len(present_ads))
            - _hit_rate(absent_hits, len(absent_ads)),
            1,
        ),
    }


def _optimal_creative_type(ads: list[Ad]) -> str:
    """Find the best creative type by hit rate."""
    groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        ct = (ad.creative_type or "unknown").lower()
        groups[ct].append(ad)

    best_type = "unknown"
    best_rate = -1.0
    for ct, group in groups.items():
        if len(group) < 2:
            continue
        hits = sum(1 for a in group if _is_hit(a))
        rate = hits / len(group) * 100
        if rate > best_rate:
            best_rate = rate
            best_type = ct

    return best_type


def _build_genre_recommendation(genre: str, ads: list[Ad]) -> dict:
    """Build a recommendation block for a specific genre."""
    total = len(ads)
    hits = sum(1 for a in ads if _is_hit(a))
    overall_hit_rate = _hit_rate(hits, total)
    avg_score = _safe_mean([_get_score(a) for a in ads])

    # Best/worst per field
    best_hook, best_hook_rate = _best_value_by_hit_rate(ads, "hook_type")
    best_cta, best_cta_rate = _best_value_by_hit_rate(ads, "cta_type")
    best_offer, best_offer_rate = _best_value_by_hit_rate(ads, "offer_type")
    best_emotion, best_emotion_rate = _best_value_by_hit_rate(ads, "emotion")

    worst_hook, worst_hook_rate = _worst_value_by_hit_rate(ads, "hook_type")
    worst_cta, worst_cta_rate = _worst_value_by_hit_rate(ads, "cta_type")
    worst_offer, worst_offer_rate = _worst_value_by_hit_rate(ads, "offer_type")
    worst_emotion, worst_emotion_rate = _worst_value_by_hit_rate(ads, "emotion")

    # Best creative type
    best_creative = _optimal_creative_type(ads)

    # Boolean feature impacts
    emoji_impact = _boolean_impact(ads, "has_emoji")
    numbers_impact = _boolean_impact(ads, "has_numbers")
    testimonial_impact = _boolean_impact(ads, "has_testimonial")
    before_after_impact = _boolean_impact(ads, "has_before_after")

    # Build "ideal formula"
    ideal_formula = {
        "hook_type": best_hook or "benefit",
        "cta_type": best_cta or "learn_more",
        "offer_type": best_offer or "none",
        "emotion": best_emotion or "desire",
        "creative_type": best_creative,
    }

    # Elements to include (features with positive impact)
    include_elements = []
    if best_hook:
        include_elements.append(f"Use '{best_hook}' hook ({best_hook_rate:.0f}% hit rate)")
    if best_cta:
        include_elements.append(f"Use '{best_cta}' CTA ({best_cta_rate:.0f}% hit rate)")
    if best_offer:
        include_elements.append(f"Include '{best_offer}' offer ({best_offer_rate:.0f}% hit rate)")
    if best_emotion:
        include_elements.append(f"Appeal to '{best_emotion}' emotion ({best_emotion_rate:.0f}% hit rate)")

    # Boolean recommendations
    for field_name, impact in [
        ("emoji", emoji_impact),
        ("numbers", numbers_impact),
        ("testimonial", testimonial_impact),
        ("before/after", before_after_impact),
    ]:
        if impact["lift"] > 5 and impact["present_count"] >= 2:
            include_elements.append(
                f"Include {field_name} (+{impact['lift']:.0f}% hit rate lift)"
            )

    # Elements to avoid
    avoid_elements = []
    if worst_hook and worst_hook != best_hook:
        avoid_elements.append(f"Avoid '{worst_hook}' hook ({worst_hook_rate:.0f}% hit rate)")
    if worst_cta and worst_cta != best_cta:
        avoid_elements.append(f"Avoid '{worst_cta}' CTA ({worst_cta_rate:.0f}% hit rate)")
    if worst_offer and worst_offer != best_offer:
        avoid_elements.append(f"Avoid '{worst_offer}' offer ({worst_offer_rate:.0f}% hit rate)")

    for field_name, impact in [
        ("emoji", emoji_impact),
        ("numbers", numbers_impact),
        ("testimonial", testimonial_impact),
        ("before/after", before_after_impact),
    ]:
        if impact["lift"] < -5 and impact["present_count"] >= 2:
            avoid_elements.append(
                f"Avoid {field_name} ({impact['lift']:.0f}% hit rate impact)"
            )

    # Text length recommendation
    hit_ads_in_genre = [a for a in ads if _is_hit(a)]
    if hit_ads_in_genre:
        avg_desc_len = _safe_mean([
            len(a.description or "") for a in hit_ads_in_genre
        ])
        avg_title_len = _safe_mean([
            len(a.title or "") for a in hit_ads_in_genre
        ])
        include_elements.append(
            f"Optimal title length: ~{avg_title_len:.0f} chars, "
            f"description: ~{avg_desc_len:.0f} chars"
        )

    return {
        "genre": genre,
        "stats": {
            "total_ads": total,
            "hit_ads": hits,
            "hit_rate": overall_hit_rate,
            "avg_score": avg_score,
        },
        "ideal_formula": ideal_formula,
        "include_elements": include_elements,
        "avoid_elements": avoid_elements,
        "boolean_feature_impacts": {
            "has_emoji": emoji_impact,
            "has_numbers": numbers_impact,
            "has_testimonial": testimonial_impact,
            "has_before_after": before_after_impact,
        },
    }


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Creative Recommendation Generator")
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

        # Group ads by genre (category)
        genre_groups: dict[str, list[Ad]] = defaultdict(list)
        for ad in ads:
            genre = (ad.category.value if ad.category else "other") or "other"
            genre_groups[genre].append(ad)

        print(f"Genres found: {len(genre_groups)}")
        for genre, group in sorted(genre_groups.items(), key=lambda x: -len(x[1])):
            print(f"  {genre}: {len(group)} ads")

        # Build recommendations per genre
        genre_recommendations = {}
        for genre, group in sorted(genre_groups.items()):
            rec = _build_genre_recommendation(genre, group)
            genre_recommendations[genre] = rec

        # Build overall (all-genre) recommendation
        overall_rec = _build_genre_recommendation("all", ads)

        # Load feature importance if available
        fi_path = os.path.join(EXPORTS_DIR, "feature_importance.json")
        feature_importance_data = None
        if os.path.exists(fi_path):
            with open(fi_path, "r", encoding="utf-8") as f:
                feature_importance_data = json.load(f)

        # Build export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "overall_recommendation": overall_rec,
            "genre_recommendations": genre_recommendations,
        }

        if feature_importance_data:
            report["model_info"] = feature_importance_data.get("model_info", {})
            report["top_features"] = feature_importance_data.get("feature_importance", [])[:15]

        # Export
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        out_path = os.path.join(EXPORTS_DIR, "creative_recommendations.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved to: {out_path}")

        # Print summary
        print(f"\n{'=' * 60}")
        print("CREATIVE RECOMMENDATIONS SUMMARY")
        print(f"{'=' * 60}")

        print(f"\n--- Overall Ideal Formula ---")
        formula = overall_rec["ideal_formula"]
        print(f"  Hook:     {formula['hook_type']}")
        print(f"  CTA:      {formula['cta_type']}")
        print(f"  Offer:    {formula['offer_type']}")
        print(f"  Emotion:  {formula['emotion']}")
        print(f"  Creative: {formula['creative_type']}")

        print(f"\n--- What to Include ---")
        for item in overall_rec["include_elements"][:7]:
            print(f"  + {item}")

        print(f"\n--- What to Avoid ---")
        for item in overall_rec["avoid_elements"][:5]:
            print(f"  - {item}")

        # Per-genre summary
        print(f"\n--- Per-Genre Best Formula ---")
        print(f"  {'Genre':<16s} {'Ads':>4s} {'HitRate':>8s} {'BestHook':<14s} {'BestCTA':<14s} {'BestOffer':<14s}")
        print(f"  {'-' * 75}")
        for genre, rec in sorted(genre_recommendations.items(), key=lambda x: -x[1]["stats"]["hit_rate"]):
            f = rec["ideal_formula"]
            s = rec["stats"]
            print(
                f"  {genre:<16s} {s['total_ads']:>4d} "
                f"{s['hit_rate']:>7.1f}% "
                f"{f['hook_type']:<14s} {f['cta_type']:<14s} {f['offer_type']:<14s}"
            )

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
