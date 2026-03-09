"""Helpers for Bedrock review queue and priority API contracts."""

from __future__ import annotations

from app.schemas.ad import build_real_metrics_payload
from app.services.ai.bedrock_classification_gateway import build_bedrock_decision_payload


def _normalize_provenance_label(value) -> str:
    text = str(value or "").strip().lower()
    if any(token in text for token in ("manual", "human", "override")):
        return "manual"
    if any(token in text for token in ("bedrock", "ai", "model", "claude")):
        return "ai"
    if text:
        return "rule"
    return "rule"


def _priority_bucket(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _real_metric_present(field_payload: dict | None) -> bool:
    provenance = field_payload or {}
    return str(provenance.get("metric_status") or "").strip().lower() == "real"


def build_bedrock_review_priority_payload(ad) -> dict:
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}
    decision = build_bedrock_decision_payload(ad)
    real_metrics = build_real_metrics_payload(ad)

    actual_metrics_present = any(
        _real_metric_present(real_metrics.get(field))
        for field in ("spend_provenance", "impressions_provenance", "reach_provenance")
    )
    if not actual_metrics_present:
        try:
            actual_metrics_present = float(getattr(ad, "view_count", 0) or 0) > 0 and not bool(meta.get("view_count_is_estimated"))
        except (TypeError, ValueError):
            actual_metrics_present = False

    provenance = {
        "language": _normalize_provenance_label(meta.get("language_source")),
        "product_category": _normalize_provenance_label(meta.get("product_category_source")),
        "topic_label": _normalize_provenance_label(meta.get("topic_source")),
        "priority": _normalize_provenance_label(meta.get("priority_score_source") or decision.get("priority_reason")),
        "review": (
            "manual"
            if decision["review_required"] or meta.get("manual_review") or meta.get("review_required")
            else _normalize_provenance_label(meta.get("review_source") or decision.get("review_reason"))
        ),
    }
    manual_override = any(label == "manual" for label in provenance.values())
    ai_used = any(label == "ai" for label in provenance.values())
    if manual_override:
        overall = "manual"
    elif ai_used:
        overall = "ai"
    else:
        overall = "rule"

    return {
        **decision,
        "priority_bucket": _priority_bucket(float(decision["priority_score"] or 0.0)),
        "actual_metrics_present": actual_metrics_present,
        "actual_metrics_focus": not actual_metrics_present and float(decision["priority_score"] or 0.0) >= 70.0,
        "provenance": provenance,
        "provenance_summary": overall,
    }
