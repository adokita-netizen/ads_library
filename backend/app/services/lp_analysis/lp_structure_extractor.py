"""LP Structure Extractor - LLM-based and rule-based LP structure extraction.

Extracts structured JSON from LP content using AWS Bedrock Claude,
populating the `extracted_json` field on LPSnapshot records.
"""

import json
import re
from typing import Any

import logging
from typing import TYPE_CHECKING

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand_registry import LPSnapshot

logger = logging.getLogger(__name__)

# Reuse boto3 client across calls (avoid per-call overhead)
_bedrock_client = None


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=_BEDROCK_REGION)
    return _bedrock_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BEDROCK_REGION = "ap-northeast-1"
_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
_DOM_TEXT_LIMIT = 6000  # chars sent to the LLM

LP_PATTERNS = [
    "quiz",
    "lead_form",
    "advertorial",
    "direct_response_lp",
    "comparison_lp",
    "ecommerce_pdp",
    "vsl_lp",
    "appointment_lp",
]

CONVERSION_TYPES = ["lead", "purchase", "appointment", "diagnosis"]

PROOF_TYPES = ["review", "doctor", "media", "ranking", "numbers", "ugc"]

URGENCY_TYPES = ["limited_time", "limited_stock", "countdown"]

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
あなたはLP（ランディングページ）構造解析の専門家です。
与えられたLPのテキストコンテンツから、以下のJSON構造を正確に抽出してください。
必ず有効なJSONのみを出力してください。説明文は不要です。"""

_USER_PROMPT_TEMPLATE = """\
以下のLPコンテンツを解析し、構造化JSONを抽出してください。

URL: {url}
タイトル: {title}

--- LP本文 ---
{dom_text}
--- LP本文ここまで ---

以下のJSON形式で出力してください。該当しない項目は空配列・空文字・falseにしてください。

{{
  "lp_pattern": "<quiz/lead_form/advertorial/direct_response_lp/comparison_lp/ecommerce_pdp/vsl_lp/appointment_lp のいずれか>",
  "hero": {{ "headline": "", "subheadline": "", "primary_cta": "" }},
  "offers": [{{"text": "", "price": "", "discount": ""}}],
  "prices": [{{"original": "", "discounted": "", "label": ""}}],
  "benefits": [{{"text": "", "proof": ""}}],
  "proofs": [{{"type": "review/doctor/media/ranking/numbers/ugc", "text": ""}}],
  "urgencies": [{{"type": "limited_time/limited_stock/countdown", "text": ""}}],
  "faqs": [{{"question": "", "answer": ""}}],
  "forms": {{ "present": true, "field_labels": [], "steps": 1 }},
  "sections": [{{"section_type": "hero", "heading": "", "body": "", "cta": ""}}],
  "conversion_type": "<lead/purchase/appointment/diagnosis>",
  "claim_flags": {{ "before_after": false, "doctor_supervised": false, "ranking_claim": false, "refund_guarantee": false }}
}}

