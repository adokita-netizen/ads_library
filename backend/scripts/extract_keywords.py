#!/usr/bin/env python3
"""Extract keywords from ad title + description using TF-IDF analysis.

For each ad, extracts top 10 keywords and stores them in
ad_metadata["keywords"]. Also builds a corpus-wide keyword frequency
table and exports the analysis.

Outputs:
  - ad_metadata["keywords"] updated for each ad
  - backend/exports/keyword_analysis.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/extract_keywords.py
"""

import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Tokenizer (stdlib only, no NLTK/spaCy) ──────────────────────────────

# Stop words: common Japanese particles, connectors, and filler words
STOP_WORDS = {
    # Japanese particles and connectors
    "no", "ha", "ga", "wo", "ni", "he", "to", "de", "ka", "mo",
    "ya", "yo", "ne", "na", "shi", "te", "ta", "da", "wa",
    # Common Japanese functional words (written in kana)
    "the", "is", "a", "an", "and", "or", "but", "in", "on", "at",
    "to", "for", "of", "with", "by", "from", "as", "into", "about",
    "this", "that", "it", "its", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "can", "could", "may", "might", "shall", "should", "not",
    "your", "you", "we", "our", "my", "me", "i", "he", "she",
    "they", "them", "their", "his", "her", "all", "each", "every",
    "more", "most", "other", "some", "such", "than", "too", "very",
    "just", "also", "now", "new", "one", "two", "first", "last",
}

# Regex for Japanese word-like tokens (katakana sequences, kanji sequences)
# and ASCII word tokens
RE_KATAKANA = re.compile(r"[\u30A0-\u30FF\u31F0-\u31FF]+")
RE_KANJI = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF]+")
RE_HIRAGANA_LONG = re.compile(r"[\u3040-\u309F]{3,}")  # 3+ hiragana = likely meaningful
RE_ASCII_WORD = re.compile(r"[a-zA-Z]{2,}")
RE_NUMBER_UNIT = re.compile(r"\d+[%\u5186\u4E07\u4EBA\u500D\u56DE\u65E5\u672C\u679A\u672C\u500B\u4EF6\u7A2E]+")


def tokenize(text: str) -> list[str]:
    """Simple tokenizer: extract meaningful tokens from Japanese/mixed text.

    Extracts:
    - Katakana word sequences (common in Japanese ads for emphasis)
    - Kanji sequences (2+ chars)
    - Long hiragana sequences (3+ chars)
    - ASCII words (2+ chars)
    - Number+unit patterns (e.g., 50%, 3000 yen)
    """
    if not text:
        return []

    tokens = []

    # Extract katakana words (very common in Japanese ad copy)
    for m in RE_KATAKANA.finditer(text):
        t = m.group()
        if len(t) >= 2:
            tokens.append(t)

    # Extract kanji sequences
    for m in RE_KANJI.finditer(text):
        t = m.group()
        if len(t) >= 2:
            tokens.append(t)

    # Extract long hiragana
    for m in RE_HIRAGANA_LONG.finditer(text):
        tokens.append(m.group())

    # Extract ASCII words
    for m in RE_ASCII_WORD.finditer(text):
        w = m.group().lower()
        if w not in STOP_WORDS and len(w) >= 2:
            tokens.append(w)

    # Extract number+unit patterns
    for m in RE_NUMBER_UNIT.finditer(text):
        tokens.append(m.group())

    return tokens


# ── TF-IDF Computation ──────────────────────────────────────────────────


