#!/usr/bin/env python3
"""Automated data quality checks for VAAP ads.

Performs three passes:
  1. Spam detection  -- flags suspicious titles (short, URL, repeated chars, non-JP/EN)
  2. Auto genre classification -- rule-based genre assignment for ads missing fine_genre
  3. fine_genre_jp backfill -- adds Japanese display label for ads that have fine_genre

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/auto_quality_check.py
"""

import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Constants ────────────────────────────────────────────────────────────────

# Japanese character ranges: hiragana, katakana, CJK unified ideographs
JP_CHAR_RE = re.compile(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")

# English word pattern (3+ consecutive ASCII letters)
EN_WORD_RE = re.compile(r"[A-Za-z]{3,}")

# URL-like pattern
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# Repeated character pattern (same char repeated >5 times in a row)
REPEATED_CHAR_RE = re.compile(r"(.)\1{5,}")


# ── Genre keyword map ────────────────────────────────────────────────────────

GENRE_KEYWORDS: dict[str, list[str]] = {
    "skincare": [
        "\u7f8e\u5bb9\u6db2",      # 美容液
        "\u30b9\u30ad\u30f3\u30b1\u30a2",  # スキンケア
        "\u5316\u7ca7\u6c34",      # 化粧水
        "\u7f8e\u808c",            # 美肌
        "\u6bdb\u7a74",            # 毛穴
    ],
    "fitness": [
        "\u30b8\u30e0",            # ジム
        "\u30c0\u30a4\u30a8\u30c3\u30c8",  # ダイエット
        "\u30c8\u30ec\u30fc\u30cb\u30f3\u30b0",  # トレーニング
        "\u7b4b\u30c8\u30ec",      # 筋トレ
        "\u30d1\u30fc\u30bd\u30ca\u30eb",  # パーソナル
    ],
    "health_food": [
        "\u30b5\u30d7\u30ea",      # サプリ
        "\u5065\u5eb7\u98df\u54c1",  # 健康食品
        "\u9752\u6c41",            # 青汁
        "\u30d7\u30ed\u30c6\u30a4\u30f3",  # プロテイン
        "\u4e73\u9178\u83cc",      # 乳酸菌
    ],
    "beauty_clinic": [
        "\u30af\u30ea\u30cb\u30c3\u30af",  # クリニック
        "\u65bd\u8853",            # 施術
        "\u8131\u6bdb",            # 脱毛
        "\u7f8e\u5bb9\u5916\u79d1",  # 美容外科
        "\u6574\u5f62",            # 整形
    ],
    "ec_shopping": [
        "\u901a\u8ca9",            # 通販
        "\u304a\u53d6\u308a\u5bc4\u305b",  # お取り寄せ
        "\u9001\u6599\u7121\u6599",  # 送料無料
        "\u30b7\u30e7\u30c3\u30d7",  # ショップ
    ],
    "finance": [
        "\u6295\u8cc7",            # 投資
        "FX",
        "\u4eee\u60f3\u901a\u8ca8",  # 仮想通貨
        "NISA",
        "\u8cc7\u7523\u904b\u7528",  # 資産運用
    ],
    "app": [
        "\u30a2\u30d7\u30ea",      # アプリ
        "\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9",  # ダウンロード
        "\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb",  # インストール
    ],
}

# fine_genre slug -> Japanese display label
FINE_GENRE_JP_MAP: dict[str, str] = {
    "medical_weight_loss": "\u533b\u7642\u75e9\u8eab",      # 医療痩身
    "diet_supplement": "\u30c0\u30a4\u30a8\u30c3\u30c8\u30b5\u30d7\u30ea",  # ダイエットサプリ
    "beauty_clinic": "\u7f8e\u5bb9\u30af\u30ea\u30cb\u30c3\u30af",  # 美容クリニック
    "skincare": "\u30b9\u30ad\u30f3\u30b1\u30a2",            # スキンケア
    "hair_removal": "\u8131\u6bdb",                          # 脱毛
    "hair_growth_aga": "\u80b2\u6bdb\u30fbAGA",              # 育毛・AGA
    "fitness": "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",      # フィットネス
    "yoga_pilates": "\u30e8\u30ac\u30fb\u30d4\u30e9\u30c6\u30a3\u30b9",  # ヨガ・ピラティス
    "protein_supplement": "\u30d7\u30ed\u30c6\u30a4\u30f3",  # プロテイン
    "health_food": "\u5065\u5eb7\u98df\u54c1",              # 健康食品
    "ec_shopping": "EC\u901a\u8ca9",                        # EC通販
    "app": "\u30a2\u30d7\u30ea",                            # アプリ
    "finance_investment": "\u91d1\u878d\u30fb\u6295\u8cc7",  # 金融・投資
    "finance": "\u91d1\u878d",                              # 金融
    "education_school": "\u6559\u80b2\u30fb\u30b9\u30af\u30fc\u30eb",  # 教育・スクール
    "real_estate": "\u4e0d\u52d5\u7523",                    # 不動産
    "jobs_recruitment": "\u8ee2\u8077\u30fb\u6c42\u4eba",    # 転職・求人
    "other": "\u305d\u306e\u4ed6",                          # その他
}


# ── 1. Spam Detection ────────────────────────────────────────────────────────

def detect_spam(ad: Ad) -> dict:
    """Analyse an ad title for spam signals.

    Returns {"spam_score": 0-100, "spam_reasons": [...]}.
    """
    title = ad.title or ""
    reasons: list[str] = []
    score = 0

    # Rule 1: title shorter than 3 characters
    if len(title.strip()) < 3:
        reasons.append("title_too_short")
        score += 30

    # Rule 2: title is a URL
    if URL_RE.match(title.strip()):
        reasons.append("title_is_url")
        score += 40

    # Rule 3: excessive repeated characters (>5 same char in a row)
    if REPEATED_CHAR_RE.search(title):
        reasons.append("repeated_characters")
        score += 25

    # Rule 4: title is entirely non-Japanese AND not English
    if title.strip():
        has_jp = bool(JP_CHAR_RE.search(title))
        en_words = EN_WORD_RE.findall(title)
        has_en = len(en_words) >= 1
        if not has_jp and not has_en:
            reasons.append("not_jp_or_en")
            score += 25

    # Cap at 100
    spam_score = min(score, 100)

    return {"spam_score": spam_score, "spam_reasons": reasons}


# ── 2. Auto Genre Classification ─────────────────────────────────────────────

def auto_classify_genre(ad: Ad) -> tuple[str | None, float]:
    """Rule-based genre classification from title + description keywords.

    Returns (genre_slug, confidence_score) or (None, 0.0) when no match.
    """
    title = ad.title or ""
    description = ad.description or ""
    search_text = f"{title} {description}"

    if not search_text.strip():
        return None, 0.0

    genre_hits: dict[str, int] = {}

    for genre, keywords in GENRE_KEYWORDS.items():
        hit_count = 0
        for kw in keywords:
            if kw in search_text:
                hit_count += 1
        if hit_count > 0:
            genre_hits[genre] = hit_count

    if not genre_hits:
        return None, 0.0

    # Pick genre with most keyword matches
    best_genre = max(genre_hits, key=lambda g: genre_hits[g])
    best_hits = genre_hits[best_genre]
    total_keywords = len(GENRE_KEYWORDS[best_genre])

    # Confidence: ratio of matched keywords, scaled to 0.0 - 1.0
    confidence = round(best_hits / total_keywords, 2)

    return best_genre, confidence


# ── 3. fine_genre_jp Backfill ─────────────────────────────────────────────────

def resolve_fine_genre_jp(fine_genre: str) -> str | None:
    """Return Japanese display label for a fine_genre slug, or None."""
    return FINE_GENRE_JP_MAP.get(fine_genre)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Automated Data Quality Check")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads to check: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        spam_flagged = 0
        genre_classified = 0
        genre_jp_assigned = 0

        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            changed = False

            # ── Pass 1: Spam detection ────────────────────────────
            spam_result = detect_spam(ad)
            meta["quality_flags"] = {
                "spam_score": spam_result["spam_score"],
                "spam_reasons": spam_result["spam_reasons"],
            }
            changed = True
            if spam_result["spam_score"] > 0:
                spam_flagged += 1

            # ── Pass 2: Auto genre classification ─────────────────
            existing_fine_genre = meta.get("fine_genre")
            if not existing_fine_genre:
                genre, confidence = auto_classify_genre(ad)
                if genre is not None:
                    meta["auto_genre"] = genre
                    meta["genre_confidence"] = confidence
                    genre_classified += 1
                    changed = True

            # ── Pass 3: fine_genre_jp backfill ────────────────────
            fine_genre = meta.get("fine_genre") or meta.get("fine_genre_en")
            existing_jp = meta.get("fine_genre_jp")
            if fine_genre and not existing_jp:
                jp_label = resolve_fine_genre_jp(fine_genre)
                if jp_label:
                    meta["fine_genre_jp"] = jp_label
                    genre_jp_assigned += 1
                    changed = True

            # ── Persist ───────────────────────────────────────────
            if changed:
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

        session.commit()

        # ── Summary ───────────────────────────────────────────────
        print(f"\n--- Quality Check Summary ---")
        print(f"  {total} ads checked")
        print(f"  {spam_flagged} flagged as potential spam")
        print(f"  {genre_classified} ads auto-classified with genre")
        print(f"  {genre_jp_assigned} ads got fine_genre_jp assigned")
        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
