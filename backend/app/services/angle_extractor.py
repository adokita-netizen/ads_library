"""Angle extraction service — structured creative persuasion analysis.

Extracts hook_type, pain_points, promises, offer_types, proof_types,
urgency_types, audience_hints, and creative_styles from ad text
(OCR, ASR, body text, LP content).

Two extraction modes:
  1. Rule-based (fast, no API cost) — keyword matching with JP/EN patterns
  2. LLM-based (deep, accurate) — AWS Bedrock Claude structured extraction
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


# ==================== Keyword Dictionaries ====================

HOOK_TYPE_PATTERNS: dict[str, list[str]] = {
    "question": [
        r"まだ.*[？?]", r"知ってい?ます?か[？?]", r"なぜ.*[？?]",
        r"どうして.*[？?]", r".*していませんか[？?]", r".*で悩んでい?",
        r"自己流", r"間違った.*方法",
    ],
    "shock": [
        r"衝撃", r"驚き", r"まさか", r"実は.*だった",
        r"知らないと損", r"ヤバい", r"危険",
    ],
    "empathy": [
        r"わかります", r"同じ悩み", r".*で悩む.*へ", r"つらい",
        r".*が気になる方", r".*に悩む",
    ],
    "benefit_first": [
        r"たった.*で", r"最短.*分", r"即効", r"すぐに",
        r".*が叶う", r".*を実感", r".*効果",
    ],
    "scarcity": [
        r"限定", r"残り.*[個名本台席]", r"今だけ", r"本日.*まで",
        r"先着", r"なくなり次第",
    ],
    "authority": [
        r"医師監修", r"専門家", r"特許", r"受賞", r"認定",
        r"公式", r"研究", r"臨床", r"エビデンス",
    ],
    "social_proof": [
        r"満足度.*[%％]", r"No\.?1", r"ナンバーワン", r"累計.*[万億]",
        r"口コミ", r"レビュー", r"リピート率", r".*人が選んだ",
    ],
    "comparison": [
        r"比較", r".*より", r"違い", r".*vs", r"他社",
        r"従来.*比", r".*とは違う",
    ],
    "curiosity": [
        r"秘密", r"裏ワザ", r".*の正体", r"意外な",
        r".*だけが知っている", r"真実",
    ],
    "storytelling": [
        r"私[はが].*でした", r"あの日", r"体験談", r"実録",
        r".*の話", r"きっかけ",
    ],
}

PAIN_POINT_KEYWORDS: dict[str, list[str]] = {
    "肌荒れ": ["肌荒れ", "ニキビ", "吹き出物", "肌トラブル"],
    "シミ・くすみ": ["シミ", "くすみ", "美白", "透明感", "色素沈着"],
    "シワ・たるみ": ["シワ", "しわ", "たるみ", "ハリ", "エイジング", "年齢肌"],
    "毛穴": ["毛穴", "黒ずみ", "いちご鼻", "角栓"],
    "乾燥": ["乾燥", "カサカサ", "保湿", "うるおい"],
    "体重・ダイエット": ["太った", "痩せたい", "ダイエット", "体重", "お腹", "ぽっこり"],
    "薄毛・抜け毛": ["薄毛", "抜け毛", "ハゲ", "育毛", "発毛", "AGA"],
    "脱毛": ["ムダ毛", "脱毛", "除毛", "自己処理"],
    "口臭・歯": ["口臭", "歯", "ホワイトニング", "黄ばみ"],
    "疲労・睡眠": ["疲れ", "疲労", "睡眠", "不眠", "眠れない"],
    "お金・借金": ["借金", "返済", "お金", "節約", "貯金"],
    "転職・キャリア": ["転職", "仕事", "キャリア", "年収", "副業"],
}

OFFER_TYPE_KEYWORDS: dict[str, list[str]] = {
    "初回限定": ["初回", "初めて", "はじめて", "お試し"],
    "割引": ["割引", "OFF", "オフ", "%引き", "円引き", "半額", "特別価格"],
    "無料": ["無料", "0円", "タダ", "フリー", "free"],
    "返金保証": ["返金", "全額返金", "保証", "満足保証"],
    "送料無料": ["送料無料", "送料込み"],
    "定期コース": ["定期", "毎月届く", "お届け", "サブスク"],
    "プレゼント": ["プレゼント", "特典", "おまけ", "セット"],
    "モニター": ["モニター", "サンプル", "トライアル"],
}

PROOF_TYPE_KEYWORDS: dict[str, list[str]] = {
    "満足度": ["満足度", "リピート率", "継続率"],
    "No.1": ["No.1", "ナンバーワン", "第1位", "1位", "トップ"],
    "医師監修": ["医師監修", "医師推奨", "皮膚科医", "専門医"],
    "特許": ["特許", "独自技術", "独自成分", "独自開発"],
    "口コミ": ["口コミ", "レビュー", "お客様の声", "体験者"],
    "ビフォーアフター": ["ビフォー", "アフター", "before", "after", "使用前", "使用後"],
    "累計販売数": ["累計", "万個", "万本", "万袋", "突破", "達成"],
    "メディア掲載": ["テレビ", "雑誌", "メディア", "掲載", "紹介"],
    "受賞": ["受賞", "アワード", "グランプリ", "金賞"],
}

URGENCY_KEYWORDS: dict[str, list[str]] = {
    "本日終了": ["本日", "今日", "今夜", "本日限り"],
    "期間限定": ["期間限定", "期限", "〜まで", "月末まで"],
    "残りわずか": ["残り", "在庫", "なくなり次第", "品薄"],
    "先着": ["先着", "限定.*名", ".*名様"],
    "カウントダウン": ["あと.*時間", "あと.*日", "締め切り"],
}

AUDIENCE_HINT_PATTERNS: dict[str, list[str]] = {
    "20代女性": ["20代", "二十代", "アラサー"],
    "30代女性": ["30代", "三十代"],
    "40代女性": ["40代", "四十代", "アラフォー"],
    "50代以上": ["50代", "五十代", "60代", "アラフィフ"],
    "男性": ["メンズ", "男性", "紳士"],
    "敏感肌": ["敏感肌", "肌が弱い"],
    "主婦": ["主婦", "ママ", "子育て"],
}

CREATIVE_STYLE_PATTERNS: dict[str, list[str]] = {
    "UGC": ["体験", "レビュー", "口コミ", "使ってみた", "リアル"],
    "direct_response": ["今すぐ", "申し込み", "購入", "注文"],
    "comparison": ["比較", "vs", "違い"],
    "before_after": ["ビフォー", "アフター", "before", "after"],
    "authority_endorsement": ["医師", "専門家", "研究", "エビデンス"],
    "storytelling": ["実録", "体験談", "ストーリー"],
    "quiz_funnel": ["診断", "クイズ", "タイプ別", "チェック"],
}

LP_PATTERN_KEYWORDS: dict[str, list[str]] = {
    "article_advertorial": ["PR", "広告", "タイアップ", "提供"],
    "long_form_sales": ["お申し込み", "ご注文", "カートに入れる"],
    "quiz_funnel": ["診断", "クイズ", "質問に答え", "タイプ別"],
    "lead_form": ["資料請求", "お問い合わせ", "無料相談", "カウンセリング"],
    "ecommerce_pdp": ["カートに入れる", "購入する", "お買い物"],
    "comparison_landing": ["比較表", "ランキング", "おすすめ.*選"],
    "vsl_landing": ["動画", "ビデオ", "セミナー", "ウェビナー"],
}


@dataclass
class AngleResult:
    """Structured angle extraction result."""
    hook_type: str | None = None
    pain_points: list[str] = field(default_factory=list)
    promises: list[str] = field(default_factory=list)
    offer_types: list[str] = field(default_factory=list)
    proof_types: list[str] = field(default_factory=list)
    urgency_types: list[str] = field(default_factory=list)
    audience_hints: list[str] = field(default_factory=list)
    creative_styles: list[str] = field(default_factory=list)
    lp_pattern: str | None = None
    confidence: float = 0.0
    extracted_from: str = "rule_based"
    angle_metadata: dict[str, Any] = field(default_factory=dict)


def _match_keywords(text: str, keyword_dict: dict[str, list[str]]) -> list[str]:
    """Match text against keyword dictionary, return matched category labels."""
    matched = []
    text_lower = text.lower()
    for label, keywords in keyword_dict.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                matched.append(label)
                break
    return matched


def _match_patterns(text: str, pattern_dict: dict[str, list[str]]) -> str | None:
    """Match text against regex patterns, return first matching type."""
    for type_name, patterns in pattern_dict.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return type_name
    return None


def _match_all_patterns(text: str, pattern_dict: dict[str, list[str]]) -> list[str]:
    """Match text against regex patterns, return all matching types."""
    matched = []
    for type_name, patterns in pattern_dict.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matched.append(type_name)
                break
    return matched


def extract_angle_from_text(
    text: str,
    lp_text: str | None = None,
) -> AngleResult:
    """Extract creative angle from text using rule-based keyword matching.

    Args:
        text: Combined ad text (OCR + ASR + body text)
        lp_text: Optional LP text for additional signals

    Returns:
        AngleResult with extracted persuasion elements
    """
    if not text:
        return AngleResult()

    combined = text
    if lp_text:
        combined = f"{text}\n{lp_text}"

    # Hook type (use first 100 chars for hook detection — it's the opening)
    opening = text[:200]
    hook_type = _match_patterns(opening, HOOK_TYPE_PATTERNS)

    # Pain points
    pain_points = _match_keywords(combined, PAIN_POINT_KEYWORDS)

    # Offers
    offer_types = _match_keywords(combined, OFFER_TYPE_KEYWORDS)

    # Proof types
    proof_types = _match_keywords(combined, PROOF_TYPE_KEYWORDS)

    # Urgency
    urgency_types = _match_keywords(combined, URGENCY_KEYWORDS)

    # Audience hints
    audience_hints = _match_all_patterns(combined, AUDIENCE_HINT_PATTERNS)

    # Creative styles
    creative_styles = _match_all_patterns(combined, CREATIVE_STYLE_PATTERNS)

    # LP pattern (from LP text primarily)
    lp_pattern = None
    if lp_text:
        lp_pattern = _match_patterns(lp_text, LP_PATTERN_KEYWORDS)

    # Promises — extract phrases after benefit keywords
    promises = []
    promise_patterns = [
        r"(.{2,20}(?:を実感|が叶う|できる|になれる|を実現))",
        r"(?:たった|最短|わずか)(.{2,15}で)",
    ]
    for pat in promise_patterns:
        for m in re.finditer(pat, text):
            promises.append(m.group(0).strip())
    # Deduplicate
    promises = list(dict.fromkeys(promises))[:5]

    # Confidence based on how many elements we found
    signal_count = sum([
        1 if hook_type else 0,
        min(len(pain_points), 2),
        min(len(offer_types), 2),
        min(len(proof_types), 2),
        min(len(urgency_types), 1),
        min(len(audience_hints), 1),
        min(len(creative_styles), 1),
    ])
    confidence = min(1.0, signal_count / 6.0)

    return AngleResult(
        hook_type=hook_type,
        pain_points=pain_points,
        promises=promises,
        offer_types=offer_types,
        proof_types=proof_types,
        urgency_types=urgency_types,
        audience_hints=audience_hints,
        creative_styles=creative_styles,
        lp_pattern=lp_pattern,
        confidence=round(confidence, 3),
        extracted_from="rule_based",
    )


def batch_extract_angles(session, limit: int = 500, use_llm: bool = False) -> dict:
    """Extract angles for all ads that don't have angle_facts yet.

    Args:
        session: SQLAlchemy session
        limit: Maximum number of ads to process
        use_llm: If True, use LLM-based extraction via async bridge

    Returns summary dict.
    """
    from app.models.ad import Ad
    from app.models.brand_registry import AngleFact

    # Find ads without angle facts
    existing_ad_ids = {
        row[0] for row in session.query(AngleFact.ad_id).filter(AngleFact.ad_id.isnot(None)).all()
    }

    ads = session.query(Ad).limit(limit + len(existing_ad_ids)).all()
    created = 0
    skipped = 0

    # If use_llm requested, delegate to async batch and run via event loop
    if use_llm:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context — caller should use batch_extract_angles_llm directly
            logger.warning(
                "batch_extract_angles called with use_llm=True inside running loop; "
                "falling back to rule-based. Use batch_extract_angles_llm() instead."
            )
        else:
            return asyncio.run(_batch_extract_angles_llm_inner(session, ads, existing_ad_ids))

    for ad in ads:
        if ad.id in existing_ad_ids:
            skipped += 1
            continue

        # Gather text signals
        texts = []
        if ad.title:
            texts.append(ad.title)
        if ad.description:
            texts.append(ad.description)
        meta = ad.ad_metadata or {}
        if isinstance(meta, dict):
            if meta.get("ocr_text"):
                texts.append(meta["ocr_text"])
            if meta.get("asr_text"):
                texts.append(meta["asr_text"])

        combined_text = "\n".join(texts)
        if not combined_text.strip():
            skipped += 1
            continue

        # LP text
        lp_text = None
        if isinstance(meta, dict) and meta.get("lp_info", {}).get("title"):
            lp_text = meta["lp_info"]["title"]

        result = extract_angle_from_text(combined_text, lp_text)

        if result.confidence < 0.1:
            skipped += 1
            continue

        fact = AngleFact(
            ad_id=ad.id,
            hook_type=result.hook_type,
            pain_points=result.pain_points or None,
            promises=result.promises or None,
            offer_types=result.offer_types or None,
            proof_types=result.proof_types or None,
            urgency_types=result.urgency_types or None,
            audience_hints=result.audience_hints or None,
            creative_styles=result.creative_styles or None,
            lp_pattern=result.lp_pattern,
            confidence=result.confidence,
            extracted_from=result.extracted_from,
            angle_metadata=result.angle_metadata or None,
        )
        session.add(fact)
        created += 1

    session.commit()
    logger.info("angle_extraction_complete", created=created, skipped=skipped)
    return {"created": created, "skipped": skipped, "total": len(ads)}


# ==================== LLM-Based Extraction ====================

_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
_BEDROCK_REGION = "ap-northeast-1"

_LLM_SYSTEM_PROMPT = """\
あなたは広告クリエイティブの訴求分析AIです。
与えられた広告テキスト（OCR/ASR/本文）とLP情報から、構造化された訴求要素を抽出してください。

