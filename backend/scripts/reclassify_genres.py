#!/usr/bin/env python3
"""Re-classify all ads with expanded genre taxonomy.

Adds short_drama, manga_webtoon, gaming_entertainment genres
and expands fitness/ec_shopping keywords.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/reclassify_genres.py
"""
import sqlite3
import json
from collections import Counter
from datetime import datetime, timezone

DB_PATH = "vaap_local.db"

# ── English/Brand keyword taxonomy ──────────────────────────
FINE_GENRE_TAXONOMY = [
    ("medical_weight_loss", [
        "GLP-1", "glp-1", "GLP1", "glp1",
        "semaglutide", "tirzepatide",
        "ozempic", "wegovy", "mounjaro", "zepbound",
    ], 15),
    ("diet_supplement", [
        "lactoferrin", "carnitine", "chitosan",
        "garcinia", "forskolin", "capsaicin",
    ], 12),
    ("beauty_clinic", [
        "hyaluronic", "botox", "juvederm", "restylane",
        "thermage", "hifu", "HIFU",
        "blepharoplasty", "rhinoplasty",
    ], 14),
    ("skincare", [
        "retinol", "niacinamide", "ceramide",
        "vitamin C serum", "hyaluronic acid",
    ], 11),
    ("hair_removal", [
        "IPL", "SHR", "VIO",
        "alexandrite", "diode laser",
    ], 13),
    ("hair_growth_aga", [
        "minoxidil", "finasteride", "dutasteride",
        "AGA", "aga", "FAGA",
    ], 13),
    ("fitness", [
        "RIZAP", "rizap", "BEYOND",
        "Anytime Fitness",
        "Gold's Gym", "JOYFIT",
        "BetterMe", "betterme", "wall pilates",
    ], 11),
    ("yoga_pilates", [
        "LAVA", "zen place",
        "Bikram", "ashtanga",
    ], 12),
    ("protein_supplement", [
        "BCAA", "bcaa", "HMB", "hmb",
        "creatine", "EAA", "eaa",
        "whey", "casein",
    ], 12),
    ("health_food", [
        "collagen peptide",
        "probiotics", "prebiotics",
        "chlorella", "spirulina",
    ], 10),
    ("ec_shopping", [
        "Qoo10", "qoo10", "SHEIN", "shein",
        "ZOZOTOWN", "Rakuten",
        "animate", "criteo.com",
    ], 9),
    ("app", [
        "Google Play", "App Store",
        "iOS app", "Android app",
        "play.google.com", "itunes.apple.com",
    ], 9),
    ("finance_investment", [
        "NISA", "nisa", "iDeCo", "ideco",
        "FX", "ETF", "bitcoin", "Bitcoin",
    ], 11),
    ("education_school", [
        "TOEIC", "TOEFL", "IELTS",
        "Udemy", "Coursera",
    ], 10),
    ("real_estate", [
        "SUUMO", "suumo", "LIFULL",
        "HOME'S", "homes",
    ], 10),
    ("jobs_recruitment", [
        "Indeed", "doda", "Recruit",
        "mynavi", "rikunabi",
    ], 10),
    # ── NEW: Short Drama / Mini Drama ─────────────────
    ("short_drama", [
        "DramaBox", "dramabox", "DramaWave", "dramawave",
        "Flick", "FlickReels", "flickreels",
        "Reelstv", "reelstv", "ShortMax", "shortmax",
        "Stardusttv", "stardusttv", "NetShort", "netshort",
        "iDrama", "idrama", "DramaBite", "dramabite",
        "DramaBuzz", "dramabuzz", "DramaKita", "dramakita",
        "MoboShort", "moboshort", "shorttv",
        "short drama", "Short Drama", "mini drama", "Mini Drama",
        "farsunpteltd", "sdtv", "dramawav",
        "bdedssql", "bvhwysgng", "bvuagb",
    ], 14),
    # ── NEW: Manga / Webtoon ─────────────────
    ("manga_webtoon", [
        "manga", "Manga", "webtoon", "Webtoon",
        "comic", "Comic", "Renta", "renta",
        "Comico", "comico", "pixiv",
    ], 10),
    # ── NEW: Gaming / VR / Entertainment ─────────────
    ("gaming_entertainment", [
        "Meta Quest", "meta quest", "Oculus",
        "PlayStation", "Xbox", "Nintendo",
        "Steam", "Epic Games",
        "VR game", "VR Game",
    ], 10),
]

