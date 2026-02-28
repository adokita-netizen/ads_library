#!/usr/bin/env python3
"""Analyze creative elements of all ads using rule-based keyword matching.

Extracts hook_type, cta_type, offer_type, emotion, text features, and
destination_type from title + description, storing results in
ad_metadata["creative_analysis"].

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_creative_elements.py
"""

import re
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Keyword Definitions ──────────────────────────────────────────────────

# Hook type: what grabs attention at the start
HOOK_RULES: list[tuple[str, list[str]]] = [
    # Order matters: first match wins (most specific first)
    ("urgency", ["今だけ", "限定", "残り", "期間限定", "本日限り", "ラスト", "締切", "急いで", "お急ぎ"]),
    ("social_proof", ["万人", "話題", "人気", "ランキング", "No.1", "第1位", "売上",
                       "大人気", "殿堂入り", "ベストセラー", "口コミ", "満足度", "リピート",
                       "累計", "突破", "実績"]),
    ("pain_point", ["悩み", "つらい", "困", "不安", "心配", "ストレス", "老化",
                     "たるみ", "シミ", "シワ", "薄毛", "痛い", "痛み", "苦し",
                     "疲れ", "だるい", "眠れ", "太", "肥満", "コンプレックス",
                     "悩んで", "気になる"]),
    ("statistic", ["%", "円", "万", "件", "人", "倍"]),
    ("benefit", ["簡単", "楽", "美し", "キレイ", "きれい", "綺麗", "若", "変わる",
                  "実感", "効果", "手軽", "お得", "安心", "便利", "快適",
                  "スッキリ", "すっきり", "ツヤ", "ハリ", "潤い", "モテ",
                  "理想", "叶", "改善", "サポート"]),
    ("question", ["？", "?"]),
    ("curiosity", ["秘密", "裏ワザ", "知ってい", "ご存知", "まだ", "実は",
                    "驚き", "衝撃", "意外", "新常識", "真実", "本当"]),
]

# CTA type: what action is requested
CTA_RULES: list[tuple[str, list[str]]] = [
    ("line_add", ["LINE", "ライン", "友だち追加", "友達追加"]),
    ("purchase", ["購入", "注文", "買", "お取り寄せ", "カートに", "ショッピング"]),
    ("signup", ["登録", "申込", "申し込", "エントリー", "会員", "入会"]),
    ("free_trial", ["無料", "0円", "タダ", "フリー", "free"]),
    ("consultation", ["相談", "カウンセリング", "診断", "見積", "査定", "お問い合わせ"]),
    ("download", ["ダウンロード", "DL", "インストール", "download", "install"]),
    ("learn_more", ["詳しく", "詳細", "チェック", "こちら", "見る", "確認", "公式"]),
]

# Offer type: what incentive is provided
OFFER_RULES: list[tuple[str, list[str]]] = [
    ("discount", ["%OFF", "%off", "割引", "値引", "OFF", "SALE", "セール",
                   "半額", "特別価格", "お買い得", "プライスダウン"]),
    ("free", ["無料", "0円", "タダ", "送料無料", "手数料無料", "free"]),
    ("trial", ["お試し", "トライアル", "体験", "サンプル", "モニター", "trial"]),
    ("limited_time", ["限定", "今だけ", "期間限定", "数量限定", "先着",
                       "本日限り", "初回限定", "特別"]),
    ("bundle", ["セット", "まとめ買い", "3本", "定期", "コース", "パック"]),
    ("comparison", ["比較", "ランキング", "おすすめ", "vs", "VS"]),
]

# Offer detail extraction patterns
OFFER_DETAIL_PATTERNS = [
    # "初回80%OFF", "今なら50%OFF" etc.
    re.compile(r"(?:初回|今なら|特別)?[\d]+%\s*(?:OFF|off|オフ)"),
    # "初回980円", "特別価格1,980円" etc.
    re.compile(r"(?:初回|特別価格|今なら)?[\d,]+円"),
    # "無料カウンセリング", "無料体験" etc.
    re.compile(r"無料[^\s、。！]{1,10}"),
    # "送料無料"
    re.compile(r"送料無料"),
    # "お試し○○" patterns
    re.compile(r"お試し[^\s、。！]{1,10}"),
]

