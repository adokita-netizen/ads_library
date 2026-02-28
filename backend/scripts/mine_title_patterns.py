#!/usr/bin/env python3
"""Mine common title patterns/templates from Japanese ads.

Extracts structural patterns from ad titles using regex and keyword
matching (no external NLP libraries). For each pattern type, computes
hit rate, average score, and example titles, then ranks by hit rate.

Pattern types:
  - number_keyword: [number] + [keyword] (e.g., "3つの理由", "たった1分で")
  - question: question marks or question-ending particles
  - before_after: transformation/comparison language
  - authority: expert endorsement signals
  - urgency: time pressure / scarcity signals
  - number: any digit in the title
  - superlative: ranking / popularity claims

Outputs:
  - backend/exports/title_patterns_v2.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/mine_title_patterns.py
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Pattern Definitions ─────────────────────────────────────────────────

# Each entry: (pattern_name, label, list of compiled regexes or keyword strings)
# A regex is used when structure matters; plain strings for simple keyword search.

PATTERN_DEFS: list[tuple[str, str, list]] = [
    # 1. [number] + [keyword] patterns
    ("number_keyword", "Number + Keyword (e.g. 3つの理由)", [
        re.compile(r"\d+つの理由"),           # N reasons
        re.compile(r"\d+つの方法"),           # N ways
        re.compile(r"\d+つのポイント"),       # N points
        re.compile(r"\d+つの秘訣"),           # N secrets
        re.compile(r"\d+つのコツ"),           # N tips
        re.compile(r"\d+つの特徴"),           # N features
        re.compile(r"\d+つのステップ"),       # N steps
        re.compile(r"\d+選"),                 # N selections
        re.compile(r"たった\d+"),             # just N (e.g. tatta 1-pun)
        re.compile(r"\d+分で"),               # in N minutes
        re.compile(r"\d+秒で"),               # in N seconds
        re.compile(r"\d+日で"),               # in N days
        re.compile(r"\d+ヶ月で"),             # in N months
        re.compile(r"\d+%OFF"),               # N% OFF
        re.compile(r"\d+%オフ"),              # N% off (katakana)
        re.compile(r"\d+%off", re.IGNORECASE),
        re.compile(r"\d+円"),                 # N yen
        re.compile(r"\d+万人"),               # N0000 people
        re.compile(r"\d+人が"),               # N people (subject)
        re.compile(r"\d+人に"),               # to N people
        re.compile(r"\d+倍"),                 # N times (multiplier)
        re.compile(r"\d+歳"),                 # N years old
    ]),

    # 2. Question patterns
    ("question", "Question Pattern", [
        re.compile(r"[?？]"),                 # question mark (half/full-width)
        re.compile(r"ですか"),                # desuka
        re.compile(r"ませんか"),              # masenka
        re.compile(r"しませんか"),            # shimasenka
        re.compile(r"ご存知"),                # gozonji (do you know)
        re.compile(r"知って"),                # shitte (did you know)
        re.compile(r"ではありませんか"),      # dewa arimasenka
        re.compile(r"でしょうか"),            # deshouka
        re.compile(r"なぜ"),                  # naze (why)
        re.compile(r"どうして"),              # doushite (why)
        re.compile(r"いかが"),                # ikaga (how about)
    ]),

    # 3. Before/After patterns
    ("before_after", "Before/After Transformation", [
        "ビフォーアフター",                   # before-after (katakana)
        "ビフォアアフター",                   # variant spelling
        re.compile(r"から.{0,8}へ"),          # kara...e (from...to)
        "使用前",                             # before use
        "使用後",                             # after use
        "変化",                               # change
        "変身",                               # transformation
        "生まれ変わ",                         # reborn
        "劇的",                               # dramatic
        "激変",                               # drastic change
        re.compile(r"Before.*After", re.IGNORECASE),
        "だった私が",                         # I who was...
        "していた私が",                       # I who had been...
        "悩んでいた",                         # was troubled by
    ]),

    # 4. Authority patterns
    ("authority", "Authority / Expert Endorsement", [
        "医師監修",                           # doctor-supervised
        "専門家推奨",                         # expert-recommended
        "専門家監修",                         # expert-supervised
        "監修",                               # supervised
        "認定",                               # certified
        "推薦",                               # recommended
        "公式",                               # official
        "医師が",                             # doctor (subject)
        "医療",                               # medical
        "薬剤師",                             # pharmacist
        "管理栄養士",                         # registered dietitian
        "特許",                               # patent
        "臨床",                               # clinical
        "学会",                               # academic society
        "研究",                               # research
        "エビデンス",                         # evidence
        "科学的",                             # scientific
    ]),

    # 5. Urgency patterns
    ("urgency", "Urgency / Scarcity", [
        "今だけ",                             # now only
        "限定",                               # limited
        "期間限定",                           # limited time
        "残りわずか",                         # few remaining
        "本日限り",                           # today only
        "急いで",                             # hurry
        "お急ぎ",                             # hurry (polite)
        "先着",                               # first come
        "締切",                               # deadline
        "ラスト",                             # last
        "最終",                               # final
        "在庫",                               # stock
        "売り切れ",                           # sold out
        "数量限定",                           # quantity limited
        "今すぐ",                             # right now
        "終了間近",                           # ending soon
        "キャンペーン",                       # campaign
        "特別価格",                           # special price
        "初回限定",                           # first-time only
    ]),

    # 6. Number patterns (any digit in title)
    ("number", "Contains Numbers", [
        re.compile(r"\d"),                    # any digit
    ]),

    # 7. Superlative / ranking patterns
    ("superlative", "Superlative / Ranking", [
        re.compile(r"No\.\s*1", re.IGNORECASE),  # No.1
        "ランキング",                         # ranking
        "人気",                               # popular
        re.compile(r"第\d+位"),               # rank N
        "1位",                                # #1
        "売上No",                             # sales No.
        "満足度",                             # satisfaction rate
        "ベストセラー",                       # bestseller
        "トップ",                             # top
        "最高",                               # best/highest
        "最強",                               # strongest
        "業界初",                             # industry first
        "日本初",                             # Japan first
        "世界初",                             # world first
        "殿堂入り",                           # hall of fame
        re.compile(r"\d+冠"),                 # N crowns/titles
    ]),
]


# ── Helpers ──────────────────────────────────────────────────────────────


def _is_hit(ad: Ad) -> bool:
    """Determine if an ad is a 'hit' based on hit_level in metadata."""
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none") in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    """Get the latest_hit_score for an ad, defaulting to 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _safe_mean(vals: list[float]) -> float:
    """Return mean or 0 if empty."""
    return mean(vals) if vals else 0.0


