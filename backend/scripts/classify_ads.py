#!/usr/bin/env python3
"""Classify all ads with NULL category using keyword-based heuristics.

Usage:
    cd backend
    python scripts/classify_ads.py
"""

import json
import re
import sys
from collections import Counter

# Ensure the backend package is importable
sys.path.insert(0, ".")

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdCategoryEnum

# ---------------------------------------------------------------------------
# Keyword rules  (order matters: first match wins within a priority tier)
# Each rule: (AdCategoryEnum, list_of_keywords, weight)
#   weight is used when multiple categories match -- highest weight wins.
# ---------------------------------------------------------------------------

CATEGORY_RULES: list[tuple[AdCategoryEnum, list[str], int]] = [
    # ── Beauty / Cosmetics ────────────────────────────────────────
    (AdCategoryEnum.BEAUTY, [
        "美容", "コスメ", "スキンケア", "化粧", "クリニック", "脱毛",
        "ダイエット", "gpl-1", "glp-1", "美肌", "エステ", "ネイル",
        "ヘアケア", "シャンプー", "beauty", "cosmetic", "skincare",
        "makeup", "hair care", "salon", "aesthetic", "脂肪吸引",
        "二重", "整形", "ボトックス", "ヒアルロン酸", "アンチエイジング",
        "ホワイトニング", "美白", "保湿", "セラム", "ファンデ",
    ], 10),

    # ── Health / Supplements ──────────────────────────────────────
    (AdCategoryEnum.HEALTH, [
        "健康", "サプリ", "医療", "薬", "ヘルスケア", "漢方",
        "プロテイン", "ビタミン", "乳酸菌", "腸活", "免疫",
        "health", "supplement", "medical", "pharmacy", "wellness",
        "cbd", "睡眠", "快眠", "疲労", "肩こり", "腰痛",
    ], 9),

    # ── Finance / Investment ──────────────────────────────────────
    (AdCategoryEnum.FINANCE, [
        "金融", "投資", "保険", "ローン", "fx", "口座", "クレジットカード",
        "キャッシング", "カードローン", "証券", "仮想通貨", "暗号資産",
        "nisa", "ideco", "資産運用", "finance", "investment", "insurance",
        "loan", "credit", "banking", "fintech", "株", "つみたて",
        "不動産投資",  # financial context of real-estate investment
    ], 10),

    # ── Real Estate ───────────────────────────────────────────────
    (AdCategoryEnum.REAL_ESTATE, [
        "不動産", "マンション", "住宅", "賃貸", "分譲", "注文住宅",
        "リフォーム", "引越", "引っ越し", "real estate", "property",
        "apartment", "housing", "rent", "物件", "新築", "中古マンション",
    ], 9),

    # ── Education ─────────────────────────────────────────────────
    (AdCategoryEnum.EDUCATION, [
        "教育", "学習", "スクール", "塾", "英語", "プログラミング",
        "資格", "通信講座", "オンライン学習", "eラーニング",
        "education", "learning", "school", "academy", "course",
        "tutoring", "英会話", "toeic", "toefl", "受験",
        "予備校", "大学", "留学", "study",
    ], 9),

    # ── Food / Beverage ───────────────────────────────────────────
    (AdCategoryEnum.FOOD, [
        "食品", "グルメ", "飲料", "レストラン", "料理", "お取り寄せ",
        "デリバリー", "出前", "food", "restaurant", "delivery",
        "recipe", "cooking", "ドリンク", "ワイン", "ビール",
        "コーヒー", "スイーツ", "弁当", "宅配",
        "ウォーターサーバー", "ミールキット",
    ], 8),

    # ── Technology / SaaS ─────────────────────────────────────────
    (AdCategoryEnum.TECHNOLOGY, [
        "テクノロジー", "ソフト", "saas", "crm", "erp",
        "クラウド", "セキュリティ", "technology", "software",
        "cloud", "ai", "人工知能", "機械学習", "iot", "api",
        "データ分析", "analytics", "automation", "自動化",
        "rpa", "vpn", "サーバー",
    ], 8),

    # ── App (mobile apps) ─────────────────────────────────────────
    (AdCategoryEnum.APP, [
        "アプリ", "app", "ダウンロード", "download", "install",
        "google play", "app store", "ios", "android",
        "マッチング", "出会い", "婚活", "恋活",
        "ポイ活", "フリマ", "メルカリ",
    ], 7),

    # ── Gaming ────────────────────────────────────────────────────
    (AdCategoryEnum.GAMING, [
        "ゲーム", "game", "gaming", "rpg", "mmorpg",
        "パズル", "ガチャ", "リセマラ", "eスポーツ",
        "steam", "playstation", "nintendo", "xbox",
        "オンラインゲーム", "ソシャゲ", "スマホゲーム",
    ], 9),

    # ── Travel / Tourism ──────────────────────────────────────────
    (AdCategoryEnum.TRAVEL, [
        "旅行", "ホテル", "航空", "travel", "hotel", "flight",
        "booking", "ツアー", "温泉", "観光", "リゾート",
        "airbnb", "expedia", "じゃらん", "楽天トラベル",
        "一休", "agoda",
    ], 9),

    # ── EC / D2C (e-commerce / direct-to-consumer) ────────────────
    (AdCategoryEnum.EC_D2C, [
        "通販", "ショッピング", "セール", "送料無料", "ec",
        "d2c", "ecommerce", "e-commerce", "shop", "store",
        "買い物", "オンラインストア", "amazon", "楽天",
        "yahoo!ショッピング", "限定", "割引", "クーポン",
        "ファッション", "服", "アパレル", "シューズ", "コーデ",
        "バッグ", "アクセサリー", "fashion",
    ], 6),  # lower weight -- acts as catch-all for commerce
]


