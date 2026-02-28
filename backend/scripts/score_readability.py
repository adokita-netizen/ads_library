#!/usr/bin/env python3
"""Score each ad's title readability using rule-based heuristics.

Factors considered:
  - Character count (optimal 25-50)
  - Presence of numbers (digits)
  - Japanese power words (urgency/benefit/free keywords)
  - Question marks (? or full-width)
  - Kanji ratio (penalize >60%)
  - Symbol density (penalize >5 non-alnum, non-CJK symbols)
  - Emoji presence
  - Before/after language

Stores result in ad_metadata["readability_score"] = {score, factors}.
Prints distribution buckets and Pearson correlation with hit_score.

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/score_readability.py
"""

import math
import re
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import sync_session_scope
from app.models.ad import Ad


# ── Constants ────────────────────────────────────────────────────────────

POWER_WORDS = [
    "\u7121\u6599",        # free
    "\u9650\u5b9a",        # limited
    "\u4eca\u3060\u3051",  # now only
    "\u7c21\u5358",        # easy
    "\u9a5a\u304d",        # surprising
    "\u79d8\u5bc6",        # secret
    "\u6700\u65b0",        # latest
    "\u7279\u5225",        # special
    "\u304a\u5f97",        # good deal
    "\u4eba\u6c17",        # popular
]

POWER_WORD_MAX_BONUS = 15

# Before/after language patterns (Japanese and English)
BEFORE_AFTER_PATTERNS = [
    re.compile(r"\u30d3\u30d5\u30a9\u30fc.*\u30a2\u30d5\u30bf\u30fc"),    # before...after (katakana)
    re.compile(r"before.*after", re.IGNORECASE),
    re.compile(r"\u4f7f\u7528\u524d.*\u4f7f\u7528\u5f8c"),                # before use...after use
    re.compile(r"\u524d.*\u5f8c"),                                         # before...after (kanji)
    re.compile(r"\u5909\u5316"),                                           # change/transformation
    re.compile(r"\u6bd4\u8f03"),                                           # comparison
]

# Emoji regex: covers common emoji Unicode ranges
EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA00-\U0001FA6F"  # chess symbols
    "\U0001FA70-\U0001FAFF"  # symbols extended-A
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # zero width joiner
    "\U00002B50"             # star
    "\U0000231A-\U0000231B"  # watch/hourglass
    "\U00002934-\U00002935"  # arrows
    "\U000025AA-\U000025AB"  # squares
    "\U000025FB-\U000025FE"  # squares
    "\U00003030\U0000303D"   # wavy dash / part alternation mark
    "]+",
    flags=re.UNICODE,
)

# CJK character ranges for symbol detection
CJK_RE = re.compile(
    "["
    "\u3040-\u309F"   # Hiragana
    "\u30A0-\u30FF"   # Katakana
    "\u4E00-\u9FFF"   # CJK Unified Ideographs
    "\u3400-\u4DBF"   # CJK Extension A
    "\uF900-\uFAFF"   # CJK Compatibility Ideographs
    "\uFF66-\uFF9F"   # Half-width Katakana
    "]"
)

# Kanji-only range
KANJI_RE = re.compile("[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]")


# ── Scoring Functions ────────────────────────────────────────────────────


def _count_power_words(title: str) -> int:
    """Count how many distinct power words appear in the title."""
    count = 0
    for word in POWER_WORDS:
        if word in title:
            count += 1
    return count


def _has_question_mark(title: str) -> bool:
    """Check for half-width or full-width question mark."""
    return "?" in title or "\uFF1F" in title


def _kanji_ratio(title: str) -> float:
    """Calculate the ratio of kanji characters in the title."""
    if not title:
        return 0.0
    kanji_count = len(KANJI_RE.findall(title))
    total = len(title)
    if total == 0:
        return 0.0
    return kanji_count / total


def _count_symbols(title: str) -> int:
    """Count non-alphanumeric, non-CJK, non-whitespace characters."""
    count = 0
    for ch in title:
        if ch.isspace():
            continue
        if ch.isascii() and ch.isalnum():
            continue
        if CJK_RE.match(ch):
            continue
        # Remaining: symbols, punctuation, emoji, etc.
        count += 1
    return count


def _has_emoji(title: str) -> bool:
    """Check if title contains any emoji."""
    return bool(EMOJI_RE.search(title))


def _has_before_after(title: str) -> bool:
    """Check if title contains before/after comparison language."""
    for pattern in BEFORE_AFTER_PATTERNS:
        if pattern.search(title):
            return True
    return False


def _has_numbers(title: str) -> bool:
    """Check if title contains any digit characters."""
    return bool(re.search(r"\d", title))


