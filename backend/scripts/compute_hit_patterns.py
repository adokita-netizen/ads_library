#!/usr/bin/env python3
"""Compute hit patterns from creative_analysis data.

Aggregates creative_analysis across all ads, comparing hit vs non-hit ads
to identify which creative patterns correlate with higher performance.

Outputs:
  - backend/exports/hit_pattern_report.json
  - Updates ad_metadata["hit_pattern_rank"] for each ad

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/compute_hit_patterns.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Helper Functions ──────────────────────────────────────────────────────


def _is_hit(ad: Ad) -> bool:
    """Determine if an ad is a 'hit' based on hit_level in metadata."""
    meta = ad.ad_metadata or {}
    hit_level = meta.get("hit_level", "none")
    return hit_level in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    """Get the hit score for an ad, defaulting to 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _get_creative_analysis(ad: Ad) -> dict | None:
    """Get creative_analysis from ad_metadata."""
    meta = ad.ad_metadata or {}
    return meta.get("creative_analysis")


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return mean(values) if values else 0.0


def _safe_median(values: list[float]) -> float:
    """Return median or 0 if empty."""
    return median(values) if values else 0.0


def _hit_rate(hit_count: int, total: int) -> float:
    """Calculate hit rate as a percentage."""
    if total == 0:
        return 0.0
    return round(hit_count / total * 100, 1)


# ── Aggregation Functions ────────────────────────────────────────────────


def aggregate_by_field(
    ads: list[Ad],
    field: str,
) -> dict:
    """Aggregate hit rate and avg score by a creative_analysis field value.

    Returns:
    {
        "value1": {"total": N, "hits": N, "hit_rate": %, "avg_score": f, "median_score": f},
        ...
    }
    """
    groups: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        ca = _get_creative_analysis(ad)
        if not ca:
            continue
        value = ca.get(field, "none")
        if value is None:
            value = "none"
        groups[str(value)].append(ad)

    result = {}
    for value, group_ads in sorted(groups.items(), key=lambda x: -len(x[1])):
        total = len(group_ads)
        hits = sum(1 for a in group_ads if _is_hit(a))
        scores = [_get_score(a) for a in group_ads]
        result[value] = {
            "total": total,
            "hits": hits,
            "hit_rate": _hit_rate(hits, total),
            "avg_score": round(_safe_mean(scores), 1),
            "median_score": round(_safe_median(scores), 1),
        }

    return result


def aggregate_boolean_field(
    ads: list[Ad],
    field: str,
) -> dict:
    """Aggregate hit rate and avg score for a boolean creative_analysis field.

    Returns:
    {
        "true": {"total": N, "hits": N, "hit_rate": %, "avg_score": f},
        "false": {"total": N, "hits": N, "hit_rate": %, "avg_score": f},
    }
    """
    true_ads = []
    false_ads = []

    for ad in ads:
        ca = _get_creative_analysis(ad)
        if not ca:
            continue
        if ca.get(field):
            true_ads.append(ad)
        else:
            false_ads.append(ad)

    result = {}
    for label, group in [("true", true_ads), ("false", false_ads)]:
        total = len(group)
        hits = sum(1 for a in group if _is_hit(a))
        scores = [_get_score(a) for a in group]
        result[label] = {
            "total": total,
            "hits": hits,
            "hit_rate": _hit_rate(hits, total),
            "avg_score": round(_safe_mean(scores), 1),
        }

    return result


def find_top_combinations(ads: list[Ad], top_n: int = 10) -> list[dict]:
    """Find the strongest pattern combinations (hook + cta + offer + emotion).

    Returns a ranked list of pattern combos sorted by avg_score descending.
    Only includes combos with at least 2 ads.
    """
    combos: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        ca = _get_creative_analysis(ad)
        if not ca:
            continue
        key = f"{ca.get('hook_type', 'none')}|{ca.get('cta_type', 'none')}|{ca.get('offer_type', 'none')}|{ca.get('emotion', 'neutral')}"
        combos[key].append(ad)

    # Build ranked list
    ranked = []
    for key, group in combos.items():
        if len(group) < 2:
            continue
        parts = key.split("|")
        total = len(group)
        hits = sum(1 for a in group if _is_hit(a))
        scores = [_get_score(a) for a in group]

        ranked.append({
            "hook_type": parts[0],
            "cta_type": parts[1],
            "offer_type": parts[2],
            "emotion": parts[3],
            "total": total,
            "hits": hits,
            "hit_rate": _hit_rate(hits, total),
            "avg_score": round(_safe_mean(scores), 1),
            "median_score": round(_safe_median(scores), 1),
        })

    # Sort by avg_score descending
    ranked.sort(key=lambda x: x["avg_score"], reverse=True)
    return ranked[:top_n]


