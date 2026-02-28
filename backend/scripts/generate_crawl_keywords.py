#!/usr/bin/env python3
"""Generate crawl keywords for underrepresented genres.

Analyzes current fine_genre distribution from ad_metadata, identifies
underrepresented genres, and generates targeted Japanese search keywords
for Meta Ad Library API (country=JP, language=ja).

Outputs:
  - Console: genre gap analysis table
  - backend/exports/crawl_keywords.json

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_crawl_keywords.py
"""

import io
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Target genre minimum counts
# ---------------------------------------------------------------------------
# For genres that are well-represented, keep their current count as target.
# For underrepresented genres, set a reasonable target based on overall DB size.
DEFAULT_TARGET_COUNT = 30


# ---------------------------------------------------------------------------
# Japanese crawl keywords by genre
# Each genre has 5-10 keywords designed for Meta Ad Library API search
# (country=JP, language=ja). Keywords use natural Japanese search terms
# that advertisers in each genre would typically use.
# ---------------------------------------------------------------------------

GENRE_CRAWL_KEYWORDS: dict[str, dict] = {
    "finance_investment": {
        "label": "Finance / Investment",
        "keywords": [
            "FX \u6295\u8cc7",                    # FX 投資
            "\u4eee\u60f3\u901a\u8ca8",            # 仮想通貨
            "\u682a\u5f0f\u6295\u8cc7",            # 株式投資
            "NISA \u3064\u307f\u305f\u3066",       # NISA つみたて
            "\u8cc7\u7523\u904b\u7528",            # 資産運用
            "\u30af\u30ec\u30b8\u30c3\u30c8\u30ab\u30fc\u30c9 \u304a\u3059\u3059\u3081",  # クレジットカード おすすめ
            "\u4e0d\u52d5\u7523\u6295\u8cc7",      # 不動産投資
            "\u4fdd\u967a \u898b\u76f4\u3057",     # 保険 見直し
            "iDeCo \u53e3\u5ea7\u958b\u8a2d",     # iDeCo 口座開設
            "\u30ed\u30fc\u30f3 \u4f4e\u91d1\u5229",  # ローン 低金利
        ],
    },
    "app": {
        "label": "App",
        "keywords": [
            "\u30a2\u30d7\u30ea \u30c0\u30a6\u30f3\u30ed\u30fc\u30c9",  # アプリ ダウンロード
            "\u30b2\u30fc\u30e0\u30a2\u30d7\u30ea",  # ゲームアプリ
            "\u30de\u30c3\u30c1\u30f3\u30b0\u30a2\u30d7\u30ea",  # マッチングアプリ
            "\u5a5a\u6d3b\u30a2\u30d7\u30ea",      # 婚活アプリ
            "\u5bb6\u8a08\u7c3f\u30a2\u30d7\u30ea",  # 家計簿アプリ
            "\u30d5\u30ea\u30de\u30a2\u30d7\u30ea",  # フリマアプリ
            "\u6f2b\u753b\u30a2\u30d7\u30ea",      # 漫画アプリ
            "\u52d5\u753b\u914d\u4fe1\u30a2\u30d7\u30ea",  # 動画配信アプリ
        ],
    },
    "ec_shopping": {
        "label": "EC / Shopping",
        "keywords": [
            "\u901a\u8ca9 \u30bb\u30fc\u30eb",    # 通販 セール
            "Qoo10 \u30e1\u30ac\u5272",           # Qoo10 メガ割
            "SHEIN \u30d5\u30a1\u30c3\u30b7\u30e7\u30f3",  # SHEIN ファッション
            "\u697d\u5929 \u30bb\u30fc\u30eb",     # 楽天 セール
            "ZOZOTOWN \u30af\u30fc\u30dd\u30f3",   # ZOZOTOWN クーポン
            "\u30d5\u30a1\u30c3\u30b7\u30e7\u30f3\u901a\u8ca9",  # ファッション通販
            "\u9001\u6599\u7121\u6599 \u30ad\u30e3\u30f3\u30da\u30fc\u30f3",  # 送料無料 キャンペーン
            "D2C \u30d6\u30e9\u30f3\u30c9",        # D2C ブランド
        ],
    },
    "education_school": {
        "label": "Education / School",
        "keywords": [
            "\u30d7\u30ed\u30b0\u30e9\u30df\u30f3\u30b0\u30b9\u30af\u30fc\u30eb",  # プログラミングスクール
            "\u82f1\u4f1a\u8a71 \u30aa\u30f3\u30e9\u30a4\u30f3",  # 英会話 オンライン
            "\u8cc7\u683c \u8b1b\u5ea7",           # 資格 講座
            "\u8ee2\u8077 \u30b9\u30af\u30fc\u30eb",  # 転職 スクール
            "\u30aa\u30f3\u30e9\u30a4\u30f3\u5b66\u7fd2",  # オンライン学習
            "\u585e \u4e88\u5099\u6821",           # 塾 予備校
            "Udemy \u8b1b\u5ea7",                  # Udemy 講座
        ],
    },
    "real_estate": {
        "label": "Real Estate",
        "keywords": [
            "\u30de\u30f3\u30b7\u30e7\u30f3 \u8cfc\u5165",  # マンション 購入
            "\u4e0d\u52d5\u7523 \u58f2\u5374",    # 不動産 売却
            "\u8cc3\u8cb8 \u304a\u90e8\u5c4b\u63a2\u3057",  # 賃貸 お部屋探し
            "\u4f4f\u5b85\u30ed\u30fc\u30f3",      # 住宅ローン
            "\u30ea\u30d5\u30a9\u30fc\u30e0 \u898b\u7a4d\u3082\u308a",  # リフォーム 見積もり
            "SUUMO \u7269\u4ef6",                  # SUUMO 物件
            "\u65b0\u7bc9\u30de\u30f3\u30b7\u30e7\u30f3 \u30e2\u30c7\u30eb\u30eb\u30fc\u30e0",  # 新築マンション モデルルーム
        ],
    },
    "jobs_recruitment": {
        "label": "Jobs / Recruitment",
        "keywords": [
            "\u8ee2\u8077 \u30b5\u30a4\u30c8",    # 転職 サイト
            "\u6c42\u4eba \u63a1\u7528",           # 求人 採用
            "\u30d0\u30a4\u30c8 \u63a2\u3057",     # バイト 探し
            "\u526f\u696d \u5728\u5b85",           # 副業 在宅
            "Indeed \u6c42\u4eba",                 # Indeed 求人
            "\u6d3e\u9063 \u4ed5\u4e8b",           # 派遣 仕事
            "\u30a8\u30f3\u30b8\u30cb\u30a2 \u8ee2\u8077",  # エンジニア 転職
            "\u770b\u8b77\u5e2b \u6c42\u4eba",    # 看護師 求人
        ],
    },
    "entertainment": {
        "label": "Entertainment",
        "keywords": [
            "\u52d5\u753b\u914d\u4fe1 \u30b5\u30d6\u30b9\u30af",  # 動画配信 サブスク
            "\u97f3\u697d \u30b9\u30c8\u30ea\u30fc\u30df\u30f3\u30b0",  # 音楽 ストリーミング
            "\u30e9\u30a4\u30d6\u30c1\u30b1\u30c3\u30c8",  # ライブチケット
            "\u6620\u753b \u516c\u958b",           # 映画 公開
            "\u30a2\u30cb\u30e1 \u65b0\u4f5c",     # アニメ 新作
            "\u30aa\u30f3\u30e9\u30a4\u30f3\u30ab\u30b8\u30ce",  # オンラインカジノ
            "\u96fb\u5b50\u66f8\u7c4d \u8aad\u307f\u653e\u984c",  # 電子書籍 読み放題
        ],
    },
    "travel": {
        "label": "Travel",
        "keywords": [
            "\u65c5\u884c \u4e88\u7d04",           # 旅行 予約
            "\u30db\u30c6\u30eb \u683c\u5b89",     # ホテル 格安
            "\u822a\u7a7a\u5238 \u6700\u5b89\u5024",  # 航空券 最安値
            "\u6e29\u6cc9 \u5bbf\u6cca",           # 温泉 宿泊
            "\u6d77\u5916\u65c5\u884c \u30c4\u30a2\u30fc",  # 海外旅行 ツアー
            "\u30ec\u30f3\u30bf\u30ab\u30fc",      # レンタカー
            "\u56fd\u5185\u65c5\u884c \u304a\u5f97",  # 国内旅行 お得
        ],
    },
    "food_delivery": {
        "label": "Food / Delivery",
        "keywords": [
            "\u30d5\u30fc\u30c9\u30c7\u30ea\u30d0\u30ea\u30fc",  # フードデリバリー
            "\u51fa\u524d\u9928",                  # 出前館
            "Uber Eats \u30af\u30fc\u30dd\u30f3",  # Uber Eats クーポン
            "\u5b85\u914d\u5f01\u5f53",            # 宅配弁当
            "\u30df\u30fc\u30eb\u30ad\u30c3\u30c8",  # ミールキット
            "\u304a\u53d6\u308a\u5bc4\u305b \u30b0\u30eb\u30e1",  # お取り寄せ グルメ
        ],
    },
    "insurance": {
        "label": "Insurance",
        "keywords": [
            "\u751f\u547d\u4fdd\u967a \u6bd4\u8f03",  # 生命保険 比較
            "\u81ea\u52d5\u8eca\u4fdd\u967a \u898b\u7a4d\u3082\u308a",  # 自動車保険 見積もり
            "\u533b\u7642\u4fdd\u967a \u304a\u3059\u3059\u3081",  # 医療保険 おすすめ
            "\u706b\u707d\u4fdd\u967a",            # 火災保険
            "\u30da\u30c3\u30c8\u4fdd\u967a",      # ペット保険
            "\u304c\u3093\u4fdd\u967a",            # がん保険
        ],
    },
    "medical_weight_loss": {
        "label": "Medical Weight Loss",
        "keywords": [
            "GLP-1 \u30c0\u30a4\u30a8\u30c3\u30c8",  # GLP-1 ダイエット
            "\u533b\u7642\u75e9\u8eab \u30af\u30ea\u30cb\u30c3\u30af",  # 医療痩身 クリニック
            "\u8102\u80aa\u6eb6\u89e3\u6ce8\u5c04",  # 脂肪溶解注射
            "\u8102\u80aa\u5438\u5f15 \u8cbb\u7528",  # 脂肪吸引 費用
            "\u30af\u30fc\u30eb\u30b9\u30ab\u30eb\u30d7\u30c6\u30a3\u30f3\u30b0",  # クールスカルプティング
            "\u30ea\u30d9\u30eb\u30b5\u30b9 \u75e9\u305b\u308b",  # リベルサス 痩せる
            "\u30e1\u30c7\u30a3\u30ab\u30eb\u30c0\u30a4\u30a8\u30c3\u30c8",  # メディカルダイエット
        ],
    },
    "diet_supplement": {
        "label": "Diet Supplement",
        "keywords": [
            "\u30c0\u30a4\u30a8\u30c3\u30c8\u30b5\u30d7\u30ea",  # ダイエットサプリ
            "\u8102\u80aa\u71c3\u713c\u30b5\u30d7\u30ea",  # 脂肪燃焼サプリ
            "\u7cd6\u8cea\u30ab\u30c3\u30c8 \u30b5\u30d7\u30ea",  # 糖質カット サプリ
            "\u9175\u7d20\u30c0\u30a4\u30a8\u30c3\u30c8",  # 酵素ダイエット
            "\u7f6e\u304d\u63db\u3048\u30c0\u30a4\u30a8\u30c3\u30c8",  # 置き換えダイエット
            "\u30d5\u30a1\u30b9\u30c6\u30a3\u30f3\u30b0 \u30c9\u30ea\u30f3\u30af",  # ファスティング ドリンク
        ],
    },
    "beauty_clinic": {
        "label": "Beauty Clinic",
        "keywords": [
            "\u7f8e\u5bb9\u30af\u30ea\u30cb\u30c3\u30af \u304a\u3059\u3059\u3081",  # 美容クリニック おすすめ
            "\u7f8e\u5bb9\u6574\u5f62 \u4e8c\u91cd",  # 美容整形 二重
            "\u30d2\u30a2\u30eb\u30ed\u30f3\u9178 \u6ce8\u5165",  # ヒアルロン酸 注入
            "\u30dc\u30c8\u30c3\u30af\u30b9 \u30b7\u30ef",  # ボトックス シワ
            "\u7f8e\u5bb9\u76ae\u819a\u79d1",      # 美容皮膚科
            "\u5c0f\u9854\u6574\u5f62",            # 小顔整形
        ],
    },
    "skincare": {
        "label": "Skincare",
        "keywords": [
            "\u30b9\u30ad\u30f3\u30b1\u30a2 \u7f8e\u5bb9\u6db2",  # スキンケア 美容液
            "\u5316\u7ca7\u6c34 \u304a\u3059\u3059\u3081",  # 化粧水 おすすめ
            "\u7f8e\u767d \u30af\u30ea\u30fc\u30e0",  # 美白 クリーム
            "\u6bdb\u7a74\u30b1\u30a2",            # 毛穴ケア
            "\u30cb\u30ad\u30d3 \u5316\u7ca7\u54c1",  # ニキビ 化粧品
            "\u30a8\u30a4\u30b8\u30f3\u30b0\u30b1\u30a2 \u7f8e\u5bb9\u6db2",  # エイジングケア 美容液
        ],
    },
    "hair_removal": {
        "label": "Hair Removal",
        "keywords": [
            "\u533b\u7642\u8131\u6bdb \u304a\u3059\u3059\u3081",  # 医療脱毛 おすすめ
            "\u5168\u8eab\u8131\u6bdb \u30ad\u30e3\u30f3\u30da\u30fc\u30f3",  # 全身脱毛 キャンペーン
            "\u30e1\u30f3\u30ba\u8131\u6bdb",      # メンズ脱毛
            "VIO\u8131\u6bdb",                     # VIO脱毛
            "\u30d2\u30b2\u8131\u6bdb \u30af\u30ea\u30cb\u30c3\u30af",  # ヒゲ脱毛 クリニック
            "\u8131\u6bdb\u30b5\u30ed\u30f3 \u53e3\u30b3\u30df",  # 脱毛サロン 口コミ
        ],
    },
    "hair_growth_aga": {
        "label": "Hair Growth / AGA",
        "keywords": [
            "AGA \u30af\u30ea\u30cb\u30c3\u30af",  # AGA クリニック
            "\u80b2\u6bdb\u5264 \u304a\u3059\u3059\u3081",  # 育毛剤 おすすめ
            "\u8584\u6bdb\u6cbb\u7642",            # 薄毛治療
            "\u767a\u6bdb \u30af\u30ea\u30cb\u30c3\u30af",  # 発毛 クリニック
            "\u30df\u30ce\u30ad\u30b7\u30b8\u30eb",  # ミノキシジル
            "FAGA \u5973\u6027 \u8584\u6bdb",      # FAGA 女性 薄毛
        ],
    },
    "fitness": {
        "label": "Fitness",
        "keywords": [
            "\u30d1\u30fc\u30bd\u30ca\u30eb\u30b8\u30e0",  # パーソナルジム
            "\u30c0\u30a4\u30a8\u30c3\u30c8 \u30b8\u30e0",  # ダイエット ジム
            "\u7b4b\u30c8\u30ec \u30b8\u30e0",     # 筋トレ ジム
            "RIZAP \u30dc\u30c7\u30a3\u30e1\u30a4\u30af",  # RIZAP ボディメイク
            "24\u6642\u9593\u30b8\u30e0",          # 24時間ジム
            "\u30aa\u30f3\u30e9\u30a4\u30f3\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",  # オンラインフィットネス
        ],
    },
    "yoga_pilates": {
        "label": "Yoga / Pilates",
        "keywords": [
            "\u30e8\u30ac \u30b9\u30bf\u30b8\u30aa",  # ヨガ スタジオ
            "\u30d4\u30e9\u30c6\u30a3\u30b9 \u4f53\u9a13",  # ピラティス 体験
            "\u30db\u30c3\u30c8\u30e8\u30ac",      # ホットヨガ
            "LAVA \u30db\u30c3\u30c8\u30e8\u30ac",  # LAVA ホットヨガ
            "\u30de\u30a4\u30f3\u30c9\u30d5\u30eb\u30cd\u30b9",  # マインドフルネス
            "\u30b9\u30c8\u30ec\u30c3\u30c1 \u30ec\u30c3\u30b9\u30f3",  # ストレッチ レッスン
        ],
    },
    "protein_supplement": {
        "label": "Protein / Supplement",
        "keywords": [
            "\u30d7\u30ed\u30c6\u30a4\u30f3 \u304a\u3059\u3059\u3081",  # プロテイン おすすめ
            "HMB \u30b5\u30d7\u30ea",              # HMB サプリ
            "\u30db\u30a8\u30a4\u30d7\u30ed\u30c6\u30a4\u30f3",  # ホエイプロテイン
            "BCAA \u30b5\u30d7\u30ea",             # BCAA サプリ
            "\u7b4b\u8089 \u30b5\u30d7\u30ea\u30e1\u30f3\u30c8",  # 筋肉 サプリメント
        ],
    },
    "health_food": {
        "label": "Health Food",
        "keywords": [
            "\u5065\u5eb7\u98df\u54c1 \u304a\u3059\u3059\u3081",  # 健康食品 おすすめ
            "\u9752\u6c41 \u304a\u3044\u3057\u3044",  # 青汁 おいしい
            "\u30b3\u30e9\u30fc\u30b2\u30f3\u30c9\u30ea\u30f3\u30af",  # コラーゲンドリンク
            "\u4e73\u9178\u83cc \u30b5\u30d7\u30ea",  # 乳酸菌 サプリ
            "\u9175\u7d20\u30c9\u30ea\u30f3\u30af",  # 酵素ドリンク
            "\u8178\u6d3b \u30b5\u30d7\u30ea",     # 腸活 サプリ
            "\u30d3\u30bf\u30df\u30f3 \u30b5\u30d7\u30ea",  # ビタミン サプリ
        ],
    },
}


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def get_genre_distribution(session) -> tuple[dict[str, int], int]:
    """Query all ads and count fine_genre occurrences from ad_metadata.

    Returns (genre_counts_dict, total_ad_count).
    """
    ads = session.query(Ad.ad_metadata).all()
    total = len(ads)

    genre_counter: Counter = Counter()
    for (meta,) in ads:
        if not meta or not isinstance(meta, dict):
            genre_counter["unclassified"] += 1
            continue
        # Use fine_genre (JP label) or fine_genre_en (EN slug) -- prefer EN slug for keys
        genre = meta.get("fine_genre_en") or meta.get("fine_genre") or "unclassified"
        genre_counter[genre] += 1

    return dict(genre_counter), total


