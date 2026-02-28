#!/usr/bin/env python3
"""Extract scenario templates from hit ads.

Analyzes existing hit ads (score >= 60) to extract scenario structures.
Decomposes each ad into Hook / Problem / Solution / Proof / CTA components.
Groups into "scenario archetypes" and ranks by average hit_score.

Stores results in ad_metadata["scenario_structure"].

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/extract_scenario_templates.py
"""

import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _safe_mean(vals: list[float]) -> float:
    return round(mean(vals), 1) if vals else 0.0


def _hit_rate(hits: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(hits / total * 100, 1)


def _get_text(ad: Ad) -> str:
    """Combine all text fields."""
    parts = []
    if ad.title:
        parts.append(ad.title)
    if ad.description:
        parts.append(ad.description)
    meta = ad.ad_metadata or {}
    for key in ("body", "link_description", "cta_text"):
        val = meta.get(key)
        if val and isinstance(val, str):
            parts.append(val)
    return "\n".join(parts)


# ── Hook Type Classification ────────────────────────────────────────────

HOOK_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("question", ["?", "\uff1f", "\u3067\u3059\u304b", "\u307e\u305b\u3093\u304b",
                   "\u3054\u5b58\u77e5", "\u77e5\u3063\u3066"]),
    ("shock", ["\u885d\u6483", "\u307e\u3055\u304b", "\u9a5a", "\u3084\u3070\u3044",
               "\u5371\u967a", "\u6ce8\u610f", "\u8b66\u544a", "\u5927\u5909",
               "\u5b9f\u306f", "\u79d8\u5bc6", "\u88cf\u30ef\u30b6"]),
    ("benefit", ["\u7c21\u5358", "\u305f\u3063\u305f", "\u3060\u3051\u3067",
                 "\u5b9f\u611f", "\u624b\u8efd", "\u304a\u5f97", "\u5b89\u5fc3",
                 "\u5feb\u9069", "\u30b9\u30c3\u30ad\u30ea", "\u6539\u5584",
                 "\u52b9\u679c"]),
    ("social_proof", ["\u4e07\u4eba", "\u8a71\u984c", "\u4eba\u6c17", "\u30e9\u30f3\u30ad\u30f3\u30b0",
                       "No.1", "\u7b2c1\u4f4d", "\u58f2\u4e0a", "\u5b9f\u7e3e",
                       "\u53e3\u30b3\u30df", "\u6e80\u8db3\u5ea6"]),
    ("urgency", ["\u4eca\u3060\u3051", "\u9650\u5b9a", "\u6b8b\u308a",
                 "\u671f\u9593\u9650\u5b9a", "\u672c\u65e5\u9650\u308a",
                 "\u30e9\u30b9\u30c8", "\u7de0\u5207"]),
    ("statistic", ["%", "\u5186", "\u4e07", "\u500d"]),
    ("pain_point", ["\u60a9\u307f", "\u3064\u3089\u3044", "\u4e0d\u5b89",
                     "\u30b9\u30c8\u30ec\u30b9", "\u8001\u5316", "\u305f\u308b\u307f",
                     "\u30b7\u30df", "\u30b7\u30ef", "\u8584\u6bdb", "\u592a"]),
]


def _classify_hook_type(text: str) -> str:
    """Classify hook type from the opening portion of text."""
    if not text:
        return "none"
    # Use first 150 chars
    opening = text[:150].lower()
    for hook_name, keywords in HOOK_TYPE_RULES:
        for kw in keywords:
            if kw.lower() in opening:
                return hook_name
    return "plain"


# ── Problem Classification ──────────────────────────────────────────────

