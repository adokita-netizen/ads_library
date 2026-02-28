#!/usr/bin/env python3
"""LP Benchmark Report: compare LP scores across genres.

Analyzes which genres have the best landing pages, correlates LP score
with ad hit rate, and identifies top/bottom LPs.

Outputs:
  - backend/exports/lp_benchmark.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/lp_benchmark.py
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


# ── Helpers ──────────────────────────────────────────────────────────────


def _is_hit(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _get_lp_score(ad: Ad) -> float | None:
    """Get LP score from ad_metadata, or None if not scored."""
    meta = ad.ad_metadata or {}
    lp_score = meta.get("lp_score")
    if isinstance(lp_score, dict):
        return float(lp_score.get("score", 0))
    elif isinstance(lp_score, (int, float)):
        return float(lp_score)
    return None


def _safe_mean(vals: list[float]) -> float:
    return round(mean(vals), 1) if vals else 0.0


def _safe_median(vals: list[float]) -> float:
    return round(median(vals), 1) if vals else 0.0


def _hit_rate(hits: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(hits / total * 100, 1)


# ── Analysis Functions ──────────────────────────────────────────────────


def analyze_by_genre(ads_with_lp: list[Ad]) -> dict:
    """Analyze LP scores by genre."""
    genre_groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads_with_lp:
        genre = (ad.category.value if ad.category else "other") or "other"
        genre_groups[genre].append(ad)

    results = {}
    for genre, group in sorted(genre_groups.items()):
        lp_scores = [_get_lp_score(a) for a in group if _get_lp_score(a) is not None]
        hit_scores = [_get_score(a) for a in group]
        hits = sum(1 for a in group if _is_hit(a))

        results[genre] = {
            "total_ads": len(group),
            "ads_with_lp_score": len(lp_scores),
            "hit_ads": hits,
            "hit_rate": _hit_rate(hits, len(group)),
            "avg_lp_score": _safe_mean(lp_scores),
            "median_lp_score": _safe_median(lp_scores),
            "min_lp_score": round(min(lp_scores), 1) if lp_scores else 0,
            "max_lp_score": round(max(lp_scores), 1) if lp_scores else 0,
            "avg_hit_score": _safe_mean(hit_scores),
        }

    return results


def analyze_lp_vs_hit_correlation(ads_with_lp: list[Ad]) -> dict:
    """Analyze correlation between LP score and ad hit rate.

    Buckets ads by LP score ranges and compares hit rates.
    """
    buckets = {
        "0-20": [],
        "21-40": [],
        "41-60": [],
        "61-80": [],
        "81-100": [],
    }

    for ad in ads_with_lp:
        lp_score = _get_lp_score(ad)
        if lp_score is None:
            continue
        if lp_score <= 20:
            buckets["0-20"].append(ad)
        elif lp_score <= 40:
            buckets["21-40"].append(ad)
        elif lp_score <= 60:
            buckets["41-60"].append(ad)
        elif lp_score <= 80:
            buckets["61-80"].append(ad)
        else:
            buckets["81-100"].append(ad)

    result = {}
    for bucket_name, group in buckets.items():
        if not group:
            result[bucket_name] = {"total": 0, "hits": 0, "hit_rate": 0, "avg_hit_score": 0}
            continue
        hits = sum(1 for a in group if _is_hit(a))
        hit_scores = [_get_score(a) for a in group]
        result[bucket_name] = {
            "total": len(group),
            "hits": hits,
            "hit_rate": _hit_rate(hits, len(group)),
            "avg_hit_score": _safe_mean(hit_scores),
        }

    return result


def find_top_bottom_lps(ads_with_lp: list[Ad], n: int = 10) -> dict:
    """Find top N and bottom N ads by LP score."""
    scored = [(ad, _get_lp_score(ad)) for ad in ads_with_lp if _get_lp_score(ad) is not None]
    scored.sort(key=lambda x: x[1], reverse=True)

    def _ad_summary(ad: Ad, lp_score: float) -> dict:
        title_safe = (ad.title or "")[:60]
        try:
            title_safe.encode("ascii")
        except UnicodeEncodeError:
            title_safe = title_safe.encode("ascii", "replace").decode("ascii")
        return {
            "ad_id": ad.id,
            "title": title_safe,
            "lp_score": lp_score,
            "hit_score": _get_score(ad),
            "is_hit": _is_hit(ad),
            "genre": ad.category.value if ad.category else "other",
        }

    top = [_ad_summary(ad, score) for ad, score in scored[:n]]
    bottom = [_ad_summary(ad, score) for ad, score in scored[-n:]] if len(scored) >= n else []

    return {"top": top, "bottom": bottom}


def analyze_component_breakdown(ads_with_lp: list[Ad]) -> dict:
    """Analyze which LP score components contribute most to hits."""
    component_names = [
        "load_speed", "has_cta", "has_form", "has_testimonials",
        "has_video", "has_price_offer", "has_urgency",
        "has_social_proof", "mobile_responsive",
    ]

    component_stats = {}
    for comp_name in component_names:
        present_ads = []
        absent_ads = []

        for ad in ads_with_lp:
            lp_score_data = (ad.ad_metadata or {}).get("lp_score")
            if not isinstance(lp_score_data, dict):
                continue
            breakdown = lp_score_data.get("breakdown", {})
            comp_score = breakdown.get(comp_name, 0)
            if comp_score > 0:
                present_ads.append(ad)
            else:
                absent_ads.append(ad)

        present_hits = sum(1 for a in present_ads if _is_hit(a))
        absent_hits = sum(1 for a in absent_ads if _is_hit(a))

        component_stats[comp_name] = {
            "present_count": len(present_ads),
            "present_hit_rate": _hit_rate(present_hits, len(present_ads)),
            "absent_count": len(absent_ads),
            "absent_hit_rate": _hit_rate(absent_hits, len(absent_ads)),
            "hit_rate_lift": round(
                _hit_rate(present_hits, len(present_ads))
                - _hit_rate(absent_hits, len(absent_ads)),
                1,
            ),
        }

    return component_stats


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("LP Benchmark Report")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads: {total}")

        # Filter ads with LP score
        ads_with_lp = [a for a in ads if _get_lp_score(a) is not None]
        print(f"Ads with LP score: {len(ads_with_lp)}")

        if not ads_with_lp:
            print("No ads with LP scores found. Run score_landing_pages.py first.")
            # Still create a minimal report
            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_ads": total,
                "ads_with_lp_score": 0,
                "note": "No LP scores available. Run score_landing_pages.py first.",
            }
        else:
            # Run analyses
            genre_analysis = analyze_by_genre(ads_with_lp)
            correlation = analyze_lp_vs_hit_correlation(ads_with_lp)
            top_bottom = find_top_bottom_lps(ads_with_lp)
            component_analysis = analyze_component_breakdown(ads_with_lp)

            # Build insights
            insights = []

            # Best genre by LP score
            if genre_analysis:
                best_genre = max(
                    ((g, d) for g, d in genre_analysis.items() if d["ads_with_lp_score"] >= 2),
                    key=lambda x: x[1]["avg_lp_score"],
                    default=None,
                )
                if best_genre:
                    insights.append(
                        f"Best LP quality genre: '{best_genre[0]}' "
                        f"(avg LP score {best_genre[1]['avg_lp_score']}, "
                        f"n={best_genre[1]['ads_with_lp_score']})"
                    )

            # LP-hit correlation
            if correlation:
                high_lp = correlation.get("81-100", {})
                low_lp = correlation.get("0-20", {})
                if high_lp.get("total", 0) >= 2 and low_lp.get("total", 0) >= 2:
                    insights.append(
                        f"High LP score (81-100) hit rate: {high_lp['hit_rate']}% vs "
                        f"Low LP score (0-20): {low_lp['hit_rate']}%"
                    )

            # Component insights
            if component_analysis:
                best_comp = max(
                    ((c, d) for c, d in component_analysis.items() if d["present_count"] >= 2),
                    key=lambda x: x[1]["hit_rate_lift"],
                    default=None,
                )
                if best_comp:
                    insights.append(
                        f"Most impactful LP component: '{best_comp[0]}' "
                        f"(+{best_comp[1]['hit_rate_lift']}% hit rate lift)"
                    )

            # Overall stats
            all_lp_scores = [_get_lp_score(a) for a in ads_with_lp if _get_lp_score(a) is not None]

            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_ads": total,
                "ads_with_lp_score": len(ads_with_lp),
                "overall_stats": {
                    "avg_lp_score": _safe_mean(all_lp_scores),
                    "median_lp_score": _safe_median(all_lp_scores),
                    "min_lp_score": round(min(all_lp_scores), 1) if all_lp_scores else 0,
                    "max_lp_score": round(max(all_lp_scores), 1) if all_lp_scores else 0,
                },
                "genre_analysis": genre_analysis,
                "lp_vs_hit_correlation": correlation,
                "top_bottom_lps": top_bottom,
                "component_analysis": component_analysis,
                "insights": insights,
            }

            # Print summary
            print(f"\n--- Overall LP Stats ---")
            print(f"  Average: {_safe_mean(all_lp_scores)}")
            print(f"  Median:  {_safe_median(all_lp_scores)}")

            print(f"\n--- Genre LP Benchmark ---")
            print(f"  {'Genre':<16s} {'Ads':>4s} {'AvgLP':>6s} {'HitRate':>8s}")
            print(f"  {'-' * 40}")
            for genre, data in sorted(genre_analysis.items(), key=lambda x: -x[1]["avg_lp_score"]):
                print(
                    f"  {genre:<16s} {data['ads_with_lp_score']:>4d} "
                    f"{data['avg_lp_score']:>5.1f} {data['hit_rate']:>7.1f}%"
                )

            print(f"\n--- LP Score vs Hit Rate Correlation ---")
            print(f"  {'LP Range':<12s} {'Ads':>4s} {'Hits':>5s} {'HitRate':>8s} {'AvgHitScore':>12s}")
            print(f"  {'-' * 45}")
            for bucket, data in correlation.items():
                print(
                    f"  {bucket:<12s} {data['total']:>4d} {data['hits']:>5d} "
                    f"{data['hit_rate']:>7.1f}% {data['avg_hit_score']:>11.1f}"
                )

            print(f"\n--- Component Impact ---")
            print(f"  {'Component':<20s} {'Present':>7s} {'HR':>7s} {'Absent':>7s} {'HR':>7s} {'Lift':>7s}")
            print(f"  {'-' * 58}")
            for comp, data in sorted(component_analysis.items(), key=lambda x: -x[1]["hit_rate_lift"]):
                print(
                    f"  {comp:<20s} {data['present_count']:>7d} "
                    f"{data['present_hit_rate']:>6.1f}% {data['absent_count']:>7d} "
                    f"{data['absent_hit_rate']:>6.1f}% {data['hit_rate_lift']:>+6.1f}%"
                )

            print(f"\n--- Insights ---")
            for i, insight in enumerate(insights, 1):
                print(f"  {i}. {insight}")

        # Export
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        out_path = os.path.join(EXPORTS_DIR, "lp_benchmark.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved to: {out_path}")

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
