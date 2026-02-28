#!/usr/bin/env python3
"""Build a genre-specific scenario database from ad scenario structures.

Reads ad_metadata["scenario_structure"] and ad_metadata["fine_genre_en"]
for every ad, groups by genre, and computes per-genre scenario archetypes
with hit rates, dominant patterns, best hooks/CTAs, power words, and
recommended creative parameters.

Outputs:
  - backend/exports/scenario_database.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/build_scenario_database.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified  # noqa: F401, E402

from app.core.database import SyncSessionLocal  # noqa: E402
from app.models.ad import Ad  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────

HIT_SCORE_THRESHOLD = 45
TOP_EXAMPLE_ADS = 3


# ── Helper Functions ──────────────────────────────────────────────────────


def _get_score(ad: Ad) -> float:
    """Get latest_hit_score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    """Determine if an ad is a hit (score >= 45)."""
    return _get_score(ad) >= HIT_SCORE_THRESHOLD


def _get_genre(ad: Ad) -> str | None:
    """Get fine_genre_en from ad_metadata."""
    return (ad.ad_metadata or {}).get("fine_genre_en")


def _get_scenario(ad: Ad) -> dict | None:
    """Get scenario_structure from ad_metadata."""
    return (ad.ad_metadata or {}).get("scenario_structure")


def _safe_mean(vals: list[float]) -> float:
    """Return mean rounded to 1 decimal, or 0.0 if empty."""
    return round(mean(vals), 1) if vals else 0.0


def _safe_median(vals: list[float]) -> float:
    """Return median rounded to nearest int, or 0 if empty."""
    return round(median(vals)) if vals else 0


def _most_common(items: list[str]) -> str:
    """Return the most common item in a list, or 'unknown' if empty."""
    if not items:
        return "unknown"
    counter = Counter(items)
    return counter.most_common(1)[0][0]


def _hit_rate(hits: int, total: int) -> float:
    """Calculate hit rate as a ratio (0.0 - 1.0), rounded to 2 decimals."""
    if total == 0:
        return 0.0
    return round(hits / total, 2)


# ── Core Logic ────────────────────────────────────────────────────────────


def _build_archetype_entry(
    archetype: str,
    ads_in_archetype: list[Ad],
) -> dict:
    """Build a single archetype entry with stats, dominant patterns,
    best hooks/CTAs, power words, and example ad IDs."""

    scores = [_get_score(a) for a in ads_in_archetype]
    hit_count = sum(1 for a in ads_in_archetype if _is_hit(a))
    total = len(ads_in_archetype)

    # Sort by score descending for "top" selections
    sorted_by_score = sorted(ads_in_archetype, key=_get_score, reverse=True)

    # Collect structural fields from scenario_structure
    hook_types: list[str] = []
    solution_approaches: list[str] = []
    proof_types: list[str] = []
    cta_types: list[str] = []

    for ad in ads_in_archetype:
        sc = _get_scenario(ad) or {}
        if sc.get("hook_type"):
            hook_types.append(sc["hook_type"])
        if sc.get("solution_approach"):
            solution_approaches.append(sc["solution_approach"])
        if sc.get("proof_type"):
            proof_types.append(sc["proof_type"])
        if sc.get("cta_type"):
            cta_types.append(sc["cta_type"])

    # Best hooks: hook_text_example from top-scored ads
    best_hooks: list[str] = []
    for ad in sorted_by_score[:10]:
        sc = _get_scenario(ad) or {}
        hook_text = sc.get("hook_text_example", "")
        if hook_text and hook_text not in best_hooks:
            best_hooks.append(hook_text)
        if len(best_hooks) >= 5:
            break

    # Best CTAs: cta_type from top-scored ads (unique)
    best_ctas: list[str] = []
    for ad in sorted_by_score[:10]:
        sc = _get_scenario(ad) or {}
        cta = sc.get("cta_type", "")
        if cta and cta not in best_ctas:
            best_ctas.append(cta)
        if len(best_ctas) >= 5:
            break

    # Power words from ad_metadata["keywords"] for ads in this archetype
    all_keywords: list[str] = []
    for ad in ads_in_archetype:
        meta = ad.ad_metadata or {}
        kws = meta.get("keywords")
        if isinstance(kws, list):
            all_keywords.extend(kws)
        elif isinstance(kws, str):
            all_keywords.append(kws)

    keyword_counter = Counter(all_keywords)
    power_words = [word for word, _ in keyword_counter.most_common(10)]

    # Example ad IDs (top 3 by score)
    example_ad_ids = [ad.id for ad in sorted_by_score[:TOP_EXAMPLE_ADS]]

    return {
        "archetype_en": archetype,
        "hit_rate": _hit_rate(hit_count, total),
        "avg_score": _safe_mean(scores),
        "sample_count": total,
        "dominant_hook": _most_common(hook_types),
        "dominant_solution": _most_common(solution_approaches),
        "dominant_proof": _most_common(proof_types),
        "dominant_cta": _most_common(cta_types),
        "best_hooks": best_hooks,
        "best_ctas": best_ctas,
        "power_words": power_words,
        "example_ad_ids": example_ad_ids,
    }