以下のJSON形式で回答してください。余計な説明は不要です。JSONのみ出力してください。

{
  "genre": ["選択肢: beauty, health, finance, career, education, ecommerce, saas, app, entertainment"],
  "hook_type": "選択肢: question, empathy, benefit_first, scarcity, authority, social_proof, comparison, before_after, shock, curiosity, storytelling",
  "primary_hook": "テキストから最も強い訴求ワンライナーを抽出",
  "pain_points": ["特定されたペインポイントのリスト"],
  "promises": ["広告が約束している内容のリスト"],
  "offer_types": ["選択肢: free_trial, first_discount, diagnosis, booking, bonus, free_shipping, refund, installment"],
  "proof_types": ["選択肢: review, testimonial, doctor, media_feature, ranking_claim, numbers_claim, ugc, expert_endorsement"],
  "urgency_types": ["選択肢: limited_time, limited_stock, countdown, first_n, today_only"],
  "audience_hints": ["例: female_30s, sensitive_skin, diet_interested"],
  "creative_styles": ["選択肢: static, ugc_video, founder_talk, testimonial_video, product_demo, slideshow, carousel, motion_graphics"],
  "cta": "抽出されたCTAテキスト",
  "lp_pattern": "選択肢: quiz, lead_form, advertorial, direct_response_lp, comparison_lp, ecommerce_pdp, vsl_lp, appointment_lp（LP情報がない場合はnull）",
  "confidence": 0.0
}