def _matches_pattern(title: str, rules: list) -> bool:
    """Check if a title matches any rule in the pattern's rule list."""
    for rule in rules:
        if isinstance(rule, re.Pattern):
            if rule.search(title):
                return True
        elif isinstance(rule, str):
            if rule in title:
                return True
    return False


# ── Core Analysis ────────────────────────────────────────────────────────


def analyze_patterns(ads: list[Ad]) -> list[dict]:
    """Analyze all pattern types across ads.

    For each pattern type, compute:
      - count: how many ads use it
      - hit_rate: fraction of ads using this pattern that are hits
      - avg_score: average latest_hit_score for matching ads
      - example_titles: up to 3 example titles (highest scoring)

    Returns a list of pattern dicts sorted by hit_rate descending.
    """
    results = []

    for pattern_name, label, rules in PATTERN_DEFS:
        matching_ads = []
        for ad in ads:
            title = ad.title or ""
            if not title.strip():
                continue
            if _matches_pattern(title, rules):
                matching_ads.append(ad)

        count = len(matching_ads)
        if count == 0:
            results.append({
                "pattern": pattern_name,
                "label": label,
                "count": 0,
                "hit_count": 0,
                "hit_rate": 0.0,
                "avg_score": 0.0,
                "example_titles": [],
            })
            continue

        hit_count = sum(1 for a in matching_ads if _is_hit(a))
        hit_rate = round(hit_count / count, 4)  # fraction, not percentage
        scores = [_get_score(a) for a in matching_ads]
        avg_score = round(_safe_mean(scores), 2)

        # Pick up to 3 examples, sorted by score descending
        sorted_by_score = sorted(matching_ads, key=lambda a: _get_score(a), reverse=True)
        examples = []
        for ad in sorted_by_score[:3]:
            examples.append({
                "ad_id": ad.id,
                "title": ad.title or "",
                "advertiser": ad.advertiser_name or "",
                "score": _get_score(ad),
                "is_hit": _is_hit(ad),
            })

        results.append({
            "pattern": pattern_name,
            "label": label,
            "count": count,
            "hit_count": hit_count,
            "hit_rate": hit_rate,
            "avg_score": avg_score,
            "example_titles": examples,
        })

    # Sort by hit_rate descending
    results.sort(key=lambda x: x["hit_rate"], reverse=True)
    return results