# Emotion keywords
PAIN_WORDS = ["悩み", "つらい", "困", "不安", "心配", "ストレス", "老化",
              "たるみ", "シミ", "シワ", "薄毛", "痛", "苦し", "疲れ",
              "だるい", "眠れ", "太", "肥満", "コンプレックス", "後悔",
              "失敗", "リスク", "危険"]
DESIRE_WORDS = ["美し", "キレイ", "きれい", "綺麗", "若", "理想", "叶",
                "モテ", "ツヤ", "ハリ", "潤い", "スッキリ", "すっきり",
                "憧れ", "夢", "輝", "変身", "チェンジ", "自信",
                "効果", "実感", "結果", "改善", "満足"]
TRUST_WORDS = ["実績", "万人", "口コミ", "満足度", "ランキング", "No.1",
               "第1位", "認定", "特許", "医師", "監修", "研究",
               "エビデンス", "論文", "大学", "専門家", "プロ", "受賞",
               "累計", "臨床", "認証"]
EXCITEMENT_WORDS = ["新", "話題", "注目", "最新", "速報", "ついに",
                     "初登場", "衝撃", "驚き", "革命", "画期的"]

# Testimonial / before-after keywords
TESTIMONIAL_WORDS = ["口コミ", "体験", "レビュー", "感想", "お客様の声",
                      "使ってみ", "試してみ", "愛用", "リピート", "実際に",
                      "個人の感想"]
BEFORE_AFTER_WORDS = ["ビフォーアフター", "ビフォー", "before", "after",
                       "使用前", "使用後", "変化", "1ヶ月後", "2週間後",
                       "3日後", "翌朝", "翌日", "→", "⇒", "から"]

# Destination URL domain patterns
DEST_EC_DOMAINS = ["qoo10", "amazon", "楽天", "rakuten", "yahoo", "mercari",
                    "shopify", "stores.jp", "base.shop", "minne", "creema"]
DEST_SNS_DOMAINS = ["instagram", "twitter", "tiktok", "facebook", "youtube",
                     "line.me", "lin.ee"]
DEST_APP_DOMAINS = ["play.google", "apps.apple", "app.adjust", ".app",
                     "onelink.me", "app.link"]

# Emoji detection regex
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # supplemental
    "\U0001FA00-\U0001FA6F"  # chess
    "\U0001FA70-\U0001FAFF"  # more symbols
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U0000200D"             # ZWJ
    "\U00002B50"             # star
    "\U00002764"             # heart
    "\U0000203C\U00002049"   # exclamation marks
    "]+",
    flags=re.UNICODE,
)


# ── Analysis Functions ────────────────────────────────────────────────────


def _match_first(text: str, rules: list[tuple[str, list[str]]]) -> str:
    """Return the first matching category from a list of (category, keywords) rules."""
    text_lower = text.lower()
    for category, keywords in rules:
        for kw in keywords:
            if kw.lower() in text_lower:
                return category
    return "none"


def _classify_hook(text: str) -> str:
    """Classify hook type from the first line or first 100 chars of text."""
    # Use first line or first 100 characters, whichever is shorter
    first_line = text.split("\n")[0][:150] if text else ""
    if not first_line.strip():
        return "none"
    return _match_first(first_line, HOOK_RULES)


def _classify_cta(text: str) -> str:
    """Classify CTA type from the full text."""
    if not text:
        return "none"
    return _match_first(text, CTA_RULES)


def _classify_offer(text: str) -> tuple[str, str | None]:
    """Classify offer type and extract offer detail from the full text."""
    if not text:
        return "none", None

    offer_type = _match_first(text, OFFER_RULES)

    # Extract offer detail
    offer_detail = None
    for pattern in OFFER_DETAIL_PATTERNS:
        match = pattern.search(text)
        if match:
            offer_detail = match.group(0).strip()
            break

    return offer_type, offer_detail


