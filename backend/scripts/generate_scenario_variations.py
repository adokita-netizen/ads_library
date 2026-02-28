#!/usr/bin/env python3
"""Generate N variations of a base scenario for a given genre/product.

Loads scenario archetypes from scenario_database.json (if available) and
generates creative variations by cycling through hook types, CTA types,
tones, and lengths.  Each variation is scored using archetype averages,
tone modifiers, and length modifiers.  If a hit predictor model is
available, hit probability is predicted; otherwise it is estimated from
genre hit rates.

Outputs:
  - backend/exports/scenario_variations.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_scenario_variations.py --genre beauty --product "skincare serum" --count 10
"""

import argparse
import itertools
import json
import os
import pickle
import sys
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# ── Template Constants ────────────────────────────────────────────────────

HOOK_TYPES = ["question", "shock", "benefit", "social_proof", "urgency", "pain_point"]
CTA_TYPES = ["line_add", "free_consultation", "purchase", "signup", "free_trial", "learn_more"]
TONES = ["formal", "casual", "urgent"]
LENGTHS = ["short", "standard", "long"]

TONE_MODIFIERS = {
    "formal": {"prefix": "", "suffix": "", "score_factor": 1.0},
    "casual": {"prefix": "", "suffix": "", "score_factor": 0.95},
    "urgent": {"prefix": "", "suffix": "", "score_factor": 1.05},
}

LENGTH_PRESETS = {
    "short": {"seconds": 15, "body_lines": 2, "score_factor": 0.9},
    "standard": {"seconds": 30, "body_lines": 4, "score_factor": 1.0},
    "long": {"seconds": 60, "body_lines": 6, "score_factor": 0.95},
}

# ── Hook Text Templates ──────────────────────────────────────────────────

HOOK_TEMPLATES = {
    "question": "Are you still struggling with {problem}? Discover {product} now.",
    "shock": "The surprising truth about {problem} that nobody talks about.",
    "benefit": "Get {benefit} in just {seconds}s with {product}.",
    "social_proof": "Over 10,000 people already use {product} for {benefit}.",
    "urgency": "Limited time only: {product} is available at a special price.",
    "pain_point": "Tired of {problem}? {product} solves it once and for all.",
}

# ── CTA Text Templates ───────────────────────────────────────────────────

CTA_TEMPLATES = {
    "line_add": "Add us on LINE for a free consultation!",
    "free_consultation": "Book your free consultation today.",
    "purchase": "Order {product} now and see the difference.",
    "signup": "Sign up for free and start your journey.",
    "free_trial": "Try {product} free for 7 days - no commitment.",
    "learn_more": "Learn more about {product} on our official site.",
}

# ── Body Outline Templates ───────────────────────────────────────────────

