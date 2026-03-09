"""Normalize Bedrock classification outputs into stable backend contracts."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.ad import build_language_taxonomy_payload

_BEDROCK_REQUIRED_FIELDS = ("language", "product_category", "topic_label")
_BEDROCK_STATUS_VOCAB = ("success", "partial", "fallback", "timeout", "missing")
_BEDROCK_DECISION_REQUIRED_FIELDS = (
    "language",
    "product_category",
    "product_subcategory",
    "topic_label",
    "offer_type",
    "funnel_type",
    "priority_score",
    "priority_reason",
    "review_required",
    "review_reason",
    "confidence_band",
    "model_name",
    "prompt_version",
    "classified_at",
)
_BEDROCK_DECISION_SOURCE_PRIORITY = ["rule_override", "bedrock_result", "rule_fallback"]
_BEDROCK_PROMPT_REGISTRY = {
    "classification-v1": {
        "prompt_version": "classification-v1",
        "model_name": "anthropic.claude-3-5-sonnet",
        "task": "language_product_topic_classification",
        "required_output_fields": [
            "language",
            "product_category",
            "product_subcategory",
            "topic_label",
            "offer_type",
            "funnel_type",
            "priority_score",
            "review_required",
        ],
    }
}


def _contains_bedrock_source(*values) -> bool:
    for value in values:
        text = str(value or "").lower()
        if "bedrock" in text:
            return True
    return False


def _normalize_text(value) -> str:
    return str(value or "").strip()


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return bool(value)


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_datetime(*values) -> str | None:
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return None


def get_bedrock_gateway_contract() -> dict:
    return {
        "required_fields": list(_BEDROCK_REQUIRED_FIELDS),
        "status_vocab": list(_BEDROCK_STATUS_VOCAB),
        "source_priority": ["bedrock_result", "rule_fallback"],
        "timeout_behavior": {
            "status": "timeout",
            "fallback_applied": True,
            "error_code": "timeout",
        },
        "partial_behavior": {
            "status": "partial",
            "fallback_applied": True,
            "error_code": "partial_bedrock_result",
        },
        "invalid_json_behavior": {
            "status": "fallback",
            "fallback_applied": True,
            "error_code": "invalid_json",
        },
    }


def build_bedrock_classification_gateway_payload(ad) -> dict:
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}
    taxonomy = build_language_taxonomy_payload(ad)

    language_bedrock = _contains_bedrock_source(meta.get("language_source"), meta.get("classification_source"))
    product_bedrock = _contains_bedrock_source(meta.get("product_category_source"), meta.get("classification_source"))
    topic_bedrock = _contains_bedrock_source(meta.get("topic_source"), meta.get("classification_source"))

    language_value = taxonomy["language"] if language_bedrock else taxonomy["language"]
    product_value = _normalize_text(meta.get("product_category")) or taxonomy["product_category"]
    topic_value = _normalize_text(meta.get("topic_label"))

    bedrock_fields_present = {
        "language": language_bedrock and bool(_normalize_text(meta.get("language"))),
        "product_category": product_bedrock and bool(_normalize_text(meta.get("product_category"))),
        "topic_label": topic_bedrock and bool(topic_value),
    }
    any_bedrock = any(bedrock_fields_present.values())
    missing_fields = [field for field, present in bedrock_fields_present.items() if any_bedrock and not present]

    error_code = None
    raw_status = _normalize_text(meta.get("classification_status") or meta.get("bedrock_status") or meta.get("classification_error_code"))
    if raw_status in {"timeout", "timed_out"}:
        status = "timeout"
        error_code = "timeout"
    elif raw_status in {"invalid_json", "malformed_json"}:
        status = "fallback"
        error_code = "invalid_json"
    elif any_bedrock and not missing_fields:
        status = "success"
    elif any_bedrock:
        status = "partial"
        error_code = "partial_bedrock_result"
    elif language_value != "unknown" or product_value != "uncategorized" or topic_value:
        status = "fallback"
    else:
        status = "missing"
        error_code = "classification_missing"

    reasons: list[str] = []
    if any_bedrock:
        reasons.append("bedrock_result_used")
    if status in {"partial", "fallback", "timeout"}:
        reasons.append("rule_fallback_used")
    if status == "partial":
        reasons.append("partial_bedrock_result")
    if status == "timeout":
        reasons.append("timeout_fallback")
    if error_code == "invalid_json":
        reasons.append("invalid_json_fallback")
    if bool(meta.get("review_required") or meta.get("manual_review") or meta.get("needs_topic_review")):
        reasons.append("manual_review_required")
    if status == "missing":
        reasons.append("classification_missing")

    confidence_candidates = [
        meta.get("classification_confidence"),
        meta.get("language_confidence") if language_bedrock else None,
        meta.get("product_category_confidence") if product_bedrock else None,
        meta.get("topic_confidence") if topic_bedrock else None,
    ]
    confidence_values = []
    for value in confidence_candidates:
        try:
            if value is not None:
                confidence_values.append(float(value))
        except (TypeError, ValueError):
            continue
    confidence = round(max(confidence_values), 4) if confidence_values else 0.0

    return {
        "ad_id": getattr(ad, "id", None),
        "language": language_value,
        "product_category": product_value,
        "topic_label": topic_value,
        "confidence": confidence,
        "reasons": reasons,
        "model_name": _normalize_text(meta.get("bedrock_model_name") or meta.get("classification_model_name") or meta.get("model_name")),
        "classified_at": _coerce_datetime(
            meta.get("bedrock_classified_at"),
            meta.get("classified_at"),
            getattr(ad, "updated_at", None),
        ),
        "status": status,
        "fallback_applied": status in {"partial", "fallback", "timeout"},
        "partial_fields": missing_fields,
        "error_code": error_code,
        "source_priority": ["bedrock_result", "rule_fallback"],
    }


def get_bedrock_prompt_registry() -> dict:
    return {
        "default_prompt_version": "classification-v1",
        "items": list(_BEDROCK_PROMPT_REGISTRY.values()),
    }


def get_bedrock_decision_contract() -> dict:
    return {
        "required_fields": list(_BEDROCK_DECISION_REQUIRED_FIELDS),
        "source_priority": list(_BEDROCK_DECISION_SOURCE_PRIORITY),
        "confidence_bands": {
            "high": {"min": 0.85, "max": 1.0},
            "medium": {"min": 0.6, "max": 0.8499},
            "low": {"min": 0.0, "max": 0.5999},
        },
        "fallback_behavior": {
            "timeout": {"status": "timeout", "review_required": True, "review_reason": "bedrock_timeout"},
            "partial": {"status": "partial", "review_required": True, "review_reason": "partial_bedrock_result"},
            "invalid_json": {"status": "fallback", "review_required": True, "review_reason": "invalid_json"},
        },
        "prompt_registry": get_bedrock_prompt_registry(),
    }


def build_bedrock_decision_payload(ad) -> dict:
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}
    taxonomy = build_language_taxonomy_payload(ad)
    gateway = build_bedrock_classification_gateway_payload(ad)
    prompt_version = _normalize_text(meta.get("prompt_version")) or "classification-v1"
    prompt_meta = _BEDROCK_PROMPT_REGISTRY.get(prompt_version, _BEDROCK_PROMPT_REGISTRY["classification-v1"])

    creative_analysis = meta.get("creative_analysis")
    creative_analysis = creative_analysis if isinstance(creative_analysis, dict) else {}

    if gateway["confidence"] >= 0.85:
        confidence_band = "high"
    elif gateway["confidence"] >= 0.6:
        confidence_band = "medium"
    else:
        confidence_band = "low"

    priority_source = _normalize_text(meta.get("priority_score_source"))
    classification_source = _normalize_text(meta.get("classification_source"))
    explicit_override = any(
        source in {"rule_override", "manual_override", "human_override"}
        for source in (
            _normalize_text(meta.get("language_source")),
            _normalize_text(meta.get("product_category_source")),
            _normalize_text(meta.get("topic_source")),
            priority_source,
            classification_source,
        )
    )
    uses_bedrock_priority = _contains_bedrock_source(priority_source, classification_source)
    if explicit_override:
        priority_reason = "rule_override"
    elif uses_bedrock_priority:
        priority_reason = "bedrock_priority_score"
    else:
        priority_reason = "rule_priority_score"

    review_required = _coerce_bool(
        meta.get("review_required") or meta.get("manual_review") or meta.get("needs_topic_review")
    )
    if gateway["error_code"] == "timeout":
        review_required = True
        review_reason = "bedrock_timeout"
    elif gateway["error_code"] == "invalid_json":
        review_required = True
        review_reason = "invalid_json"
    elif gateway["status"] == "partial":
        review_required = True
        review_reason = "partial_bedrock_result"
    elif review_required:
        review_reason = _normalize_text(meta.get("review_reason")) or "manual_review_required"
    else:
        review_reason = _normalize_text(meta.get("review_reason"))

    return {
        "ad_id": getattr(ad, "id", None),
        "language": gateway["language"] or taxonomy["language"],
        "product_category": gateway["product_category"] or taxonomy["product_category"],
        "product_subcategory": _normalize_text(meta.get("product_subcategory")) or taxonomy["product_subcategory"],
        "topic_label": gateway["topic_label"],
        "offer_type": _normalize_text(meta.get("offer_type")) or _normalize_text(creative_analysis.get("offer_type")),
        "funnel_type": _normalize_text(meta.get("funnel_type")),
        "priority_score": round(_coerce_float(meta.get("priority_score"), 0.0), 3),
        "priority_reason": priority_reason,
        "review_required": review_required,
        "review_reason": review_reason or None,
        "confidence_band": confidence_band,
        "model_name": gateway["model_name"] or prompt_meta["model_name"],
        "prompt_version": prompt_version,
        "classified_at": gateway["classified_at"],
        "status": gateway["status"],
        "fallback_applied": gateway["fallback_applied"],
        "error_code": gateway["error_code"],
        "source_priority": list(_BEDROCK_DECISION_SOURCE_PRIORITY),
    }
