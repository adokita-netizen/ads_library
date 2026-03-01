"""CI-133: Data Quality Dashboard API.

Provides real-time endpoints for monitoring data quality, freshness,
batch execution status, and field fill rates.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_async_session, check_pool_health
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics
from app.models.user import User

router = APIRouter(prefix="/data-quality", tags=["Data Quality"])


@router.get("/overview")
async def get_quality_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get overall data quality overview with fill rates and freshness."""
    total_result = await db.execute(select(func.count(Ad.id)))
    total_ads = total_result.scalar() or 0

    if total_ads == 0:
        return {"total_ads": 0, "grade": "N/A", "message": "No ads in database"}

    # Field fill rates
    fields = {
        "title": Ad.title,
        "category": Ad.category,
        "destination_url": Ad.destination_url,
        "platform": Ad.platform,
        "advertiser_name": Ad.advertiser_name,
        "creative_type": Ad.creative_type,
        "thumbnail_url": Ad.thumbnail_url,
        "video_url": Ad.video_url,
    }

    fill_rates = {}
    for name, col in fields.items():
        non_null = await db.execute(
            select(func.count(Ad.id)).where(col.isnot(None))
        )
        count = non_null.scalar() or 0
        fill_rates[name] = round(count / total_ads * 100, 1)

    avg_fill = sum(fill_rates.values()) / len(fill_rates) if fill_rates else 0

    # Grade
    if avg_fill >= 90:
        grade = "A"
    elif avg_fill >= 80:
        grade = "B"
    elif avg_fill >= 70:
        grade = "C"
    elif avg_fill >= 50:
        grade = "D"
    else:
        grade = "F"

    # Freshness distribution
    freshness = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE (ad_metadata->>'freshness_score')::float >= 70) as fresh,
            COUNT(*) FILTER (WHERE (ad_metadata->>'freshness_score')::float >= 30
                              AND (ad_metadata->>'freshness_score')::float < 70) as moderate,
            COUNT(*) FILTER (WHERE (ad_metadata->>'freshness_score')::float < 30) as stale,
            COUNT(*) FILTER (WHERE ad_metadata->>'freshness_score' IS NULL) as unknown
        FROM ads
    """))
    row = freshness.fetchone()
    freshness_dist = {
        "fresh": row[0] if row else 0,
        "moderate": row[1] if row else 0,
        "stale": row[2] if row else 0,
        "unknown": row[3] if row else 0,
    }

    # Metadata completeness (key fields in ad_metadata)
    meta_keys = ["hit_score", "creative_analysis", "longevity_class", "is_still_running"]
    meta_fill = {}
    for key in meta_keys:
        r = await db.execute(
            text("SELECT COUNT(*) FROM ads WHERE ad_metadata->>:key IS NOT NULL").bindparams(key=key)
        )
        meta_fill[key] = round((r.scalar() or 0) / total_ads * 100, 1)

    return {
        "total_ads": total_ads,
        "grade": grade,
        "avg_fill_rate": round(avg_fill, 1),
        "field_fill_rates": fill_rates,
        "metadata_fill_rates": meta_fill,
        "freshness": freshness_dist,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics-health")
async def get_metrics_health(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get metrics collection health for the past N days."""
    result = await db.execute(text("""
        SELECT
            date,
            COUNT(*) as records,
            COUNT(DISTINCT ad_id) as unique_ads,
            AVG(view_count) as avg_views,
            AVG(estimated_spend) as avg_spend,
            SUM(CASE WHEN view_count_increase < 0 THEN 1 ELSE 0 END) as negative_deltas
        FROM ad_daily_metrics
        WHERE date >= CURRENT_DATE - :days
        GROUP BY date
        ORDER BY date DESC
    """), {"days": days})

    rows = result.fetchall()
    daily = []
    for r in rows:
        daily.append({
            "date": str(r[0]),
            "records": r[1],
            "unique_ads": r[2],
            "avg_views": round(float(r[3]), 0) if r[3] else 0,
            "avg_spend": round(float(r[4]), 0) if r[4] else 0,
            "negative_deltas": r[5],
        })

    # Total metrics count
    total_result = await db.execute(select(func.count(AdDailyMetrics.id)))
    total_metrics = total_result.scalar() or 0

    return {
        "total_metrics_rows": total_metrics,
        "daily_breakdown": daily,
        "days_requested": days,
    }


@router.get("/pool-health")
async def get_pool_health(
    current_user: User = Depends(get_current_user),
):
    """Get database connection pool utilization stats."""
    return check_pool_health()


@router.get("/score-distribution")
async def get_score_distribution(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get hit score distribution across all ads."""
    result = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE (ad_metadata->>'hit_score')::float >= 80) as excellent,
            COUNT(*) FILTER (WHERE (ad_metadata->>'hit_score')::float >= 60
                              AND (ad_metadata->>'hit_score')::float < 80) as good,
            COUNT(*) FILTER (WHERE (ad_metadata->>'hit_score')::float >= 40
                              AND (ad_metadata->>'hit_score')::float < 60) as average,
            COUNT(*) FILTER (WHERE (ad_metadata->>'hit_score')::float < 40) as low,
            COUNT(*) FILTER (WHERE ad_metadata->>'hit_score' IS NULL) as unscored,
            AVG((ad_metadata->>'hit_score')::float) as avg_score,
            MAX((ad_metadata->>'hit_score')::float) as max_score,
            MIN((ad_metadata->>'hit_score')::float) as min_score
        FROM ads
        WHERE ad_metadata IS NOT NULL
    """))

    row = result.fetchone()
    return {
        "distribution": {
            "excellent_80plus": row[0] if row else 0,
            "good_60_80": row[1] if row else 0,
            "average_40_60": row[2] if row else 0,
            "low_under_40": row[3] if row else 0,
            "unscored": row[4] if row else 0,
        },
        "stats": {
            "avg": round(float(row[5]), 1) if row and row[5] else None,
            "max": round(float(row[6]), 1) if row and row[6] else None,
            "min": round(float(row[7]), 1) if row and row[7] else None,
        },
    }


@router.get("/alerts-summary")
async def get_alerts_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get summary of recent alerts."""
    result = await db.execute(text("""
        SELECT
            alert_type,
            severity,
            COUNT(*) as count,
            COUNT(*) FILTER (WHERE is_read = false) as unread
        FROM alert_history
        WHERE triggered_at >= NOW() - INTERVAL '7 days'
        GROUP BY alert_type, severity
        ORDER BY count DESC
    """))

    rows = result.fetchall()
    summary = []
    for r in rows:
        summary.append({
            "alert_type": r[0],
            "severity": r[1],
            "count": r[2],
            "unread": r[3],
        })

    total_unread = await db.execute(text(
        "SELECT COUNT(*) FROM alert_history WHERE is_read = false"
    ))

    return {
        "past_7_days": summary,
        "total_unread": total_unread.scalar() or 0,
    }