# ── Japanese keyword layer ──────────────────────────
JP_GENRE_KEYWORDS = [
    ("medical_weight_loss", [
        "\u533b\u7642\u75e9\u8eab",        # 医療痩身
        "\u30de\u30f3\u30b8\u30e3\u30ed",    # マンジャロ
        "\u30a6\u30b4\u30fc\u30d3",          # ウゴービ
        "\u75e9\u8eab\u30af\u30ea\u30cb\u30c3\u30af",  # 痩身クリニック
        "\u533b\u7642\u30c0\u30a4\u30a8\u30c3\u30c8",  # 医療ダイエット
        "\u8102\u80aa\u5438\u5f15",          # 脂肪吸引
        "\u8102\u80aa\u51b7\u5374",          # 脂肪冷却
        "\u75e9\u8eab\u6ce8\u5c04",          # 痩身注射
        "\u8102\u80aa\u6eb6\u89e3",          # 脂肪溶解
        "\u30b5\u30af\u30bb\u30f3\u30c0",    # サクセンダ
        "\u30ea\u30d9\u30eb\u30b5\u30b9",    # リベルサス
        "\u30aa\u30bc\u30f3\u30d4\u30c3\u30af",  # オゼンピック
    ], 15),
    ("diet_supplement", [
        "\u30c0\u30a4\u30a8\u30c3\u30c8\u30b5\u30d7\u30ea",  # ダイエットサプリ
        "\u75e9\u305b\u308b\u30b5\u30d7\u30ea",  # 痩せるサプリ
        "\u8102\u80aa\u71c3\u713c",          # 脂肪燃焼
        "\u4ee3\u8b1d\u30a2\u30c3\u30d7",    # 代謝アップ
        "\u7f6e\u304d\u63db\u3048",          # 置き換え
        "\u7cd6\u8cea\u30ab\u30c3\u30c8",    # 糖質カット
        "\u98df\u6b32\u6291\u5236",          # 食欲抑制
        "\u6e1b\u91cf",                      # 減量
        "\u4f53\u91cd",                      # 体重
        "\u30b9\u30ea\u30e0",                # スリム
        "\u9ad8\u30bf\u30f3\u30d1\u30af",    # 高タンパク
        "\u4f4e\u30ab\u30ed\u30ea\u30fc",    # 低カロリー
        "\u30de\u30c3\u30b9\u30eb\u30c7\u30ea",  # マッスルデリ
    ], 12),
    ("beauty_clinic", [
        "\u7f8e\u5bb9\u30af\u30ea\u30cb\u30c3\u30af",  # 美容クリニック
        "\u7f8e\u5bb9\u6574\u5f62",          # 美容整形
        "\u30d2\u30a2\u30eb\u30ed\u30f3\u9178",  # ヒアルロン酸
        "\u30dc\u30c8\u30c3\u30af\u30b9",    # ボトックス
        "\u4e8c\u91cd",                      # 二重
        "\u7f8e\u5bb9\u5916\u79d1",          # 美容外科
        "\u305f\u308b\u307f",                # たるみ
        "\u30b7\u30ef",                      # シワ
        "\u30b7\u30df",                      # シミ
        "\u5c0f\u9854",                      # 小顔
        "\u7f8e\u5bb9\u30b5\u30ed\u30f3",    # 美容サロン
        "\u7f8e\u5bb9\u76ae\u819a\u79d1",    # 美容皮膚科
        "\u8a17\u5150\u6240\u4ed8\u304d\u7f8e\u5bb9",  # 託児所付き美容
    ], 14),
    ("skincare", [
        "\u30b9\u30ad\u30f3\u30b1\u30a2",    # スキンケア
        "\u5316\u7ca7\u6c34",                # 化粧水
        "\u7f8e\u5bb9\u6db2",                # 美容液
        "\u4fdd\u6e7f",                      # 保湿
        "\u7f8e\u767d",                      # 美白
        "\u7f8e\u808c",                      # 美肌
        "\u5316\u7ca7\u54c1",                # 化粧品
        "\u30b3\u30b9\u30e1",                # コスメ
        "\u30e1\u30a4\u30af",                # メイク
        "\u6d17\u9854",                      # 洗顔
        "\u65e5\u713c\u3051\u6b62\u3081",    # 日焼け止め
        "\u6bdb\u7a74",                      # 毛穴
        "\u30cb\u30ad\u30d3",                # ニキビ
    ], 11),
    ("hair_removal", [
        "\u8131\u6bdb",                      # 脱毛
        "\u533b\u7642\u8131\u6bdb",          # 医療脱毛
        "\u5149\u8131\u6bdb",                # 光脱毛
        "\u5168\u8eab\u8131\u6bdb",          # 全身脱毛
        "\u30e0\u30c0\u6bdb",                # ムダ毛
    ], 13),
    ("hair_growth_aga", [
        "\u80b2\u6bdb",                      # 育毛
        "\u8584\u6bdb",                      # 薄毛
        "\u767a\u6bdb",                      # 発毛
        "\u629c\u3051\u6bdb",                # 抜け毛
        "\u982d\u76ae",                      # 頭皮
        "\u80b2\u6bdb\u5264",                # 育毛剤
        "\u9aea",                            # 髪
    ], 13),
    ("fitness", [
        "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",  # フィットネス
        "\u30b8\u30e0",                      # ジム
        "\u30c8\u30ec\u30fc\u30cb\u30f3\u30b0",  # トレーニング
        "\u30dc\u30c7\u30a3\u30e1\u30a4\u30af",  # ボディメイク
        "\u7b4b\u30c8\u30ec",                # 筋トレ
        "\u30a8\u30af\u30b5\u30b5\u30a4\u30ba",  # エクササイズ
        "\u30ef\u30fc\u30af\u30a2\u30a6\u30c8",  # ワークアウト
        "\u7b4b\u529b",                      # 筋力
        "\u6301\u4e45\u529b",                # 持久力
        "\u67d4\u8edf\u6027",                # 柔軟性
        "\u59ff\u52e2",                      # 姿勢
        "\u5909\u8eab",                      # 変身
    ], 11),
    ("yoga_pilates", [
        "\u30e8\u30ac",                      # ヨガ
        "\u30d4\u30e9\u30c6\u30a3\u30b9",    # ピラティス
        "\u30b9\u30c8\u30ec\u30c3\u30c1",    # ストレッチ
        "\u7792\u60f3",                      # 瞑想
    ], 12),
    ("protein_supplement", [
        "\u30d7\u30ed\u30c6\u30a4\u30f3",    # プロテイン
        "\u30db\u30a8\u30a4",                # ホエイ
    ], 12),
    ("health_food", [
        "\u5065\u5eb7\u98df\u54c1",          # 健康食品
        "\u9752\u6c41",                      # 青汁
        "\u30b3\u30e9\u30fc\u30b2\u30f3",    # コラーゲン
        "\u4e73\u9178\u83cc",                # 乳酸菌
        "\u30d3\u30bf\u30df\u30f3",          # ビタミン
        "\u30b5\u30d7\u30ea\u30e1\u30f3\u30c8",  # サプリメント
        "\u30b5\u30d7\u30ea",                # サプリ
        "\u8178\u6d3b",                      # 腸活
        "\u514d\u75ab",                      # 免疫
        "\u5065\u5eb7",                      # 健康
    ], 10),
    ("ec_shopping", [
        "\u901a\u8ca9",                      # 通販
        "\u30b7\u30e7\u30c3\u30d4\u30f3\u30b0",  # ショッピング
        "\u30bb\u30fc\u30eb",                # セール
        "\u5272\u5f15",                      # 割引
        "\u9001\u6599\u7121\u6599",          # 送料無料
        "\u30af\u30fc\u30dd\u30f3",          # クーポン
    ], 9),
    ("app", [
        "\u30a2\u30d7\u30ea",                # アプリ
        "\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9",  # ダウンロード
        "\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb",  # インストール
        "\u30de\u30c3\u30c1\u30f3\u30b0",    # マッチング
        "\u51fa\u4f1a\u3044",                # 出会い
        "\u5a5a\u6d3b",                      # 婚活
    ], 9),
    ("finance_investment", [
        "\u6295\u8cc7",                      # 投資
        "\u4eee\u60f3\u901a\u8ca8",          # 仮想通貨
        "\u30ed\u30fc\u30f3",                # ローン
        "\u8a3c\u5238",                      # 証券
        "\u8cc7\u7523\u904b\u7528",          # 資産運用
        "\u91d1\u878d",                      # 金融
        "\u4fdd\u967a",                      # 保険
        "\u682a",                            # 株
    ], 11),
    ("education_school", [
        "\u30b9\u30af\u30fc\u30eb",          # スクール
        "\u8b1b\u5ea7",                      # 講座
        "\u8cc7\u683c",                      # 資格
        "\u82f1\u4f1a\u8a71",                # 英会話
        "\u5b66\u7fd2",                      # 学習
        "\u6559\u80b2",                      # 教育
        "\u585e",                            # 塾
    ], 10),
    ("real_estate", [
        "\u4e0d\u52d5\u7523",                # 不動産
        "\u30de\u30f3\u30b7\u30e7\u30f3",    # マンション
        "\u8cc3\u8cb8",                      # 賃貸
        "\u4f4f\u5b85",                      # 住宅
        "\u7269\u4ef6",                      # 物件
        "\u65b0\u7bc9",                      # 新築
    ], 10),
    ("jobs_recruitment", [
        "\u8ee2\u8077",                      # 転職
        "\u6c42\u4eba",                      # 求人
        "\u30d0\u30a4\u30c8",                # バイト
        "\u5c31\u8077",                      # 就職
        "\u63a1\u7528",                      # 採用
        "\u6d3e\u9063",                      # 派遣
        "\u526f\u696d",                      # 副業
    ], 10),
    # ── NEW genres ──
    ("short_drama", [
        "\u30b7\u30e7\u30fc\u30c8\u30c9\u30e9\u30de",  # ショートドラマ
        "\u77ed\u7de8\u30c9\u30e9\u30de",    # 短編ドラマ
        "\u30df\u30cb\u30c9\u30e9\u30de",    # ミニドラマ
        "\u5439\u66ff\u7248",                # 吹替版
        "\u5439\u304d\u66ff\u3048",          # 吹き替え
        "\u8ee2\u751f",                      # 転生
        "\u4eca\u3059\u3050\u898b\u308b",    # 今すぐ見る
        "\u4eba\u6c17\u306e\u77ed\u7de8",    # 人気の短編
        "\u7d4c\u5178\u77ed\u5287",          # 經典短劇
    ], 14),
    ("manga_webtoon", [
        "\u30de\u30f3\u30ac",                # マンガ
        "\u6f2b\u753b",                      # 漫画
        "\u30b3\u30df\u30c3\u30af",          # コミック
        "\u30a6\u30a7\u30d6\u30c8\u30a5\u30fc\u30f3",  # ウェブトゥーン
    ], 10),
    ("gaming_entertainment", [
        "\u30b2\u30fc\u30e0",                # ゲーム
        "VR",
    ], 10),
]

