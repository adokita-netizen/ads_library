"""Compare LPs of hit ads vs non-hit ads.

Analyzes what LP elements appear more frequently in hit ad LPs:
  - Form types, CTA patterns, social proof, testimonials, etc.
  - Compares hit vs non-hit distributions
  - Exports results to backend/exports/lp_comparison.json

Run from the backend directory:
    cd backend
    python scripts/compare_lps.py
"""

import os
import sys
import json
import logging
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")


def _safe_get(d: dict, *keys, default=None):
    """Safely navigate nested dict keys."""
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _compute_element_rates(ads_with_analysis: list) -> dict:
    """Compute element presence rates for a list of ads with lp_analysis."""
    if not ads_with_analysis:
        return {}

    total = len(ads_with_analysis)
    counts = defaultdict(int)

    for ad in ads_with_analysis:
        meta = ad.ad_metadata or {}
        analysis = meta.get("lp_analysis", {})

        # Form
        if _safe_get(analysis, "form_info", "has_form"):
            counts["has_form"] += 1
        form_type = _safe_get(analysis, "form_info", "form_type")
        if form_type:
            counts[f"form_type_{form_type}"] += 1

        # CTA
        cta_count = len(_safe_get(analysis, "cta_buttons", default=[]))
        if cta_count > 0:
            counts["has_cta"] += 1
        if cta_count >= 3:
            counts["has_3plus_ctas"] += 1

        # Testimonials
        if _safe_get(analysis, "testimonials", "has_testimonials"):
            counts["has_testimonials"] += 1
        if _safe_get(analysis, "testimonials", "has_star_ratings"):
            counts["has_star_ratings"] += 1

        # Before/After
        if _safe_get(analysis, "has_before_after"):
            counts["has_before_after"] += 1

        # Price
        if _safe_get(analysis, "price_info", "has_price"):
            counts["has_price"] += 1
        if _safe_get(analysis, "price_info", "has_discount"):
            counts["has_discount"] += 1
        if _safe_get(analysis, "price_info", "has_free_offer"):
            counts["has_free_offer"] += 1

        # FAQ
        if _safe_get(analysis, "has_faq"):
            counts["has_faq"] += 1

        # Countdown
        if _safe_get(analysis, "has_countdown"):
            counts["has_countdown"] += 1

        # Social proof
        if _safe_get(analysis, "social_proof", "has_social_proof"):
            counts["has_social_proof"] += 1
        if _safe_get(analysis, "social_proof", "has_media_mentions"):
            counts["has_media_mentions"] += 1

        # Video
        if _safe_get(analysis, "video_info", "has_video"):
            counts["has_video"] += 1

        # LP type
        lp_type = _safe_get(analysis, "lp_type")
        if lp_type:
            counts[f"lp_type_{lp_type}"] += 1

        # Destination type
        dest_type = _safe_get(analysis, "destination_type") or meta.get("destination_type")
        if dest_type:
            counts[f"dest_type_{dest_type}"] += 1

    # Convert to rates
    rates = {}
    for key, count in counts.items():
        rates[key] = {
            "count": count,
            "total": total,
            "rate": round(count / total * 100, 1),
        }

    return rates


