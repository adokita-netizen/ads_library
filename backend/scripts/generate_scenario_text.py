#!/usr/bin/env python3
"""Generate ad scenario text from templates (VAAP).

Template-based scenario text generator. Loads scenario_database.json,
finds the matching genre, and produces title / hook / body / CTA
variations using string templates with {product}, {benefit}, {cta}
placeholders. No external AI API calls.

Outputs:
  - JSON to stdout (always)
  - JSON to --output file (optional)

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_scenario_text.py --genre beauty --product "SakuraClinic"
    python scripts/generate_scenario_text.py --genre health --product "VitalGym" --benefit "metabolism boost" --cta consultation --output out.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)
SCENARIO_DB_PATH = os.path.join(EXPORTS_DIR, "scenario_database.json")


# ── Hook Templates (Japanese ad content) ─────────────────────────────────
# Keys correspond to hook_type values in scenario_database.json archetypes.

HOOK_TEMPLATES: dict[str, list[str]] = {
    "question": [
        "{product} \u2015 \u6b63\u3057\u3044\u65b9\u6cd5\u3001\u77e5\u3063\u3066\u3044\u307e\u3059\u304b\uff1f",
        "\u307e\u3060\u305d\u306e\u60a9\u307f\u3001\u62b1\u3048\u3066\u3044\u307e\u305b\u3093\u304b\uff1f{product}\u304c\u89e3\u6c7a\u3057\u307e\u3059",
        "{benefit}\u3063\u3066\u672c\u5f53\uff1f{product}\u306e\u5b9f\u529b\u3092\u691c\u8a3c",
    ],
    "shock": [
        "\u3010\u885d\u6483\u3011{product}\u3067\u3053\u3053\u307e\u3067\u5909\u308f\u308b\u3068\u306f\u2026",
        "\u5b9f\u306f\u77e5\u3089\u306a\u304b\u3063\u305f\u2026{product}\u306e\u88cf\u30ef\u30b6",
        "\u3010\u8b66\u544a\u3011{benefit}\u3092\u77e5\u3089\u306a\u3044\u3068\u640d\u3057\u307e\u3059",
    ],
    "benefit": [
        "\u305f\u3063\u305f\u3053\u308c\u3060\u3051\u3067{benefit}\u3092\u5b9f\u73fe\uff01{product}",
        "{product}\u3067\u624b\u8efd\u306b{benefit}\u3092\u5b9f\u611f",
        "\u7c21\u5358\u30fb\u5b89\u5fc3\u30fb{benefit}\u3002{product}\u304c\u9078\u3070\u308c\u308b\u7406\u7531",
    ],
    "social_proof": [
        "\u3059\u3067\u306b1\u4e07\u4eba\u304c\u4f53\u9a13\uff01{product}\u306e\u5b9f\u529b",
        "\u53e3\u30b3\u30df\u6e80\u8db3\u5ea695%\u203b {product}\u306e\u79d8\u5bc6",
        "\u30e9\u30f3\u30ad\u30f3\u30b0No.1\u203b {product}\u304c\u8a71\u984c\u306e\u7406\u7531",
    ],
    "urgency": [
        "\u3010\u671f\u9593\u9650\u5b9a\u3011{product}\u7279\u5225\u30ad\u30e3\u30f3\u30da\u30fc\u30f3\u5b9f\u65bd\u4e2d",
        "\u4eca\u3060\u3051\uff01{product}\u3092\u304a\u5f97\u306b\u8a66\u305b\u308b\u30c1\u30e3\u30f3\u30b9",
        "\u6b8b\u308a\u308f\u305a\u304b\uff01{product}\u9650\u5b9a\u30aa\u30d5\u30a1\u30fc",
    ],
    "pain_point": [
        "{benefit}\u304c\u3067\u304d\u306a\u3044\u2026\u305d\u306e\u60a9\u307f\u3001{product}\u304c\u89e3\u6c7a",
        "\u3082\u3046\u6211\u6162\u3057\u306a\u304f\u3066\u3044\u3044\u3002{product}\u3067{benefit}\u3092",
        "\u305d\u306e\u65b9\u6cd5\u3001\u53e4\u304f\u306a\u3044\u3067\u3059\u304b\uff1f{product}\u306a\u3089{benefit}",
    ],
    "statistic": [
        "80%\u306e\u4eba\u304c\u77e5\u3089\u306a\u3044{product}\u306e\u771f\u5b9f",
        "\u6e80\u8db3\u5ea693%\u203b {product}\u304c\u652f\u6301\u3055\u308c\u308b{benefit}\u306e\u79d8\u5bc6",
        "\u7d2f\u8a0850\u4e07\u500b\u7a81\u7834\uff01{product}\u306e\u5b9f\u529b\u3068\u306f",
    ],
}

# ── Title Templates ──────────────────────────────────────────────────────

TITLE_TEMPLATES: list[str] = [
    "{hook} \u00d7 {product}\uff5c{benefit}\u3092\u5b9f\u73fe",
    "{product}\uff5c{benefit}\u306e\u65b0\u5e38\u8b58",
    "\u3010\u516c\u5f0f\u3011{product}\uff5c{hook}\u3067{benefit}",
]

# ── Body Templates ───────────────────────────────────────────────────────
# Structure: problem -> solution -> proof

BODY_PROBLEM_TEMPLATES: list[str] = [
    "\u300c{benefit}\u304c\u3067\u304d\u306a\u3044\u300d\u300c\u7d9a\u304b\u306a\u3044\u300d\u300c\u52b9\u679c\u304c\u611f\u3058\u3089\u308c\u306a\u3044\u300d\u2026\u305d\u3093\u306a\u60a9\u307f\u3092\u62b1\u3048\u3066\u3044\u307e\u305b\u3093\u304b\uff1f",
    "\u591a\u304f\u306e\u65b9\u304c{benefit}\u306b\u304a\u3044\u3066\u3001\u540c\u3058\u58c1\u306b\u3076\u3064\u304b\u3063\u3066\u3044\u307e\u3059\u3002",
]

BODY_SOLUTION_TEMPLATES: list[str] = [
    "{product}\u306f\u3001\u305d\u306e\u60a9\u307f\u3092\u6839\u672c\u304b\u3089\u89e3\u6c7a\u3002\u72ec\u81ea\u306e\u30a2\u30d7\u30ed\u30fc\u30c1\u3067{benefit}\u3092\u30b5\u30dd\u30fc\u30c8\u3057\u307e\u3059\u3002",
    "{product}\u306a\u3089\u3001\u7c21\u5358\u30b9\u30c6\u30c3\u30d7\u3067{benefit}\u3092\u5b9f\u73fe\u3002\u5fd9\u3057\u3044\u3042\u306a\u305f\u3067\u3082\u5b89\u5fc3\u3067\u3059\u3002",
]

BODY_PROOF_TEMPLATES: list[str] = [
    "\u5229\u7528\u8005\u6e80\u8db3\u5ea693%\u203b\u3001\u7d2f\u8a08\u8ca9\u58f2\u6570\u304c50\u4e07\u500b\u3092\u7a81\u7834\u3002\u305d\u306e\u5b9f\u529b\u306f\u6570\u5b57\u304c\u8a3c\u660e\u3057\u3066\u3044\u307e\u3059\u3002",
    "\u5c02\u9580\u5bb6\u3082\u63a8\u85a6\u3002\u591a\u304f\u306e\u30e1\u30c7\u30a3\u30a2\u3067\u53d6\u308a\u4e0a\u3052\u3089\u308c\u305f{product}\u306e{benefit}\u52b9\u679c\u3002",
]

# ── CTA Templates ────────────────────────────────────────────────────────

CTA_TEMPLATES: dict[str, list[str]] = {
    "learn_more": [
        "\u8a73\u3057\u304f\u306f\u3053\u3061\u3089 \u25b6 {product}\u516c\u5f0f\u30b5\u30a4\u30c8",
        "\u4eca\u3059\u3050{product}\u3092\u30c1\u30a7\u30c3\u30af \u203a",
        "{product}\u306e\u8a73\u7d30\u3092\u898b\u308b",
    ],
    "line_add": [
        "\u4eca\u3059\u3050LINE\u8ffd\u52a0\u3067{product}\u306e\u7279\u5178\u3092GET",
        "LINE\u53cb\u3060\u3061\u8ffd\u52a0\u3067\u7121\u6599\u76f8\u8ac7\u53d7\u4ed8\u4e2d",
        "\u516c\u5f0fLINE\u3067{product}\u306e\u6700\u65b0\u60c5\u5831\u3092\u53d7\u3051\u53d6\u308b",
    ],
    "purchase": [
        "\u4eca\u3059\u3050{product}\u3092\u8a66\u3059 \u25b6",
        "\u7279\u5225\u4fa1\u683c\u3067{product}\u3092\u624b\u306b\u5165\u308c\u308b",
        "{product}\u3092\u30ab\u30fc\u30c8\u306b\u8ffd\u52a0",
    ],
    "consultation": [
        "\u7121\u6599\u30ab\u30a6\u30f3\u30bb\u30ea\u30f3\u30b0\u3092\u4e88\u7d04\u3059\u308b",
        "{product}\u306e\u7121\u6599\u76f8\u8ac7\u306f\u3053\u3061\u3089",
        "\u307e\u305a\u306f\u7121\u6599\u3067\u304a\u8a66\u3057\u304f\u3060\u3055\u3044",
    ],
    "signup": [
        "\u7121\u6599\u3067{product}\u3092\u59cb\u3081\u308b",
        "\u4eca\u3059\u3050\u7121\u6599\u767b\u9332 \u25b6",
        "{product}\u306b\u7121\u6599\u4f1a\u54e1\u767b\u9332",
    ],
    "free_trial": [
        "\u307e\u305a\u306f\u7121\u6599\u3067\u304a\u8a66\u3057 \u25b6",
        "0\u5186\u3067{product}\u3092\u4f53\u9a13\u3059\u308b",
        "\u7121\u6599\u30c8\u30e9\u30a4\u30a2\u30eb\u306f\u3053\u3061\u3089\u304b\u3089",
    ],
    "download": [
        "\u4eca\u3059\u3050\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9 \u25b6",
        "{product}\u30a2\u30d7\u30ea\u3092\u7121\u6599\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb",
        "\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u3057\u3066{benefit}\u3092\u4f53\u9a13",
    ],
}

# ── Power Words by Genre ─────────────────────────────────────────────────

GENRE_POWER_WORDS: dict[str, list[str]] = {
    "beauty": [
        "\u900f\u660e\u611f", "\u30cf\u30ea", "\u30c4\u30e4", "\u6f64\u3044",
        "\u5b9f\u611f", "\u7f8e\u808c", "\u30a8\u30a4\u30b8\u30f3\u30b0\u30b1\u30a2",
        "\u81ea\u7136\u7531\u6765", "\u533b\u5e2b\u76e3\u4fee",
    ],
    "health": [
        "\u4ee3\u8b1d", "\u514d\u75ab\u529b", "\u5feb\u7720",
        "\u30b9\u30c3\u30ad\u30ea", "\u5143\u6c17", "\u7d9a\u3051\u3089\u308c\u308b",
        "\u5b9f\u8a3c\u6e08\u307f", "\u5c02\u9580\u5bb6\u63a8\u85a6",
    ],
    "ec_d2c": [
        "\u9001\u6599\u7121\u6599", "\u521d\u56de\u9650\u5b9a", "\u5b9a\u671f\u4fbf",
        "\u5168\u984d\u8fd4\u91d1", "\u6e80\u8db3\u5ea6No.1",
        "\u30ea\u30d4\u30fc\u30c8\u738790%",
    ],
    "finance": [
        "\u7121\u6599", "\u7c21\u5358", "\u6700\u77ed", "\u5b89\u5fc3",
        "\u5b9f\u7e3e", "\u30d7\u30ed", "\u7a0e\u5bfe\u7b56",
    ],
    "education": [
        "\u5b9f\u8df5", "\u5373\u6226\u529b", "\u672a\u7d4c\u9a13OK",
        "\u30de\u30f3\u30c4\u30fc\u30de\u30f3", "\u5408\u683c\u7387",
        "\u5b9f\u7e3e\u591a\u6570",
    ],
    "food": [
        "\u7523\u5730\u76f4\u9001", "\u7121\u6dfb\u52a0", "\u56fd\u7523",
        "\u624b\u4f5c\u308a", "\u00b7\u65b0\u9bae", "\u9650\u5b9a",
    ],
    "app": [
        "\u7121\u6599", "\u7c21\u5358", "\u6700\u77ed", "AI",
        "\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9", "\u30a2\u30d7\u30ea",
    ],
    "gaming": [
        "\u7121\u6599", "\u9650\u5b9a", "\u30b3\u30e9\u30dc",
        "\u65b0\u30a4\u30d9\u30f3\u30c8", "\u30ac\u30c1\u30e3", "\u5f53\u305f\u308a",
    ],
    "technology": [
        "\u6700\u65b0", "AI", "\u9769\u547d\u7684", "\u6642\u77ed",
        "\u81ea\u52d5\u5316", "\u52b9\u7387",
    ],
    "real_estate": [
        "\u99c5\u8fd1", "\u65b0\u7bc9", "\u9650\u5b9a", "\u8cc7\u7523",
        "\u5229\u56de\u308a", "\u7a0e\u5bfe\u7b56",
    ],
    "travel": [
        "\u9650\u5b9a", "\u7279\u5225\u4fa1\u683c", "\u7d76\u666f",
        "\u8d05\u6ca2", "\u5168\u8fbc\u307f", "\u65e9\u5272",
    ],
    "other": [
        "\u7121\u6599", "\u9650\u5b9a", "\u5b9f\u611f", "\u5b89\u5fc3",
        "\u5b9f\u7e3e", "\u7c21\u5358",
    ],
}

# ── Default genre fallback for power words ────────────────────────────────
DEFAULT_POWER_WORDS: list[str] = GENRE_POWER_WORDS["other"]


# ── Helpers ──────────────────────────────────────────────────────────────


def _load_scenario_database() -> dict | None:
    """Load scenario_database.json from exports directory."""
    if not os.path.exists(SCENARIO_DB_PATH):
        return None
    try:
        with open(SCENARIO_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _find_genre_entry(db: dict, genre: str) -> dict | None:
    """Find matching genre entry in scenario database."""
    genres = db.get("genres", [])
    for g in genres:
        if g.get("genre_en") == genre or g.get("genre") == genre:
            return g
    return None


def _get_top_archetype(genre_entry: dict) -> dict | None:
    """Get the top-ranked scenario archetype for a genre (by avg_score)."""
    templates = genre_entry.get("templates", [])
    if not templates:
        return None
    # Sort by avg_score descending, take the best one
    return max(templates, key=lambda t: t.get("avg_score", 0))


def _pick_hook_type(archetype: dict) -> str:
    """Determine hook type from archetype metadata."""
    archetype_key = archetype.get("archetype_en", "problem_solution")
    mapping = {
        "problem_solution": "pain_point",
        "before_after_transformation": "shock",
        "testimonial_story": "social_proof",
        "authority_expert": "statistic",
        "urgency_limited": "urgency",
        "comparison": "question",
        "tutorial_howto": "benefit",
        "lifestyle": "benefit",
    }
    return mapping.get(archetype_key, "benefit")


def _fill_template(template: str, product: str, benefit: str, cta: str) -> str:
    """Fill a template string with product/benefit/cta values."""
    return (
        template
        .replace("{product}", product)
        .replace("{benefit}", benefit)
        .replace("{cta}", cta)
    )


def _generate_titles(
    hook_texts: list[str],
    product: str,
    benefit: str,
) -> list[str]:
    """Generate 3 title variations by combining hooks + product + benefit."""
    titles = []
    for i, tmpl in enumerate(TITLE_TEMPLATES[:3]):
        hook = hook_texts[i % len(hook_texts)] if hook_texts else product
        filled = (
            tmpl
            .replace("{hook}", hook)
            .replace("{product}", product)
            .replace("{benefit}", benefit)
        )
        titles.append(filled)
    return titles[:3]


def _generate_hooks(
    hook_type: str,
    product: str,
    benefit: str,
) -> list[str]:
    """Generate 3 hook text variations from templates."""
    templates = HOOK_TEMPLATES.get(hook_type, HOOK_TEMPLATES["benefit"])
    hooks = []
    for tmpl in templates[:3]:
        filled = _fill_template(tmpl, product, benefit, "")
        hooks.append(filled)
    return hooks[:3]


def _generate_body(product: str, benefit: str) -> str:
    """Generate body text: problem + solution + proof."""
    problem = _fill_template(BODY_PROBLEM_TEMPLATES[0], product, benefit, "")
    solution = _fill_template(BODY_SOLUTION_TEMPLATES[0], product, benefit, "")
    proof = _fill_template(BODY_PROOF_TEMPLATES[0], product, benefit, "")
    return f"{problem}\n\n{solution}\n\n{proof}"


def _generate_ctas(cta_type: str, product: str, benefit: str) -> list[str]:
    """Generate 3 CTA variations."""
    templates = CTA_TEMPLATES.get(cta_type, CTA_TEMPLATES["learn_more"])
    ctas = []
    for tmpl in templates[:3]:
        filled = _fill_template(tmpl, product, benefit, "")
        ctas.append(filled)
    return ctas[:3]


def _get_power_words(genre: str) -> list[str]:
    """Get recommended power words for genre."""
    return GENRE_POWER_WORDS.get(genre, DEFAULT_POWER_WORDS)


def _estimate_score(archetype: dict) -> float:
    """Estimate performance score: archetype avg_score * 0.8 (conservative)."""
    avg = archetype.get("avg_score", 50.0)
    try:
        return round(float(avg) * 0.8, 1)
    except (ValueError, TypeError):
        return 40.0


def _get_duration_recommendation(genre_entry: dict) -> int:
    """Get recommended duration from genre data, default 30s."""
    # Check if genre entry has duration data
    dur = genre_entry.get("recommended_duration")
    if dur and isinstance(dur, (int, float)) and dur > 0:
        return int(dur)
    # Check templates for avg duration
    templates = genre_entry.get("templates", [])
    if templates:
        durations = [
            t.get("avg_duration", 0)
            for t in templates
            if t.get("avg_duration", 0) > 0
        ]
        if durations:
            return int(sum(durations) / len(durations))
    return 30


def _get_reference_ad_ids(archetype: dict) -> list[int]:
    """Get reference hit ad IDs from the archetype data."""
    ids = archetype.get("example_ad_ids", [])
    if isinstance(ids, list):
        return [int(i) for i in ids[:10] if isinstance(i, (int, float, str))]
    return []


# ── Main ─────────────────────────────────────────────────────────────────


def generate_scenario(
    genre: str,
    product: str,
    benefit: str,
    cta_type: str,
) -> dict:
    """Generate a complete scenario from templates for the given parameters.

    Returns a dict matching the output JSON schema.
    """
    # Load scenario database
    db = _load_scenario_database()

    genre_entry = None
    archetype_data = None

    if db:
        genre_entry = _find_genre_entry(db, genre)
        if genre_entry:
            archetype_data = _get_top_archetype(genre_entry)

    # Fallback defaults if no database or genre match
    if genre_entry is None:
        genre_entry = {
            "genre_en": genre,
            "genre": genre,
            "templates": [],
        }

    if archetype_data is None:
        archetype_data = {
            "archetype_en": "problem_solution",
            "archetype_name": "problem_solution",
            "avg_score": 50.0,
            "example_ad_ids": [],
        }

    archetype_key = archetype_data.get(
        "archetype_en",
        archetype_data.get("archetype_name", "problem_solution"),
    )

    # Determine hook type from archetype
    hook_type = _pick_hook_type(archetype_data)

    # Generate variations
    hooks = _generate_hooks(hook_type, product, benefit)
    titles = _generate_titles(hooks, product, benefit)
    body = _generate_body(product, benefit)
    ctas = _generate_ctas(cta_type, product, benefit)
    power_words = _get_power_words(genre)
    estimated_score = _estimate_score(archetype_data)
    duration = _get_duration_recommendation(genre_entry)
    reference_ids = _get_reference_ad_ids(archetype_data)

    scenario = {
        "archetype": archetype_key,
        "titles": titles,
        "hooks": hooks,
        "body": body,
        "ctas": ctas,
        "power_words": power_words,
        "estimated_score": estimated_score,
        "duration_recommendation": duration,
        "reference_ad_ids": reference_ids,
    }

    result = {
        "genre": genre,
        "product": product,
        "benefit": benefit,
        "cta_type": cta_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_scenarios": [scenario],
    }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate ad scenario text from templates (VAAP)",
    )
    parser.add_argument(
        "--genre",
        required=True,
        help="Genre key (e.g. beauty, health, ec_d2c, finance)",
    )
    parser.add_argument(
        "--product",
        required=True,
        help="Product or brand name",
    )
    parser.add_argument(
        "--benefit",
        default="",
        help="Key benefit phrase (optional)",
    )
    parser.add_argument(
        "--cta",
        default="learn_more",
        choices=list(CTA_TEMPLATES.keys()),
        help="CTA type (default: learn_more)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path (optional)",
    )

    args = parser.parse_args()

    # Default benefit if not provided
    benefit = args.benefit if args.benefit else args.product

    print("=" * 60)
    print("VAAP Scenario Text Generator (Template-Based)")
    print("=" * 60)
    print(f"  Genre   : {args.genre}")
    print(f"  Product : {args.product}")
    print(f"  Benefit : {benefit}")
    print(f"  CTA type: {args.cta}")
    print("")

    # Check scenario database
    if os.path.exists(SCENARIO_DB_PATH):
        print(f"Scenario database: FOUND ({SCENARIO_DB_PATH})")
    else:
        print(f"Scenario database: NOT FOUND (using fallback defaults)")
        print(f"  Expected at: {SCENARIO_DB_PATH}")
    print("")

    # Generate scenario
    result = generate_scenario(
        genre=args.genre,
        product=args.product,
        benefit=benefit,
        cta_type=args.cta,
    )

    # Print summary
    for scenario in result["generated_scenarios"]:
        print(f"--- Archetype: {scenario['archetype']} ---")
        print("")
        print(f"  Titles ({len(scenario['titles'])}):")
        for i, t in enumerate(scenario["titles"], 1):
            print(f"    {i}. {t}")
        print("")
        print(f"  Hooks ({len(scenario['hooks'])}):")
        for i, h in enumerate(scenario["hooks"], 1):
            print(f"    {i}. {h}")
        print("")
        print("  Body (preview):")
        body_preview = scenario["body"][:200]
        for line in body_preview.split("\n"):
            print(f"    {line}")
        if len(scenario["body"]) > 200:
            print("    ...")
        print("")
        print(f"  CTAs ({len(scenario['ctas'])}):")
        for i, c in enumerate(scenario["ctas"], 1):
            print(f"    {i}. {c}")
        print("")
        print(f"  Power words: {', '.join(scenario['power_words'][:6])}...")
        print(f"  Estimated score: {scenario['estimated_score']}")
        print(f"  Duration recommendation: {scenario['duration_recommendation']}s")
        print(f"  Reference ad IDs: {scenario['reference_ad_ids']}")
    print("")

    # Output to file if requested
    if args.output:
        output_path = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Output written to: {output_path}")
    else:
        print("(No --output specified, JSON not written to file)")

    print("")
    print("Done.")


if __name__ == "__main__":
    main()