# Display labels (Japanese)
GENRE_DISPLAY_JP = {
    "medical_weight_loss": "\u533b\u7642\u75e9\u8eab",
    "diet_supplement": "\u30c0\u30a4\u30a8\u30c3\u30c8\u30b5\u30d7\u30ea",
    "beauty_clinic": "\u7f8e\u5bb9\u30af\u30ea\u30cb\u30c3\u30af",
    "skincare": "\u30b9\u30ad\u30f3\u30b1\u30a2",
    "hair_removal": "\u8131\u6bdb",
    "hair_growth_aga": "\u80b2\u6bdb\u30fbAGA",
    "fitness": "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",
    "yoga_pilates": "\u30e8\u30ac\u30fb\u30d4\u30e9\u30c6\u30a3\u30b9",
    "protein_supplement": "\u30d7\u30ed\u30c6\u30a4\u30f3",
    "health_food": "\u5065\u5eb7\u98df\u54c1",
    "ec_shopping": "EC\u901a\u8ca9",
    "app": "\u30a2\u30d7\u30ea",
    "finance_investment": "\u91d1\u878d\u30fb\u6295\u8cc7",
    "education_school": "\u6559\u80b2\u30fb\u30b9\u30af\u30fc\u30eb",
    "real_estate": "\u4e0d\u52d5\u7523",
    "jobs_recruitment": "\u8ee2\u8077\u30fb\u6c42\u4eba",
    "short_drama": "\u30b7\u30e7\u30fc\u30c8\u30c9\u30e9\u30de",
    "manga_webtoon": "\u30de\u30f3\u30ac\u30fb\u30a6\u30a7\u30d6\u30c8\u30a5\u30fc\u30f3",
    "gaming_entertainment": "\u30b2\u30fc\u30e0\u30fb\u30a8\u30f3\u30bf\u30e1",
    "other": "\u305d\u306e\u4ed6",
}


