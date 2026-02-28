#!/usr/bin/env python3
"""Conversion Funnel Analysis: Ad Creative -> LP -> Conversion Action.

Maps the full funnel for each ad:
  ad_score (hit_score) + lp_score + alignment_score = funnel_score

Ranks ads by funnel_score and exports analysis.

Outputs:
  - backend/exports/funnel_analysis.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/funnel_analysis.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _safe_mean(vals: list[float]) -> float:
    return round(mean(vals), 1) if vals else 0.0


def _safe_median(vals: list[float]) -> float:
    return round(median(vals), 1) if vals else 0.0


def _is_hit(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_ad_score(ad: Ad) -> float:
    """Get hit score (0-100), normalized."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _get_lp_score(ad: Ad) -> float | None:
    """Get LP score from ad_metadata."""
    meta = ad.ad_metadata or {}
    lp_score = meta.get("lp_score")
    if isinstance(lp_score, dict):
        return float(lp_score.get("score", 0))
    elif isinstance(lp_score, (int, float)):
        return float(lp_score)
    return None


def _get_alignment_score(ad: Ad) -> float | None:
    """Get LP alignment score from ad_metadata."""
    meta = ad.ad_metadata or {}
    alignment = meta.get("lp_alignment")
    if isinstance(alignment, dict):
        return float(alignment.get("alignment_score", 0))
    elif isinstance(alignment, (int, float)):
        return float(alignment)
    return None


def compute_funnel_score(
    ad_score: float,
    lp_score: float | None,
    alignment_score: float | None,
) -> dict:
    """Compute a composite funnel score.

    Weights:
      - ad_score (hit score): 40%
      - lp_score: 30%
      - alignment_score: 30%

    If LP or alignment data is missing, the score is based on available
    components with adjusted weights.
    """
    components = {}
    total_weight = 0.0
    weighted_sum = 0.0

    # Ad score (always available)
    components["ad_score"] = {
        "value": round(ad_score, 1),
        "weight": 0.4,
        "weighted": round(ad_score * 0.4, 1),
    }
    weighted_sum += ad_score * 0.4
    total_weight += 0.4

    # LP score
    if lp_score is not None:
        components["lp_score"] = {
            "value": round(lp_score, 1),
            "weight": 0.3,
            "weighted": round(lp_score * 0.3, 1),
        }
        weighted_sum += lp_score * 0.3
        total_weight += 0.3
    else:
        components["lp_score"] = {"value": None, "weight": 0.0, "weighted": 0.0}

    # Alignment score
    if alignment_score is not None:
        components["alignment_score"] = {
            "value": round(alignment_score, 1),
            "weight": 0.3,
            "weighted": round(alignment_score * 0.3, 1),
        }
        weighted_sum += alignment_score * 0.3
        total_weight += 0.3
    else:
        components["alignment_score"] = {"value": None, "weight": 0.0, "weighted": 0.0}

    # Normalize to 0-100 scale
    if total_weight > 0:
        funnel_score = round(weighted_sum / total_weight, 1)
    else:
        funnel_score = 0.0

    # Completeness: how many funnel stages have data
    completeness = 1  # Ad score always present
    if lp_score is not None:
        completeness += 1
    if alignment_score is not None:
        completeness += 1

    return {
        "funnel_score": funnel_score,
        "components": components,
        "completeness": f"{completeness}/3",
        "data_available": {
            "ad_score": True,
            "lp_score": lp_score is not None,
            "alignment_score": alignment_score is not None,
        },
    }