def _build_search_text(ad: Ad) -> str:
    """Concatenate all searchable text from an ad into a single lowercase string."""
    parts: list[str] = []

    if ad.title:
        parts.append(ad.title)
    if ad.description:
        parts.append(ad.description)
    if ad.advertiser_name:
        parts.append(ad.advertiser_name)
    if ad.destination_url:
        parts.append(ad.destination_url)
    if ad.brand_name:
        parts.append(ad.brand_name)

    # Extract useful text from ad_metadata JSON
    meta = ad.ad_metadata
    if meta and isinstance(meta, dict):
        for key in ("page_name", "byline", "disclaimer", "cta_text",
                     "link_title", "link_description", "body",
                     "advertiser", "page_categories", "languages"):
            val = meta.get(key)
            if val:
                if isinstance(val, list):
                    parts.append(" ".join(str(v) for v in val))
                elif isinstance(val, str):
                    parts.append(val)
                else:
                    parts.append(str(val))

    return " ".join(parts).lower()


def classify(ad: Ad) -> AdCategoryEnum:
    """Return the best-matching category for an ad based on keyword matching."""
    text = _build_search_text(ad)
    if not text.strip():
        return AdCategoryEnum.OTHER

    # Score each category: count how many distinct keywords matched, weighted
    scores: dict[AdCategoryEnum, int] = {}
    for category, keywords, weight in CATEGORY_RULES:
        match_count = 0
        for kw in keywords:
            if kw.lower() in text:
                match_count += 1
        if match_count > 0:
            scores[category] = match_count * weight

    if not scores:
        return AdCategoryEnum.OTHER

    # Return category with highest score
    best = max(scores, key=lambda c: scores[c])
    return best


def main() -> None:
    session = SyncSessionLocal()

    try:
        # ── Step 1: Show current state ────────────────────────────
        total = session.query(Ad).count()
        null_count = session.query(Ad).filter(Ad.category.is_(None)).count()
        print(f"Total ads in database: {total}")
        print(f"Ads with NULL category: {null_count}")

        if null_count == 0:
            print("All ads already have a category. Nothing to do.")
            return

        # ── Step 2: Show 10 sample ads before classification ──────
        print("\n--- Sample ads (first 10 with NULL category) ---")
        samples = session.query(Ad).filter(Ad.category.is_(None)).limit(10).all()
        for ad in samples:
            print(f"  ID={ad.id}  advertiser={ad.advertiser_name!r}  "
                  f"title={ad.title!r}  desc={str(ad.description or '')[:80]!r}")

        # ── Step 3: Classify all NULL-category ads ────────────────
        print(f"\nClassifying {null_count} ads ...")
        null_ads = session.query(Ad).filter(Ad.category.is_(None)).all()

        category_counter: Counter = Counter()
        for ad in null_ads:
            cat = classify(ad)
            ad.category = cat
            category_counter[cat.value] += 1

        session.commit()
        print("Classification complete. Committed to database.")

        # ── Step 4: Report distribution ───────────────────────────
        print("\n--- Category distribution ---")
        for cat_val, count in sorted(category_counter.items(), key=lambda x: -x[1]):
            print(f"  {cat_val:20s} : {count}")
        print(f"  {'TOTAL':20s} : {sum(category_counter.values())}")

        # ── Step 5: Verify no NULLs remain ────────────────────────
        remaining_null = session.query(Ad).filter(Ad.category.is_(None)).count()
        print(f"\nRemaining ads with NULL category: {remaining_null}")
        if remaining_null == 0:
            print("SUCCESS: All ads have been classified.")
        else:
            print(f"WARNING: {remaining_null} ads still have NULL category.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