def classify(title, desc, adv, brand, dest_url, meta_str):
    """Classify an ad into a fine-grained genre using keyword matching."""
    parts = [p for p in [title, desc, adv, brand, dest_url] if p]
    if meta_str:
        try:
            meta = json.loads(meta_str)
            for key in ("page_name", "byline", "disclaimer", "cta_text",
                        "link_title", "link_description", "body",
                        "advertiser", "page_categories"):
                val = meta.get(key)
                if val:
                    if isinstance(val, list):
                        parts.append(" ".join(str(v) for v in val))
                    elif isinstance(val, str):
                        parts.append(val)
        except (json.JSONDecodeError, TypeError):
            pass

    text = " ".join(parts)
    if not text.strip():
        return "other"

    text_lower = text.lower()
    genre_scores = {}

    # Score JP keywords (primary)
    for slug, keywords, weight in JP_GENRE_KEYWORDS:
        match_count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if match_count > 0:
            genre_scores[slug] = genre_scores.get(slug, 0) + match_count * weight

    # Score EN/brand keywords (supplementary)
    for slug, keywords, weight in FINE_GENRE_TAXONOMY:
        match_count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if match_count > 0:
            genre_scores[slug] = genre_scores.get(slug, 0) + match_count * weight

    if not genre_scores:
        return "other"

    return max(genre_scores, key=lambda s: genre_scores[s])