JSONのみを出力してください。"""

# ---------------------------------------------------------------------------
# Skeleton for empty / error responses
# ---------------------------------------------------------------------------


def _empty_structure() -> dict:
    """Return a minimal valid structure dict with all fields at defaults."""
    return {
        "lp_pattern": "",
        "hero": {"headline": "", "subheadline": "", "primary_cta": ""},
        "offers": [],
        "prices": [],
        "benefits": [],
        "proofs": [],
        "urgencies": [],
        "faqs": [],
        "forms": {"present": False, "field_labels": [], "steps": 0},
        "sections": [],
        "conversion_type": "",
        "claim_flags": {
            "before_after": False,
            "doctor_supervised": False,
            "ranking_claim": False,
            "refund_guarantee": False,
        },
    }


# ---------------------------------------------------------------------------
# LLM-based extraction
# ---------------------------------------------------------------------------


def extract_lp_structure(
    dom_text: str,
    url: str | None = None,
    title: str | None = None,
) -> dict:
    """Extract LP structure via AWS Bedrock Claude.

    Args:
        dom_text: Raw text extracted from the LP DOM.
        url: Optional LP URL for context.
        title: Optional page title for context.

    Returns:
        Structured dict matching the LP structure schema.
        Falls back to rule-based extraction on any LLM error.
    """
    if not dom_text or not dom_text.strip():
        logger.warning("extract_lp_structure called with empty dom_text", url=url)
        return _empty_structure()

    truncated = dom_text[:_DOM_TEXT_LIMIT]

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        url=url or "(不明)",
        title=title or "(不明)",
        dom_text=truncated,
    )

    try:
        client = _get_bedrock_client()

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "system": _SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": user_prompt},
                ],
            }
        )

        response = client.invoke_model(
            modelId=_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = json.loads(response["body"].read())
        raw_text: str = response_body["content"][0]["text"]

        parsed = _parse_json_response(raw_text)
        result = _validate_and_normalise(parsed)

        logger.info(
            "extract_lp_structure succeeded",
            url=url,
            lp_pattern=result.get("lp_pattern"),
        )
        return result

    except Exception:
        logger.exception("extract_lp_structure LLM call failed, falling back to rule-based", url=url)
        return extract_lp_structure_rule_based(dom_text)


def _parse_json_response(raw: str) -> dict:
    """Extract JSON object from the LLM response text.

    Handles cases where the model wraps JSON in markdown code fences.
    """
    # Try direct parse first
    stripped = raw.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)

    # Try to extract from code fences
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
    if match:
        return json.loads(match.group(1))

    # Last resort: find the first { ... } block
    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        return json.loads(raw[brace_start : brace_end + 1])

    raise ValueError("No JSON object found in LLM response")


def _validate_and_normalise(data: dict) -> dict:
    """Ensure all required top-level keys exist and values are sane."""
    base = _empty_structure()

    # Merge known keys from data into base
    for key in base:
        if key in data:
            base[key] = data[key]

    # Normalise lp_pattern
    if base["lp_pattern"] not in LP_PATTERNS:
        base["lp_pattern"] = ""

    # Normalise conversion_type
    if base["conversion_type"] not in CONVERSION_TYPES:
        base["conversion_type"] = ""

    # Ensure list fields are actually lists
    for list_key in ("offers", "prices", "benefits", "proofs", "urgencies", "faqs", "sections"):
        if not isinstance(base[list_key], list):
            base[list_key] = []

    # Ensure hero is a dict
    if not isinstance(base.get("hero"), dict):
        base["hero"] = {"headline": "", "subheadline": "", "primary_cta": ""}

    # Ensure forms is a dict
    if not isinstance(base.get("forms"), dict):
        base["forms"] = {"present": False, "field_labels": [], "steps": 0}

    # Ensure claim_flags is a dict with boolean values
    if not isinstance(base.get("claim_flags"), dict):
        base["claim_flags"] = {
            "before_after": False,
            "doctor_supervised": False,
            "ranking_claim": False,
            "refund_guarantee": False,
        }

    return base


# ---------------------------------------------------------------------------
# Rule-based fallback extraction
# ---------------------------------------------------------------------------


def extract_lp_structure_rule_based(dom_text: str) -> dict:
    """Regex-based fallback extraction without LLM.

    Extracts whatever structure can be detected from raw text using
    keyword matching and simple patterns.
    """
    result = _empty_structure()
    if not dom_text:
        return result

    text = dom_text[:_DOM_TEXT_LIMIT]
    text_lower = text.lower()

    # --- lp_pattern detection ---
    result["lp_pattern"] = _detect_lp_pattern(text_lower)

    # --- prices ---
    result["prices"] = _extract_prices(text)

    # --- form presence ---
    form_present = bool(
        re.search(r"<(form|input|textarea|select)\b", text_lower)
        or re.search(r"(入力|送信|申し込み|お申込み|登録|フォーム)", text)
    )
    result["forms"]["present"] = form_present

    if form_present:
        # Try to find field labels
        labels = re.findall(
            r"(?:お名前|名前|氏名|メール|メールアドレス|電話|電話番号|住所|生年月日|年齢|性別)",
            text,
        )
        result["forms"]["field_labels"] = list(dict.fromkeys(labels))  # deduplicate, preserve order

    # --- claim_flags ---
    result["claim_flags"] = _detect_claim_flags(text)

    # --- conversion_type ---
    result["conversion_type"] = _detect_conversion_type(text_lower, text)

    # --- hero headline (first prominent line) ---
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if lines:
        result["hero"]["headline"] = lines[0][:200]

    # --- urgencies ---
    result["urgencies"] = _extract_urgencies(text)

    logger.info(
        "extract_lp_structure_rule_based completed",
        lp_pattern=result["lp_pattern"],
        prices_count=len(result["prices"]),
        form_present=form_present,
    )
    return result


def _detect_lp_pattern(text_lower: str) -> str:
    """Detect LP pattern from keywords."""
    pattern_keywords: list[tuple[str, list[str]]] = [
        ("quiz", ["診断", "クイズ", "質問に答え", "あなたに合った", "タイプ診断"]),
        ("lead_form", ["無料相談", "資料請求", "お問い合わせ", "無料カウンセリング"]),
        ("advertorial", ["PR", "広告", "タイアップ", "体験レポート", "体験談", "私が試した"]),
        ("comparison_lp", ["比較", "ランキング", "おすすめ", "vs", "徹底比較"]),
        ("ecommerce_pdp", ["カートに入れる", "購入する", "お買い物", "在庫", "数量"]),
        ("vsl_lp", ["動画", "ビデオ", "再生", "視聴"]),
        ("appointment_lp", ["予約", "来店", "ご来院", "カウンセリング予約"]),
        ("direct_response_lp", ["今すぐ", "申し込む", "注文", "お試し"]),
    ]
    for pattern, keywords in pattern_keywords:
        if any(kw in text_lower for kw in keywords):
            return pattern
    return ""


def _extract_prices(text: str) -> list[dict[str, str]]:
    """Extract price mentions from text."""
    prices: list[dict[str, str]] = []
    seen: set[str] = set()

    # ¥1,234 or ¥1234
    for m in re.finditer(r"[¥￥]\s?([\d,]+)", text):
        val = m.group(0).strip()
        if val not in seen:
            seen.add(val)
            prices.append({"original": val, "discounted": "", "label": ""})

    # 1,234円 or 1234円
    for m in re.finditer(r"([\d,]+)\s*円", text):
        val = m.group(0).strip()
        if val not in seen:
            seen.add(val)
            prices.append({"original": val, "discounted": "", "label": ""})

    return prices


def _detect_claim_flags(text: str) -> dict[str, bool]:
    """Detect claim flags from keywords."""
    return {
        "before_after": bool(re.search(r"(ビフォー|アフター|before.*after|使用前.*使用後)", text, re.IGNORECASE)),
        "doctor_supervised": bool(re.search(r"(医師|ドクター|医学|監修|クリニック)", text)),
        "ranking_claim": bool(re.search(r"(第?1位|No\.?\s*1|ランキング.*1位|売上.*1位|人気.*1位)", text)),
        "refund_guarantee": bool(re.search(r"(返金保証|全額返金|返金制度|満足保証)", text)),
    }


def _detect_conversion_type(text_lower: str, text: str) -> str:
    """Detect the primary conversion type."""
    if re.search(r"(予約|来店|来院|カウンセリング)", text):
        return "appointment"
    if re.search(r"(診断|タイプ|あなたに合った)", text):
        return "diagnosis"
    if re.search(r"(購入|注文|カート|お買い物|定期)", text):
        return "purchase"
    if re.search(r"(資料請求|無料相談|お問い合わせ|登録|申し込み)", text):
        return "lead"
    return ""


def _extract_urgencies(text: str) -> list[dict[str, str]]:
    """Extract urgency mentions."""
    urgencies: list[dict[str, str]] = []
    seen: set[str] = set()

    patterns: list[tuple[str, str]] = [
        ("limited_time", r"(期間限定|今だけ|本日限り|キャンペーン中|〜まで|～まで|\d+月\d+日まで)"),
        ("limited_stock", r"(残り\d+|在庫わずか|数量限定|限定\d+|先着\d+)"),
        ("countdown", r"(あと\d+[時日分秒]|カウントダウン|タイムセール)"),
    ]
    for urgency_type, pattern in patterns:
        for m in re.finditer(pattern, text):
            matched = m.group(0).strip()
            if matched not in seen:
                seen.add(matched)
                urgencies.append({"type": urgency_type, "text": matched})

    return urgencies


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


def batch_extract_lp_structures(
    session: Session,
    limit: int = 100,
) -> dict[str, int]:
    """Process LPSnapshot records that lack extracted_json.

    Finds up to ``limit`` LPSnapshot rows where ``extracted_json IS NULL``
    and ``dom_text IS NOT NULL``, runs structure extraction on each, and
    persists the result.

    Args:
        session: A sync SQLAlchemy session.
        limit: Maximum number of records to process in one batch.

    Returns:
        ``{"processed": <int>, "errors": <int>}``
    """
    snapshots = (
        session.query(LPSnapshot)
        .filter(LPSnapshot.extracted_json.is_(None))
        .filter(LPSnapshot.dom_text.isnot(None))
        .order_by(LPSnapshot.id)
        .limit(limit)
        .all()
    )

    processed = 0
    errors = 0

    for snap in snapshots:
        try:
            extracted = extract_lp_structure(
                dom_text=snap.dom_text,  # type: ignore[arg-type]
                url=snap.final_url or snap.initial_url,
                title=None,
            )
            snap.extracted_json = extracted  # type: ignore[assignment]
            processed += 1
            logger.info(
                "batch_extract: snapshot updated, snapshot_id=%s, lp_pattern=%s",
                snap.id, extracted.get("lp_pattern"),
            )
        except Exception:
            errors += 1
            logger.exception("batch_extract: failed for snapshot, snapshot_id=%s", snap.id)

    session.flush()

    logger.info(
        "batch_extract_lp_structures completed, processed=%d, errors=%d, total_found=%d",
        processed, errors, len(snapshots),
    )
    return {"processed": processed, "errors": errors}
