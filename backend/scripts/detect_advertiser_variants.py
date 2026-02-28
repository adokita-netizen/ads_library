#!/usr/bin/env python3
"""Detect A/B test variant pairs within the same advertiser.

Groups ads by advertiser_name, compares titles within each group using
character trigram Jaccard similarity, and identifies likely A/B test pairs:
ads with similar titles (Jaccard > 0.5) but different hook_type or cta_type.

Exports to backend/exports/ab_test_pairs.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/detect_advertiser_variants.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)

SIMILARITY_THRESHOLD = 0.5


# -- Trigram Jaccard similarity ----------------------------------------

def _char_trigrams(text: str) -> set[str]:
    """Extract character-level trigrams from text.

    Lowercases and strips whitespace before extraction.
    Returns an empty set for strings shorter than 3 characters.
    """
    t = text.lower().strip()
    if len(t) < 3:
        return set()
    return {t[i:i + 3] for i in range(len(t) - 2)}


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets.

    Returns 0.0 if both sets are empty.
    """
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


# -- Metadata helpers --------------------------------------------------

def _get_creative_analysis(ad: Ad) -> dict:
    """Get creative_analysis dict from ad_metadata."""
    return (ad.ad_metadata or {}).get("creative_analysis", {})


def _get_hook_type(ad: Ad) -> str:
    """Get hook_type from creative_analysis, default 'none'."""
    return _get_creative_analysis(ad).get("hook_type", "none") or "none"


def _get_cta_type(ad: Ad) -> str:
    """Get cta_type from creative_analysis, default 'none'."""
    return _get_creative_analysis(ad).get("cta_type", "none") or "none"


