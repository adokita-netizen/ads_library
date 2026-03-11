"""Hit proxy scoring service.

Estimates ad effectiveness using observable signals since we can't see
actual spend/conversions for competitor ads.

Reference architecture formula:
  hit_proxy_score =
    0.35 * active_days_norm          # Long-running = effective
  + 0.20 * recurrence_norm           # Same creative recurring = confident advertiser
  + 0.15 * platform_spread_norm      # Multi-platform deployment
  + 0.10 * variant_spread_norm       # Number of variants in family
  + 0.10 * ad_to_lp_consistency_norm # Ad-LP text similarity
  + 0.10 * capture_confidence_norm   # Data quality completeness
"""

import math
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import func as sa_func
from sqlalchemy import text as sa_text
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = structlog.get_logger()

# Normalization constants
_ACTIVE_DAYS_P90 = 60  # 90th percentile active days for normalization
_VIEW_COUNT_P90 = 500_000  # 90th percentile view count (kept for backward compat)
_MAX_PLATFORMS = 5  # Max distinct platforms for normalization
_RECURRENCE_P90 = 10  # 90th percentile recurrence count (family member_count)
_VARIANT_P90 = 8  # 90th percentile variant count


def _sigmoid(x: float, midpoint: float = 0.5, steepness: float = 10.0) -> float:
    """Smooth sigmoid normalization to [0, 1]."""
    return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))