def compute_sub_patterns(ads: list[Ad]) -> dict:
    """Break down the number_keyword pattern into specific sub-patterns.

    Returns a dict keyed by sub-pattern regex description with stats.
    This gives finer granularity than the top-level pattern grouping.
    """
    sub_patterns: list[tuple[str, re.Pattern]] = [
        ("Nつの理由 (N reasons)", re.compile(r"\d+つの理由")),
        ("Nつの方法 (N ways)", re.compile(r"\d+つの方法")),
        ("N選 (N selections)", re.compile(r"\d+選")),
        ("たったN (just N)", re.compile(r"たった\d+")),
        ("N分で (in N min)", re.compile(r"\d+分で")),
        ("N秒で (in N sec)", re.compile(r"\d+秒で")),
        ("N%OFF", re.compile(r"\d+%(?:OFF|オフ|off)", re.IGNORECASE)),
        ("N円 (N yen)", re.compile(r"\d+円")),
        ("N万人 (N0k people)", re.compile(r"\d+万人")),
        ("N倍 (N times)", re.compile(r"\d+倍")),
        ("N歳 (N years old)", re.compile(r"\d+歳")),
        ("N日で (in N days)", re.compile(r"\d+日で")),
    ]

    results = {}
    for desc, regex in sub_patterns:
        matching = [a for a in ads if a.title and regex.search(a.title)]
        if not matching:
            continue
        hit_count = sum(1 for a in matching if _is_hit(a))
        scores = [_get_score(a) for a in matching]
        results[desc] = {
            "count": len(matching),
            "hit_count": hit_count,
            "hit_rate": round(hit_count / len(matching), 4) if matching else 0.0,
            "avg_score": round(_safe_mean(scores), 2),
        }

    # Sort by hit_rate descending
    return dict(sorted(results.items(), key=lambda x: x[1]["hit_rate"], reverse=True))


