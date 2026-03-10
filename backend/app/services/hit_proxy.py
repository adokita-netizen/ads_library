"""Hit proxy scoring service.

Estimates ad effectiveness using observable signals since we can't see
actual spend/conversions for competitor ads.

Reference formula:
  hit_proxy = 0.35 * active_days_norm
            + 0.25 * platform_diversity
            + 0.20 * impression_proxy
            + 0.10 * variant_count_norm
            + 0.10 * recency_boost
"""

import math
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import text as sa_text
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = structlog.get_logger()

# Normalization constants
_ACTIVE_DAYS_P90 = 60  # 90th percentile active days for normalization
_VIEW_COUNT_P90 = 500_000  # 90th percentile view count
_MAX_PLATFORMS = 5  # Max distinct platforms for normalization


def _sigmoid(x: float, midpoint: float = 0.5, steepness: float = 10.0) -> float:
    """Smooth sigmoid normalization to [0, 1]."""
    return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))


def compute_active_days(ad: Ad) -> int:
    """Calculate days the ad has been active (last_seen - first_seen)."""
    def _ensure_tz(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    first = _ensure_tz(ad.first_seen_at)
    last = _ensure_tz(ad.last_seen_at)

    if first and last:
        return max(0, (last - first).days)
    if first:
        return max(0, (datetime.now(timezone.utc) - first).days)
    return 0


def compute_hit_proxy_score(
    active_days: int,
    view_count: int = 0,
    platform_count: int = 1,
    variant_count: int = 1,
    last_seen_at: Optional[datetime] = None,
) -> float:
    """Compute hit proxy score (0-100 scale).

    Args:
        active_days: Number of days the ad/family has been active
        view_count: Total views/impressions (proxy)
        platform_count: Number of distinct platforms where this creative appeared
        variant_count: Number of creative variants in the family
        last_seen_at: When the ad was last observed (for recency)

    Returns:
        Score from 0 to 100
    """
    # 1. Active days (35%) — most reliable signal
    active_norm = min(1.0, active_days / _ACTIVE_DAYS_P90)

    # 2. Platform diversity (25%)
    platform_norm = min(1.0, platform_count / _MAX_PLATFORMS)

    # 3. Impression proxy (20%) — log-scaled view count
    if view_count and view_count > 0:
        impression_norm = min(1.0, math.log1p(view_count) / math.log1p(_VIEW_COUNT_P90))
    else:
        impression_norm = 0.0

    # 4. Variant count (10%) — more variants = advertiser investing in testing
    variant_norm = min(1.0, _sigmoid(variant_count / 5.0))

    # 5. Recency boost (10%) — recently active ads score higher
    recency = 0.0
    if last_seen_at:
        # Handle both tz-aware and tz-naive datetimes from SQLite
        now = datetime.now(timezone.utc)
        if last_seen_at.tzinfo is None:
            last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
        days_since_last = (now - last_seen_at).days
        if days_since_last <= 3:
            recency = 1.0
        elif days_since_last <= 7:
            recency = 0.8
        elif days_since_last <= 14:
            recency = 0.6
        elif days_since_last <= 30:
            recency = 0.3
        else:
            recency = 0.0

    raw_score = (
        0.35 * active_norm
        + 0.25 * platform_norm
        + 0.20 * impression_norm
        + 0.10 * variant_norm
        + 0.10 * recency
    )

    return round(raw_score * 100, 2)


def batch_compute_hit_proxy(batch_size: int = 500) -> dict:
    """Score all ads and persist hit_proxy_score + active_days.

    Returns summary dict with counts.
    """
    session = SyncSessionLocal()
    updated = 0
    total = 0

    try:
        ads = session.query(Ad).all()
        total = len(ads)
        logger.info("hit_proxy_batch_start", total=total)

        # Pre-compute advertiser variant counts
        variant_counts: dict[str, int] = {}
        for ad in ads:
            key = (ad.advertiser_name or "unknown").lower()
            variant_counts[key] = variant_counts.get(key, 0) + 1

        for ad in ads:
            days = compute_active_days(ad)
            advertiser_key = (ad.advertiser_name or "unknown").lower()
            variants = variant_counts.get(advertiser_key, 1)

            score = compute_hit_proxy_score(
                active_days=days,
                view_count=ad.view_count or 0,
                platform_count=1,  # Single platform per ad; family-level has multi
                variant_count=variants,
                last_seen_at=ad.last_seen_at,
            )

            ad.active_days = days
            ad.hit_proxy_score = score
            updated += 1

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