BODY_OUTLINE_TEMPLATES = {
    2: [
        "1. Introduce the core problem",
        "2. Present {product} as the solution",
    ],
    4: [
        "1. Hook: highlight the problem",
        "2. Agitate: show the consequences",
        "3. Solution: introduce {product}",
        "4. Social proof / results",
    ],
    6: [
        "1. Hook: highlight the problem",
        "2. Agitate: emotional impact",
        "3. Authority: expert endorsement",
        "4. Solution: introduce {product}",
        "5. Proof: testimonials / data",
        "6. CTA: drive action",
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────


def _safe_mean(vals: list[float]) -> float:
    return round(mean(vals), 1) if vals else 0.0


def _get_score(ad: Ad) -> float:
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _load_scenario_database() -> dict | None:
    """Load scenario_database.json if it exists."""
    path = os.path.join(EXPORTS_DIR, "scenario_database.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_hit_predictor() -> dict | None:
    """Load hit_predictor.pkl if it exists."""
    path = os.path.join(MODELS_DIR, "hit_predictor.pkl")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _compute_genre_hit_rates(session, genre: str) -> dict:
    """Compute hit rate stats for a genre from the database."""
    ads = session.query(Ad).all()
    genre_ads = [
        a for a in ads
        if (a.category.value if a.category else "other") == genre
    ]
    all_scores = [_get_score(a) for a in genre_ads if _get_score(a) > 0]
    hit_count = sum(1 for a in genre_ads if _is_hit(a))
    total = len(genre_ads)

    return {
        "total_ads": total,
        "hit_count": hit_count,
        "hit_rate": round(hit_count / total * 100, 1) if total > 0 else 0.0,
        "avg_score": _safe_mean(all_scores),
    }


def _get_archetype_avg_score(scenario_db: dict | None, genre: str) -> float:
    """Extract average archetype score for the genre from scenario_database.json."""
    if scenario_db is None:
        return 50.0  # default baseline

    # Try to find genre-specific archetype data
    archetypes = scenario_db.get("archetypes", {})
    genre_archetypes = scenario_db.get("genre_archetypes", {}).get(genre, {})

    scores = []

    # Genre-specific archetypes
    if genre_archetypes:
        for arch_data in genre_archetypes.values() if isinstance(genre_archetypes, dict) else []:
            avg = arch_data.get("avg_score", 0)
            if avg > 0:
                scores.append(avg)

    # Global archetypes fallback
    if not scores and archetypes:
        for arch_data in archetypes.values() if isinstance(archetypes, dict) else []:
            avg = arch_data.get("avg_score", 0)
            if avg > 0:
                scores.append(avg)

    return _safe_mean(scores) if scores else 50.0


def _generate_title(hook_type: str, product: str, tone: str) -> str:
    """Generate a variation title based on hook type and tone."""
    base_titles = {
        "question": f"Why {product} is the answer you have been looking for",
        "shock": f"The hidden secret behind {product} effectiveness",
        "benefit": f"Transform your results with {product}",
        "social_proof": f"Why thousands choose {product} every day",
        "urgency": f"Last chance to get {product} at this price",
        "pain_point": f"Stop suffering - {product} changes everything",
    }
    title = base_titles.get(hook_type, f"Discover {product}")

    tone_mod = TONE_MODIFIERS.get(tone, TONE_MODIFIERS["formal"])
    if tone_mod["prefix"]:
        title = tone_mod["prefix"] + " " + title
    if tone_mod["suffix"]:
        title = title + " " + tone_mod["suffix"]

    return title


def _generate_hook_text(
    hook_type: str, product: str, benefit: str, length: str
) -> str:
    """Generate hook text from templates."""
    seconds = LENGTH_PRESETS.get(length, LENGTH_PRESETS["standard"])["seconds"]
    problem = benefit if benefit else "this common problem"

    template = HOOK_TEMPLATES.get(hook_type, HOOK_TEMPLATES["benefit"])
    return template.format(
        product=product,
        benefit=benefit if benefit else "amazing results",
        problem=problem,
        seconds=seconds,
    )


def _generate_body_outline(product: str, length: str) -> str:
    """Generate body outline based on length preset."""
    body_lines = LENGTH_PRESETS.get(length, LENGTH_PRESETS["standard"])["body_lines"]
    template_lines = BODY_OUTLINE_TEMPLATES.get(
        body_lines, BODY_OUTLINE_TEMPLATES[4]
    )
    return "\n".join(line.format(product=product) for line in template_lines)


def _generate_cta_text(cta_type: str, product: str) -> str:
    """Generate CTA text from templates."""
    template = CTA_TEMPLATES.get(cta_type, CTA_TEMPLATES["learn_more"])
    return template.format(product=product)


def _estimate_hit_probability(
    estimated_score: float, genre_stats: dict
) -> float:
    """Estimate hit probability from the estimated score and genre hit rate."""
    genre_hit_rate = genre_stats.get("hit_rate", 10.0) / 100.0
    genre_avg_score = genre_stats.get("avg_score", 50.0)

    if genre_avg_score <= 0:
        genre_avg_score = 50.0

    # Scale probability relative to genre averages
    ratio = estimated_score / genre_avg_score
    probability = genre_hit_rate * ratio

    # Clamp to [0.0, 1.0]
    return round(max(0.0, min(1.0, probability)), 4)


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate N scenario variations for a given genre/product."
    )
    parser.add_argument(
        "--genre", required=True,
        help="Ad genre/category (e.g. beauty, health, ec_d2c, finance, education)."
    )
    parser.add_argument(
        "--product", required=True,
        help="Product name (e.g. 'skincare serum', 'fitness app')."
    )
    parser.add_argument(
        "--benefit", default="",
        help="Key benefit to highlight (optional)."
    )
    parser.add_argument(
        "--count", type=int, default=5,
        help="Number of variations to generate (default: 5)."
    )
    args = parser.parse_args()

    genre = args.genre.strip()
    product = args.product.strip()
    benefit = args.benefit.strip()
    count = max(1, args.count)

    print("=" * 60)
    print("Scenario Variation Generator")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    print(f"  Genre:   {genre}")
    print(f"  Product: {product}")
    print(f"  Benefit: {benefit if benefit else '(not specified)'}")
    print(f"  Count:   {count}")

    # ── Load resources ────────────────────────────────────────────────
    print("\nLoading resources...")

    scenario_db = _load_scenario_database()
    if scenario_db:
        print("  scenario_database.json loaded.")
    else:
        print("  scenario_database.json not found, using defaults.")

    predictor_package = _load_hit_predictor()
    has_predictor = predictor_package is not None
    if has_predictor:
        print("  hit_predictor.pkl loaded.")
    else:
        print("  hit_predictor.pkl not found, will estimate from genre hit rates.")

    # ── Compute genre stats from DB ───────────────────────────────────
    print("\nQuerying database for genre statistics...")
    session = SyncSessionLocal()
    try:
        genre_stats = _compute_genre_hit_rates(session, genre)
        print(f"  Genre '{genre}': {genre_stats['total_ads']} ads, "
              f"hit rate {genre_stats['hit_rate']}%, "
              f"avg score {genre_stats['avg_score']}")
    finally:
        session.close()

    # ── Get archetype baseline score ──────────────────────────────────
    archetype_avg = _get_archetype_avg_score(scenario_db, genre)
    print(f"  Archetype avg score: {archetype_avg}")

    # ── Generate all possible combinations ────────────────────────────
    print(f"\nGenerating variation combinations...")

    # Create a cycle over all combination axes
    combo_cycle = itertools.product(HOOK_TYPES, CTA_TYPES, TONES, LENGTHS)
    all_combos = list(combo_cycle)
    print(f"  Total possible combinations: {len(all_combos)}")

    # If count > total combos, we repeat; otherwise take a spread
    if count >= len(all_combos):
        selected_combos = all_combos[:]
        # Extend with cycling if needed
        cycle_iter = itertools.cycle(all_combos)
        while len(selected_combos) < count:
            selected_combos.append(next(cycle_iter))
    else:
        # Spread evenly across the combination space
        step = max(1, len(all_combos) // count)
        selected_combos = []
        for i in range(0, len(all_combos), step):
            if len(selected_combos) >= count:
                break
            selected_combos.append(all_combos[i])
        # Fill remaining if needed
        idx = 0
        while len(selected_combos) < count:
            candidate = all_combos[idx]
            if candidate not in selected_combos:
                selected_combos.append(candidate)
            idx += 1

    selected_combos = selected_combos[:count]

    # ── Build variations ──────────────────────────────────────────────
    print(f"  Building {len(selected_combos)} variations...")

    variations = []
    for vid, (hook_type, cta_type, tone, length) in enumerate(selected_combos, 1):
        title = _generate_title(hook_type, product, tone)
        hook_text = _generate_hook_text(hook_type, product, benefit, length)
        body_outline = _generate_body_outline(product, length)
        cta_text = _generate_cta_text(cta_type, product)

        # Score: archetype_avg * tone_modifier * length_modifier
        tone_factor = TONE_MODIFIERS[tone]["score_factor"]
        length_factor = LENGTH_PRESETS[length]["score_factor"]
        estimated_score = round(archetype_avg * tone_factor * length_factor, 1)

        # Hit probability
        if has_predictor:
            try:
                model = predictor_package["model"]
                feature_names = predictor_package.get("feature_names", [])
                scaler = predictor_package.get("scaler")
                model_type = predictor_package.get("model_type", "unknown")

                # Build a minimal feature vector from the variation
                features = {fn: 0.0 for fn in feature_names}
                # Set hook and CTA features if they exist in feature names
                for fn in feature_names:
                    if f"hook_{hook_type}" in fn:
                        features[fn] = 1.0
                    elif f"cta_{cta_type}" in fn:
                        features[fn] = 1.0

                feature_vec = [float(features.get(fn, 0)) for fn in feature_names]

                if model_type == "sklearn" and scaler is not None:
                    import numpy as np
                    X = scaler.transform(np.array([feature_vec]))
                    hit_probability = float(model.predict_proba(X)[0][1])
                else:
                    probs = model.predict_proba([feature_vec])
                    hit_probability = float(probs[0]) if isinstance(probs[0], (int, float)) else float(probs[0][1])

                hit_probability = round(max(0.0, min(1.0, hit_probability)), 4)
            except Exception:
                # Fallback to estimation if prediction fails
                hit_probability = _estimate_hit_probability(estimated_score, genre_stats)
        else:
            hit_probability = _estimate_hit_probability(estimated_score, genre_stats)

        variation = {
            "variation_id": vid,
            "hook_type": hook_type,
            "cta_type": cta_type,
            "tone": tone,
            "length": length,
            "duration_seconds": LENGTH_PRESETS[length]["seconds"],
            "title": title,
            "hook_text": hook_text,
            "body_outline": body_outline,
            "cta_text": cta_text,
            "estimated_score": estimated_score,
            "hit_probability": hit_probability,
            "rank": 0,  # will be set after sorting
        }
        variations.append(variation)

    # ── Rank by estimated score (descending), then hit probability ─────
    variations.sort(
        key=lambda v: (v["estimated_score"], v["hit_probability"]),
        reverse=True,
    )
    for rank, var in enumerate(variations, 1):
        var["rank"] = rank

    # ── Build output ──────────────────────────────────────────────────
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "genre": genre,
        "product": product,
        "benefit": benefit if benefit else None,
        "variation_count": len(variations),
        "genre_stats": genre_stats,
        "archetype_avg_score": archetype_avg,
        "predictor_available": has_predictor,
        "variations": variations,
    }

    # ── Export to JSON ────────────────────────────────────────────────
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    out_path = os.path.join(EXPORTS_DIR, "scenario_variations.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nExported to: {out_path}")

    # ── Print Summary ─────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("SCENARIO VARIATIONS RANKING")
    print(f"{'=' * 60}")
    print(f"  Genre: {genre}  |  Product: {product}  |  Variations: {len(variations)}")
    print()
    print(f"  {'Rank':>4s}  {'Hook':<14s} {'CTA':<18s} {'Tone':<8s} "
          f"{'Length':<9s} {'Score':>6s} {'HitProb':>8s}")
    print(f"  {'-' * 73}")

    for var in variations:
        print(
            f"  {var['rank']:>4d}  {var['hook_type']:<14s} "
            f"{var['cta_type']:<18s} {var['tone']:<8s} "
            f"{var['length']:<9s} {var['estimated_score']:>6.1f} "
            f"{var['hit_probability']:>7.4f}"
        )

    # Top variation detail
    if variations:
        top = variations[0]
        print(f"\n--- Top Variation (Rank 1) ---")
        print(f"  Title:    {top['title']}")
        print(f"  Hook:     {top['hook_text']}")
        print(f"  CTA:      {top['cta_text']}")
        print(f"  Duration: {top['duration_seconds']}s ({top['length']})")
        print(f"  Score:    {top['estimated_score']}")
        print(f"  Hit Prob: {top['hit_probability']}")
        print(f"\n  Body Outline:")
        for line in top["body_outline"].split("\n"):
            print(f"    {line}")

    print(f"\nDone! {len(variations)} variations generated and ranked.")


if __name__ == "__main__":
    main()
