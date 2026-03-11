"""Video timeline builder service.

Combines frame-level OCR (TextDetection) and ASR transcript segments
(Transcription) into unified VideoTimeline table entries, with derived
fields for opening_hook, proof_sequence, and cta_endcard.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.models.ad import Ad, AdFrame
from app.models.analysis import AdAnalysis, TextDetection, Transcription
from app.models.brand_registry import VideoTimeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword sets for classification
# ---------------------------------------------------------------------------

_PAIN_KEYWORDS = [
    "悩み", "つらい", "困って", "痛い", "不安", "ストレス", "老化",
    "肌荒れ", "シミ", "くすみ", "たるみ", "シワ", "乾燥", "薄毛",
    "太り", "疲れ", "不眠", "problem", "pain", "worry", "trouble",
]

_SHOCK_KEYWORDS = [
    "衝撃", "驚き", "まさか", "ヤバい", "やばい", "嘘", "うそ",
    "知らない", "知らなかった", "実は", "危険", "要注意", "閲覧注意",
    "shocking", "unbelievable", "incredible",
]

_BENEFIT_KEYWORDS = [
    "簡単", "たった", "だけで", "最短", "すぐに", "即効", "効果",
    "変わる", "改善", "実感", "キレイ", "美肌", "スッキリ",
    "benefit", "result", "transform", "easy",
]

_AUTHORITY_KEYWORDS = [
    "医師", "専門家", "監修", "特許", "認定", "公式", "No.1",
    "ナンバーワン", "受賞", "TV", "テレビ", "雑誌",
    "doctor", "expert", "certified", "award", "official",
]

_PROOF_KEYWORDS = [
    "満足度", "口コミ", "レビュー", "実績", "ビフォーアフター",
    "before", "after", "証拠", "データ", "臨床", "試験",
    "No.1", "ナンバーワン", "受賞", "特許", "監修", "医師",
    "万人", "万本", "万個", "突破", "達成",
    "testimonial", "review", "proof", "clinical",
]


# ---------------------------------------------------------------------------
# Hook type classification
# ---------------------------------------------------------------------------

def _classify_hook_type(text: str) -> str | None:
    """Classify opening hook text into a type using keyword matching."""
    if not text:
        return None

    stripped = text.strip()

    # Question: ends with ? or Japanese question markers
    if stripped.endswith(("?", "？")):
        return "question"

    lowered = stripped.lower()

    # Problem / pain
    if any(kw in lowered for kw in _PAIN_KEYWORDS):
        return "problem"

    # Shock
    if any(kw in lowered for kw in _SHOCK_KEYWORDS):
        return "shock"

    # Authority
    if any(kw in lowered for kw in _AUTHORITY_KEYWORDS):
        return "authority"

    # Benefit
    if any(kw in lowered for kw in _BENEFIT_KEYWORDS):
        return "benefit"

    return None


# ---------------------------------------------------------------------------
# Timeline entry builders
# ---------------------------------------------------------------------------

def _build_ocr_map(
    text_detections: list[TextDetection],
    frames: list[AdFrame],
) -> dict[float, str]:
    """Map keyframe timestamps to concatenated OCR text.

    TextDetection has frame_number + timestamp_seconds.  We use
    timestamp_seconds directly but also build a frame_number -> timestamp
    lookup from AdFrame for any detections missing an explicit timestamp.
    """
    frame_ts: dict[int, float] = {f.frame_number: f.timestamp_seconds for f in frames}

    # Group OCR text by timestamp (rounded to 1 decimal for grouping)
    ts_texts: dict[float, list[str]] = {}
    for td in text_detections:
        ts = td.timestamp_seconds
        if ts is None:
            ts = frame_ts.get(td.frame_number)
        if ts is None:
            continue
        key = round(ts, 1)
        ts_texts.setdefault(key, []).append(td.text)

    return {ts: " ".join(texts) for ts, texts in ts_texts.items()}


def _build_asr_index(transcriptions: list[Transcription]) -> list[dict[str, Any]]:
    """Return sorted ASR segments as dicts with start/end in seconds."""
    segments = []
    for tr in transcriptions:
        if tr.start_time_ms is None or tr.end_time_ms is None:
            continue
        segments.append({
            "text": tr.text,
            "start_s": tr.start_time_ms / 1000.0,
            "end_s": tr.end_time_ms / 1000.0,
        })
    segments.sort(key=lambda s: s["start_s"])
    return segments


def _asr_at_timestamp(segments: list[dict[str, Any]], ts: float) -> str | None:
    """Find ASR text active at a given timestamp (seconds)."""
    for seg in segments:
        if seg["start_s"] <= ts <= seg["end_s"]:
            return seg["text"]
    return None


def _collect_text_in_range(
    ocr_map: dict[float, str],
    asr_segments: list[dict[str, Any]],
    start_s: float,
    end_s: float,
) -> str:
    """Collect all OCR and ASR text within a time range."""
    parts: list[str] = []

    # OCR in range
    for ts, text in sorted(ocr_map.items()):
        if start_s <= ts <= end_s and text:
            parts.append(text)

    # ASR in range
    for seg in asr_segments:
        if seg["end_s"] >= start_s and seg["start_s"] <= end_s and seg["text"]:
            parts.append(seg["text"])

    return " ".join(parts)


def _extract_proof_sequence(
    ocr_map: dict[float, str],
    asr_segments: list[dict[str, Any]],
) -> list[str]:
    """Find proof-related keywords mentioned in OCR/ASR text."""
    all_text_parts: list[str] = list(ocr_map.values())
    all_text_parts.extend(seg["text"] for seg in asr_segments)
    combined = " ".join(all_text_parts).lower()

    found: list[str] = []
    seen: set[str] = set()
    for kw in _PROOF_KEYWORDS:
        if kw.lower() in combined and kw not in seen:
            found.append(kw)
            seen.add(kw)
    return found


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build_timeline_for_ad(session: Session, ad_id: int) -> VideoTimeline | None:
    """Build a unified OCR+ASR VideoTimeline for a single ad.

    Returns the created VideoTimeline object (already added to session),
    or None if insufficient data exists.
    """
    # Load AdAnalysis with text_detections and transcriptions
    analysis: AdAnalysis | None = session.execute(
        select(AdAnalysis)
        .options(
            joinedload(AdAnalysis.text_detections),
            joinedload(AdAnalysis.transcriptions),
        )
        .where(AdAnalysis.ad_id == ad_id)
    ).unique().scalar_one_or_none()

    if analysis is None:
        logger.debug("No AdAnalysis found for ad_id=%s", ad_id)
        return None

    text_detections: list[TextDetection] = analysis.text_detections or []
    transcriptions: list[Transcription] = analysis.transcriptions or []

    if not text_detections and not transcriptions:
        logger.debug("No text_detections or transcriptions for ad_id=%s", ad_id)
        return None

    # Load AdFrames
    frames: list[AdFrame] = (
        session.execute(
            select(AdFrame)
            .where(AdFrame.ad_id == ad_id)
            .order_by(AdFrame.timestamp_seconds)
        )
        .scalars()
        .all()
    )

    # Build OCR map and ASR index
    ocr_map = _build_ocr_map(text_detections, frames)
    asr_segments = _build_asr_index(transcriptions)

    # Determine all keyframe timestamps (union of frame timestamps and OCR timestamps)
    keyframe_timestamps: set[float] = set()
    for f in frames:
        keyframe_timestamps.add(round(f.timestamp_seconds, 1))
    for ts in ocr_map:
        keyframe_timestamps.add(ts)
    # Also add ASR segment start times as keyframe points
    for seg in asr_segments:
        keyframe_timestamps.add(round(seg["start_s"], 1))

    if not keyframe_timestamps:
        logger.debug("No keyframe timestamps for ad_id=%s", ad_id)
        return None

    sorted_timestamps = sorted(keyframe_timestamps)

    # Build timeline entries
    timeline_entries: list[dict[str, Any]] = []
    unique_ocr_set: set[str] = set()
    has_asr = bool(transcriptions)

    for ts in sorted_timestamps:
        ocr_text = ocr_map.get(ts)
        asr_text = _asr_at_timestamp(asr_segments, ts)

        entry: dict[str, Any] = {
            "t": round(ts * 1000.0, 1),  # convert to milliseconds
            "ocr": ocr_text,
            "asr": asr_text,
            "visual_tags": [],
        }
        timeline_entries.append(entry)

        if ocr_text:
            unique_ocr_set.add(ocr_text)

    # Determine total duration
    max_ts = sorted_timestamps[-1] if sorted_timestamps else 0.0
    # Also consider ASR end times
    if asr_segments:
        max_asr_end = max(seg["end_s"] for seg in asr_segments)
        max_ts = max(max_ts, max_asr_end)
    total_duration_ms = int(round(max_ts * 1000.0))

    # Opening hook: text from first 5 seconds
    opening_text = _collect_text_in_range(ocr_map, asr_segments, 0.0, 5.0)
    opening_hook = opening_text.strip() if opening_text.strip() else None
    opening_hook_type = _classify_hook_type(opening_hook) if opening_hook else None

    # Proof sequence
    proof_sequence = _extract_proof_sequence(ocr_map, asr_segments)

    # CTA endcard: OCR text from last 5 seconds
    cta_start_s = max(0.0, max_ts - 5.0)
    cta_parts: list[str] = []
    for ts, text in sorted(ocr_map.items()):
        if ts >= cta_start_s and text:
            cta_parts.append(text)
    cta_endcard = " ".join(cta_parts).strip() if cta_parts else None

    # Create VideoTimeline
    vt = VideoTimeline(
        ad_id=ad_id,
        timeline=timeline_entries,
        opening_hook=opening_hook,
        opening_hook_type=opening_hook_type,
        proof_sequence=proof_sequence if proof_sequence else None,
        cta_endcard=cta_endcard,
        total_duration_ms=total_duration_ms,
        keyframe_count=len(sorted_timestamps),
        unique_ocr_texts=len(unique_ocr_set),
        has_asr=has_asr,
    )
    session.add(vt)

    logger.info(
        "Built VideoTimeline for ad_id=%s: %d entries, duration=%dms, hook_type=%s",
        ad_id,
        len(timeline_entries),
        total_duration_ms,
        opening_hook_type,
    )
    return vt


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def batch_build_timelines(session: Session, limit: int = 200) -> dict[str, int]:
    """Build VideoTimeline for ads that don't have one yet.

    Targets video ads with AdAnalysis containing text_detections or
    transcriptions.

    Returns:
        {"processed": int, "created": int}
    """
    # Find video ad IDs that already have a VideoTimeline
    existing_vt_subq = (
        select(VideoTimeline.ad_id)
        .scalar_subquery()
    )

    # Find ad IDs that have AdAnalysis with at least text_detections or transcriptions
    has_ocr_subq = select(TextDetection.analysis_id).correlate(AdAnalysis).limit(1)
    has_asr_subq = select(Transcription.analysis_id).correlate(AdAnalysis).limit(1)

    # Query: video ads with analysis that have OCR or ASR, but no VideoTimeline
    candidate_ids: list[int] = (
        session.execute(
            select(Ad.id)
            .join(AdAnalysis, AdAnalysis.ad_id == Ad.id)
            .where(
                and_(
                    Ad.creative_type == "video",
                    Ad.id.notin_(existing_vt_subq),
                    (
                        AdAnalysis.id.in_(
                            select(TextDetection.analysis_id).distinct()
                        )
                        | AdAnalysis.id.in_(
                            select(Transcription.analysis_id).distinct()
                        )
                    ),
                )
            )
            .order_by(Ad.id)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    processed = 0
    created = 0

    for ad_id in candidate_ids:
        processed += 1
        try:
            vt = build_timeline_for_ad(session, ad_id)
            if vt is not None:
                created += 1
        except Exception:
            logger.exception("Failed to build timeline for ad_id=%s", ad_id)
            continue

    if created > 0:
        session.flush()

    logger.info(
        "batch_build_timelines: processed=%d, created=%d",
        processed,
        created,
    )
    return {"processed": processed, "created": created}
