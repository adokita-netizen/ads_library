#!/usr/bin/env python3
"""Cross-genre pattern analysis for VAAP platform.

Finds creative patterns that work across multiple genres by analysing
hit rates of hook_type, cta_type, offer_type, and emotion values
per genre. Identifies universal winners, genre-specific winners,
cross-genre combo effectiveness, and genre similarity.

Outputs:
  - backend/exports/cross_genre_patterns.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/cross_genre_analysis.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)

CREATIVE_FIELDS = ["hook_type", "cta_type", "offer_type", "emotion"]

# Minimum sample size for a (genre, field_value) pair to be considered
MIN_SAMPLE = 3


# ── Helper functions ─────────────────────────────────────────────────────


def _is_hit(ad: Ad) -> bool:
    """Determine if an ad is a 'hit' based on hit_level in metadata."""
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    """Get the hit score for an ad, defaulting to 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _get_genre(ad: Ad) -> str | None:
    """Get fine_genre_en from ad_metadata."""
    return (ad.ad_metadata or {}).get("fine_genre_en")


def _get_creative_analysis(ad: Ad) -> dict | None:
    """Get creative_analysis from ad_metadata."""
    return (ad.ad_metadata or {}).get("creative_analysis")


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return round(mean(values), 4) if values else 0.0


def _hit_rate(hits: int, total: int) -> float:
    """Calculate hit rate as a ratio (0.0 - 1.0)."""
    if total == 0:
        return 0.0
    return round(hits / total, 4)


# ── Step 1: Build per-genre per-field hit rates ──────────────────────────