PROBLEM_KEYWORDS: dict[str, list[str]] = {
    "appearance": ["\u808c\u8352\u308c", "\u30b7\u30df", "\u30b7\u30ef", "\u305f\u308b\u307f",
                   "\u6bdb\u7a74", "\u30cb\u30ad\u30d3", "\u80b2\u6bdb", "\u8584\u6bdb",
                   "\u592a", "\u808c", "\u8131\u6bdb", "\u30e0\u30c0\u6bdb",
                   "\u30b3\u30f3\u30d7\u30ec\u30c3\u30af\u30b9"],
    "health": ["\u75b2\u308c", "\u30b9\u30c8\u30ec\u30b9", "\u7761\u7720",
               "\u75db\u307f", "\u4e0d\u5b89", "\u8001\u5316", "\u4f53\u91cd",
               "\u80a5\u6e80", "\u4ee3\u8b1d", "\u514d\u75ab"],
    "lifestyle": ["\u6642\u9593\u304c\u306a\u3044", "\u5fd9\u3057\u3044",
                  "\u9762\u5012", "\u7d9a\u304b\u306a\u3044",
                  "\u7c21\u5358\u3058\u3083\u306a\u3044", "\u96e3\u3057\u3044"],
    "cost": ["\u9ad8\u3044", "\u8cbb\u7528", "\u4fa1\u683c", "\u304a\u91d1",
             "\u7bc0\u7d04", "\u30b3\u30b9\u30d1"],
}


def _classify_problem(text: str) -> str:
    """Classify the main problem addressed in the ad."""
    if not text:
        return "none"
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for problem_type, keywords in PROBLEM_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            scores[problem_type] = count
    if not scores:
        return "general"
    return max(scores, key=lambda k: scores[k])


def _extract_problem_keywords(text: str) -> list[str]:
    """Extract which problem keywords were found."""
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for keywords in PROBLEM_KEYWORDS.values():
        for kw in keywords:
            if kw.lower() in text_lower and kw not in found:
                found.append(kw)
    return found[:5]


# ── Solution Approach Classification ────────────────────────────────────

SOLUTION_KEYWORDS: dict[str, list[str]] = {
    "product_demo": ["\u7d39\u4ecb", "\u7279\u5fb4", "\u6210\u5206",
                     "\u914d\u5408", "\u6280\u8853", "\u958b\u767a"],
    "testimonial": ["\u53e3\u30b3\u30df", "\u4f53\u9a13", "\u30ec\u30d3\u30e5\u30fc",
                    "\u611f\u60f3", "\u304a\u5ba2\u69d8\u306e\u58f0",
                    "\u4f7f\u3063\u3066\u307f", "\u5b9f\u969b\u306b"],
    "expert_authority": ["\u533b\u5e2b", "\u76e3\u4fee", "\u5c02\u9580\u5bb6",
                         "\u7814\u7a76", "\u8a8d\u5b9a", "\u7279\u8a31",
                         "\u30a8\u30d3\u30c7\u30f3\u30b9"],
    "comparison": ["\u6bd4\u8f03", "\u5dee", "\u9055\u3044", "vs", "VS",
                   "\u5f93\u6765", "\u4eca\u307e\u3067"],
    "process_steps": ["\u30b9\u30c6\u30c3\u30d7", "\u624b\u9806", "\u65b9\u6cd5",
                      "\u3084\u308a\u65b9", "\u4f7f\u3044\u65b9",
                      "\u3064\u306e\u30b9\u30c6\u30c3\u30d7"],
}


def _classify_solution(text: str) -> str:
    """Classify the solution approach used."""
    if not text:
        return "none"
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for approach, keywords in SOLUTION_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            scores[approach] = count
    if not scores:
        return "direct_pitch"
    return max(scores, key=lambda k: scores[k])


# ── Proof Type Classification ───────────────────────────────────────────

