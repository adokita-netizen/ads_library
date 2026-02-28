#!/usr/bin/env python3
"""Analyze title structure patterns and their correlation with hit rate.

Classifies titles by structural patterns:
  - Question type
  - Number type
  - Testimonial type
  - Command type
  - Shock type
  - Plain/other

Computes hit rate and avg score per pattern, then exports results.

Outputs:
  - backend/exports/title_patterns.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_title_structure.py
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Pattern Definitions ─────────────────────────────────────────────────

# Order matters: first match wins (most specific first)
TITLE_PATTERNS: list[tuple[str, list[str | re.Pattern]]] = [
    # Question type: ends with ? or uses question particles
    ("question", [
        re.compile(r"[\?\uff1f]"),                      # ? or full-width ?
        re.compile(r"\u3067\u3059\u304b"),               # desuka
        re.compile(r"\u307e\u305b\u3093\u304b"),         # masenka
        re.compile(r"\u3057\u3066\u3044\u307e\u305b\u3093\u304b"),  # shiteimasenka
        re.compile(r"\u3068\u306f"),                     # toha (defining question)
        re.compile(r"\u3054\u5b58\u77e5"),               # gozonji (do you know)
        re.compile(r"\u77e5\u3063\u3066"),               # shitte (did you know)
    ]),

    # Number type: contains stats, percentages, lists
    ("number", [
        re.compile(r"\d+\u3064\u306e"),                  # N-tsu no (N things)
        re.compile(r"\d+\u9078"),                        # N-sen (N selections)
        re.compile(r"\d+%"),                             # N%
        re.compile(r"\d+\u5186"),                        # N yen
        re.compile(r"\d+\u4e07"),                        # N man (ten thousands)
        re.compile(r"\d+\u4eba"),                        # N people
        re.compile(r"\d+\u500d"),                        # N times
        re.compile(r"\u7b2c\d+\u4f4d"),                  # rank N
        re.compile(r"No\.\d+", re.IGNORECASE),           # No.1
        re.compile(r"\d+\u65e5"),                        # N days
        re.compile(r"\d+\u79d2"),                        # N seconds
        re.compile(r"\d+\u6b73"),                        # N years old
        re.compile(r"\d+\u30f6\u6708"),                  # N months
    ]),

    # Testimonial type: personal experience
    ("testimonial", [
        re.compile(r"\u79c1\u304c"),                     # watashi ga (I...)
        re.compile(r"\u3057\u305f\u7d50\u679c"),         # shita kekka (result of doing)
        re.compile(r"\u4f53\u9a13\u8ac7"),               # taikendan (experience story)
        re.compile(r"\u4f7f\u3063\u3066\u307f"),         # tsukatte mi (tried using)
        re.compile(r"\u8a66\u3057\u3066\u307f"),         # tameshite mi (tried)
        re.compile(r"\u611f\u60f3"),                     # kansou (impressions)
        re.compile(r"\u53e3\u30b3\u30df"),               # kuchikomi (reviews)
        re.compile(r"\u304a\u5ba2\u69d8\u306e\u58f0"),   # customer voice
        re.compile(r"\u500b\u4eba\u306e"),               # personal
        re.compile(r"\u5b9f\u969b\u306b"),               # actually
        re.compile(r"\u30ec\u30d3\u30e5\u30fc"),         # review
    ]),

    # Command type: imperative/instruction
    ("command", [
        re.compile(r"\u3057\u3066\u304f\u3060\u3055\u3044"),  # shite kudasai (please do)
        re.compile(r"\u3057\u3088\u3046"),               # shiyou (let's do)
        re.compile(r"\u3057\u307e\u3057\u3087\u3046"),   # shimashou (let's do - polite)
        re.compile(r"\u3057\u306a\u3044\u3067"),         # shinaide (don't do)
        re.compile(r"\u59cb\u3081\u3088\u3046"),         # hajimeyou (let's start)
        re.compile(r"\u624b\u306b\u5165\u308c"),         # te ni ire (get/obtain)
        re.compile(r"\u30c1\u30a7\u30c3\u30af"),         # check
        re.compile(r"\u4eca\u3059\u3050"),               # ima sugu (right now)
        re.compile(r"\u8a66\u3057\u3066"),               # tameshite (try it)
        re.compile(r"\u898b\u3066"),                     # mite (look/watch)
    ]),

    # Shock type: surprising/provocative
    ("shock", [
        re.compile(r"\u885d\u6483"),                     # shougeki (shock)
        re.compile(r"\u307e\u3055\u304b"),               # masaka (no way)
        re.compile(r"\u77e5\u3089\u306a\u304b\u3063\u305f"),  # shiranakatta (didn't know)
        re.compile(r"\u9a5a"),                           # odoro (surprise)
        re.compile(r"\u3084\u3070\u3044"),               # yabai (amazing/crazy)
        re.compile(r"\u5371\u967a"),                     # kiken (danger)
        re.compile(r"\u6ce8\u610f"),                     # chuui (caution)
        re.compile(r"\u8b66\u544a"),                     # keikoku (warning)
        re.compile(r"\u7981\u6b62"),                     # kinshi (prohibited)
        re.compile(r"\u5927\u5909"),                     # taihen (serious/terrible)
        re.compile(r"\u5b9f\u306f"),                     # jitsu ha (actually)
        re.compile(r"\u30a6\u30bd"),                     # uso (lie/unbelievable)
        re.compile(r"\u9006\u8ee2"),                     # gyakuten (reversal)
        re.compile(r"\u771f\u5b9f"),                     # shinjitsu (truth)
        re.compile(r"\u79d8\u5bc6"),                     # himitsu (secret)
        re.compile(r"\u88cf\u30ef\u30b6"),               # urawaza (hidden trick)
        re.compile(r"\u65b0\u5e38\u8b58"),               # new common sense
    ]),
]


# ── Helpers ──────────────────────────────────────────────────────────────


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


# ── Classification ──────────────────────────────────────────────────────


def classify_title(title: str) -> list[str]:
    """Classify a title into one or more structural patterns.

    Returns all matching patterns (a title can be both 'question' and 'number').
    If no pattern matches, returns ['plain'].
    """
    if not title or not title.strip():
        return ["empty"]

    matched = []
    for pattern_name, rules in TITLE_PATTERNS:
        for rule in rules:
            if isinstance(rule, re.Pattern):
                if rule.search(title):
                    matched.append(pattern_name)
                    break
            elif isinstance(rule, str):
                if rule in title:
                    matched.append(pattern_name)
                    break

    return matched if matched else ["plain"]


def classify_title_primary(title: str) -> str:
    """Classify a title into its primary (first matching) pattern."""
    patterns = classify_title(title)
    return patterns[0]


# ── Analysis Functions ──────────────────────────────────────────────────


def compute_pattern_stats(ads: list[Ad]) -> dict:
    """Compute hit rate, avg score, and count per title pattern."""
    # Use primary pattern for main stats
    groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        title = ad.title or ""
        pattern = classify_title_primary(title)
        groups[pattern].append(ad)

    results = {}
    for pattern, pattern_ads in groups.items():
        scores = [_get_score(a) for a in pattern_ads]
        hits = sum(1 for a in pattern_ads if _is_hit(a))
        results[pattern] = {
            "count": len(pattern_ads),
            "hit_count": hits,
            "hit_rate": round(hits / len(pattern_ads) * 100, 1) if pattern_ads else 0,
            "avg_score": round(_safe_mean(scores), 1),
            "median_score": round(sorted(scores)[len(scores) // 2], 1) if scores else 0,
        }

    return dict(sorted(results.items(), key=lambda x: x[1]["hit_rate"], reverse=True))


def compute_multi_pattern_stats(ads: list[Ad]) -> dict:
    """Compute stats for ads matching multiple patterns (e.g., question + number)."""
    multi: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        title = ad.title or ""
        patterns = classify_title(title)
        if len(patterns) >= 2:
            combo = "+".join(sorted(set(patterns)))
            multi[combo].append(ad)

    results = {}
    for combo, combo_ads in multi.items():
        if len(combo_ads) < 2:
            continue
        scores = [_get_score(a) for a in combo_ads]
        hits = sum(1 for a in combo_ads if _is_hit(a))
        results[combo] = {
            "count": len(combo_ads),
            "hit_count": hits,
            "hit_rate": round(hits / len(combo_ads) * 100, 1),
            "avg_score": round(_safe_mean(scores), 1),
        }

    return dict(sorted(results.items(), key=lambda x: x[1]["hit_rate"], reverse=True))


def compute_title_length_by_pattern(ads: list[Ad]) -> dict:
    """Compute average title length per pattern."""
    lengths: dict[str, list[int]] = defaultdict(list)
    for ad in ads:
        title = ad.title or ""
        pattern = classify_title_primary(title)
        lengths[pattern].append(len(title))

    return {
        pattern: {
            "avg_length": round(_safe_mean([float(l) for l in lens]), 1),
            "min_length": min(lens) if lens else 0,
            "max_length": max(lens) if lens else 0,
        }
        for pattern, lens in lengths.items()
    }


def find_pattern_examples(ads: list[Ad], max_per_pattern: int = 3) -> dict:
    """Find example ad titles for each pattern (top scoring ones)."""
    groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        title = ad.title or ""
        pattern = classify_title_primary(title)
        groups[pattern].append(ad)

    examples = {}
    for pattern, pattern_ads in groups.items():
        sorted_ads = sorted(pattern_ads, key=lambda a: _get_score(a), reverse=True)
        examples[pattern] = []
        for ad in sorted_ads[:max_per_pattern]:
            title = ad.title or ""
            examples[pattern].append({
                "ad_id": ad.id,
                "title": title,
                "score": _get_score(ad),
                "is_hit": _is_hit(ad),
            })

    return examples


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Title Structure Analysis Script")
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

        # 1. Primary pattern stats
        print("\nClassifying title patterns...")
        pattern_stats = compute_pattern_stats(ads)

        total_hits = sum(1 for a in ads if _is_hit(a))
        baseline_hit_rate = round(total_hits / total * 100, 1) if total > 0 else 0

        print(f"  Baseline hit rate: {baseline_hit_rate}%")
        print(f"\n--- Title Pattern Performance ---")
        print(f"  {'Pattern':<16s} {'Count':>6s} {'Hits':>5s} {'HitRate':>8s} {'AvgScore':>9s} {'vs Baseline':>11s}")
        print(f"  {'-' * 60}")
        for pattern, stats in pattern_stats.items():
            diff = round(stats["hit_rate"] - baseline_hit_rate, 1)
            diff_str = f"{diff:+.1f}%"
            print(
                f"  {pattern:<16s} {stats['count']:>6d} {stats['hit_count']:>5d} "
                f"{stats['hit_rate']:>7.1f}% {stats['avg_score']:>8.1f} "
                f"{diff_str:>10s}"
            )

        # 2. Multi-pattern combos
        multi_stats = compute_multi_pattern_stats(ads)
        if multi_stats:
            print(f"\n--- Multi-Pattern Combinations ---")
            print(f"  {'Combo':<24s} {'Count':>6s} {'HitRate':>8s} {'AvgScore':>9s}")
            print(f"  {'-' * 50}")
            for combo, stats in list(multi_stats.items())[:10]:
                print(
                    f"  {combo:<24s} {stats['count']:>6d} "
                    f"{stats['hit_rate']:>7.1f}% {stats['avg_score']:>8.1f}"
                )

        # 3. Title length by pattern
        length_stats = compute_title_length_by_pattern(ads)
        print(f"\n--- Avg Title Length by Pattern ---")
        for pattern, ls in length_stats.items():
            print(f"  {pattern:<16s}: avg={ls['avg_length']:.0f} chars "
                  f"(range {ls['min_length']}-{ls['max_length']})")

        # 4. Examples
        examples = find_pattern_examples(ads, max_per_pattern=3)
        print(f"\n--- Pattern Examples (top scored) ---")
        for pattern, exs in examples.items():
            print(f"  [{pattern}]")
            for ex in exs:
                title_safe = ex["title"][:50].encode("ascii", "replace").decode("ascii")
                hit_marker = "HIT" if ex["is_hit"] else ""
                print(f"    score={ex['score']:.0f} {hit_marker} {title_safe!r}")

        # 5. Build insights
        insights = []

        # Best pattern
        if pattern_stats:
            patterns_with_count = {
                p: s for p, s in pattern_stats.items()
                if s["count"] >= 3 and p not in ("empty", "plain")
            }
            if patterns_with_count:
                best = max(patterns_with_count.items(), key=lambda x: x[1]["hit_rate"])
                insights.append(
                    f"Best performing title pattern: '{best[0]}' "
                    f"({best[1]['hit_rate']}% hit rate, {best[1]['count']} ads, "
                    f"avg score {best[1]['avg_score']})"
                )
                worst = min(patterns_with_count.items(), key=lambda x: x[1]["hit_rate"])
                if worst[0] != best[0]:
                    insights.append(
                        f"Worst performing pattern: '{worst[0]}' "
                        f"({worst[1]['hit_rate']}% hit rate, {worst[1]['count']} ads)"
                    )

        # Plain vs structured comparison
        plain_stats = pattern_stats.get("plain", {})
        structured_ads = [
            s for p, s in pattern_stats.items()
            if p not in ("plain", "empty")
        ]
        if plain_stats and structured_ads:
            total_structured = sum(s["count"] for s in structured_ads)
            total_structured_hits = sum(s["hit_count"] for s in structured_ads)
            structured_hr = round(total_structured_hits / total_structured * 100, 1) if total_structured > 0 else 0
            plain_hr = plain_stats.get("hit_rate", 0)
            if abs(structured_hr - plain_hr) >= 5:
                better = "structured" if structured_hr > plain_hr else "plain"
                insights.append(
                    f"{better.capitalize()} titles perform better: "
                    f"structured {structured_hr}% vs plain {plain_hr}% hit rate"
                )

        print(f"\n--- Key Insights ---")
        for i, insight in enumerate(insights, 1):
            print(f"  {i}. {insight}")

        # 6. Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "baseline_hit_rate": baseline_hit_rate,
            "pattern_stats": pattern_stats,
            "multi_pattern_combos": multi_stats,
            "title_length_by_pattern": length_stats,
            "examples": examples,
            "insights": insights,
        }

        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "title_patterns.json")
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