def compute_pattern_strength(ads: list[Ad]) -> dict[int, int]:
    """Compute a 'pattern strength rank' for each ad based on how strong
    their creative pattern combo is.

    Returns a dict of ad_id -> rank (1 = strongest pattern).
    """
    # Group ads by their pattern combination
    combos: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        ca = _get_creative_analysis(ad)
        if not ca:
            continue
        key = f"{ca.get('hook_type', 'none')}|{ca.get('cta_type', 'none')}|{ca.get('offer_type', 'none')}|{ca.get('emotion', 'neutral')}"
        combos[key].append(ad)

    # Rank each combo by avg score
    combo_scores = []
    for key, group in combos.items():
        scores = [_get_score(a) for a in group]
        avg = _safe_mean(scores)
        combo_scores.append((key, avg, [a.id for a in group]))

    combo_scores.sort(key=lambda x: x[1], reverse=True)

    # Assign rank to each ad
    ad_ranks: dict[int, int] = {}
    for rank, (key, avg, ad_ids) in enumerate(combo_scores, 1):
        for ad_id in ad_ids:
            ad_ranks[ad_id] = rank

    return ad_ranks


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Hit Pattern Analysis Script")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Check how many have creative_analysis
        analyzed = [a for a in ads if _get_creative_analysis(a)]
        print(f"Ads with creative_analysis: {len(analyzed)}/{total}")

        if len(analyzed) == 0:
            print("ERROR: No ads have creative_analysis. Run analyze_creative_elements.py first.")
            return

        # Count hits vs non-hits
        hit_ads = [a for a in analyzed if _is_hit(a)]
        non_hit_ads = [a for a in analyzed if not _is_hit(a)]
        print(f"Hit ads: {len(hit_ads)} ({_hit_rate(len(hit_ads), len(analyzed))}%)")
        print(f"Non-hit ads: {len(non_hit_ads)} ({_hit_rate(len(non_hit_ads), len(analyzed))}%)")

        # ── Aggregate by each field ──────────────────────────────────

        print("\nAggregating by creative fields...")

        hook_stats = aggregate_by_field(analyzed, "hook_type")
        cta_stats = aggregate_by_field(analyzed, "cta_type")
        offer_stats = aggregate_by_field(analyzed, "offer_type")
        emotion_stats = aggregate_by_field(analyzed, "emotion")
        dest_stats = aggregate_by_field(analyzed, "destination_type")
        text_stats = aggregate_by_field(analyzed, "text_length")

        # Boolean fields
        emoji_stats = aggregate_boolean_field(analyzed, "has_emoji")
        numbers_stats = aggregate_boolean_field(analyzed, "has_numbers")
        testimonial_stats = aggregate_boolean_field(analyzed, "has_testimonial")
        before_after_stats = aggregate_boolean_field(analyzed, "has_before_after")

        # ── Top Combinations ─────────────────────────────────────────

        print("Finding top pattern combinations...")
        top_combos = find_top_combinations(analyzed, top_n=15)

        # ── Compute Pattern Strength Ranks ───────────────────────────

        print("Computing pattern strength ranks...")
        ad_ranks = compute_pattern_strength(analyzed)

        # Update ad_metadata with hit_pattern_rank
        rank_updated = 0
        for ad in ads:
            rank = ad_ranks.get(ad.id)
            if rank is not None:
                meta = dict(ad.ad_metadata or {})
                meta["hit_pattern_rank"] = rank
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                rank_updated += 1

        session.commit()
        print(f"Updated hit_pattern_rank for {rank_updated} ads.")

        # ── Build Report ─────────────────────────────────────────────

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "analyzed_ads": len(analyzed),
            "hit_ads": len(hit_ads),
            "non_hit_ads": len(non_hit_ads),
            "overall_hit_rate": _hit_rate(len(hit_ads), len(analyzed)),
            "analysis": {
                "hook_type": hook_stats,
                "cta_type": cta_stats,
                "offer_type": offer_stats,
                "emotion": emotion_stats,
                "destination_type": dest_stats,
                "text_length": text_stats,
                "has_emoji": emoji_stats,
                "has_numbers": numbers_stats,
                "has_testimonial": testimonial_stats,
                "has_before_after": before_after_stats,
            },
            "top_combinations": top_combos,
            "insights": [],
        }

        # ── Generate Insights ────────────────────────────────────────

        insights = []

        # Find the best hook type
        if hook_stats:
            best_hook = max(
                ((k, v) for k, v in hook_stats.items() if v["total"] >= 3),
                key=lambda x: x[1]["avg_score"],
                default=None,
            )
            if best_hook:
                insights.append(
                    f"Best hook type: '{best_hook[0]}' "
                    f"(avg score {best_hook[1]['avg_score']}, "
                    f"hit rate {best_hook[1]['hit_rate']}%, "
                    f"n={best_hook[1]['total']})"
                )

        # Find the best CTA
        if cta_stats:
            best_cta = max(
                ((k, v) for k, v in cta_stats.items() if v["total"] >= 3),
                key=lambda x: x[1]["avg_score"],
                default=None,
            )
            if best_cta:
                insights.append(
                    f"Best CTA type: '{best_cta[0]}' "
                    f"(avg score {best_cta[1]['avg_score']}, "
                    f"hit rate {best_cta[1]['hit_rate']}%, "
                    f"n={best_cta[1]['total']})"
                )

        # Find the best offer
        if offer_stats:
            best_offer = max(
                ((k, v) for k, v in offer_stats.items() if v["total"] >= 3),
                key=lambda x: x[1]["avg_score"],
                default=None,
            )
            if best_offer:
                insights.append(
                    f"Best offer type: '{best_offer[0]}' "
                    f"(avg score {best_offer[1]['avg_score']}, "
                    f"hit rate {best_offer[1]['hit_rate']}%, "
                    f"n={best_offer[1]['total']})"
                )

        # Find the best emotion
        if emotion_stats:
            best_emotion = max(
                ((k, v) for k, v in emotion_stats.items() if v["total"] >= 3),
                key=lambda x: x[1]["avg_score"],
                default=None,
            )
            if best_emotion:
                insights.append(
                    f"Best emotional appeal: '{best_emotion[0]}' "
                    f"(avg score {best_emotion[1]['avg_score']}, "
                    f"hit rate {best_emotion[1]['hit_rate']}%, "
                    f"n={best_emotion[1]['total']})"
                )

        # Boolean insights
        for field_name, stats in [
            ("emoji", emoji_stats),
            ("numbers", numbers_stats),
            ("testimonial", testimonial_stats),
        ]:
            if stats.get("true", {}).get("total", 0) >= 3 and stats.get("false", {}).get("total", 0) >= 3:
                true_score = stats["true"]["avg_score"]
                false_score = stats["false"]["avg_score"]
                diff = true_score - false_score
                if abs(diff) >= 3:
                    better = "with" if diff > 0 else "without"
                    insights.append(
                        f"Ads {better} {field_name}: "
                        f"avg score {max(true_score, false_score):.1f} vs "
                        f"{min(true_score, false_score):.1f} "
                        f"(delta={abs(diff):.1f})"
                    )

        # Top combo insight
        if top_combos:
            top = top_combos[0]
            insights.append(
                f"Strongest pattern combo: "
                f"hook={top['hook_type']}, cta={top['cta_type']}, "
                f"offer={top['offer_type']}, emotion={top['emotion']} "
                f"(avg score {top['avg_score']}, hit rate {top['hit_rate']}%, "
                f"n={top['total']})"
            )

        report["insights"] = insights

        # ── Save Report ──────────────────────────────────────────────

        exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(exports_dir, exist_ok=True)
        report_path = os.path.join(exports_dir, "hit_pattern_report.json")

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\nReport saved to: {report_path}")

        # ── Print Summary ────────────────────────────────────────────

        def _print_field_stats(title: str, stats: dict):
            print(f"\n--- {title} ---")
            print(f"  {'Value':<16s} {'Total':>5s} {'Hits':>5s} {'HitRate':>8s} {'AvgScore':>9s}")
            print(f"  {'-' * 50}")
            for value, data in sorted(stats.items(), key=lambda x: -x[1]["avg_score"]):
                print(
                    f"  {value:<16s} {data['total']:>5d} {data['hits']:>5d} "
                    f"{data['hit_rate']:>7.1f}% {data['avg_score']:>8.1f}"
                )

        _print_field_stats("Hook Type vs Hit Rate", hook_stats)
        _print_field_stats("CTA Type vs Hit Rate", cta_stats)
        _print_field_stats("Offer Type vs Hit Rate", offer_stats)
        _print_field_stats("Emotion vs Hit Rate", emotion_stats)
        _print_field_stats("Destination Type vs Hit Rate", dest_stats)
        _print_field_stats("Text Length vs Hit Rate", text_stats)

        print(f"\n--- Boolean Features vs Hit Rate ---")
        for field_name, stats in [
            ("has_emoji", emoji_stats),
            ("has_numbers", numbers_stats),
            ("has_testimonial", testimonial_stats),
            ("has_before_after", before_after_stats),
        ]:
            t = stats.get("true", {})
            f_data = stats.get("false", {})
            print(
                f"  {field_name:<20s} "
                f"TRUE: n={t.get('total', 0)}, hit_rate={t.get('hit_rate', 0):.1f}%, avg={t.get('avg_score', 0):.1f} | "
                f"FALSE: n={f_data.get('total', 0)}, hit_rate={f_data.get('hit_rate', 0):.1f}%, avg={f_data.get('avg_score', 0):.1f}"
            )

        print(f"\n--- Top 10 Pattern Combinations ---")
        print(f"  {'#':>2s} {'Hook':<14s} {'CTA':<14s} {'Offer':<14s} {'Emotion':<12s} {'N':>3s} {'Hits':>4s} {'HitRate':>8s} {'AvgScore':>9s}")
        print(f"  {'-' * 85}")
        for i, combo in enumerate(top_combos[:10], 1):
            print(
                f"  {i:>2d} {combo['hook_type']:<14s} {combo['cta_type']:<14s} "
                f"{combo['offer_type']:<14s} {combo['emotion']:<12s} "
                f"{combo['total']:>3d} {combo['hits']:>4d} "
                f"{combo['hit_rate']:>7.1f}% {combo['avg_score']:>8.1f}"
            )

        print(f"\n--- Key Insights ---")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