PROOF_KEYWORDS: dict[str, list[str]] = {
    "before_after": ["\u30d3\u30d5\u30a9\u30fc\u30a2\u30d5\u30bf\u30fc", "before", "after",
                     "\u4f7f\u7528\u524d", "\u4f7f\u7528\u5f8c", "\u5909\u5316",
                     "\u2192", "\u21d2", "\u304b\u3089"],
    "data_stats": ["%", "\u4e07\u4eba", "\u4ef6", "\u500d", "\u6e80\u8db3\u5ea6",
                   "\u7d71\u8a08", "\u30c7\u30fc\u30bf", "\u7d50\u679c",
                   "\u81e8\u5e8a"],
    "testimonial": ["\u53e3\u30b3\u30df", "\u4f53\u9a13\u8ac7", "\u30ec\u30d3\u30e5\u30fc",
                    "\u611f\u60f3", "\u304a\u5ba2\u69d8\u306e\u58f0",
                    "\u500b\u4eba\u306e\u611f\u60f3"],
    "authority": ["\u533b\u5e2b", "\u76e3\u4fee", "\u5c02\u9580\u5bb6",
                  "\u8a8d\u5b9a", "\u7279\u8a31", "\u53d7\u8cde", "\u5927\u5b66"],
    "social_proof": ["\u4eba\u6c17", "\u30e9\u30f3\u30ad\u30f3\u30b0", "No.1",
                     "\u7b2c1\u4f4d", "\u58f2\u4e0a", "\u7d2f\u8a08",
                     "\u7a81\u7834", "\u30d9\u30b9\u30c8\u30bb\u30e9\u30fc"],
}


def _classify_proof(text: str) -> str:
    """Classify the proof/credibility type used."""
    if not text:
        return "none"
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for proof_type, keywords in PROOF_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > 0:
            scores[proof_type] = count
    if not scores:
        return "none"
    return max(scores, key=lambda k: scores[k])


# ── CTA Type Classification ────────────────────────────────────────────

CTA_TYPE_RULES: list[tuple[str, list[str]]] = [
    ("line_add", ["LINE", "\u30e9\u30a4\u30f3", "\u53cb\u3060\u3061\u8ffd\u52a0",
                  "\u53cb\u9054\u8ffd\u52a0"]),
    ("free_consultation", ["\u7121\u6599\u76f8\u8ac7", "\u7121\u6599\u30ab\u30a6\u30f3\u30bb\u30ea\u30f3\u30b0",
                           "\u7121\u6599\u4f53\u9a13", "\u7121\u6599\u8a3a\u65ad"]),
    ("purchase", ["\u8cfc\u5165", "\u6ce8\u6587", "\u8cb7", "\u30ab\u30fc\u30c8\u306b"]),
    ("signup", ["\u767b\u9332", "\u7533\u8fbc", "\u7533\u3057\u8fbc",
                "\u4f1a\u54e1", "\u5165\u4f1a"]),
    ("free_trial", ["\u7121\u6599", "0\u5186", "\u30bf\u30c0", "\u304a\u8a66\u3057",
                    "\u30c8\u30e9\u30a4\u30a2\u30eb"]),
    ("download", ["\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9", "\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb"]),
    ("learn_more", ["\u8a73\u3057\u304f", "\u8a73\u7d30", "\u30c1\u30a7\u30c3\u30af",
                    "\u3053\u3061\u3089", "\u516c\u5f0f"]),
]


def _classify_cta(text: str) -> str:
    """Classify CTA type."""
    if not text:
        return "none"
    text_lower = text.lower()
    for cta_name, keywords in CTA_TYPE_RULES:
        for kw in keywords:
            if kw.lower() in text_lower:
                return cta_name
    return "none"


# ── Archetype Determination ─────────────────────────────────────────────

def _determine_archetype(hook_type: str, solution: str, proof: str) -> str:
    """Determine the scenario archetype from component analysis."""
    # Before/after transformation
    if proof == "before_after" or solution == "comparison":
        return "before_after_transformation"

    # Problem -> Solution
    if hook_type in ("pain_point", "question") and solution in ("product_demo", "process_steps"):
        return "problem_solution"

    # Social proof / authority driven
    if hook_type == "social_proof" or proof in ("social_proof", "authority"):
        return "authority_proof"

    # Testimonial-driven
    if solution == "testimonial" or proof == "testimonial":
        return "testimonial_story"

    # Urgency / limited offer
    if hook_type == "urgency":
        return "urgency_offer"

    # Shock / curiosity hook
    if hook_type in ("shock", "curiosity"):
        return "curiosity_reveal"

    # Benefit-led
    if hook_type == "benefit":
        return "benefit_first"

    # Statistics-led
    if hook_type == "statistic" or proof == "data_stats":
        return "data_driven"

    return "standard"