def _classify_emotion(text: str, hook_type: str, offer_type: str) -> str:
    """Classify the primary emotional appeal from text, hook, and offer context."""
    if not text:
        return "neutral"

    text_lower = text.lower()

    # Score each emotion
    scores = {
        "fear": 0,
        "desire": 0,
        "trust": 0,
        "excitement": 0,
        "relief": 0,
        "curiosity": 0,
    }

    for w in PAIN_WORDS:
        if w.lower() in text_lower:
            scores["fear"] += 1

    for w in DESIRE_WORDS:
        if w.lower() in text_lower:
            scores["desire"] += 1

    for w in TRUST_WORDS:
        if w.lower() in text_lower:
            scores["trust"] += 1

    for w in EXCITEMENT_WORDS:
        if w.lower() in text_lower:
            scores["excitement"] += 1

    # Boost based on hook/offer context
    if hook_type == "pain_point":
        scores["fear"] += 2
    elif hook_type == "benefit":
        scores["desire"] += 2
    elif hook_type == "social_proof":
        scores["trust"] += 2
    elif hook_type == "curiosity":
        scores["curiosity"] += 2
    elif hook_type == "urgency":
        scores["fear"] += 1
        scores["excitement"] += 1

    if offer_type == "free" or offer_type == "trial":
        scores["relief"] += 1
    if offer_type == "limited_time":
        scores["excitement"] += 1

    # Return the highest scoring emotion
    max_score = max(scores.values())
    if max_score == 0:
        return "neutral"

    # Get the emotion with the highest score
    best_emotion = max(scores, key=lambda k: scores[k])
    return best_emotion


def _has_numbers(text: str) -> bool:
    """Check if text contains Japanese-style numbers (digits + units)."""
    return bool(re.search(r"\d+[%％円万件個人本倍回日]", text))


def _has_testimonial(text: str) -> bool:
    """Check if text contains testimonial/review indicators."""
    text_lower = text.lower()
    return any(w.lower() in text_lower for w in TESTIMONIAL_WORDS)


def _has_before_after(text: str) -> bool:
    """Check if text contains before/after comparison indicators."""
    text_lower = text.lower()
    return any(w.lower() in text_lower for w in BEFORE_AFTER_WORDS)


def _has_emoji(text: str) -> bool:
    """Check if text contains emoji characters."""
    return bool(EMOJI_PATTERN.search(text))


def _text_length_class(text: str) -> str:
    """Classify text length: short (<50), medium (50-150), long (>150)."""
    length = len(text) if text else 0
    if length < 50:
        return "short"
    elif length <= 150:
        return "medium"
    else:
        return "long"


def _line_count(text: str) -> int:
    """Count the number of non-empty lines."""
    if not text:
        return 0
    return len([line for line in text.split("\n") if line.strip()])


def _classify_destination(url: str | None) -> str:
    """Classify the destination URL type."""
    if not url:
        return "other"

    url_lower = url.lower()

    # EC / Shopping platforms
    for domain in DEST_EC_DOMAINS:
        if domain in url_lower:
            return "ec"

    # SNS platforms
    for domain in DEST_SNS_DOMAINS:
        if domain in url_lower:
            return "sns"

    # App stores
    for domain in DEST_APP_DOMAINS:
        if domain in url_lower:
            return "app_store"

    # Corporate domains (co.jp patterns)
    if re.search(r"\.co\.jp", url_lower) or re.search(r"corporate|company|about", url_lower):
        return "corporate"

    # Landing page (default for typical ad destinations)
    return "lp"