def compute_tf(tokens: list[str]) -> dict[str, float]:
    """Compute term frequency (normalized by document length)."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {word: count / total for word, count in counts.items()}


def compute_idf(doc_tokens: list[list[str]]) -> dict[str, float]:
    """Compute inverse document frequency across all documents."""
    n_docs = len(doc_tokens)
    if n_docs == 0:
        return {}

    # Count how many documents each word appears in
    doc_freq: Counter = Counter()
    for tokens in doc_tokens:
        unique_words = set(tokens)
        for word in unique_words:
            doc_freq[word] += 1

    # IDF = log(N / df)  (with +1 smoothing)
    idf = {}
    for word, df in doc_freq.items():
        idf[word] = math.log((n_docs + 1) / (df + 1)) + 1  # smoothed IDF

    return idf


def compute_tfidf(tf: dict[str, float], idf: dict[str, float]) -> dict[str, float]:
    """Compute TF-IDF scores."""
    return {word: tf_val * idf.get(word, 1.0) for word, tf_val in tf.items()}


def extract_top_keywords(tfidf: dict[str, float], top_n: int = 10) -> list[str]:
    """Return top N keywords by TF-IDF score."""
    sorted_words = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)
    return [word for word, score in sorted_words[:top_n]]


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_text(ad: Ad) -> str:
    """Combine title + description + metadata text for keyword extraction."""
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


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("Keyword Extraction Script (TF-IDF)")
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

        # Step 1: Tokenize all ads
        print("Tokenizing all ads...")
        ad_tokens: list[tuple[Ad, list[str]]] = []
        for ad in ads:
            text = _get_text(ad)
            tokens = tokenize(text)
            ad_tokens.append((ad, tokens))

        tokenized_count = sum(1 for _, t in ad_tokens if t)
        print(f"  Ads with tokens: {tokenized_count}/{total}")

        # Step 2: Compute IDF across the corpus
        print("Computing IDF across corpus...")
        all_doc_tokens = [tokens for _, tokens in ad_tokens]
        idf = compute_idf(all_doc_tokens)
        print(f"  Unique terms in corpus: {len(idf)}")

        # Step 3: Extract keywords per ad and store in ad_metadata
        print("Extracting keywords per ad...")
        updated = 0
        all_keywords: Counter = Counter()
        hit_keywords: Counter = Counter()
        non_hit_keywords: Counter = Counter()

        for ad, tokens in ad_tokens:
            if not tokens:
                continue

            tf = compute_tf(tokens)
            tfidf = compute_tfidf(tf, idf)
            keywords = extract_top_keywords(tfidf, top_n=10)

            # Update ad_metadata
            meta = dict(ad.ad_metadata or {})
            meta["keywords"] = keywords
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            # Corpus-wide frequency
            for kw in keywords:
                all_keywords[kw] += 1
                if _is_hit(ad):
                    hit_keywords[kw] += 1
                else:
                    non_hit_keywords[kw] += 1

        session.commit()
        print(f"  Updated keywords for {updated}/{total} ads.")

        # Step 4: Compute keyword-hit correlation
        print("\nComputing keyword-hit correlation...")
        total_hits = sum(1 for ad in ads if _is_hit(ad))
        total_non_hits = total - total_hits
        print(f"  Hit ads: {total_hits}, Non-hit ads: {total_non_hits}")

        keyword_analysis = []
        for kw, count in all_keywords.most_common(100):
            hits = hit_keywords.get(kw, 0)
            non_hits = non_hit_keywords.get(kw, 0)
            hit_rate = round(hits / count * 100, 1) if count > 0 else 0
            keyword_analysis.append({
                "keyword": kw,
                "total_count": count,
                "hit_count": hits,
                "non_hit_count": non_hits,
                "hit_rate": hit_rate,
                "idf_score": round(idf.get(kw, 0), 3),
            })

        # Step 5: Print top keywords
        print(f"\n--- Top 30 Keywords by Frequency ---")
        print(f"  {'Keyword':<20s} {'Total':>5s} {'Hits':>5s} {'HitRate':>8s} {'IDF':>6s}")
        print(f"  {'-' * 50}")
        for ka in keyword_analysis[:30]:
            kw_display = ka["keyword"][:18]
            try:
                kw_display.encode("ascii")
            except UnicodeEncodeError:
                kw_display = kw_display.encode("ascii", "replace").decode("ascii")
            print(
                f"  {kw_display:<20s} {ka['total_count']:>5d} {ka['hit_count']:>5d} "
                f"{ka['hit_rate']:>7.1f}% {ka['idf_score']:>5.2f}"
            )

        # High hit-rate keywords (min 3 occurrences)
        high_hit_kw = [ka for ka in keyword_analysis if ka["total_count"] >= 3 and ka["hit_rate"] >= 70]
        high_hit_kw.sort(key=lambda x: x["hit_rate"], reverse=True)
        print(f"\n--- High Hit-Rate Keywords (>=70%, min 3 occurrences) ---")
        for ka in high_hit_kw[:15]:
            kw_display = ka["keyword"][:18]
            try:
                kw_display.encode("ascii")
            except UnicodeEncodeError:
                kw_display = kw_display.encode("ascii", "replace").decode("ascii")
            print(f"  {kw_display}: {ka['hit_rate']}% hit rate (n={ka['total_count']})")

        # Step 6: Build insights
        insights = []
        if keyword_analysis:
            top_kw = keyword_analysis[0]
            insights.append(
                f"Most common keyword: '{top_kw['keyword']}' "
                f"(appears in {top_kw['total_count']} ads, {top_kw['hit_rate']}% hit rate)"
            )
        if high_hit_kw:
            best = high_hit_kw[0]
            insights.append(
                f"Highest hit-rate keyword: '{best['keyword']}' "
                f"({best['hit_rate']}% hit rate, n={best['total_count']})"
            )

        # Step 7: Export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "ads_with_keywords": updated,
            "unique_keywords": len(all_keywords),
            "total_hit_ads": total_hits,
            "top_keywords": keyword_analysis[:100],
            "high_hit_rate_keywords": high_hit_kw[:30],
            "insights": insights,
        }

        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "keyword_analysis.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\nReport saved to: {out_path}")

        # Print sample
        print(f"\n--- Sample Keywords (first 5 ads) ---")
        sample = session.query(Ad).limit(5).all()
        for ad in sample:
            kws = (ad.ad_metadata or {}).get("keywords", [])
            title_safe = (ad.title or "")[:40].encode("ascii", "replace").decode("ascii")
            kws_safe = ", ".join(
                kw.encode("ascii", "replace").decode("ascii") for kw in kws[:5]
            )
            print(f"  ID={ad.id} title={title_safe!r}")
            print(f"    keywords: [{kws_safe}]")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