def _funnel_grade(score: float) -> str:
    """Convert funnel score to letter grade."""
    if score >= 80:
        return "A"
    elif score >= 65:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 35:
        return "D"
    else:
        return "F"


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Conversion Funnel Analysis Script")
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

        # Compute funnel score for each ad
        funnel_data: list[dict] = []
        score_sum = 0.0
        grade_counts: dict[str, int] = {}
        completeness_counts: dict[str, int] = {}

        for ad in ads:
            ad_score = _get_ad_score(ad)
            lp_score = _get_lp_score(ad)
            alignment_score = _get_alignment_score(ad)

            result = compute_funnel_score(ad_score, lp_score, alignment_score)
            funnel_score = result["funnel_score"]
            grade = _funnel_grade(funnel_score)

            # Store in ad_metadata
            meta = dict(ad.ad_metadata or {})
            meta["funnel_score"] = {
                "score": funnel_score,
                "grade": grade,
                "components": result["components"],
                "completeness": result["completeness"],
                "scored_at": datetime.now(timezone.utc).isoformat(),
            }
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            # Build record for ranking
            title_safe = (ad.title or "")[:60]
            try:
                title_safe.encode("ascii")
            except UnicodeEncodeError:
                title_safe = title_safe.encode("ascii", "replace").decode("ascii")

            funnel_data.append({
                "ad_id": ad.id,
                "title": title_safe,
                "genre": ad.category.value if ad.category else "other",
                "funnel_score": funnel_score,
                "grade": grade,
                "ad_score": ad_score,
                "lp_score": lp_score,
                "alignment_score": alignment_score,
                "is_hit": _is_hit(ad),
                "completeness": result["completeness"],
            })

            score_sum += funnel_score
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
            comp_key = result["completeness"]
            completeness_counts[comp_key] = completeness_counts.get(comp_key, 0) + 1

        session.commit()
        print(f"Funnel scores computed for {len(funnel_data)} ads.")

        # Sort by funnel_score descending
        funnel_data.sort(key=lambda x: x["funnel_score"], reverse=True)

        # Per-genre analysis
        genre_groups: dict[str, list[dict]] = defaultdict(list)
        for item in funnel_data:
            genre_groups[item["genre"]].append(item)

        genre_analysis = {}
        for genre, items in sorted(genre_groups.items()):
            scores = [i["funnel_score"] for i in items]
            hits = sum(1 for i in items if i["is_hit"])
            genre_analysis[genre] = {
                "total_ads": len(items),
                "hit_ads": hits,
                "hit_rate": round(hits / len(items) * 100, 1) if items else 0,
                "avg_funnel_score": _safe_mean(scores),
                "median_funnel_score": _safe_median(scores),
            }

        # Correlation: funnel score vs hit rate
        score_buckets = {
            "0-20": [],
            "21-40": [],
            "41-60": [],
            "61-80": [],
            "81-100": [],
        }
        for item in funnel_data:
            s = item["funnel_score"]
            if s <= 20:
                score_buckets["0-20"].append(item)
            elif s <= 40:
                score_buckets["21-40"].append(item)
            elif s <= 60:
                score_buckets["41-60"].append(item)
            elif s <= 80:
                score_buckets["61-80"].append(item)
            else:
                score_buckets["81-100"].append(item)

        correlation = {}
        for bucket_name, items in score_buckets.items():
            hits = sum(1 for i in items if i["is_hit"])
            correlation[bucket_name] = {
                "total": len(items),
                "hits": hits,
                "hit_rate": round(hits / len(items) * 100, 1) if items else 0,
            }

        # Insights
        insights = []
        avg_funnel = score_sum / len(funnel_data) if funnel_data else 0
        insights.append(f"Average funnel score: {avg_funnel:.1f}")

        # Completeness insight
        full_data = completeness_counts.get("3/3", 0)
        partial_data = completeness_counts.get("2/3", 0)
        ad_only = completeness_counts.get("1/3", 0)
        insights.append(
            f"Data completeness: {full_data} full (3/3), "
            f"{partial_data} partial (2/3), {ad_only} ad-only (1/3)"
        )

        # Top funnel ads
        if funnel_data:
            top = funnel_data[0]
            insights.append(
                f"Best funnel: ad_id={top['ad_id']} "
                f"(score={top['funnel_score']}, grade={top['grade']})"
            )

        # Genre insight
        if genre_analysis:
            best_genre = max(
                ((g, d) for g, d in genre_analysis.items() if d["total_ads"] >= 2),
                key=lambda x: x[1]["avg_funnel_score"],
                default=None,
            )
            if best_genre:
                insights.append(
                    f"Best genre by funnel: '{best_genre[0]}' "
                    f"(avg {best_genre[1]['avg_funnel_score']}, n={best_genre[1]['total_ads']})"
                )

        # Build export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "overall_stats": {
                "avg_funnel_score": round(avg_funnel, 1),
                "median_funnel_score": _safe_median([i["funnel_score"] for i in funnel_data]),
            },
            "grade_distribution": grade_counts,
            "completeness_distribution": completeness_counts,
            "genre_analysis": genre_analysis,
            "funnel_vs_hit_correlation": correlation,
            "top_20_ads": funnel_data[:20],
            "bottom_10_ads": funnel_data[-10:] if len(funnel_data) >= 10 else [],
            "insights": insights,
        }

        # Export
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        out_path = os.path.join(EXPORTS_DIR, "funnel_analysis.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved to: {out_path}")

        # Print summary
        print(f"\n--- Funnel Score Summary ---")
        print(f"  Average:  {avg_funnel:.1f}")
        print(f"  Median:   {_safe_median([i['funnel_score'] for i in funnel_data])}")

        print(f"\n--- Grade Distribution ---")
        for grade in ["A", "B", "C", "D", "F"]:
            count = grade_counts.get(grade, 0)
            pct = count / total * 100
            bar = "#" * int(pct / 2)
            print(f"  {grade}: {count:>4d} ({pct:>5.1f}%) {bar}")

        print(f"\n--- Data Completeness ---")
        for comp, count in sorted(completeness_counts.items()):
            pct = count / total * 100
            print(f"  {comp}: {count:>4d} ({pct:>5.1f}%)")

        print(f"\n--- Genre Funnel Benchmark ---")
        print(f"  {'Genre':<16s} {'Ads':>4s} {'AvgFunnel':>10s} {'HitRate':>8s}")
        print(f"  {'-' * 42}")
        for genre, data in sorted(genre_analysis.items(), key=lambda x: -x[1]["avg_funnel_score"]):
            print(
                f"  {genre:<16s} {data['total_ads']:>4d} "
                f"{data['avg_funnel_score']:>9.1f} "
                f"{data['hit_rate']:>7.1f}%"
            )

        print(f"\n--- Funnel Score vs Hit Rate ---")
        print(f"  {'Score Range':<12s} {'Ads':>4s} {'Hits':>5s} {'HitRate':>8s}")
        print(f"  {'-' * 32}")
        for bucket, data in correlation.items():
            print(
                f"  {bucket:<12s} {data['total']:>4d} {data['hits']:>5d} "
                f"{data['hit_rate']:>7.1f}%"
            )

        print(f"\n--- Top 10 by Funnel Score ---")
        print(f"  {'#':>3s} {'ID':>5s} {'Funnel':>7s} {'Ad':>5s} {'LP':>5s} {'Align':>6s} {'Grade':<5s} {'Hit':>3s}")
        print(f"  {'-' * 45}")
        for i, item in enumerate(funnel_data[:10], 1):
            lp_str = f"{item['lp_score']:.0f}" if item['lp_score'] is not None else "  -"
            al_str = f"{item['alignment_score']:.0f}" if item['alignment_score'] is not None else "   -"
            hit_str = "Y" if item["is_hit"] else "N"
            print(
                f"  {i:>3d} {item['ad_id']:>5d} {item['funnel_score']:>6.1f} "
                f"{item['ad_score']:>4.0f} {lp_str:>5s} {al_str:>6s} "
                f"{item['grade']:<5s} {hit_str:>3s}"
            )

        print(f"\n--- Insights ---")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