def analyze_ad(ad: Ad) -> dict:
    """Analyze a single ad's creative elements and return the analysis dict."""
    # Combine title and description for full text analysis
    title = ad.title or ""
    description = ad.description or ""

    # Also pull body/link_description from metadata if available
    meta = ad.ad_metadata or {}
    body = meta.get("body", "") or ""
    link_desc = meta.get("link_description", "") or ""
    cta_text = meta.get("cta_text", "") or ""

    # Full text = all available text concatenated
    full_text = "\n".join(filter(None, [title, description, body, link_desc, cta_text]))

    # Primary analysis text = description first, fallback to title
    primary_text = description if description.strip() else title

    # Hook analysis: use the first line of the primary text
    hook_type = _classify_hook(primary_text)

    # CTA analysis: use full text
    cta_type = _classify_cta(full_text)

    # Offer analysis: use full text
    offer_type, offer_detail = _classify_offer(full_text)

    # Emotion analysis: use full text + context from hook/offer
    emotion = _classify_emotion(full_text, hook_type, offer_type)

    # Text features
    has_emoji = _has_emoji(full_text)
    has_numbers = _has_numbers(full_text)
    has_testimonial = _has_testimonial(full_text)
    has_before_after = _has_before_after(full_text)
    text_length = _text_length_class(description)
    line_ct = _line_count(description)

    # Destination type
    destination_type = _classify_destination(ad.destination_url)

    return {
        "hook_type": hook_type,
        "cta_type": cta_type,
        "offer_type": offer_type,
        "offer_detail": offer_detail,
        "emotion": emotion,
        "has_emoji": has_emoji,
        "has_numbers": has_numbers,
        "has_testimonial": has_testimonial,
        "has_before_after": has_before_after,
        "text_length": text_length,
        "line_count": line_ct,
        "destination_type": destination_type,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Creative Element Analysis Script (Rule-Based)")
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

        # Counters for summary
        hook_counts: dict[str, int] = {}
        cta_counts: dict[str, int] = {}
        offer_counts: dict[str, int] = {}
        emotion_counts: dict[str, int] = {}
        dest_counts: dict[str, int] = {}
        emoji_count = 0
        numbers_count = 0
        testimonial_count = 0
        before_after_count = 0
        text_length_counts: dict[str, int] = {}
        updated = 0

        print(f"Analyzing {total} ads ...")

        for ad in ads:
            analysis = analyze_ad(ad)

            # Update ad_metadata using the flag_modified pattern
            meta = dict(ad.ad_metadata or {})
            meta["creative_analysis"] = analysis
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            # Tally counters
            hook_counts[analysis["hook_type"]] = hook_counts.get(analysis["hook_type"], 0) + 1
            cta_counts[analysis["cta_type"]] = cta_counts.get(analysis["cta_type"], 0) + 1
            offer_counts[analysis["offer_type"]] = offer_counts.get(analysis["offer_type"], 0) + 1
            emotion_counts[analysis["emotion"]] = emotion_counts.get(analysis["emotion"], 0) + 1
            dest_counts[analysis["destination_type"]] = dest_counts.get(analysis["destination_type"], 0) + 1
            text_length_counts[analysis["text_length"]] = text_length_counts.get(analysis["text_length"], 0) + 1

            if analysis["has_emoji"]:
                emoji_count += 1
            if analysis["has_numbers"]:
                numbers_count += 1
            if analysis["has_testimonial"]:
                testimonial_count += 1
            if analysis["has_before_after"]:
                before_after_count += 1

        session.commit()
        print(f"\nCommitted. Updated {updated}/{total} ads with creative_analysis.")

        # Print distribution summaries
        def _print_dist(title: str, counts: dict[str, int]):
            print(f"\n--- {title} ---")
            for label, count in sorted(counts.items(), key=lambda x: -x[1]):
                pct = count / total * 100
                bar = "#" * int(pct / 2)
                print(f"  {label:<16s} {count:>4d} ({pct:>5.1f}%) {bar}")

        _print_dist("Hook Type Distribution", hook_counts)
        _print_dist("CTA Type Distribution", cta_counts)
        _print_dist("Offer Type Distribution", offer_counts)
        _print_dist("Emotion Distribution", emotion_counts)
        _print_dist("Destination Type Distribution", dest_counts)
        _print_dist("Text Length Distribution", text_length_counts)

        print(f"\n--- Boolean Features ---")
        print(f"  has_emoji:        {emoji_count:>4d} ({emoji_count / total * 100:.1f}%)")
        print(f"  has_numbers:      {numbers_count:>4d} ({numbers_count / total * 100:.1f}%)")
        print(f"  has_testimonial:  {testimonial_count:>4d} ({testimonial_count / total * 100:.1f}%)")
        print(f"  has_before_after: {before_after_count:>4d} ({before_after_count / total * 100:.1f}%)")

        # Show 5 sample analyses
        print(f"\n--- Sample Analyses (first 5) ---")
        sample_ads = session.query(Ad).limit(5).all()
        for ad in sample_ads:
            ca = (ad.ad_metadata or {}).get("creative_analysis", {})
            title_safe = (ad.title or "")[:40].encode("ascii", "replace").decode("ascii")
            print(f"  ID={ad.id} title={title_safe!r}")
            print(f"    hook={ca.get('hook_type')} cta={ca.get('cta_type')} "
                  f"offer={ca.get('offer_type')} emotion={ca.get('emotion')} "
                  f"dest={ca.get('destination_type')}")
            if ca.get("offer_detail"):
                print(f"    offer_detail={ca['offer_detail']}")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