def compute_target_distribution(
    current: dict[str, int],
    total: int,
) -> dict[str, int]:
    """Compute target counts for each genre.

    Strategy:
    - For genres already above DEFAULT_TARGET_COUNT, keep their current count.
    - For genres below DEFAULT_TARGET_COUNT, set target to DEFAULT_TARGET_COUNT.
    - Include all genres from GENRE_CRAWL_KEYWORDS even if they have 0 ads.
    """
    target = {}

    # Include all current genres
    for genre, count in current.items():
        if genre in ("unclassified", "other"):
            target[genre] = count  # no target growth for unclassified
        else:
            target[genre] = max(count, DEFAULT_TARGET_COUNT)

    # Include genres from keyword map that are not yet in DB
    for genre in GENRE_CRAWL_KEYWORDS:
        if genre not in target:
            target[genre] = DEFAULT_TARGET_COUNT

    return target


def build_keywords_by_genre(
    current: dict[str, int],
    target: dict[str, int],
) -> dict[str, dict]:
    """Build the keywords_by_genre structure for output JSON.

    Only includes genres that have a gap (target > current).
    """
    result = {}

    for genre, kw_info in GENRE_CRAWL_KEYWORDS.items():
        current_count = current.get(genre, 0)
        target_count = target.get(genre, DEFAULT_TARGET_COUNT)
        gap = target_count - current_count

        if gap <= 0:
            continue

        result[genre] = {
            "current_count": current_count,
            "target_count": target_count,
            "gap": gap,
            "keywords": kw_info["keywords"],
        }

    # Sort by gap descending
    result = dict(sorted(result.items(), key=lambda x: -x[1]["gap"]))
    return result


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_distribution_table(current: dict[str, int], total: int) -> None:
    """Print current genre distribution as a table."""
    print("\n--- Current Genre Distribution ---")
    print(f"{'Genre':<30s} {'Count':>6s} {'Pct':>7s}  Bar")
    print("-" * 65)

    for genre, count in sorted(current.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total > 0 else 0.0
        bar = "#" * int(pct / 2)
        print(f"  {genre:<28s} {count:>6d} {pct:>6.1f}%  {bar}")


def print_gap_analysis_table(keywords_by_genre: dict[str, dict]) -> None:
    """Print genre gap analysis table to console."""
    print("\n" + "=" * 72)
    print("  Genre Gap Analysis")
    print("=" * 72)
    print(
        f"  {'Genre':<28s} {'Current':>8s} {'Target':>8s} "
        f"{'Gap':>6s} {'Priority':>10s}"
    )
    print(f"  {'-' * 66}")

    for genre, info in keywords_by_genre.items():
        current_count = info["current_count"]
        target_count = info["target_count"]
        gap = info["gap"]

        # Determine priority
        if current_count == 0:
            priority = "CRITICAL"
        elif gap >= 20:
            priority = "HIGH"
        elif gap >= 10:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        print(
            f"  {genre:<28s} {current_count:>8d} {target_count:>8d} "
            f"{gap:>6d} {priority:>10s}"
        )

    # Print keyword preview
    print("\n" + "=" * 72)
    print("  Keywords by Genre (preview)")
    print("=" * 72)

    for genre, info in keywords_by_genre.items():
        kw_list = info["keywords"]
        kw_count = len(kw_list)
        print(f"\n  [{genre}] ({kw_count} keywords, gap={info['gap']})")
        for kw in kw_list[:5]:
            # Safe print for Windows console
            kw_safe = kw.encode("ascii", "replace").decode("ascii")
            print(f"    - {kw_safe}")
        if kw_count > 5:
            print(f"    ... and {kw_count - 5} more")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 72)
    print("  Generate Crawl Keywords for Underrepresented Genres")
    print(f"  Meta Ad Library API (country=JP, language=ja)")
    print(f"  Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 72)

    session = SyncSessionLocal()
    try:
        # 1. Analyze current distribution
        current_distribution, total = get_genre_distribution(session)

        print(f"\nTotal ads in database: {total}")
        if total == 0:
            print("No ads found. Exiting.")
            return

        print(f"Distinct genres: {len(current_distribution)}")
        print_distribution_table(current_distribution, total)

        # 2. Compute target distribution
        target_distribution = compute_target_distribution(
            current_distribution, total
        )

        # 3. Build keywords by genre (only underrepresented)
        keywords_by_genre = build_keywords_by_genre(
            current_distribution, target_distribution
        )

        if not keywords_by_genre:
            print("\nAll genres meet target counts. No crawl keywords needed.")
            return

        # 4. Print gap analysis table
        print_gap_analysis_table(keywords_by_genre)

        # 5. Summary stats
        total_gap = sum(info["gap"] for info in keywords_by_genre.values())
        total_keywords = sum(
            len(info["keywords"]) for info in keywords_by_genre.values()
        )
        critical_count = sum(
            1 for info in keywords_by_genre.values() if info["current_count"] == 0
        )

        print("\n" + "=" * 72)
        print("  Summary")
        print("=" * 72)
        print(f"  Genres needing crawl:    {len(keywords_by_genre)}")
        print(f"  Critical (0 ads):        {critical_count}")
        print(f"  Total ad gap:            {total_gap}")
        print(f"  Total keywords:          {total_keywords}")

        # 6. Export to JSON
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "crawl_keywords.json")

        # Build clean current_distribution for output (exclude unclassified)
        clean_current = {
            k: v for k, v in sorted(
                current_distribution.items(), key=lambda x: -x[1]
            )
            if k != "unclassified"
        }

        clean_target = {
            k: v for k, v in sorted(
                target_distribution.items(), key=lambda x: -x[1]
            )
            if k != "unclassified"
        }

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "current_distribution": clean_current,
            "target_distribution": clean_target,
            "keywords_by_genre": keywords_by_genre,
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n  Exported: {out_path}")
        print("\nDone.")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