def _compute_avg_scores(ads_with_analysis: list) -> dict:
    """Compute average LP quality scores and page metrics."""
    if not ads_with_analysis:
        return {}

    scores = []
    page_sizes = []
    load_times = []

    for ad in ads_with_analysis:
        meta = ad.ad_metadata or {}
        analysis = meta.get("lp_analysis", {})
        lp_data = meta.get("lp_data", {})

        score = _safe_get(analysis, "lp_quality_score")
        if score is not None:
            scores.append(score)

        page_size = _safe_get(lp_data, "page_size_kb")
        if page_size is not None:
            page_sizes.append(page_size)

        load_time = _safe_get(lp_data, "load_time_ms")
        if load_time is not None:
            load_times.append(load_time)

    result = {}
    if scores:
        result["avg_lp_quality_score"] = round(sum(scores) / len(scores), 1)
        result["median_lp_quality_score"] = round(sorted(scores)[len(scores) // 2], 1)
    if page_sizes:
        result["avg_page_size_kb"] = round(sum(page_sizes) / len(page_sizes), 1)
    if load_times:
        result["avg_load_time_ms"] = round(sum(load_times) / len(load_times), 0)

    return result


def main():
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    print("=" * 60)
    print("  LP Comparison: Hit Ads vs Non-Hit Ads")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Total ads: {total}")

        # Split into hit and non-hit based on ad_metadata
        hit_ads = []
        non_hit_ads = []
        no_analysis = 0

        for ad in ads:
            meta = ad.ad_metadata or {}

            # Check if LP analysis exists
            if not meta.get("lp_analysis"):
                no_analysis += 1
                continue

            # Determine hit status from metadata
            is_hit = meta.get("is_hit", False)
            hit_score = meta.get("latest_hit_score")

            if is_hit or (hit_score is not None and hit_score >= 70):
                hit_ads.append(ad)
            else:
                non_hit_ads.append(ad)

        print(f"Ads with LP analysis: {len(hit_ads) + len(non_hit_ads)}")
        print(f"  Hit ads:     {len(hit_ads)}")
        print(f"  Non-hit ads: {len(non_hit_ads)}")
        print(f"  No LP analysis: {no_analysis}")

        if not hit_ads and not non_hit_ads:
            print("\nNo ads with LP analysis found. Run analyze_lp_structure.py first.")
            return

        # Compute element rates for each group
        print("\nComputing element rates...")
        hit_rates = _compute_element_rates(hit_ads)
        non_hit_rates = _compute_element_rates(non_hit_ads)
        all_rates = _compute_element_rates(hit_ads + non_hit_ads)

        # Compute average scores
        hit_scores = _compute_avg_scores(hit_ads)
        non_hit_scores = _compute_avg_scores(non_hit_ads)
        all_scores = _compute_avg_scores(hit_ads + non_hit_ads)

        # Compute differences (hit rate - non-hit rate)
        all_elements = set(list(hit_rates.keys()) + list(non_hit_rates.keys()))
        differences = []

        for element in sorted(all_elements):
            hit_rate = hit_rates.get(element, {}).get("rate", 0)
            non_hit_rate = non_hit_rates.get(element, {}).get("rate", 0)
            diff = round(hit_rate - non_hit_rate, 1)
            differences.append({
                "element": element,
                "hit_rate": hit_rate,
                "non_hit_rate": non_hit_rate,
                "difference": diff,
                "advantage": "hit" if diff > 0 else "non_hit" if diff < 0 else "neutral",
            })

        # Sort by absolute difference (most impactful first)
        differences.sort(key=lambda x: abs(x["difference"]), reverse=True)

        # Build report
        report = {
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "total_ads": total,
            "hit_ads_count": len(hit_ads),
            "non_hit_ads_count": len(non_hit_ads),
            "no_analysis_count": no_analysis,
            "hit_element_rates": hit_rates,
            "non_hit_element_rates": non_hit_rates,
            "all_element_rates": all_rates,
            "hit_scores": hit_scores,
            "non_hit_scores": non_hit_scores,
            "all_scores": all_scores,
            "element_differences": differences,
            "top_hit_advantages": [d for d in differences if d["advantage"] == "hit"][:10],
            "top_non_hit_advantages": [d for d in differences if d["advantage"] == "non_hit"][:10],
        }

        # Save to file
        output_path = os.path.join(EXPORTS_DIR, "lp_comparison.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nExported to: {output_path}")

        # ── Print Summary ──
        print(f"\n{'=' * 60}")
        print(f"  LP COMPARISON RESULTS")
        print(f"{'=' * 60}")
        print()

        # Scores
        print(f"  Average LP Quality Scores:")
        print(f"    Hit ads:     {hit_scores.get('avg_lp_quality_score', 'N/A')}")
        print(f"    Non-hit ads: {non_hit_scores.get('avg_lp_quality_score', 'N/A')}")
        print(f"    All ads:     {all_scores.get('avg_lp_quality_score', 'N/A')}")
        print()

        # Performance
        print(f"  Average Load Time (ms):")
        print(f"    Hit ads:     {hit_scores.get('avg_load_time_ms', 'N/A')}")
        print(f"    Non-hit ads: {non_hit_scores.get('avg_load_time_ms', 'N/A')}")
        print()

        # Top differences
        print(f"  Elements MORE common in HIT ads:")
        for d in differences:
            if d["advantage"] == "hit" and abs(d["difference"]) >= 5:
                print(f"    {d['element']}: +{d['difference']}% ({d['hit_rate']}% vs {d['non_hit_rate']}%)")
        print()

        print(f"  Elements MORE common in NON-HIT ads:")
        for d in differences:
            if d["advantage"] == "non_hit" and abs(d["difference"]) >= 5:
                print(f"    {d['element']}: {d['difference']}% ({d['hit_rate']}% vs {d['non_hit_rate']}%)")

        print(f"\n{'=' * 60}")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        logger.exception("compare_lps failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
