"""Seed genre keyword packs for ad discovery.

Run: python -m scripts.seed_genre_keyword_packs
"""

from datetime import datetime, timezone

from app.core.database import Base, SyncSessionLocal
from app.models.brand_registry import GenreKeywordPack

PACKS = [
    {
        "genre_code": "skincare",
        "search_keywords_ja": ["スキンケア", "美容液", "化粧水", "クレンジング", "洗顔", "美肌", "シミ対策", "くすみ", "毛穴ケア"],
        "search_keywords_en": ["skincare", "serum", "moisturizer", "cleanser"],
        "appeal_keywords": ["医師監修", "初回限定", "満足度No.1", "無添加", "自然派"],
        "negative_keywords": ["求人", "採用", "アルバイト", "バイト"],
    },
    {
        "genre_code": "diet",
        "search_keywords_ja": ["ダイエット", "痩せる", "脂肪燃焼", "糖質制限", "プロテイン", "置き換え", "ファスティング", "酵素"],
        "search_keywords_en": ["diet", "weight loss", "fat burn", "keto"],
        "appeal_keywords": ["-10kg", "たった1ヶ月", "リバウンドなし", "体験談", "ビフォーアフター"],
        "negative_keywords": ["レシピ", "料理", "グルメ"],
    },
    {
        "genre_code": "hair_removal",
        "search_keywords_ja": ["脱毛", "医療脱毛", "全身脱毛", "VIO脱毛", "ヒゲ脱毛", "光脱毛", "レーザー脱毛"],
        "search_keywords_en": ["hair removal", "laser hair", "IPL"],
        "appeal_keywords": ["初回無料", "痛くない", "最短○ヶ月", "キャンペーン"],
        "negative_keywords": ["育毛", "発毛", "AGA"],
    },
    {
        "genre_code": "supplements",
        "search_keywords_ja": ["サプリ", "サプリメント", "プロバイオティクス", "ビタミン", "鉄分", "葉酸", "コラーゲン", "NMN"],
        "search_keywords_en": ["supplement", "vitamin", "probiotic", "collagen"],
        "appeal_keywords": ["定期初回", "GMP認定", "国内製造", "特許成分"],
        "negative_keywords": ["薬", "処方", "病院"],
    },
    {
        "genre_code": "fitness",
        "search_keywords_ja": ["ジム", "パーソナルトレーニング", "フィットネス", "筋トレ", "ヨガ", "ピラティス", "ボディメイク"],
        "search_keywords_en": ["gym", "personal training", "fitness", "workout"],
        "appeal_keywords": ["無料体験", "入会金0円", "24時間", "完全個室"],
        "negative_keywords": ["求人", "トレーナー募集"],
    },
    {
        "genre_code": "cosmetics",
        "search_keywords_ja": ["化粧品", "ファンデーション", "リップ", "アイシャドウ", "メイク", "コスメ", "下地"],
        "search_keywords_en": ["cosmetics", "makeup", "foundation", "lipstick"],
        "appeal_keywords": ["新色", "限定色", "崩れない", "カバー力"],
        "negative_keywords": ["求人", "美容部員"],
    },
    {
        "genre_code": "hair_care",
        "search_keywords_ja": ["シャンプー", "トリートメント", "育毛", "発毛", "AGA", "薄毛", "白髪染め", "ヘアオイル"],
        "search_keywords_en": ["shampoo", "hair growth", "AGA", "hair treatment"],
        "appeal_keywords": ["臨床試験済み", "医薬部外品", "特許成分"],
        "negative_keywords": ["美容師", "サロン求人"],
    },
    {
        "genre_code": "oral_care",
        "search_keywords_ja": ["ホワイトニング", "歯磨き粉", "口臭", "マウスウォッシュ", "歯科矯正", "インビザライン"],
        "search_keywords_en": ["whitening", "toothpaste", "dental", "orthodontics"],
        "appeal_keywords": ["自宅で簡単", "歯科医推奨", "初回特別価格"],
        "negative_keywords": ["歯科助手", "衛生士"],
    },
    {
        "genre_code": "finance",
        "search_keywords_ja": ["投資", "FX", "仮想通貨", "NISA", "iDeCo", "不動産投資", "株", "資産運用"],
        "search_keywords_en": ["investment", "forex", "crypto", "stocks"],
        "appeal_keywords": ["無料セミナー", "年利", "不労所得", "口座開設"],
        "negative_keywords": ["求人", "営業"],
    },
    {
        "genre_code": "insurance",
        "search_keywords_ja": ["保険", "生命保険", "医療保険", "がん保険", "自動車保険", "火災保険"],
        "search_keywords_en": ["insurance", "life insurance", "medical insurance"],
        "appeal_keywords": ["無料相談", "見積もり", "保険料シミュレーション"],
        "negative_keywords": ["保険代理店求人"],
    },
    {
        "genre_code": "credit_card",
        "search_keywords_ja": ["クレジットカード", "ポイント還元", "年会費無料", "キャッシュバック"],
        "search_keywords_en": ["credit card", "cashback", "rewards"],
        "appeal_keywords": ["入会キャンペーン", "ポイント○倍", "即日発行"],
        "negative_keywords": [],
    },
    {
        "genre_code": "career",
        "search_keywords_ja": ["転職", "求人", "キャリア", "年収アップ", "副業", "フリーランス", "プログラミングスクール"],
        "search_keywords_en": ["job", "career", "freelance", "coding bootcamp"],
        "appeal_keywords": ["年収○万円以上", "未経験OK", "無料カウンセリング"],
        "negative_keywords": [],
    },
    {
        "genre_code": "education",
        "search_keywords_ja": ["英会話", "オンライン学習", "資格", "プログラミング", "TOEIC", "受験"],
        "search_keywords_en": ["English", "online learning", "certification", "TOEIC"],
        "appeal_keywords": ["無料体験", "挫折しない", "○日で習得"],
        "negative_keywords": ["講師募集"],
    },
    {
        "genre_code": "saas",
        "search_keywords_ja": ["業務効率化", "DX", "クラウド", "SaaS", "勤怠管理", "会計ソフト", "CRM", "MA"],
        "search_keywords_en": ["SaaS", "cloud", "CRM", "automation", "productivity"],
        "appeal_keywords": ["無料トライアル", "導入実績○社", "コスト削減"],
        "negative_keywords": ["エンジニア募集"],
    },
    {
        "genre_code": "marketing",
        "search_keywords_ja": ["広告運用", "SEO", "SNSマーケティング", "LP制作", "コンテンツマーケティング", "リスティング"],
        "search_keywords_en": ["marketing", "SEO", "advertising", "content marketing"],
        "appeal_keywords": ["成果報酬", "ROAS○倍", "CV数○倍"],
        "negative_keywords": [],
    },
    {
        "genre_code": "food",
        "search_keywords_ja": ["お取り寄せ", "宅配", "冷凍食品", "健康食品", "有機", "無添加食品"],
        "search_keywords_en": ["organic", "meal delivery", "health food"],
        "appeal_keywords": ["初回限定", "送料無料", "定期お届け"],
        "negative_keywords": ["レシピ", "調理師"],
    },
    {
        "genre_code": "pet",
        "search_keywords_ja": ["ドッグフード", "キャットフード", "ペット保険", "ペットサプリ"],
        "search_keywords_en": ["dog food", "cat food", "pet insurance"],
        "appeal_keywords": ["獣医師推奨", "グレインフリー", "国産"],
        "negative_keywords": ["ペットショップ求人"],
    },
    {
        "genre_code": "real_estate",
        "search_keywords_ja": ["不動産", "マンション", "住宅", "リフォーム", "引っ越し", "賃貸"],
        "search_keywords_en": ["real estate", "apartment", "renovation"],
        "appeal_keywords": ["無料査定", "一括見積り", "相場より○%安い"],
        "negative_keywords": ["不動産営業"],
    },
    {
        "genre_code": "travel",
        "search_keywords_ja": ["旅行", "ホテル", "航空券", "温泉", "ツアー"],
        "search_keywords_en": ["travel", "hotel", "flight", "tour"],
        "appeal_keywords": ["最安値", "早割", "ポイント○倍"],
        "negative_keywords": ["添乗員募集"],
    },
    {
        "genre_code": "fashion",
        "search_keywords_ja": ["ファッション", "アパレル", "通販", "ブランド", "コーデ"],
        "search_keywords_en": ["fashion", "clothing", "brand", "style"],
        "appeal_keywords": ["新作", "セール", "送料無料", "返品無料"],
        "negative_keywords": ["アパレル求人"],
    },
]


def seed_keyword_packs():
    """Insert genre keyword packs."""
    session = SyncSessionLocal()
    Base.metadata.create_all(session.get_bind())

    try:
        existing = {row.genre_code for row in session.query(GenreKeywordPack.genre_code).all()}

        created = 0
        for pack_data in PACKS:
            if pack_data["genre_code"] in existing:
                continue
            pack = GenreKeywordPack(
                genre_code=pack_data["genre_code"],
                search_keywords_ja=pack_data.get("search_keywords_ja"),
                search_keywords_en=pack_data.get("search_keywords_en"),
                appeal_keywords=pack_data.get("appeal_keywords"),
                negative_keywords=pack_data.get("negative_keywords"),
            )
            session.add(pack)
            created += 1

        session.commit()
        print(f"Genre keyword packs seeded: {created} created, {len(existing)} already existed")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_keyword_packs()