def _get_score(ad: Ad) -> float:
    """Get latest_hit_score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


# -- Core detection logic ----------------------------------------------

def _find_ab_pairs(ads: list[Ad]) -> list[dict]:
    """Find A/B test pairs within a list of ads from the same advertiser.

    Compares every pair; returns list of pair dicts for those with
    title similarity > SIMILARITY_THRESHOLD and differing hook or cta.
    """
    pairs = []

    # Pre-compute trigrams for each ad
    trigram_cache: dict[int, set[str]] = {}
    for ad in ads:
        trigram_cache[ad.id] = _char_trigrams(ad.title or "")

    for ad_a, ad_b in combinations(ads, 2):
        # Skip if either has no title
        if not ad_a.title or not ad_b.title:
            continue

        # Compute similarity
        sim = _jaccard_similarity(trigram_cache[ad_a.id], trigram_cache[ad_b.id])
        if sim < SIMILARITY_THRESHOLD:
            continue

        # Check for differences in hook_type or cta_type
        hook_a = _get_hook_type(ad_a)
        hook_b = _get_hook_type(ad_b)
        cta_a = _get_cta_type(ad_a)
        cta_b = _get_cta_type(ad_b)

        differs_in = []
        if hook_a != hook_b:
            differs_in.append("hook_type")
        if cta_a != cta_b:
            differs_in.append("cta_type")

        # Must differ in at least one dimension to be an A/B test
        if not differs_in:
            continue

        # Determine winner by score
        score_a = _get_score(ad_a)
        score_b = _get_score(ad_b)
        if score_a >= score_b:
            winner = {"id": ad_a.id, "score": score_a}
        else:
            winner = {"id": ad_b.id, "score": score_b}

        pairs.append({
            "advertiser": ad_a.advertiser_name,
            "ad_a": {
                "id": ad_a.id,
                "title": ad_a.title,
                "hook_type": hook_a,
                "cta_type": cta_a,
            },
            "ad_b": {
                "id": ad_b.id,
                "title": ad_b.title,
                "hook_type": hook_b,
                "cta_type": cta_b,
            },
            "title_similarity": round(sim, 4),
            "differs_in": differs_in,
            "winner": winner,
        })

    return pairs


def main() -> None:
    print("=" * 60)
    print("A/B TEST VARIANT DETECTOR")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print(f"Similarity threshold: {SIMILARITY_THRESHOLD}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Total ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # -- Step 1: Group by advertiser_name --------------------------
        advertiser_groups: dict[str, list[Ad]] = defaultdict(list)
        skipped = 0
        for ad in ads:
            name = ad.advertiser_name
            if not name or name.strip() == "":
                skipped += 1
                continue
            advertiser_groups[name].append(ad)

        print(f"Unique advertisers: {len(advertiser_groups)}")
        print(f"Ads without advertiser_name: {skipped}")

        # Filter to advertisers with at least 2 ads (need pairs)
        eligible = {
            name: group
            for name, group in advertiser_groups.items()
            if len(group) >= 2
        }
        print(f"Advertisers with 2+ ads (eligible): {len(eligible)}")

        # -- Step 2: Find A/B test pairs -------------------------------
        print(f"\nScanning for A/B test pairs...")
        all_pairs: list[dict] = []
        advertisers_with_pairs = set()

        for advertiser, group_ads in eligible.items():
            pairs = _find_ab_pairs(group_ads)
            if pairs:
                advertisers_with_pairs.add(advertiser)
                all_pairs.extend(pairs)

        # Sort by title_similarity descending
        all_pairs.sort(key=lambda p: p["title_similarity"], reverse=True)

        # Assign pair_ids
        for i, pair in enumerate(all_pairs, 1):
            pair["pair_id"] = i

        print(f"Found {len(all_pairs)} likely A/B test pairs across {len(advertisers_with_pairs)} advertisers")

        # -- Step 3: Export to JSON ------------------------------------
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_pairs": len(all_pairs),
            "total_advertisers_with_pairs": len(advertisers_with_pairs),
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "pairs": all_pairs,
        }

        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "ab_test_pairs.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Exported to: {export_path}")

        # -- Step 4: Print summary -------------------------------------
        if not all_pairs:
            print("\nNo A/B test pairs detected.")
            print("Done!")
            return

        # Top pairs by similarity
        print(f"\n{'=' * 60}")
        print("TOP A/B TEST PAIRS (by title similarity)")
        print(f"{'=' * 60}")
        display_count = min(15, len(all_pairs))
        print(f"  {'#':>3s} {'Advertiser':<25s} {'Sim':>5s} {'Differs':>15s} {'Winner':>8s}")
        print(f"  {'-' * 62}")

        for pair in all_pairs[:display_count]:
            adv_safe = pair["advertiser"][:23].encode("ascii", "replace").decode("ascii")
            differs = ", ".join(pair["differs_in"])
            winner_id = pair["winner"]["id"]
            winner_score = pair["winner"]["score"]
            print(
                f"  {pair['pair_id']:>3d} {adv_safe:<25s} "
                f"{pair['title_similarity']:>5.2f} {differs:>15s} "
                f"id={winner_id} ({winner_score:.0f})"
            )

        # Detail of top 5 pairs
        print(f"\n{'=' * 60}")
        print("DETAILED VIEW - TOP 5 PAIRS")
        print(f"{'=' * 60}")

        for pair in all_pairs[:5]:
            adv_safe = pair["advertiser"].encode("ascii", "replace").decode("ascii")
            print(f"\n  Pair #{pair['pair_id']} | Advertiser: {adv_safe}")
            print(f"  Similarity: {pair['title_similarity']:.4f} | Differs in: {', '.join(pair['differs_in'])}")

            title_a = (pair["ad_a"]["title"] or "")[:60].encode("ascii", "replace").decode("ascii")
            title_b = (pair["ad_b"]["title"] or "")[:60].encode("ascii", "replace").decode("ascii")
            print(f"    Ad A (id={pair['ad_a']['id']}): {title_a}")
            print(f"      hook={pair['ad_a']['hook_type']}, cta={pair['ad_a']['cta_type']}")
            print(f"    Ad B (id={pair['ad_b']['id']}): {title_b}")
            print(f"      hook={pair['ad_b']['hook_type']}, cta={pair['ad_b']['cta_type']}")

            w = pair["winner"]
            print(f"    Winner: Ad id={w['id']} (score={w['score']:.1f})")

        # -- Step 5: Top performing variants analysis ------------------
        print(f"\n{'=' * 60}")
        print("TOP PERFORMING VARIANTS")
        print(f"{'=' * 60}")

        # Find pairs where the winner has the highest score
        pairs_with_scores = [
            p for p in all_pairs if p["winner"]["score"] > 0
        ]
        pairs_with_scores.sort(key=lambda p: p["winner"]["score"], reverse=True)

        if pairs_with_scores:
            print(f"\n  Highest-scoring winners from A/B pairs:")
            print(f"  {'#':>3s} {'Winner ID':>10s} {'Score':>7s} {'Advertiser':<25s} {'Winning Strategy':<30s}")
            print(f"  {'-' * 80}")

            for i, pair in enumerate(pairs_with_scores[:10], 1):
                w = pair["winner"]
                adv_safe = pair["advertiser"][:23].encode("ascii", "replace").decode("ascii")

                # Determine what the winner does differently
                winner_ad = pair["ad_a"] if w["id"] == pair["ad_a"]["id"] else pair["ad_b"]
                strategies = []
                if "hook_type" in pair["differs_in"]:
                    strategies.append(f"hook={winner_ad['hook_type']}")
                if "cta_type" in pair["differs_in"]:
                    strategies.append(f"cta={winner_ad['cta_type']}")
                strategy_str = ", ".join(strategies)

                print(
                    f"  {i:>3d} {w['id']:>10d} {w['score']:>7.1f} "
                    f"{adv_safe:<25s} {strategy_str:<30s}"
                )
        else:
            print("  No pairs with scored winners found.")

        # Hook/CTA win rate analysis
        print(f"\n{'=' * 60}")
        print("WINNING HOOK/CTA PATTERN ANALYSIS")
        print(f"{'=' * 60}")

        hook_wins: dict[str, int] = defaultdict(int)
        hook_losses: dict[str, int] = defaultdict(int)
        cta_wins: dict[str, int] = defaultdict(int)
        cta_losses: dict[str, int] = defaultdict(int)

        for pair in all_pairs:
            w_id = pair["winner"]["id"]
            winner_ad = pair["ad_a"] if w_id == pair["ad_a"]["id"] else pair["ad_b"]
            loser_ad = pair["ad_b"] if w_id == pair["ad_a"]["id"] else pair["ad_a"]

            if "hook_type" in pair["differs_in"]:
                hook_wins[winner_ad["hook_type"]] += 1
                hook_losses[loser_ad["hook_type"]] += 1

            if "cta_type" in pair["differs_in"]:
                cta_wins[winner_ad["cta_type"]] += 1
                cta_losses[loser_ad["cta_type"]] += 1

        all_hooks = set(hook_wins.keys()) | set(hook_losses.keys())
        if all_hooks:
            print(f"\n  Hook type win rates:")
            print(f"  {'Hook Type':<20s} {'Wins':>5s} {'Losses':>7s} {'Win Rate':>9s}")
            print(f"  {'-' * 45}")

            hook_stats = []
            for hook in all_hooks:
                wins = hook_wins.get(hook, 0)
                losses = hook_losses.get(hook, 0)
                total_h = wins + losses
                win_rate = round(wins / total_h * 100, 1) if total_h > 0 else 0.0
                hook_stats.append((hook, wins, losses, win_rate))

            hook_stats.sort(key=lambda x: x[3], reverse=True)
            for hook, wins, losses, win_rate in hook_stats:
                print(f"  {hook:<20s} {wins:>5d} {losses:>7d} {win_rate:>8.1f}%")

        all_ctas = set(cta_wins.keys()) | set(cta_losses.keys())
        if all_ctas:
            print(f"\n  CTA type win rates:")
            print(f"  {'CTA Type':<20s} {'Wins':>5s} {'Losses':>7s} {'Win Rate':>9s}")
            print(f"  {'-' * 45}")

            cta_stats = []
            for cta in all_ctas:
                wins = cta_wins.get(cta, 0)
                losses = cta_losses.get(cta, 0)
                total_c = wins + losses
                win_rate = round(wins / total_c * 100, 1) if total_c > 0 else 0.0
                cta_stats.append((cta, wins, losses, win_rate))

            cta_stats.sort(key=lambda x: x[3], reverse=True)
            for cta, wins, losses, win_rate in cta_stats:
                print(f"  {cta:<20s} {wins:>5d} {losses:>7d} {win_rate:>8.1f}%")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