def score_title(title: str) -> dict:
    """Score a single title and return score + factor breakdown.

    Returns:
        {"score": int, "factors": {...}}
    """
    if not title:
        return {
            "score": 0,
            "factors": {
                "char_count": 0,
                "has_numbers": False,
                "power_word_count": 0,
                "has_question_mark": False,
                "kanji_ratio": 0.0,
                "symbol_count": 0,
                "has_emoji": False,
                "has_before_after": False,
            },
        }

    char_count = len(title)
    has_nums = _has_numbers(title)
    power_word_count = _count_power_words(title)
    has_qmark = _has_question_mark(title)
    k_ratio = round(_kanji_ratio(title), 3)
    symbol_count = _count_symbols(title)
    has_em = _has_emoji(title)
    has_ba = _has_before_after(title)

    # Base score
    score = 50

    # Character count scoring
    if 25 <= char_count <= 50:
        score += 10
    elif char_count < 10:
        score -= 10
    elif char_count > 80:
        score -= 5

    # Numbers
    if has_nums:
        score += 5

    # Power words: +3 per word, max +15
    pw_bonus = min(power_word_count * 3, POWER_WORD_MAX_BONUS)
    score += pw_bonus

    # Question mark
    if has_qmark:
        score += 5

    # Excessive kanji ratio
    if k_ratio > 0.6:
        score -= 5

    # Too many symbols
    if symbol_count > 5:
        score -= 3

    # Emoji
    if has_em:
        score += 3

    # Before/after language
    if has_ba:
        score += 5

    # Clamp to [0, 100]
    score = max(0, min(100, score))

    factors = {
        "char_count": char_count,
        "has_numbers": has_nums,
        "power_word_count": power_word_count,
        "has_question_mark": has_qmark,
        "kanji_ratio": k_ratio,
        "symbol_count": symbol_count,
        "has_emoji": has_em,
        "has_before_after": has_ba,
    }

    return {"score": score, "factors": factors}


# ── Pearson Correlation ──────────────────────────────────────────────────


def pearson_correlation(xs: list, ys: list):
    """Compute Pearson correlation coefficient. Returns None if insufficient data."""
    n = len(xs)
    if n < 3 or len(ys) != n:
        return None

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return None

    return cov / denom


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Title Readability Scoring Script")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Score each ad
        readability_scores = []
        hit_scores = []
        read_scores_for_corr = []
        updated = 0
        skipped_no_title = 0

        for ad in ads:
            title = ad.title or ""
            if not title.strip():
                skipped_no_title += 1
                continue

            result = score_title(title)

            # Store in ad_metadata
            meta = dict(ad.ad_metadata or {})
            meta["readability_score"] = result
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            readability_scores.append(result["score"])

            # Collect hit_score for correlation
            hit_score = meta.get("latest_hit_score")
            if hit_score is not None:
                try:
                    hs = float(hit_score)
                    hit_scores.append(hs)
                    read_scores_for_corr.append(float(result["score"]))
                except (ValueError, TypeError):
                    pass

        session.commit()

        print(f"\nScoring complete:")
        print(f"  Updated:            {updated}")
        print(f"  Skipped (no title): {skipped_no_title}")

        if not readability_scores:
            print("No scores computed. Exiting.")
            return

        # Statistics
        avg_score = sum(readability_scores) / len(readability_scores)
        max_score = max(readability_scores)
        min_score = min(readability_scores)

        print(f"\n{'=' * 60}")
        print("Score Statistics")
        print(f"{'=' * 60}")
        print(f"  Average score:    {avg_score:.1f}")
        print(f"  Max score:        {max_score}")
        print(f"  Min score:        {min_score}")

        # Distribution buckets: 0-20, 20-40, 40-60, 60-80, 80-100
        buckets = {
            "0-20": 0,
            "20-40": 0,
            "40-60": 0,
            "60-80": 0,
            "80-100": 0,
        }
        for s in readability_scores:
            if s < 20:
                buckets["0-20"] += 1
            elif s < 40:
                buckets["20-40"] += 1
            elif s < 60:
                buckets["40-60"] += 1
            elif s < 80:
                buckets["60-80"] += 1
            else:
                buckets["80-100"] += 1

        print(f"\n{'=' * 60}")
        print("Score Distribution")
        print(f"{'=' * 60}")
        for label, count in buckets.items():
            pct = count / len(readability_scores) * 100
            bar = "#" * int(pct / 2)
            print(f"  {label:>6s}: {count:>4d} ({pct:>5.1f}%) {bar}")

        # Pearson correlation with hit_score
        print(f"\n{'=' * 60}")
        print("Correlation with Hit Score")
        print(f"{'=' * 60}")

        if len(hit_scores) >= 3:
            r = pearson_correlation(read_scores_for_corr, hit_scores)
            if r is not None:
                print(f"  Pearson r:        {r:+.4f}  (n={len(hit_scores)})")
                # Interpret
                abs_r = abs(r)
                if abs_r < 0.1:
                    interpretation = "negligible"
                elif abs_r < 0.3:
                    interpretation = "weak"
                elif abs_r < 0.5:
                    interpretation = "moderate"
                elif abs_r < 0.7:
                    interpretation = "strong"
                else:
                    interpretation = "very strong"
                direction = "positive" if r > 0 else "negative"
                print(f"  Interpretation:   {interpretation} {direction} correlation")
            else:
                print("  Pearson r:        N/A (zero variance in data)")
        else:
            print(f"  Insufficient data for correlation (need >= 3 pairs, have {len(hit_scores)})")

        print(f"\nDone!")


if __name__ == "__main__":
    main()