def main():
    print("=" * 60)
    print("Fine-Grained Genre Re-Classification")
    print(f"  New genres: short_drama, manga_webtoon, gaming_entertainment")
    print(f"  Expanded: fitness, diet_supplement, beauty_clinic, ec_shopping")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, description, advertiser_name, brand_name, "
        "destination_url, metadata FROM ads"
    )
    rows = cur.fetchall()
    total = len(rows)
    print(f"\nTotal ads: {total}")

    genre_counter = Counter()
    now = datetime.now(timezone.utc).isoformat()
    updates = []

    for row in rows:
        ad_id, title, desc, adv, brand, dest_url, meta_str = row
        slug = classify(title, desc, adv, brand, dest_url, meta_str)
        jp_label = GENRE_DISPLAY_JP.get(slug, slug)

        meta = json.loads(meta_str) if meta_str else {}
        meta["fine_genre"] = jp_label
        meta["fine_genre_en"] = slug
        meta["fine_genre_classified_at"] = now
        updates.append((json.dumps(meta, ensure_ascii=False), now, ad_id))
        genre_counter[slug] += 1

    cur.executemany(
        "UPDATE ads SET metadata = ?, updated_at = ? WHERE id = ?",
        updates,
    )
    conn.commit()
    conn.close()

    print(f"Updated {len(updates)} ads. Committed.\n")
    print("--- Fine Genre Distribution ---")
    for slug, count in sorted(genre_counter.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {slug:<25s} {count:>4d} ({pct:>5.1f}%) {bar}")

    classified = sum(c for s, c in genre_counter.items() if s != "other")
    other_count = genre_counter.get("other", 0)
    print()
    print(f"  Classified:        {classified} ({classified / total * 100:.1f}%)")
    print(f"  Other (unmatched): {other_count} ({other_count / total * 100:.1f}%)")
    print(f"  Unique genres:     {len(genre_counter)}")
    print(f"\nDone!")


if __name__ == "__main__":
    main()
