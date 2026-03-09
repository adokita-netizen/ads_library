"""Ad360 unified per-ad record helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.models.ad import Ad

AD360_REQUIRED_FIELDS = {
    "core": ["title", "advertiser_name", "platform", "first_seen_at", "last_seen_at", "status"],
    "creative": ["thumbnail_url", "image_url", "video_url", "snapshot_url", "duration_seconds"],
    "text": ["description", "ocr_texts", "lp_text", "transcript"],
    "analysis": ["topic_tags", "evidence_terms", "hit_drivers", "hit_score"],
    "lp": ["destination_url", "final_url", "lp_meta"],
}


def _missing_fields(data: dict, required: list[str]) -> list[str]:
    missing = []
    for field in required:
        value = data.get(field)
        if value is None or value == "" or value == [] or value == {}:
            missing.append(field)
    return missing


def build_ad360_sections(ad: Ad, *, ad_anal=None, text_rows=None, tr_rows=None, lp=None, lp_anal=None) -> dict:
    meta = ad.ad_metadata or {}
    ocr_texts = [t.text for t in (text_rows or []) if getattr(t, "text", None)]
    transcript = " ".join([t.text for t in (tr_rows or []) if getattr(t, "text", None)]).strip()
    final_url = (
        (lp.final_url if lp else None)
        or ((meta.get("lp_info") or {}).get("final_url") if isinstance(meta.get("lp_info"), dict) else None)
        or ((meta.get("lp_data") or {}).get("final_url") if isinstance(meta.get("lp_data"), dict) else None)
        or ""
    )
    lp_meta = (meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}) or (
        meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    )

    sections = {
        "core": {
            "data": {
                "ad_id": ad.id,
                "external_id": ad.external_id or "",
                "title": ad.title or "",
                "advertiser_name": ad.advertiser_name or "",
                "platform": str(getattr(ad.platform, "value", ad.platform) or ""),
                "first_seen_at": ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                "last_seen_at": ad.last_seen_at.isoformat() if ad.last_seen_at else "",
                "status": str(getattr(ad.status, "value", ad.status) or ""),
            },
        },
        "creative": {
            "data": {
                "thumbnail_url": ad.thumbnail_url or "",
                "image_url": ad.image_url or "",
                "video_url": ad.video_url or "",
                "snapshot_url": ad.snapshot_url or "",
                "orientation": str(meta.get("orientation") or ""),
                "duration_seconds": ad.duration_seconds,
            },
        },
        "text": {
            "data": {
                "description": ad.description or "",
                "ocr_texts": ocr_texts,
                "lp_text": str(meta.get("lp_text") or ""),
                "transcript": transcript,
            },
        },
        "analysis": {
            "data": {
                "topic_tags": meta.get("topic_tags") if isinstance(meta.get("topic_tags"), list) else [],
                "evidence_terms": meta.get("topic_evidence") if isinstance(meta.get("topic_evidence"), list) else [],
                "hit_drivers": meta.get("hit_drivers") if isinstance(meta.get("hit_drivers"), list) else [],
                "hit_score": float(meta.get("latest_hit_score") or 0) if meta.get("latest_hit_score") is not None else None,
                "topic_label": str(meta.get("topic_label") or ""),
                "topic_confidence": meta.get("topic_confidence"),
                "extract_quality_score": meta.get("extract_quality_score"),
            },
        },
        "lp": {
            "data": {
                "destination_url": ad.destination_url or "",
                "final_url": final_url,
                "lp_meta": lp_meta,
                "has_lp": lp is not None or bool(lp_meta),
            },
        },
        "quality": {
            "data": {
                "needs_media_retry": bool(meta.get("needs_media_retry")),
                "quarantine_reason": str(meta.get("quarantine_reason") or ""),
                "is_incomplete_record": bool(meta.get("is_incomplete_record")),
            },
        },
    }

    for section, required in AD360_REQUIRED_FIELDS.items():
        sections[section]["missing_fields"] = _missing_fields(sections[section]["data"], required)
    return sections


def summarize_ad360_completeness(sections: dict, *, threshold: float = 0.8) -> dict:
    required_count = 0
    missing: list[str] = []
    for section, required in AD360_REQUIRED_FIELDS.items():
        required_count += len(required)
        missing.extend([f"{section}.{field}" for field in sections.get(section, {}).get("missing_fields", [])])
    missing_count = len(missing)
    filled_count = max(0, required_count - missing_count)
    completeness_pct = round((filled_count / required_count), 3) if required_count else 1.0
    return {
        "required_field_count": required_count,
        "filled_required_field_count": filled_count,
        "missing_required_fields": missing,
        "completeness_pct": completeness_pct,
        "should_reprocess": completeness_pct < threshold,
    }


def audit_ad360_completeness(session, *, threshold: float = 0.8) -> dict:
    queued_ids: list[int] = []
    quarantined_ids: list[int] = []
    for ad in session.query(Ad).all():
        sections = build_ad360_sections(ad)
        completeness = summarize_ad360_completeness(sections, threshold=threshold)
        meta = dict(ad.ad_metadata or {})
        meta["ad360_completeness"] = completeness["completeness_pct"]
        meta["ad360_missing_fields"] = completeness["missing_required_fields"]
        meta["ad360_needs_reprocess"] = completeness["should_reprocess"]
        if completeness["should_reprocess"]:
            queued_ids.append(ad.id)
            if completeness["completeness_pct"] < 0.5 and not meta.get("quarantine_reason"):
                meta["quarantine_reason"] = "ad360_low_completeness"
                meta["quarantined_at"] = datetime.now(timezone.utc).isoformat()
                quarantined_ids.append(ad.id)
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
    session.flush()
    return {
        "queued_reprocess_ad_ids": queued_ids,
        "queued_reprocess_count": len(queued_ids),
        "quarantined_ad_ids": quarantined_ids,
        "quarantined_count": len(quarantined_ids),
    }