def _compute_genre_metadata(genre_ads: list[Ad]) -> dict:
    """Compute recommended_duration, recommended_format, and optimal_text_length
    for a genre based on its hit ads."""

    hit_ads = [a for a in genre_ads if _is_hit(a)]
    # Fall back to all ads if no hits
    reference_ads = hit_ads if hit_ads else genre_ads

    # recommended_duration: median of duration_seconds among top ads
    durations = []
    for ad in reference_ads:
        if ad.duration_seconds and ad.duration_seconds > 0:
            durations.append(ad.duration_seconds)
    recommended_duration = _safe_median(durations) if durations else 30

    # recommended_format: most common creative_type among hit ads
    creative_types = [
        ad.creative_type for ad in reference_ads
        if ad.creative_type
    ]
    recommended_format = _most_common(creative_types) if creative_types else "video"

    # optimal_text_length: avg title and description length of hit ads
    title_lengths = []
    desc_lengths = []
    for ad in reference_ads:
        if ad.title:
            title_lengths.append(len(ad.title))
        if ad.description:
            desc_lengths.append(len(ad.description))

    optimal_title = round(mean(title_lengths)) if title_lengths else 0
    optimal_desc = round(mean(desc_lengths)) if desc_lengths else 0

    return {
        "recommended_duration": recommended_duration,
        "recommended_format": recommended_format,
        "optimal_text_length": {
            "title": optimal_title,
            "description": optimal_desc,
        },
    }


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Build Scenario Database")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        # Step 1: Load all ads
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Count ads with scenario_structure and fine_genre_en
        ads_with_scenario = [a for a in ads if _get_scenario(a)]
        ads_with_genre = [a for a in ads if _get_genre(a)]
        ads_usable = [a for a in ads if _get_scenario(a) and _get_genre(a)]

        print(f"Ads with scenario_structure: {len(ads_with_scenario)}")
        print(f"Ads with fine_genre_en: {len(ads_with_genre)}")
        print(f"Ads usable (both): {len(ads_usable)}")

        if not ads_usable:
            print("ERROR: No ads have both scenario_structure and fine_genre_en.")
            print("Run extract_scenario_templates.py and classify_fine_genre.py first.")
            return

        # Step 2: Group ads by fine_genre_en
        print("\nStep 2: Grouping ads by genre...")
        genre_groups: dict[str, list[Ad]] = defaultdict(list)
        for ad in ads_usable:
            genre = _get_genre(ad)
            if genre:
                genre_groups[genre].append(ad)

        print(f"  Genres found: {len(genre_groups)}")
        for genre, g_ads in sorted(genre_groups.items(), key=lambda x: -len(x[1])):
            hit_count = sum(1 for a in g_ads if _is_hit(a))
            print(f"    {genre}: {len(g_ads)} ads ({hit_count} hits)")

        # Step 3: Build scenario database per genre
        print("\nStep 3: Building scenario database per genre...")
        scenario_database: list[dict] = []

        for genre, g_ads in sorted(genre_groups.items(), key=lambda x: -len(x[1])):
            # Group by archetype within this genre
            archetype_groups: dict[str, list[Ad]] = defaultdict(list)
            for ad in g_ads:
                sc = _get_scenario(ad)
                if sc:
                    archetype = sc.get("archetype", "standard")
                    archetype_groups[archetype].append(ad)

            # Build archetype entries, sorted by avg_score descending
            top_scenarios: list[dict] = []
            for archetype, arch_ads in archetype_groups.items():
                entry = _build_archetype_entry(archetype, arch_ads)
                top_scenarios.append(entry)

            # Sort by avg_score descending
            top_scenarios.sort(key=lambda x: x["avg_score"], reverse=True)

            # Compute genre-level metadata
            genre_meta = _compute_genre_metadata(g_ads)

            genre_entry = {
                "genre_en": genre,
                "total_ads": len(g_ads),
                "hit_ads": sum(1 for a in g_ads if _is_hit(a)),
                "top_scenarios": top_scenarios,
                "recommended_duration": genre_meta["recommended_duration"],
                "recommended_format": genre_meta["recommended_format"],
                "optimal_text_length": genre_meta["optimal_text_length"],
            }

            scenario_database.append(genre_entry)

        # Sort genres by total_ads descending
        scenario_database.sort(key=lambda x: x["total_ads"], reverse=True)

        # Step 4: Export to JSON
        print("\nStep 4: Exporting scenario database...")
        exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(exports_dir, exist_ok=True)
        output_path = os.path.join(exports_dir, "scenario_database.json")

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_genres": len(scenario_database),
            "total_ads_analyzed": len(ads_usable),
            "hit_score_threshold": HIT_SCORE_THRESHOLD,
            "genres": scenario_database,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"  Saved to: {output_path}")

        # Step 5: Print summary
        print(f"\n{'=' * 60}")
        print("SCENARIO DATABASE SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total genres: {len(scenario_database)}")
        print(f"Total ads analyzed: {len(ads_usable)}")
        print(f"Hit threshold: score >= {HIT_SCORE_THRESHOLD}")

        print(f"\n{'Genre':<30s} {'Ads':>5s} {'Hits':>5s} {'HitRate':>8s} {'Archetypes':>10s} {'Duration':>8s} {'Format':<10s}")
        print(f"{'-' * 82}")

        for ge in scenario_database:
            hr = _hit_rate(ge["hit_ads"], ge["total_ads"])
            print(
                f"{ge['genre_en']:<30s} "
                f"{ge['total_ads']:>5d} "
                f"{ge['hit_ads']:>5d} "
                f"{hr:>7.0%} "
                f"{len(ge['top_scenarios']):>10d} "
                f"{ge['recommended_duration']:>7d}s "
                f"{ge['recommended_format']:<10s}"
            )

        # Print top archetype per genre
        print(f"\n--- Top Archetype per Genre ---")
        print(f"{'Genre':<30s} {'Top Archetype':<30s} {'AvgScore':>9s} {'HitRate':>8s} {'N':>4s}")
        print(f"{'-' * 85}")

        for ge in scenario_database:
            if ge["top_scenarios"]:
                top = ge["top_scenarios"][0]
                print(
                    f"{ge['genre_en']:<30s} "
                    f"{top['archetype_en']:<30s} "
                    f"{top['avg_score']:>8.1f} "
                    f"{top['hit_rate']:>7.0%} "
                    f"{top['sample_count']:>4d}"
                )

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