注意:
- 該当しない項目は空リスト[]またはnullにしてください
- confidenceは0〜1で自己評価してください（情報が豊富なら高く、少なければ低く）
- genre, hook_type, offer_types等は指定選択肢から選んでください
- primary_hookは広告テキストからそのまま抜き出してください
- 日本語の広告テキストに最適化して分析してください
"""


def _build_user_message(text: str, lp_text: str | None = None) -> str:
    """Build the user message for Bedrock Claude."""
    msg = f"## 広告テキスト\n{text}"
    if lp_text:
        msg += f"\n\n## LPテキスト\n{lp_text}"
    return msg


def _get_bedrock_client():
    """Lazy-initialize boto3 bedrock-runtime client."""
    import boto3
    return boto3.client("bedrock-runtime", region_name=_BEDROCK_REGION)


def _parse_llm_response(response_body: dict) -> dict[str, Any]:
    """Extract and parse JSON from Bedrock Claude Messages API response."""
    content_blocks = response_body.get("content", [])
    raw_text = ""
    for block in content_blocks:
        if block.get("type") == "text":
            raw_text += block["text"]

    # Strip markdown code fences if present
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = raw_text.index("\n")
        raw_text = raw_text[first_newline + 1:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    return json.loads(raw_text)


def _llm_result_to_angle(parsed: dict[str, Any]) -> AngleResult:
    """Map parsed LLM JSON to AngleResult dataclass."""
    # Map offer_types from LLM taxonomy to DB-compatible labels
    return AngleResult(
        hook_type=parsed.get("hook_type"),
        pain_points=parsed.get("pain_points") or [],
        promises=parsed.get("promises") or [],
        offer_types=parsed.get("offer_types") or [],
        proof_types=parsed.get("proof_types") or [],
        urgency_types=parsed.get("urgency_types") or [],
        audience_hints=parsed.get("audience_hints") or [],
        creative_styles=parsed.get("creative_styles") or [],
        lp_pattern=parsed.get("lp_pattern"),
        confidence=min(1.0, max(0.0, float(parsed.get("confidence", 0.5)))),
        extracted_from="llm",
        angle_metadata={
            "primary_hook": parsed.get("primary_hook"),
            "cta": parsed.get("cta"),
            "genre": parsed.get("genre") or [],
            "model": _BEDROCK_MODEL_ID,
        },
    )


async def extract_angle_with_llm(
    text: str,
    lp_text: str | None = None,
) -> AngleResult:
    """Extract creative angle using AWS Bedrock Claude.

    Calls Claude 3 Haiku via the Bedrock Messages API for cost-efficient
    structured angle extraction. Falls back to rule-based on any error.

    Args:
        text: Combined ad text (OCR + ASR + body text)
        lp_text: Optional LP text for additional signals

    Returns:
        AngleResult with extracted persuasion elements
    """
    if not text or not text.strip():
        return AngleResult()

    try:
        client = _get_bedrock_client()

        request_body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": _LLM_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": _build_user_message(text, lp_text),
                }
            ],
            "temperature": 0.0,
        })

        # Run blocking boto3 call in executor to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model(
                modelId=_BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=request_body,
            ),
        )

        response_body = json.loads(response["body"].read())
        parsed = _parse_llm_response(response_body)
        result = _llm_result_to_angle(parsed)

        logger.info(
            "llm_angle_extraction_success",
            hook_type=result.hook_type,
            confidence=result.confidence,
            pain_points_count=len(result.pain_points),
        )
        return result

    except Exception:
        logger.exception("llm_angle_extraction_failed, falling back to rule-based")
        return extract_angle_from_text(text, lp_text)


async def batch_extract_angles_llm(session, limit: int = 500) -> dict:
    """Extract angles for ads using LLM-based extraction.

    Processes ads sequentially (Bedrock has rate limits) with LLM extraction,
    falling back to rule-based per-ad on errors.

    Returns summary dict.
    """
    return await _batch_extract_angles_llm_inner(session, None, None, limit=limit)


async def _batch_extract_angles_llm_inner(
    session,
    ads=None,
    existing_ad_ids=None,
    limit: int = 500,
) -> dict:
    """Inner implementation for LLM batch extraction.

    Shared by both batch_extract_angles(use_llm=True) and batch_extract_angles_llm().
    """
    from app.models.ad import Ad
    from app.models.brand_registry import AngleFact

    if existing_ad_ids is None:
        existing_ad_ids = {
            row[0]
            for row in session.query(AngleFact.ad_id).filter(AngleFact.ad_id.isnot(None)).all()
        }

    if ads is None:
        ads = session.query(Ad).limit(limit + len(existing_ad_ids)).all()

    created = 0
    skipped = 0

    for ad in ads:
        if ad.id in existing_ad_ids:
            skipped += 1
            continue

        # Gather text signals
        texts = []
        if ad.title:
            texts.append(ad.title)
        if ad.description:
            texts.append(ad.description)
        meta = ad.ad_metadata or {}
        if isinstance(meta, dict):
            if meta.get("ocr_text"):
                texts.append(meta["ocr_text"])
            if meta.get("asr_text"):
                texts.append(meta["asr_text"])

        combined_text = "\n".join(texts)
        if not combined_text.strip():
            skipped += 1
            continue

        # LP text
        lp_text = None
        if isinstance(meta, dict) and meta.get("lp_info", {}).get("title"):
            lp_text = meta["lp_info"]["title"]

        result = await extract_angle_with_llm(combined_text, lp_text)

        if result.confidence < 0.1:
            skipped += 1
            continue

        fact = AngleFact(
            ad_id=ad.id,
            hook_type=result.hook_type,
            pain_points=result.pain_points or None,
            promises=result.promises or None,
            offer_types=result.offer_types or None,
            proof_types=result.proof_types or None,
            urgency_types=result.urgency_types or None,
            audience_hints=result.audience_hints or None,
            creative_styles=result.creative_styles or None,
            lp_pattern=result.lp_pattern,
            confidence=result.confidence,
            extracted_from=result.extracted_from,
            angle_metadata=result.angle_metadata or None,
        )
        session.add(fact)
        created += 1

    session.commit()
    logger.info("llm_angle_extraction_complete", created=created, skipped=skipped)
    return {"created": created, "skipped": skipped, "total": len(ads)}