def _ensure_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware (UTC)."""
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_active_days(ad: Ad) -> int:
    """Calculate days the ad has been active.

    Prefers ad_delivery_start_time / ad_delivery_stop_time (from Meta API)
    over first_seen_at / last_seen_at (observation-based).
    """
    # Prefer delivery dates from Meta API
    start = _ensure_tz(getattr(ad, "ad_delivery_start_time", None))
    stop = _ensure_tz(getattr(ad, "ad_delivery_stop_time", None))

    # Fallback to observation-based dates
    if start is None:
        start = _ensure_tz(ad.first_seen_at)
    if stop is None:
        stop = _ensure_tz(ad.last_seen_at)

    if start and stop:
        return max(0, (stop - start).days)
    if start:
        return max(0, (datetime.now(timezone.utc) - start).days)
    return 0


def compute_capture_confidence(ad: Ad) -> float:
    """Compute data completeness score (0-1) for an ad.

    Components and weights:
      has_thumbnail   0.15
      has_body_text   0.15
      has_ocr         0.15
      has_asr         0.10
      has_lp          0.20
      has_destination 0.10
      has_angle_fact  0.15
    """
    score = 0.0

    # has_thumbnail: thumbnail_s3_key or thumbnail_url
    if ad.thumbnail_s3_key or ad.thumbnail_url or ad.image_s3_key:
        score += 0.15

    # has_body_text: description or title
    if ad.description and len(ad.description.strip()) > 0:
        score += 0.15
    elif ad.title and len(ad.title.strip()) > 0:
        score += 0.10  # partial credit for title-only

    # has_ocr: check cards or searchable_text for OCR content
    has_ocr = False
    if hasattr(ad, "cards") and ad.cards:
        has_ocr = any(
            c.ocr_text and len(c.ocr_text.strip()) > 0
            for c in ad.cards
        )
    if not has_ocr and hasattr(ad, "creative_assets") and ad.creative_assets:
        has_ocr = any(
            a.ocr_text and len(a.ocr_text.strip()) > 0
            for a in ad.creative_assets
        )
    if has_ocr:
        score += 0.15

    # has_asr: check cards or creative_assets
    has_asr = False
    if hasattr(ad, "cards") and ad.cards:
        has_asr = any(
            c.asr_text and len(c.asr_text.strip()) > 0
            for c in ad.cards
        )
    if not has_asr and hasattr(ad, "creative_assets") and ad.creative_assets:
        has_asr = any(
            a.asr_text and len(a.asr_text.strip()) > 0
            for a in ad.creative_assets
        )
    if has_asr:
        score += 0.10

    # has_lp: check cards for LP snapshots, or ad_metadata lp_info
    has_lp = False
    if hasattr(ad, "cards") and ad.cards:
        has_lp = any(
            hasattr(c, "lp_snapshots") and c.lp_snapshots
            for c in ad.cards
        )
    if not has_lp:
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        lp_info = meta.get("lp_info", {})
        if isinstance(lp_info, dict) and lp_info.get("final_url"):
            has_lp = True
    if has_lp:
        score += 0.20

    # has_destination_url
    if ad.destination_url and len(ad.destination_url.strip()) > 0:
        score += 0.10

    # has_angle_fact: check cards for angle_facts
    has_angle = False
    if hasattr(ad, "cards") and ad.cards:
        has_angle = any(
            hasattr(c, "angle_facts") and c.angle_facts
            for c in ad.cards
        )
    if has_angle:
        score += 0.15

    return round(min(1.0, score), 4)


def compute_hit_proxy_score(
    active_days: int,
    recurrence_count: int = 1,
    platform_count: int = 1,
    variant_count: int = 1,
    ad_to_lp_consistency: float = 0.0,
    capture_confidence: float = 0.0,
    last_seen_at: Optional[datetime] = None,
    *,
    # Legacy parameters kept for backward compatibility
    view_count: int = 0,
) -> float:
    """Compute hit proxy score (0-100 scale).

    Reference architecture formula:
      0.35 * active_days_norm
    + 0.20 * recurrence_norm
    + 0.15 * platform_spread_norm
    + 0.10 * variant_spread_norm
    + 0.10 * ad_to_lp_consistency_norm
    + 0.10 * capture_confidence_norm

    Args:
        active_days: Number of days the ad/family has been active
        recurrence_count: Times this creative family was re-used (member_count)
        platform_count: Number of distinct platforms where this creative appeared
        variant_count: Number of creative variants in the family
        ad_to_lp_consistency: Pre-computed ad-LP text similarity score (0-1)
        capture_confidence: Data completeness score (0-1)
        last_seen_at: When the ad was last observed (retained for filtering, not in formula)
        view_count: Legacy parameter, ignored in new formula but kept for API compat

    Returns:
        Score from 0 to 100
    """
    # 1. Active days (35%) — most reliable signal
    active_norm = min(1.0, active_days / _ACTIVE_DAYS_P90)

    # 2. Recurrence (20%) — same creative recurring = confident advertiser
    recurrence_norm = min(1.0, math.log1p(recurrence_count) / math.log1p(_RECURRENCE_P90))

    # 3. Platform spread (15%) — multi-platform deployment
    platform_norm = min(1.0, platform_count / _MAX_PLATFORMS)

    # 4. Variant spread (10%) — number of variants in family
    variant_norm = min(1.0, math.log1p(variant_count) / math.log1p(_VARIANT_P90))

    # 5. Ad-to-LP consistency (10%) — already 0-1 range
    consistency_norm = min(1.0, max(0.0, ad_to_lp_consistency))

    # 6. Capture confidence (10%) — already 0-1 range
    confidence_norm = min(1.0, max(0.0, capture_confidence))

    raw_score = (
        0.35 * active_norm
        + 0.20 * recurrence_norm
        + 0.15 * platform_norm
        + 0.10 * variant_norm
        + 0.10 * consistency_norm
        + 0.10 * confidence_norm
    )

    return round(raw_score * 100, 2)


def batch_compute_hit_proxy(batch_size: int = 500) -> dict:
    """Score all ads and persist hit_proxy_score + active_days.

    Uses the full reference architecture formula:
    - active_days from ad_delivery_start/stop_time (fallback first/last_seen)
    - recurrence from creative_families member_count
    - platform_count from ad.publisher_platforms
    - variant_count from creative_families variant_count
    - capture_confidence computed per ad
    - ad_to_lp_consistency placeholder (0.0 until similarity pipeline is built)

    Also updates brand avg_hit_proxy_score.

    Returns summary dict with counts.
    """
    session = SyncSessionLocal()
    updated = 0
    total = 0

    try:
        total = session.query(Ad).count()
        logger.info("hit_proxy_batch_start", total=total)
        BATCH_SIZE = 500
        ads = []
        for offset in range(0, total, BATCH_SIZE):
            ads.extend(session.query(Ad).order_by(Ad.id).offset(offset).limit(BATCH_SIZE).all())

        # ── Pre-compute recurrence & variant counts from creative_families ──
        # Map ad_id → (member_count, variant_count) via creative_assets → family
        family_info: dict[int, tuple[int, int]] = {}
        try:
            from app.models.creative_asset import CreativeAsset, CreativeFamily

            family_rows = (
                session.query(
                    CreativeAsset.ad_id,
                    CreativeFamily.member_count,
                    CreativeFamily.variant_count,
                )
                .join(CreativeFamily, CreativeAsset.family_id == CreativeFamily.id)
                .filter(CreativeAsset.family_id.isnot(None))
                .all()
            )
            for ad_id, member_ct, variant_ct in family_rows:
                existing = family_info.get(ad_id)
                if existing is None or member_ct > existing[0]:
                    family_info[ad_id] = (member_ct, variant_ct)
        except Exception as e:
            logger.warning("hit_proxy_family_lookup_skipped", error=str(e))

        # ── Score each ad ──
        for ad in ads:
            days = compute_active_days(ad)

            # Platform count from publisher_platforms JSONB
            platforms = ad.publisher_platforms if isinstance(ad.publisher_platforms, list) else []
            platform_count = max(1, len(platforms))

            # Recurrence & variant from family, fallback to advertiser-level heuristic
            fam = family_info.get(ad.id)
            if fam:
                recurrence_count = fam[0]  # member_count
                variant_count = fam[1]      # variant_count
            else:
                recurrence_count = 1
                variant_count = 1

            # Capture confidence
            cap_conf = compute_capture_confidence(ad)

            # Ad-to-LP consistency: placeholder until similarity pipeline is built
            ad_to_lp = 0.0

            score = compute_hit_proxy_score(
                active_days=days,
                recurrence_count=recurrence_count,
                platform_count=platform_count,
                variant_count=variant_count,
                ad_to_lp_consistency=ad_to_lp,
                capture_confidence=cap_conf,
                last_seen_at=ad.last_seen_at,
            )

            ad.active_days = days
            ad.hit_proxy_score = score
            updated += 1

        session.flush()

        # ── Update brand avg_hit_proxy_score ──
        try:
            from app.models.brand_registry import BrandRegistry

            brand_avgs = (
                session.query(
                    Ad.brand_id,
                    sa_func.avg(Ad.hit_proxy_score),
                )
                .filter(Ad.brand_id.isnot(None), Ad.hit_proxy_score.isnot(None))
                .group_by(Ad.brand_id)
                .all()
            )
            for brand_id, avg_score in brand_avgs:
                brand = session.query(BrandRegistry).get(brand_id)
                if brand:
                    brand.avg_hit_proxy_score = round(float(avg_score), 2)

            logger.info("hit_proxy_brand_avg_updated", brands=len(brand_avgs))
        except Exception as e:
            logger.warning("hit_proxy_brand_avg_skipped", error=str(e))

        session.commit()
        logger.info("hit_proxy_batch_complete", total=total, updated=updated)

    except Exception as e:
        session.rollback()
        logger.error("hit_proxy_batch_failed", error=str(e))
        raise
    finally:
        session.close()

    return {"total": total, "updated": updated}


def get_hit_proxy_distribution() -> dict:
    """Get score distribution for dashboard display."""
    session = SyncSessionLocal()
    try:
        rows = session.execute(sa_text("""
            SELECT
                CASE
                    WHEN hit_proxy_score >= 80 THEN 'elite'
                    WHEN hit_proxy_score >= 60 THEN 'high'
                    WHEN hit_proxy_score >= 40 THEN 'medium'
                    WHEN hit_proxy_score >= 20 THEN 'low'
                    ELSE 'minimal'
                END as tier,
                COUNT(*) as cnt,
                AVG(hit_proxy_score) as avg_score,
                AVG(active_days) as avg_active_days
            FROM ads
            WHERE hit_proxy_score IS NOT NULL
            GROUP BY tier
            ORDER BY avg_score DESC
        """)).fetchall()

        return {
            "tiers": [
                {
                    "tier": row[0],
                    "count": row[1],
                    "avg_score": round(float(row[2] or 0), 2),
                    "avg_active_days": round(float(row[3] or 0), 1),
                }
                for row in rows
            ],
            "total_scored": sum(row[1] for row in rows),
        }
    finally:
        session.close()


if __name__ == "__main__":
    result = batch_compute_hit_proxy()
    print(f"Hit proxy scoring complete: {result}")
