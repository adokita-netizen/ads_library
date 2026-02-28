#!/usr/bin/env python3
"""Analyze Japanese "power words" in ad copy.

Defines lists of power words by category (urgency, social_proof, benefit,
fear, free), counts occurrences in hit vs non-hit ads, and calculates
a "power score" for each word.

Outputs:
  - backend/exports/power_words.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/power_words.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Power Word Definitions ──────────────────────────────────────────────

POWER_WORD_CATEGORIES: dict[str, list[str]] = {
    "urgency": [
        "\u4eca\u3060\u3051",        # now only
        "\u9650\u5b9a",              # limited
        "\u6b8b\u308a\u308f\u305a\u304b",  # few remaining
        "\u6025\u3044\u3067",        # hurry
        "\u672c\u65e5\u9650\u308a",  # today only
        "\u671f\u9593\u9650\u5b9a",  # limited time
        "\u5148\u7740",              # first come
        "\u7de0\u5207",              # deadline
        "\u30e9\u30b9\u30c8",        # last
        "\u304a\u6025\u304e",        # hurry (polite)
        "\u6700\u7d42",              # final
        "\u3042\u3068\u308f\u305a\u304b",  # just a little left
    ],
    "social_proof": [
        "\u4eba\u6c17",              # popular
        "\u8a71\u984c",              # trending
        "\u58f2\u4e0aNo.1",          # sales No.1
        "\u6e80\u8db3\u5ea6",        # satisfaction rate
        "\u30ec\u30d3\u30e5\u30fc",  # review
        "\u53e3\u30b3\u30df",        # word of mouth
        "\u30e9\u30f3\u30ad\u30f3\u30b0",  # ranking
        "\u7d2f\u8a08",              # cumulative
        "\u7a81\u7834",              # breakthrough
        "\u5b9f\u7e3e",              # track record
        "\u6bbf\u5802\u5165\u308a",  # hall of fame
        "\u30d9\u30b9\u30c8\u30bb\u30e9\u30fc",  # bestseller
        "\u30ea\u30d4\u30fc\u30c8",  # repeat
        "\u7b2c1\u4f4d",             # #1
    ],
    "benefit": [
        "\u7c21\u5358",              # easy
        "\u305f\u3063\u305f",        # just/only
        "\u3060\u3051\u3067",        # just by
        "\u9a5a\u304d\u306e",        # surprising
        "\u5b9f\u611f",              # felt/realized
        "\u624b\u8efd",              # handy
        "\u304a\u5f97",              # good deal
        "\u5b89\u5fc3",              # peace of mind
        "\u4fbf\u5229",              # convenient
        "\u5feb\u9069",              # comfortable
        "\u30b9\u30c3\u30ad\u30ea",  # refreshing
        "\u7406\u60f3",              # ideal
        "\u6539\u5584",              # improvement
        "\u52b9\u679c",              # effect
        "\u7d50\u679c",              # result
    ],
    "fear": [
        "\u5371\u967a",              # danger
        "\u77e5\u3089\u306a\u3044\u3068",  # if you don't know
        "\u640d",                    # loss
        "\u5f8c\u6094",              # regret
        "\u8001\u5316",              # aging
        "\u653e\u7f6e",              # neglect
        "\u624b\u9045\u308c",        # too late
        "\u30ea\u30b9\u30af",        # risk
        "\u5931\u6557",              # failure
        "\u4e0d\u5b89",              # anxiety
        "\u8b66\u544a",              # warning
        "\u8981\u6ce8\u610f",        # caution needed
    ],
    "free": [
        "\u7121\u6599",              # free
        "0\u5186",                   # 0 yen
        "\u30bf\u30c0",              # free (colloquial)
        "\u30d7\u30ec\u30bc\u30f3\u30c8",  # present/gift
        "\u7279\u5178",              # bonus/benefit
        "\u9001\u6599\u7121\u6599",  # free shipping
        "\u624b\u6570\u6599\u7121\u6599",  # no fees
        "\u304a\u8a66\u3057",        # trial
        "\u30c8\u30e9\u30a4\u30a2\u30eb",  # trial (katakana)
        "\u30b5\u30f3\u30d7\u30eb",  # sample
        "\u30e2\u30cb\u30bf\u30fc",  # monitor
    ],
}


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_text(ad: Ad) -> str:
    """Combine all text fields for power word scanning."""
    parts = []
    if ad.title:
        parts.append(ad.title)
    if ad.description:
        parts.append(ad.description)
    meta = ad.ad_metadata or {}
    body = meta.get("body")
    if body and isinstance(body, str):
        parts.append(body)
    link_desc = meta.get("link_description")
    if link_desc and isinstance(link_desc, str):
        parts.append(link_desc)
    cta_text = meta.get("cta_text")
    if cta_text and isinstance(cta_text, str):
        parts.append(cta_text)
    return " ".join(parts)


def _is_hit(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _safe_mean(vals: list[float]) -> float:
    return mean(vals) if vals else 0.0


# ── Analysis Functions ──────────────────────────────────────────────────


def scan_power_words(ads: list[Ad]) -> dict:
    """Scan all ads for power words and compute statistics.

    Returns a nested dict:
    {
        category: {
            word: {
                total: N, hit_count: N, non_hit_count: N,
                hit_rate: %, avg_score_with: f, avg_score_without: f,
                power_score: f  (hit_rate when present)
            }
        }
    }
    """
    # Pre-compute hit status and scores
    ad_data = []
    for ad in ads:
        text = _get_text(ad)
        if not text:
            continue
        ad_data.append({
            "text": text.lower(),
            "is_hit": _is_hit(ad),
            "score": _get_score(ad),
        })

    total_ads = len(ad_data)
    total_hits = sum(1 for d in ad_data if d["is_hit"])

    results = {}
    for category, words in POWER_WORD_CATEGORIES.items():
        cat_results = {}
        for word in words:
            word_lower = word.lower()
            present_ads = [d for d in ad_data if word_lower in d["text"]]
            absent_ads = [d for d in ad_data if word_lower not in d["text"]]

            total_present = len(present_ads)
            if total_present == 0:
                continue

            hit_present = sum(1 for d in present_ads if d["is_hit"])
            non_hit_present = total_present - hit_present
            hit_rate = round(hit_present / total_present * 100, 1)

            avg_score_with = round(_safe_mean([d["score"] for d in present_ads]), 1)
            avg_score_without = round(_safe_mean([d["score"] for d in absent_ads]), 1) if absent_ads else 0

            # Power score = hit_rate when the word is present
            # Bonus: compare to baseline hit_rate
            baseline_hit_rate = round(total_hits / total_ads * 100, 1) if total_ads > 0 else 0
            lift = round(hit_rate - baseline_hit_rate, 1)

            cat_results[word] = {
                "total": total_present,
                "hit_count": hit_present,
                "non_hit_count": non_hit_present,
                "hit_rate": hit_rate,
                "avg_score_with": avg_score_with,
                "avg_score_without": avg_score_without,
                "score_lift": round(avg_score_with - avg_score_without, 1),
                "power_score": hit_rate,
                "lift_vs_baseline": lift,
            }

        # Sort by power_score descending
        results[category] = dict(
            sorted(cat_results.items(), key=lambda x: x[1]["power_score"], reverse=True)
        )

    return results


def compute_category_summary(power_word_data: dict) -> dict:
    """Summarize power word effectiveness by category."""
    summary = {}
    for category, words in power_word_data.items():
        if not words:
            summary[category] = {"words_found": 0}
            continue

        total_occurrences = sum(w["total"] for w in words.values())
        avg_hit_rate = round(
            _safe_mean([w["hit_rate"] for w in words.values()]), 1
        )
        avg_score_lift = round(
            _safe_mean([w["score_lift"] for w in words.values()]), 1
        )
        best_word = max(words.items(), key=lambda x: x[1]["power_score"])

        summary[category] = {
            "words_found": len(words),
            "total_occurrences": total_occurrences,
            "avg_hit_rate": avg_hit_rate,
            "avg_score_lift": avg_score_lift,
            "best_word": best_word[0],
            "best_word_hit_rate": best_word[1]["hit_rate"],
            "best_word_count": best_word[1]["total"],
        }

    return summary


def compute_power_word_density(ads: list[Ad]) -> dict:
    """Compute power word density (avg power words per ad) for hit vs non-hit."""
    all_words = []
    for words in POWER_WORD_CATEGORIES.values():
        all_words.extend(words)

    hit_densities = []
    non_hit_densities = []

    for ad in ads:
        text = _get_text(ad).lower()
        if not text:
            continue
        count = sum(1 for w in all_words if w.lower() in text)
        if _is_hit(ad):
            hit_densities.append(count)
        else:
            non_hit_densities.append(count)

    return {
        "hit_avg_power_words": round(_safe_mean(hit_densities), 2),
        "non_hit_avg_power_words": round(_safe_mean(non_hit_densities), 2),
        "hit_ads_count": len(hit_densities),
        "non_hit_ads_count": len(non_hit_densities),
    }


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Power Words Analysis Script")
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

        # 1. Scan power words
        print("Scanning power words across all ads...")
        power_word_data = scan_power_words(ads)

        # Count total power words found
        total_found = sum(
            len(words) for words in power_word_data.values()
        )
        print(f"  Power words found in corpus: {total_found}")

        # 2. Category summary
        category_summary = compute_category_summary(power_word_data)

        # 3. Power word density
        density = compute_power_word_density(ads)

        # 4. Print results
        for category, words in power_word_data.items():
            print(f"\n--- {category.upper()} ---")
            if not words:
                print("  (no occurrences found)")
                continue
            print(f"  {'Word':<16s} {'Total':>5s} {'Hits':>5s} {'HitRate':>8s} {'AvgScore':>9s} {'Lift':>6s}")
            print(f"  {'-' * 55}")
            for word, stats in list(words.items())[:10]:
                word_display = word[:14]
                try:
                    word_display.encode("ascii")
                except UnicodeEncodeError:
                    word_display = word_display.encode("ascii", "replace").decode("ascii")
                print(
                    f"  {word_display:<16s} {stats['total']:>5d} {stats['hit_count']:>5d} "
                    f"{stats['hit_rate']:>7.1f}% {stats['avg_score_with']:>8.1f} "
                    f"{stats['score_lift']:>+5.1f}"
                )

        print(f"\n--- Category Summary ---")
        print(f"  {'Category':<16s} {'Words':>5s} {'Occur':>6s} {'AvgHitRate':>10s} {'AvgLift':>8s} {'Best Word':<14s}")
        print(f"  {'-' * 65}")
        for cat, info in category_summary.items():
            if info["words_found"] == 0:
                continue
            best_w = info.get("best_word", "?")[:12]
            try:
                best_w.encode("ascii")
            except UnicodeEncodeError:
                best_w = best_w.encode("ascii", "replace").decode("ascii")
            print(
                f"  {cat:<16s} {info['words_found']:>5d} "
                f"{info['total_occurrences']:>6d} "
                f"{info['avg_hit_rate']:>9.1f}% "
                f"{info['avg_score_lift']:>+7.1f} "
                f"{best_w:<14s}"
            )

        print(f"\n--- Power Word Density ---")
        print(f"  Hit ads: avg {density['hit_avg_power_words']:.1f} power words/ad (n={density['hit_ads_count']})")
        print(f"  Non-hit: avg {density['non_hit_avg_power_words']:.1f} power words/ad (n={density['non_hit_ads_count']})")

        # 5. Build insights
        insights = []

        # Best category
        best_cat = max(
            ((c, s) for c, s in category_summary.items() if s.get("words_found", 0) > 0),
            key=lambda x: x[1]["avg_hit_rate"],
            default=None,
        )
        if best_cat:
            insights.append(
                f"Most effective category: '{best_cat[0]}' "
                f"(avg {best_cat[1]['avg_hit_rate']}% hit rate, "
                f"avg +{best_cat[1]['avg_score_lift']} score lift)"
            )

        # Best individual word
        all_words_flat = []
        for cat, words in power_word_data.items():
            for word, stats in words.items():
                if stats["total"] >= 3:
                    all_words_flat.append({"word": word, "category": cat, **stats})
        if all_words_flat:
            best_word = max(all_words_flat, key=lambda x: x["power_score"])
            insights.append(
                f"Most powerful word: '{best_word['word']}' ({best_word['category']}) "
                f"with {best_word['power_score']}% hit rate (n={best_word['total']})"
            )

        # Density insight
        if density["hit_avg_power_words"] > density["non_hit_avg_power_words"]:
            insights.append(
                f"Hit ads use more power words: {density['hit_avg_power_words']:.1f} vs "
                f"{density['non_hit_avg_power_words']:.1f} per ad"
            )
        else:
            insights.append(
                f"Non-hit ads use more power words ({density['non_hit_avg_power_words']:.1f} vs "
                f"{density['hit_avg_power_words']:.1f}), suggesting quantity != quality"
            )

        print(f"\n--- Insights ---")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        # 6. Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "power_words": power_word_data,
            "category_summary": category_summary,
            "density_analysis": density,
            "insights": insights,
        }

        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "power_words.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\nReport saved to: {out_path}")
        print("Done!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