def compute_pattern_combinations(ads: list[Ad]) -> list[dict]:
    """Find which pattern combinations appear together and their hit rates.

    Only includes combinations that appear in at least 2 ads.
    """
    combo_groups: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        title = ad.title or ""
        if not title.strip():
            continue

        matched_patterns = []
        for pattern_name, _label, rules in PATTERN_DEFS:
            if _matches_pattern(title, rules):
                matched_patterns.append(pattern_name)

        if len(matched_patterns) >= 2:
            combo_key = "+".join(sorted(matched_patterns))
            combo_groups[combo_key].append(ad)

    results = []
    for combo, group_ads in combo_groups.items():
        if len(group_ads) < 2:
            continue
        hit_count = sum(1 for a in group_ads if _is_hit(a))
        scores = [_get_score(a) for a in group_ads]
        results.append({
            "combination": combo,
            "count": len(group_ads),
            "hit_count": hit_count,
            "hit_rate": round(hit_count / len(group_ads), 4),
            "avg_score": round(_safe_mean(scores), 2),
        })

    results.sort(key=lambda x: x["hit_rate"], reverse=True)
    return results


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Title Pattern Mining Script (v2)")
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

        # Filter to ads with titles
        ads_with_titles = [a for a in ads if a.title and a.title.strip()]
        print(f"Ads with non-empty titles: {len(ads_with_titles)}")

        total_hits = sum(1 for a in ads_with_titles if _is_hit(a))
        baseline_hit_rate = round(total_hits / len(ads_with_titles), 4) if ads_with_titles else 0.0
        print(f"Baseline hit rate: {baseline_hit_rate:.2%}")

        # 1. Analyze all pattern types
        print("\nAnalyzing title patterns...")
        pattern_results = analyze_patterns(ads_with_titles)

        # 2. Sub-pattern breakdown for number_keyword
        print("Analyzing number+keyword sub-patterns...")
        sub_patterns = compute_sub_patterns(ads_with_titles)

        # 3. Pattern combinations
        print("Analyzing pattern combinations...")
        combos = compute_pattern_combinations(ads_with_titles)

        # ── Print Top 20 Patterns with Hit Rates ────────────────────

        print("\n" + "=" * 60)
        print("TOP 20 PATTERNS BY HIT RATE")
        print("=" * 60)

        # Build a unified ranked list: top-level patterns + sub-patterns + combos
        all_ranked: list[dict] = []

        for p in pattern_results:
            all_ranked.append({
                "name": f"[{p['pattern']}] {p['label']}",
                "count": p["count"],
                "hit_rate": p["hit_rate"],
                "avg_score": p["avg_score"],
            })

        for desc, stats in sub_patterns.items():
            all_ranked.append({
                "name": f"  sub: {desc}",
                "count": stats["count"],
                "hit_rate": stats["hit_rate"],
                "avg_score": stats["avg_score"],
            })

        for combo in combos:
            all_ranked.append({
                "name": f"  combo: {combo['combination']}",
                "count": combo["count"],
                "hit_rate": combo["hit_rate"],
                "avg_score": combo["avg_score"],
            })

        # Sort all by hit_rate descending, then by count descending
        all_ranked.sort(key=lambda x: (x["hit_rate"], x["count"]), reverse=True)

        print(f"\n  {'#':>3s}  {'Pattern':<45s} {'Count':>5s} {'HitRate':>8s} {'AvgScore':>9s}")
        print(f"  {'-' * 75}")
        for i, item in enumerate(all_ranked[:20], 1):
            name_display = item["name"][:43]
            print(
                f"  {i:>3d}  {name_display:<45s} {item['count']:>5d} "
                f"{item['hit_rate']:>7.1%} {item['avg_score']:>8.1f}"
            )

        # ── Print per-pattern details ────────────────────────────────

        print("\n" + "=" * 60)
        print("PATTERN DETAILS")
        print("=" * 60)

        for p in pattern_results:
            hr_pct = f"{p['hit_rate']:.1%}"
            diff = p["hit_rate"] - baseline_hit_rate
            diff_str = f"{diff:+.1%}"
            print(
                f"\n  [{p['pattern']}] {p['label']}: "
                f"count={p['count']}, hit_rate={hr_pct} ({diff_str} vs baseline), "
                f"avg_score={p['avg_score']}"
            )
            if p["example_titles"]:
                for ex in p["example_titles"]:
                    title_safe = ex["title"][:60].encode("ascii", "replace").decode("ascii")
                    hit_mark = " [HIT]" if ex["is_hit"] else ""
                    print(f"    - score={ex['score']:.0f}{hit_mark} {title_safe!r}")

        # ── Print sub-pattern breakdown ──────────────────────────────

        if sub_patterns:
            print(f"\n--- Number+Keyword Sub-Patterns ---")
            print(f"  {'Sub-Pattern':<30s} {'Count':>5s} {'HitRate':>8s} {'AvgScore':>9s}")
            print(f"  {'-' * 55}")
            for desc, stats in sub_patterns.items():
                print(
                    f"  {desc:<30s} {stats['count']:>5d} "
                    f"{stats['hit_rate']:>7.1%} {stats['avg_score']:>8.1f}"
                )

        # ── Print combinations ───────────────────────────────────────

        if combos:
            print(f"\n--- Pattern Combinations ---")
            print(f"  {'Combination':<40s} {'Count':>5s} {'HitRate':>8s} {'AvgScore':>9s}")
            print(f"  {'-' * 58}")
            for combo in combos[:15]:
                print(
                    f"  {combo['combination']:<40s} {combo['count']:>5d} "
                    f"{combo['hit_rate']:>7.1%} {combo['avg_score']:>8.1f}"
                )

        # ── Build & Save Report ──────────────────────────────────────

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "ads_with_titles": len(ads_with_titles),
            "total_hits": total_hits,
            "baseline_hit_rate": baseline_hit_rate,
            "patterns": pattern_results,
            "number_keyword_sub_patterns": sub_patterns,
            "pattern_combinations": combos,
            "top_20_ranked": all_ranked[:20],
        }

        exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(exports_dir, exist_ok=True)
        out_path = os.path.join(exports_dir, "title_patterns_v2.json")

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