def build_genre_field_stats(
    ads: list[Ad],
) -> dict[str, dict[str, dict[str, dict]]]:
    """For each creative field, compute hit_rate per genre per value.

    Returns:
        {
            field: {
                genre: {
                    value: {"hits": int, "total": int, "hit_rate": float, "avg_score": float}
                }
            }
        }
    """
    # genre -> field -> value -> list of (is_hit, score)
    data: dict[str, dict[str, dict[str, list[tuple[bool, float]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )

    for ad in ads:
        genre = _get_genre(ad)
        ca = _get_creative_analysis(ad)
        if not genre or not ca:
            continue

        hit = _is_hit(ad)
        score = _get_score(ad)

        for field in CREATIVE_FIELDS:
            value = ca.get(field)
            if value is None:
                value = "none"
            value = str(value)
            data[genre][field][value].append((hit, score))

    # Aggregate
    result: dict[str, dict[str, dict[str, dict]]] = {}
    for genre, field_map in data.items():
        result[genre] = {}
        for field, value_map in field_map.items():
            result[genre][field] = {}
            for value, entries in value_map.items():
                total = len(entries)
                hits = sum(1 for h, _ in entries if h)
                scores = [s for _, s in entries]
                result[genre][field][value] = {
                    "hits": hits,
                    "total": total,
                    "hit_rate": _hit_rate(hits, total),
                    "avg_score": _safe_mean(scores),
                }

    return result


# ── Step 2: Identify universal and genre-specific winners ────────────────


def find_universal_winners(
    genre_field_stats: dict,
    min_hit_rate: float = 0.50,
    min_genres: int = 3,
) -> list[dict]:
    """Find values with hit_rate >= min_hit_rate in min_genres+ genres."""
    winners = []

    for field in CREATIVE_FIELDS:
        # Collect all values across genres for this field
        value_genres: dict[str, list[dict]] = defaultdict(list)

        for genre, field_map in genre_field_stats.items():
            value_map = field_map.get(field, {})
            for value, stats in value_map.items():
                if stats["total"] >= MIN_SAMPLE and stats["hit_rate"] >= min_hit_rate:
                    value_genres[value].append({
                        "genre": genre,
                        "hit_rate": stats["hit_rate"],
                        "total": stats["total"],
                        "hits": stats["hits"],
                        "avg_score": stats["avg_score"],
                    })

        for value, genre_list in value_genres.items():
            if len(genre_list) >= min_genres:
                avg_rate = _safe_mean([g["hit_rate"] for g in genre_list])
                winners.append({
                    "field": field,
                    "value": value,
                    "genres_effective_in": len(genre_list),
                    "avg_hit_rate": avg_rate,
                    "genres": sorted(
                        [{"genre": g["genre"], "hit_rate": g["hit_rate"], "total": g["total"]}
                         for g in genre_list],
                        key=lambda x: -x["hit_rate"],
                    ),
                })

    # Sort by genres_effective_in desc, then avg_hit_rate desc
    winners.sort(key=lambda w: (-w["genres_effective_in"], -w["avg_hit_rate"]))
    return winners


def find_genre_specific_winners(
    genre_field_stats: dict,
    min_hit_rate: float = 0.60,
    max_genres: int = 2,
) -> list[dict]:
    """Find values with hit_rate >= min_hit_rate in exactly 1-max_genres genres."""
    winners = []

    for field in CREATIVE_FIELDS:
        value_genres: dict[str, list[dict]] = defaultdict(list)

        for genre, field_map in genre_field_stats.items():
            value_map = field_map.get(field, {})
            for value, stats in value_map.items():
                if stats["total"] >= MIN_SAMPLE and stats["hit_rate"] >= min_hit_rate:
                    value_genres[value].append({
                        "genre": genre,
                        "hit_rate": stats["hit_rate"],
                        "total": stats["total"],
                        "hits": stats["hits"],
                        "avg_score": stats["avg_score"],
                    })

        for value, genre_list in value_genres.items():
            if 1 <= len(genre_list) <= max_genres:
                avg_rate = _safe_mean([g["hit_rate"] for g in genre_list])
                winners.append({
                    "field": field,
                    "value": value,
                    "genres_effective_in": len(genre_list),
                    "avg_hit_rate": avg_rate,
                    "genres": sorted(
                        [{"genre": g["genre"], "hit_rate": g["hit_rate"], "total": g["total"]}
                         for g in genre_list],
                        key=lambda x: -x["hit_rate"],
                    ),
                })

    winners.sort(key=lambda w: (-w["avg_hit_rate"], -w["genres_effective_in"]))
    return winners


# ── Step 3: Cross-genre combo analysis (hook + cta) ─────────────────────


def find_universal_combos(
    ads: list[Ad],
    min_hit_rate: float = 0.50,
    min_genres: int = 2,
) -> list[dict]:
    """Find hook+cta combos that work well across multiple genres."""
    # genre -> combo_key -> list of (is_hit, score)
    combo_data: dict[str, dict[str, list[tuple[bool, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for ad in ads:
        genre = _get_genre(ad)
        ca = _get_creative_analysis(ad)
        if not genre or not ca:
            continue

        hook = ca.get("hook_type", "none")
        cta = ca.get("cta_type", "none")
        combo_key = f"{hook}+{cta}"
        combo_data[genre][combo_key].append((_is_hit(ad), _get_score(ad)))

    # For each combo, find genres where it has high hit rate
    combo_genres: dict[str, list[dict]] = defaultdict(list)

    for genre, combo_map in combo_data.items():
        for combo_key, entries in combo_map.items():
            total = len(entries)
            if total < MIN_SAMPLE:
                continue
            hits = sum(1 for h, _ in entries if h)
            hr = _hit_rate(hits, total)
            if hr >= min_hit_rate:
                scores = [s for _, s in entries]
                combo_genres[combo_key].append({
                    "genre": genre,
                    "hit_rate": hr,
                    "total": total,
                    "hits": hits,
                    "avg_score": _safe_mean(scores),
                })

    results = []
    for combo_key, genre_list in combo_genres.items():
        if len(genre_list) >= min_genres:
            parts = combo_key.split("+", 1)
            avg_rate = _safe_mean([g["hit_rate"] for g in genre_list])
            results.append({
                "hook_type": parts[0],
                "cta_type": parts[1] if len(parts) > 1 else "none",
                "combo": combo_key,
                "genres_effective_in": len(genre_list),
                "avg_hit_rate": avg_rate,
                "genres": sorted(
                    [{"genre": g["genre"], "hit_rate": g["hit_rate"], "total": g["total"]}
                     for g in genre_list],
                    key=lambda x: -x["hit_rate"],
                ),
            })

    results.sort(key=lambda r: (-r["genres_effective_in"], -r["avg_hit_rate"]))
    return results


# ── Step 4: Genre similarity matrix (Jaccard) ───────────────────────────


def compute_genre_similarity(
    genre_field_stats: dict,
    min_hit_rate: float = 0.50,
) -> dict[str, dict[str, float]]:
    """Compute Jaccard similarity of winning patterns between genre pairs.

    A 'winning pattern' for a genre is any (field, value) pair where
    hit_rate >= min_hit_rate and sample size >= MIN_SAMPLE.
    """
    # Build set of winning patterns per genre
    genre_patterns: dict[str, set[str]] = {}

    for genre, field_map in genre_field_stats.items():
        patterns: set[str] = set()
        for field, value_map in field_map.items():
            for value, stats in value_map.items():
                if stats["total"] >= MIN_SAMPLE and stats["hit_rate"] >= min_hit_rate:
                    patterns.add(f"{field}:{value}")
        if patterns:
            genre_patterns[genre] = patterns

    genres = sorted(genre_patterns.keys())
    matrix: dict[str, dict[str, float]] = {}

    for g1 in genres:
        matrix[g1] = {}
        for g2 in genres:
            if g1 == g2:
                matrix[g1][g2] = 1.0
                continue
            s1 = genre_patterns[g1]
            s2 = genre_patterns[g2]
            intersection = len(s1 & s2)
            union = len(s1 | s2)
            matrix[g1][g2] = round(intersection / union, 4) if union > 0 else 0.0

    return matrix


# ── Step 5: Generate insights ────────────────────────────────────────────


def generate_insights(
    universal_patterns: list[dict],
    genre_specific_patterns: list[dict],
    universal_combos: list[dict],
    similarity_matrix: dict[str, dict[str, float]],
) -> list[str]:
    """Generate human-readable insights from the analysis."""
    insights = []

    # Universal patterns insight
    if universal_patterns:
        top = universal_patterns[0]
        insights.append(
            f"Most universal pattern: {top['field']}='{top['value']}' "
            f"works in {top['genres_effective_in']} genres "
            f"(avg hit_rate={top['avg_hit_rate']:.1%})"
        )
        count_by_field = defaultdict(int)
        for p in universal_patterns:
            count_by_field[p["field"]] += 1
        for field, count in sorted(count_by_field.items(), key=lambda x: -x[1]):
            insights.append(
                f"  {field}: {count} universal winner(s) found"
            )
    else:
        insights.append("No universal patterns found (hit_rate>=50% in 3+ genres)")

    # Genre-specific patterns insight
    if genre_specific_patterns:
        insights.append(
            f"Found {len(genre_specific_patterns)} genre-specific pattern(s) "
            f"(hit_rate>=60% in 1-2 genres only)"
        )
        top_specific = genre_specific_patterns[:3]
        for p in top_specific:
            genre_names = ", ".join(g["genre"] for g in p["genres"])
            insights.append(
                f"  {p['field']}='{p['value']}' -> {genre_names} "
                f"(avg hit_rate={p['avg_hit_rate']:.1%})"
            )
    else:
        insights.append("No genre-specific patterns found (hit_rate>=60% in 1-2 genres)")

    # Universal combos insight
    if universal_combos:
        top_combo = universal_combos[0]
        insights.append(
            f"Best cross-genre combo: {top_combo['combo']} "
            f"works in {top_combo['genres_effective_in']} genres "
            f"(avg hit_rate={top_combo['avg_hit_rate']:.1%})"
        )
    else:
        insights.append("No universal combos found (hook+cta with hit_rate>=50% in 2+ genres)")

    # Genre similarity insight
    if similarity_matrix:
        # Find most similar pair
        best_pair = None
        best_sim = -1.0
        genres = sorted(similarity_matrix.keys())
        for g1, g2 in combinations(genres, 2):
            sim = similarity_matrix.get(g1, {}).get(g2, 0.0)
            if sim > best_sim:
                best_sim = sim
                best_pair = (g1, g2)

        if best_pair and best_sim > 0:
            insights.append(
                f"Most similar genres: {best_pair[0]} <-> {best_pair[1]} "
                f"(Jaccard={best_sim:.2f})"
            )

        # Find most unique genre (lowest avg similarity)
        if len(genres) >= 3:
            avg_sims = {}
            for g in genres:
                others = [
                    similarity_matrix[g].get(g2, 0.0)
                    for g2 in genres if g2 != g
                ]
                avg_sims[g] = _safe_mean(others) if others else 0.0
            most_unique = min(avg_sims, key=lambda k: avg_sims[k])
            insights.append(
                f"Most unique genre: {most_unique} "
                f"(avg Jaccard with others={avg_sims[most_unique]:.2f})"
            )

    return insights


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("CROSS-GENRE PATTERN ANALYSIS")
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

        # Filter to ads with both genre and creative_analysis
        eligible = [
            a for a in ads
            if _get_genre(a) and _get_creative_analysis(a)
        ]
        print(f"Ads with genre + creative_analysis: {len(eligible)}/{total}")

        if len(eligible) == 0:
            print("ERROR: No ads have both fine_genre_en and creative_analysis.")
            print("Run classify_fine_genre.py and analyze_creative_elements.py first.")
            return

        # Genre distribution
        genre_counts: dict[str, int] = defaultdict(int)
        for ad in eligible:
            genre_counts[_get_genre(ad)] += 1
        print(f"Genres found: {len(genre_counts)}")
        for genre, count in sorted(genre_counts.items(), key=lambda x: -x[1]):
            hit_count = sum(1 for a in eligible if _get_genre(a) == genre and _is_hit(a))
            hr = _hit_rate(hit_count, count)
            print(f"  {genre:<30s} n={count:>4d}  hits={hit_count:>3d}  hit_rate={hr:.1%}")

        # ── Step 1: Build per-genre per-field hit rate stats ───────────
        print("\nBuilding per-genre per-field statistics...")
        genre_field_stats = build_genre_field_stats(eligible)

        # ── Step 2: Universal and genre-specific winners ──────────────
        print("Identifying universal winners (hit_rate>=50% in 3+ genres)...")
        universal_patterns = find_universal_winners(genre_field_stats)
        print(f"  Found {len(universal_patterns)} universal pattern(s)")

        print("Identifying genre-specific winners (hit_rate>=60% in 1-2 genres)...")
        genre_specific_patterns = find_genre_specific_winners(genre_field_stats)
        print(f"  Found {len(genre_specific_patterns)} genre-specific pattern(s)")

        # ── Step 3: Cross-genre combo analysis ────────────────────────
        print("Analysing hook+cta combos across genres...")
        universal_combos = find_universal_combos(eligible)
        print(f"  Found {len(universal_combos)} universal combo(s)")

        # ── Step 4: Genre similarity matrix ───────────────────────────
        print("Computing genre similarity matrix (Jaccard)...")
        similarity_matrix = compute_genre_similarity(genre_field_stats)

        # ── Step 5: Generate insights ─────────────────────────────────
        insights = generate_insights(
            universal_patterns,
            genre_specific_patterns,
            universal_combos,
            similarity_matrix,
        )

        # ── Build output JSON ─────────────────────────────────────────
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "eligible_ads": len(eligible),
            "genres_analysed": len(genre_counts),
            "universal_patterns": universal_patterns,
            "genre_specific_patterns": genre_specific_patterns,
            "universal_combos": universal_combos,
            "genre_similarity_matrix": similarity_matrix,
            "insights": insights,
        }

        # ── Export ────────────────────────────────────────────────────
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "cross_genre_patterns.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nExported to: {export_path}")

        # ── Print summary ─────────────────────────────────────────────

        # Universal patterns
        print(f"\n{'=' * 60}")
        print("UNIVERSAL PATTERNS (hit_rate>=50% in 3+ genres)")
        print(f"{'=' * 60}")
        if universal_patterns:
            print(f"  {'Field':<14s} {'Value':<20s} {'Genres':>6s} {'AvgRate':>8s}")
            print(f"  {'-' * 52}")
            for p in universal_patterns[:15]:
                print(
                    f"  {p['field']:<14s} {p['value']:<20s} "
                    f"{p['genres_effective_in']:>6d} {p['avg_hit_rate']:>7.1%}"
                )
                for g in p["genres"][:3]:
                    print(f"    -> {g['genre']:<26s} rate={g['hit_rate']:.1%} (n={g['total']})")
        else:
            print("  (none found)")

        # Genre-specific patterns
        print(f"\n{'=' * 60}")
        print("GENRE-SPECIFIC PATTERNS (hit_rate>=60% in 1-2 genres)")
        print(f"{'=' * 60}")
        if genre_specific_patterns:
            print(f"  {'Field':<14s} {'Value':<20s} {'Genres':>6s} {'AvgRate':>8s} {'Where'}")
            print(f"  {'-' * 72}")
            for p in genre_specific_patterns[:20]:
                genre_names = ", ".join(g["genre"] for g in p["genres"])
                print(
                    f"  {p['field']:<14s} {p['value']:<20s} "
                    f"{p['genres_effective_in']:>6d} {p['avg_hit_rate']:>7.1%} "
                    f"{genre_names}"
                )
        else:
            print("  (none found)")

        # Universal combos
        print(f"\n{'=' * 60}")
        print("UNIVERSAL COMBOS (hook+cta with hit_rate>=50% in 2+ genres)")
        print(f"{'=' * 60}")
        if universal_combos:
            print(f"  {'Combo':<30s} {'Genres':>6s} {'AvgRate':>8s}")
            print(f"  {'-' * 48}")
            for c in universal_combos[:15]:
                print(
                    f"  {c['combo']:<30s} "
                    f"{c['genres_effective_in']:>6d} {c['avg_hit_rate']:>7.1%}"
                )
                for g in c["genres"][:3]:
                    print(f"    -> {g['genre']:<26s} rate={g['hit_rate']:.1%} (n={g['total']})")
        else:
            print("  (none found)")

        # Similarity matrix
        print(f"\n{'=' * 60}")
        print("GENRE SIMILARITY MATRIX (Jaccard of winning patterns)")
        print(f"{'=' * 60}")
        if similarity_matrix:
            genres_sorted = sorted(similarity_matrix.keys())
            # Print top similar pairs
            pairs = []
            for g1, g2 in combinations(genres_sorted, 2):
                sim = similarity_matrix.get(g1, {}).get(g2, 0.0)
                pairs.append((g1, g2, sim))
            pairs.sort(key=lambda x: -x[2])
            print("  Top similar genre pairs:")
            for g1, g2, sim in pairs[:10]:
                print(f"    {g1:<25s} <-> {g2:<25s}  Jaccard={sim:.3f}")

            if len(pairs) > 0:
                print("\n  Least similar genre pairs:")
                for g1, g2, sim in pairs[-5:]:
                    print(f"    {g1:<25s} <-> {g2:<25s}  Jaccard={sim:.3f}")
        else:
            print("  (not enough data)")

        # Insights
        print(f"\n{'=' * 60}")
        print("KEY INSIGHTS")
        print(f"{'=' * 60}")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
