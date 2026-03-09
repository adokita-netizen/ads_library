"""CI-123: Extraction result validity scoring."""

import structlog

logger = structlog.get_logger()


def score_extraction(ad) -> dict:
    """Score extraction validity for a single ad.

    Returns a 0-100 validity score, breakdown, and operator-facing reasons.
    """
    breakdown = {}
    total = 0
    meta = ad.ad_metadata or {}

    # 1. Creative payload consistency (0-30)
    creative_score = 0
    has_thumb = bool(ad.thumbnail_s3_key or ad.thumbnail_url)
    has_image = bool(getattr(ad, "image_s3_key", None) or ad.image_url)
    has_video = bool(getattr(ad, "s3_key", None) or ad.video_url)
    if has_video:
        creative_score += 15
    if has_image:
        creative_score += 10
    if has_thumb:
        creative_score += 5
    breakdown["creative_payload"] = creative_score
    total += creative_score

    # 2. Core metadata fidelity (0-25)
    metadata_score = 0
    if ad.title:
        metadata_score += 5
    if ad.advertiser_name:
        metadata_score += 5
    if meta.get("genre") or (ad.category and str(ad.category) != "other"):
        metadata_score += 5
    if ad.duration_seconds and ad.duration_seconds > 0:
        metadata_score += 5
    if ad.destination_url or meta.get("destination_url"):
        metadata_score += 5
    breakdown["metadata_fidelity"] = metadata_score
    total += metadata_score

    # 3. Semantic extraction alignment (0-25)
    semantic_score = 0
    topic_confidence = float(meta.get("topic_confidence") or 0.0)
    if topic_confidence >= 0.8:
        semantic_score += 10
    elif topic_confidence >= 0.6:
        semantic_score += 6
    elif topic_confidence > 0:
        semantic_score += 2
    creative_analysis = meta.get("creative_analysis") if isinstance(meta.get("creative_analysis"), dict) else {}
    if creative_analysis:
        semantic_score += 10
    matched_terms = meta.get("matched_terms") if isinstance(meta.get("matched_terms"), list) else []
    if matched_terms:
        semantic_score += 5
    breakdown["semantic_alignment"] = semantic_score
    total += semantic_score

    # 4. LP/extraction traceability (0-20)
    trace_score = 0
    lp_status = str(meta.get("lp_status") or "").lower()
    if lp_status in {"alive", "redirect", "200", "301", "302", "303", "307", "308"}:
        trace_score += 10
    elif ad.destination_url or meta.get("destination_url"):
        trace_score += 4
    if meta.get("extractor_version"):
        trace_score += 5
    if meta.get("creative_fetch_source") or meta.get("extraction_method"):
        trace_score += 5
    breakdown["traceability"] = trace_score
    total += trace_score

    validity_reasons: list[str] = []
    if creative_score < 10:
        validity_reasons.append("creative_payload_weak")
    if metadata_score < 15:
        validity_reasons.append("metadata_sparse")
    if semantic_score < 10:
        validity_reasons.append("semantic_signals_weak")
    if trace_score < 10:
        validity_reasons.append("traceability_incomplete")

    final_score = min(100, total)
    return {
        "score": final_score,
        "breakdown": breakdown,
        "is_valid": final_score >= 60,
        "validity_reasons": validity_reasons,
    }