# Archetype display names (English only for print safety)
ARCHETYPE_NAMES: dict[str, str] = {
    "before_after_transformation": "Before/After Transformation",
    "problem_solution": "Problem -> Solution",
    "authority_proof": "Authority/Social Proof",
    "testimonial_story": "Testimonial Story",
    "urgency_offer": "Urgency Offer",
    "curiosity_reveal": "Curiosity Reveal",
    "benefit_first": "Benefit First",
    "data_driven": "Data Driven",
    "standard": "Standard",
}


# ── Hook Text Extraction ────────────────────────────────────────────────

def _extract_hook_text(ad: Ad) -> str:
    """Extract the opening hook text from the ad (first line/sentence)."""
    text = ad.title or ""
    if not text:
        desc = ad.description or ""
        text = desc.split("\n")[0][:100] if desc else ""
    return text.strip()[:100]


# ── Duration Estimation ─────────────────────────────────────────────────

def _estimate_duration(ad: Ad) -> int:
    """Estimate scenario duration in seconds."""
    if ad.duration_seconds and ad.duration_seconds > 0:
        return int(ad.duration_seconds)
    # Default estimates based on creative type
    if ad.creative_type == "video":
        return 30
    return 15


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Scenario Template Extraction Script")
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

        # Filter hit ads (score >= 60)
        hit_ads = [a for a in ads if _get_score(a) >= 60]
        print(f"Hit ads (score >= 60): {len(hit_ads)}")

        if not hit_ads:
            print("No hit ads found (score >= 60). Processing all ads with score > 0 instead.")
            hit_ads = [a for a in ads if _get_score(a) > 0]
            if not hit_ads:
                print("No scored ads found. Exiting.")
                return
            print(f"Using {len(hit_ads)} scored ads instead.")

        # ── Step 1: Analyze each hit ad into scenario components ──────
        print("\nStep 1: Decomposing hit ads into scenario components...")

        scenario_data: list[dict] = []
        archetype_counter: Counter = Counter()

        for ad in hit_ads:
            text = _get_text(ad)
            score = _get_score(ad)

            hook_type = _classify_hook_type(text)
            problem = _classify_problem(text)
            problem_kws = _extract_problem_keywords(text)
            solution = _classify_solution(text)
            proof = _classify_proof(text)
            cta_type = _classify_cta(text)
            archetype = _determine_archetype(hook_type, solution, proof)
            hook_text = _extract_hook_text(ad)
            duration = _estimate_duration(ad)

            scenario_struct = {
                "archetype": archetype,
                "hook_type": hook_type,
                "hook_text_example": hook_text,
                "problem_type": problem,
                "problem_keywords": problem_kws,
                "solution_approach": solution,
                "proof_type": proof,
                "cta_type": cta_type,
                "estimated_duration_seconds": duration,
                "scenario_score": round(score, 1),
            }

            scenario_data.append({
                "ad_id": ad.id,
                "score": score,
                "archetype": archetype,
                "structure": scenario_struct,
            })

            archetype_counter[archetype] += 1

        print(f"  Analyzed {len(scenario_data)} hit ads.")
        print(f"  Archetypes found: {len(archetype_counter)}")

        # ── Step 2: Update ad_metadata with scenario_structure ────────
        print("\nStep 2: Updating ad_metadata with scenario_structure...")

        updated = 0
        for ad in ads:
            text = _get_text(ad)
            score = _get_score(ad)

            hook_type = _classify_hook_type(text)
            problem = _classify_problem(text)
            problem_kws = _extract_problem_keywords(text)
            solution = _classify_solution(text)
            proof = _classify_proof(text)
            cta_type = _classify_cta(text)
            archetype = _determine_archetype(hook_type, solution, proof)
            hook_text = _extract_hook_text(ad)
            duration = _estimate_duration(ad)

            scenario_struct = {
                "archetype": archetype,
                "hook_type": hook_type,
                "hook_text_example": hook_text,
                "problem_type": problem,
                "problem_keywords": problem_kws,
                "solution_approach": solution,
                "proof_type": proof,
                "cta_type": cta_type,
                "estimated_duration_seconds": duration,
                "scenario_score": round(score, 1),
            }

            meta = dict(ad.ad_metadata or {})
            meta["scenario_structure"] = scenario_struct
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

        session.commit()
        print(f"  Updated scenario_structure for {updated}/{total} ads.")

        # ── Step 3: Archetype ranking by avg score ────────────────────
        print("\nStep 3: Ranking archetypes by average score...")

        archetype_groups: dict[str, list[dict]] = defaultdict(list)
        for sd in scenario_data:
            archetype_groups[sd["archetype"]].append(sd)

        archetype_rankings = []
        for archetype, group in archetype_groups.items():
            scores = [g["score"] for g in group]
            hit_count = sum(1 for g in group if g["score"] >= 60)
            archetype_rankings.append({
                "archetype": archetype,
                "display_name": ARCHETYPE_NAMES.get(archetype, archetype),
                "count": len(group),
                "avg_score": _safe_mean(scores),
                "max_score": round(max(scores), 1),
                "hit_rate": _hit_rate(hit_count, len(group)),
            })

        archetype_rankings.sort(key=lambda x: x["avg_score"], reverse=True)

        # ── Print Results ─────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print("SCENARIO ARCHETYPE RANKINGS")
        print(f"{'=' * 60}")
        print(f"  {'#':>2s} {'Archetype':<30s} {'Count':>5s} {'AvgScore':>9s} {'MaxScore':>9s} {'HitRate':>8s}")
        print(f"  {'-' * 67}")

        for i, ar in enumerate(archetype_rankings, 1):
            print(
                f"  {i:>2d} {ar['display_name']:<30s} {ar['count']:>5d} "
                f"{ar['avg_score']:>8.1f} {ar['max_score']:>8.1f} "
                f"{ar['hit_rate']:>7.1f}%"
            )

        # ── Component Distribution (hit ads only) ────────────────────
        print(f"\n--- Hook Type Distribution (hit ads) ---")
        hook_dist: Counter = Counter()
        for sd in scenario_data:
            hook_dist[sd["structure"]["hook_type"]] += 1
        for hook, count in hook_dist.most_common():
            pct = count / len(scenario_data) * 100
            print(f"  {hook:<20s} {count:>4d} ({pct:>5.1f}%)")

        print(f"\n--- Solution Approach Distribution (hit ads) ---")
        sol_dist: Counter = Counter()
        for sd in scenario_data:
            sol_dist[sd["structure"]["solution_approach"]] += 1
        for sol, count in sol_dist.most_common():
            pct = count / len(scenario_data) * 100
            print(f"  {sol:<20s} {count:>4d} ({pct:>5.1f}%)")

        print(f"\n--- Proof Type Distribution (hit ads) ---")
        proof_dist: Counter = Counter()
        for sd in scenario_data:
            proof_dist[sd["structure"]["proof_type"]] += 1
        for proof, count in proof_dist.most_common():
            pct = count / len(scenario_data) * 100
            print(f"  {proof:<20s} {count:>4d} ({pct:>5.1f}%)")

        print(f"\n--- CTA Type Distribution (hit ads) ---")
        cta_dist: Counter = Counter()
        for sd in scenario_data:
            cta_dist[sd["structure"]["cta_type"]] += 1
        for cta, count in cta_dist.most_common():
            pct = count / len(scenario_data) * 100
            print(f"  {cta:<20s} {count:>4d} ({pct:>5.1f}%)")

        print(f"\nDone! Scenario templates extracted for {updated} ads.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
