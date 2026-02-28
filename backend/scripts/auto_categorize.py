#!/usr/bin/env python3
"""Auto-categorize ads with NULL category using keyword matching.

Scans title + description for genre-specific keywords and assigns the
best matching AdCategoryEnum value.

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/auto_categorize.py
"""

import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdCategoryEnum


# ── Category Keywords ────────────────────────────────────────────────────

CATEGORY_KEYWORDS: dict[AdCategoryEnum, list[str]] = {
    AdCategoryEnum.BEAUTY: [
        "美容", "スキンケア", "化粧", "美白", "肌", "コスメ", "メイク",
        "クレンジング", "美容液", "保湿", "シミ", "シワ", "たるみ",
        "エステ", "脱毛", "医療脱毛", "美容クリニック", "ヒアルロン酸",
        "ボトックス", "二重", "美容整形", "ダイエット", "痩せ", "体重",
        "減量", "脂肪", "痩身", "GLP-1", "ウゴービ", "マンジャロ",
        "フェイシャル", "アンチエイジング", "リフトアップ",
    ],
    AdCategoryEnum.HEALTH: [
        "健康", "サプリ", "栄養", "ビタミン", "乳酸菌", "酵素",
        "青汁", "コラーゲン", "プロテイン", "筋トレ", "フィットネス",
        "ジム", "パーソナル", "ヨガ", "ピラティス", "BCAA", "HMB",
        "育毛", "AGA", "薄毛", "発毛", "ミノキシジル",
        "免疫", "腸活", "デトックス",
    ],
    AdCategoryEnum.EC_D2C: [
        "通販", "ショッピング", "セール", "割引", "お買い得",
        "送料無料", "定期購入", "定期便", "初回限定",
        "EC", "D2C", "お取り寄せ", "ギフト",
    ],
    AdCategoryEnum.FOOD: [
        "食品", "グルメ", "レストラン", "料理", "レシピ",
        "お取り寄せ", "スイーツ", "ケーキ", "ワイン", "コーヒー",
        "宅配", "ミールキット", "冷凍", "オーガニック",
    ],
    AdCategoryEnum.APP: [
        "アプリ", "ダウンロード", "インストール", "ゲーム",
        "App Store", "Google Play", "マッチング",
    ],
    AdCategoryEnum.FINANCE: [
        "投資", "FX", "仮想通貨", "クレジットカード", "ローン",
        "保険", "株", "資産運用", "NISA", "iDeCo", "不動産投資",
    ],
    AdCategoryEnum.EDUCATION: [
        "スクール", "講座", "資格", "プログラミング", "英会話",
        "学習", "オンライン", "セミナー", "教育",
    ],
    AdCategoryEnum.TECHNOLOGY: [
        "テクノロジー", "IT", "SaaS", "クラウド", "AI",
        "DX", "システム", "ソフトウェア",
    ],
    AdCategoryEnum.REAL_ESTATE: [
        "マンション", "不動産", "賃貸", "住宅", "一戸建て",
        "リフォーム", "引越し",
    ],
    AdCategoryEnum.TRAVEL: [
        "旅行", "ホテル", "航空", "ツアー", "予約",
        "温泉", "リゾート",
    ],
    AdCategoryEnum.GAMING: [
        "ゲーム", "RPG", "オンラインゲーム", "e-sports",
        "ガチャ", "課金",
    ],
}


def classify_ad(ad: Ad) -> AdCategoryEnum | None:
    """Classify an ad based on keyword matching in title + description."""
    text = f"{ad.title or ''} {ad.description or ''}".lower()
    if not text.strip():
        return None

    scores: Counter = Counter()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[category] += 1

    if not scores:
        return AdCategoryEnum.OTHER

    best = scores.most_common(1)[0]
    return best[0]


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        # Find ads with NULL category
        null_ads = session.query(Ad).filter(Ad.category.is_(None)).all()
        print(f"[auto_categorize] Ads with NULL category: {len(null_ads)}")

        if not null_ads:
            print("  Nothing to do.")
            return

        distribution: Counter = Counter()
        updated = 0

        for ad in null_ads:
            category = classify_ad(ad)
            if category:
                ad.category = category
                distribution[category.value] += 1
                updated += 1

        session.commit()
        print(f"  Categorized: {updated}/{len(null_ads)}")
        print(f"\n  Distribution:")
        for cat, count in distribution.most_common():
            print(f"    {cat}: {count}")

        # Verify
        remaining = session.query(Ad).filter(Ad.category.is_(None)).count()
        print(f"\n  Remaining NULL: {remaining}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
