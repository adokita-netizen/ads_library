"""A47 Meta creative extraction precision audit + retry helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.models.ad import Ad

_REPORTS_FILE = __import__("pathlib").Path(__file__).resolve().parent.parent.parent / "data" / "meta_creative_extraction_reports.json"
_SOURCE_NORMALIZATION = {
    "meta_api": "api_render_ad",
    "render_ad": "api_render_ad",
    "api_render_ad": "api_render_ad",
    "browser_overlay": "browser_overlay",
    "snapshot_parse": "snapshot_parse",
    "fallback": "fallback",
}
_RETRY_SOURCE_ORDER = ["api_render_ad", "browser_overlay", "snapshot_parse", "fallback"]


def _normalize_source(meta: dict) -> str:
    raw = str(
        meta.get("extract_source")
        or meta.get("creative_fetch_source")
        or meta.get("extraction_method")
        or meta.get("thumbnail_recovery_source")
        or meta.get("source")
        or "fallback"
    ).strip().lower()
    return _SOURCE_NORMALIZATION.get(raw, "fallback")


def _is_small_image(meta: dict) -> bool:
    width = int(meta.get("image_width") or meta.get("thumbnail_width") or 0)
    height = int(meta.get("image_height") or meta.get("thumbnail_height") or 0)
    return bool(width and height and (width < 300 or height < 300))


def build_extraction_audit_row(ad: Ad) -> dict:
    meta = ad.ad_metadata or {}
    extract_quality_score = int(meta.get("extract_quality_score") or 0)
    failure_reason = str(meta.get("creative_fetch_reason") or "").strip().lower() or ""
    text_missing = not str(ad.description or "").strip()
    creative_complete = bool((ad.image_url or ad.thumbnail_url or ad.video_url) and not text_missing)
    low_quality = _is_small_image(meta) or extract_quality_score < 40 or (str(getattr(ad.creative_type, "value", ad.creative_type) or "").lower() == "video" and not ad.video_url)
    return {
        "ad_id": ad.id,
        "extract_source": _normalize_source(meta),
        "extract_quality_score": extract_quality_score,
        "creative_complete": creative_complete,
        "failure_reason": failure_reason or ("text_missing" if text_missing else ""),
        "needs_reextract": bool(low_quality or text_missing or not creative_complete),
        "has_image": bool(ad.image_url or ad.thumbnail_url),
        "has_video": bool(ad.video_url),
        "has_text": not text_missing,
    }


def queue_low_quality_reextractions(session, *, min_quality: int = 40) -> dict:
    queued_ids: list[int] = []
    for ad in session.query(Ad).all():
        row = build_extraction_audit_row(ad)
        if not row["needs_reextract"]:
            continue
        meta = dict(ad.ad_metadata or {})
        meta["needs_media_retry"] = True
        meta["extract_source"] = row["extract_source"]
        meta["preferred_extract_source_order"] = list(_RETRY_SOURCE_ORDER)
        meta["extract_retry_queued_at"] = datetime.now(timezone.utc).isoformat()
        if row["extract_quality_score"] < min_quality:
            meta["extract_retry_reason"] = "low_extract_quality"
        elif not row["has_text"]:
            meta["extract_retry_reason"] = "text_missing"
        else:
            meta["extract_retry_reason"] = row["failure_reason"] or "creative_incomplete"
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        queued_ids.append(ad.id)
    session.flush()
    return {"queued_ad_ids": queued_ids, "queued_count": len(queued_ids)}


def build_meta_creative_extraction_report(session, *, persist: bool = True, top_n: int = 20) -> dict:
    rows = [build_extraction_audit_row(ad) for ad in session.query(Ad).all()]
    failure_rank: dict[str, int] = {}
    for row in rows:
        reason = row["failure_reason"] or ("incomplete_creative" if not row["creative_complete"] else "")
        if reason:
            failure_rank[reason] = failure_rank.get(reason, 0) + 1
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_ads": len(rows),
            "creative_complete_count": sum(int(row["creative_complete"]) for row in rows),
            "needs_reextract_count": sum(int(row["needs_reextract"]) for row in rows),
            "avg_extract_quality_score": round(sum(row["extract_quality_score"] for row in rows) / len(rows), 2) if rows else 0.0,
        },
        "failure_reason_ranking": [
            {"reason": reason, "count": count}
            for reason, count in sorted(failure_rank.items(), key=lambda item: item[1], reverse=True)[:top_n]
        ],
        "ad_rows": rows[:top_n],
    }
    if persist:
        import json

        payload = []
        if _REPORTS_FILE.exists():
            try:
                loaded = json.loads(_REPORTS_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    payload = [row for row in loaded if isinstance(row, dict)]
            except Exception:
                payload = []
        payload.append(report)
        _REPORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _REPORTS_FILE.write_text(json.dumps(payload[-30:], ensure_ascii=False, indent=2), encoding="utf-8")
    return report
