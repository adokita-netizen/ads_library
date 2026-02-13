"""Analytics and reporting API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.ad import Ad, AdPlatformEnum, AdCategoryEnum, AdStatusEnum
from app.models.analysis import AdAnalysis

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_async_session),
):
    """Get dashboard overview statistics."""
    # Total ads
    total_result = await db.execute(select(func.count(Ad.id)))
    total_ads = total_result.scalar() or 0

    # Analyzed ads
    analyzed_result = await db.execute(
        select(func.count(Ad.id)).where(Ad.status == AdStatusEnum.ANALYZED)
    )
    analyzed_ads = analyzed_result.scalar() or 0

    # Ads by platform
    platform_result = await db.execute(
        select(Ad.platform, func.count(Ad.id))
        .group_by(Ad.platform)
    )
    ads_by_platform = {
        (row[0].value if hasattr(row[0], 'value') else str(row[0])): row[1]
        for row in platform_result.all()
    }

    # Ads by category
    category_result = await db.execute(
        select(Ad.category, func.count(Ad.id))
        .where(Ad.category.isnot(None))
        .group_by(Ad.category)
    )
    ads_by_category = {
        (row[0].value if hasattr(row[0], 'value') else str(row[0])): row[1]
        for row in category_result.all()
    }

    # Average winning score
    avg_score_result = await db.execute(
        select(func.avg(AdAnalysis.winning_score))
        .where(AdAnalysis.winning_score.isnot(None))
    )
    avg_winning_score = avg_score_result.scalar()

    # Sentiment distribution
    sentiment_result = await db.execute(
        select(AdAnalysis.overall_sentiment, func.count(AdAnalysis.id))
        .where(AdAnalysis.overall_sentiment.isnot(None))
        .group_by(AdAnalysis.overall_sentiment)
    )
    sentiment_distribution = {str(row[0]): row[1] for row in sentiment_result.all()}

    return {
        "total_ads": total_ads,
        "analyzed_ads": analyzed_ads,
        "analysis_rate": analyzed_ads / total_ads if total_ads > 0 else 0,
        "ads_by_platform": ads_by_platform,
        "ads_by_category": ads_by_category,
        "avg_winning_score": round(float(avg_winning_score), 1) if avg_winning_score else None,
        "sentiment_distribution": sentiment_distribution,
    }


@router.get("/competitor/{advertiser_name}")
async def get_competitor_analysis(
    advertiser_name: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get competitor analysis for a specific advertiser."""
    # Get all ads by this advertiser
    result = await db.execute(
        select(Ad).where(Ad.advertiser_name.ilike(f"%{advertiser_name}%"))
    )
    ads = result.scalars().all()

    if not ads:
        return {"advertiser": advertiser_name, "ads_count": 0, "message": "No ads found"}

    ad_ids = [ad.id for ad in ads]

    # Get analyses
    analyses_result = await db.execute(
        select(AdAnalysis).where(AdAnalysis.ad_id.in_(ad_ids))
    )
    analyses = analyses_result.scalars().all()

    # Platform distribution
    platform_counts = {}
    for ad in ads:
        platform = ad.platform.value if hasattr(ad.platform, 'value') else str(ad.platform)
        platform_counts[platform] = platform_counts.get(platform, 0) + 1

    # Sentiment analysis
    sentiments = [a.overall_sentiment for a in analyses if a.overall_sentiment]
    sentiment_dist = {s: sentiments.count(s) for s in set(sentiments)} if sentiments else {}

    # Common keywords
    all_keywords = []
    for analysis in analyses:
        if analysis.keywords:
            all_keywords.extend(analysis.keywords)

    keyword_counts = {}
    for kw in all_keywords:
        if isinstance(kw, str):
            keyword = kw
        elif isinstance(kw, dict):
            keyword = kw.get("keyword", "") or kw.get("text", "")
        else:
            keyword = str(kw)
        if keyword:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
    top_keywords = sorted(keyword_counts.items(), key=lambda x: -x[1])[:20]

    # Winning score stats
    winning_scores = [a.winning_score for a in analyses if a.winning_score is not None]

    return {
        "advertiser": advertiser_name,
        "total_ads": len(ads),
        "analyzed_ads": len(analyses),
        "platform_distribution": platform_counts,
        "sentiment_distribution": sentiment_dist,
        "top_keywords": [{"keyword": k, "count": c} for k, c in top_keywords],
        "avg_winning_score": round(sum(winning_scores) / len(winning_scores), 1) if winning_scores else None,
        "winning_score_range": {
            "min": min(winning_scores) if winning_scores else None,
            "max": max(winning_scores) if winning_scores else None,
        },
    }


@router.get("/trends")
async def get_trends(
    category: Optional[str] = None,
    platform: Optional[str] = None,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_async_session),
):
    """Get industry trends and patterns."""
    query = select(AdAnalysis).join(Ad)

    if category:
        query = query.where(Ad.category == category)
    if platform:
        query = query.where(Ad.platform == platform)

    result = await db.execute(query.order_by(Ad.created_at.desc()).limit(500))
    analyses = result.scalars().all()

    if not analyses:
        return {"message": "No data available for the selected filters"}

    # Aggregate patterns
    hook_types = {}
    cta_types = {}
    color_palettes = []
    avg_durations = []
    ugc_count = 0
    subtitle_count = 0

    for a in analyses:
        if a.hook_type:
            hook_types[a.hook_type] = hook_types.get(a.hook_type, 0) + 1
        if a.cta_type:
            cta_types[a.cta_type] = cta_types.get(a.cta_type, 0) + 1
        if a.dominant_color_palette:
            color_palettes.extend(a.dominant_color_palette[:3])
        if a.is_ugc_style:
            ugc_count += 1
        if a.has_subtitles:
            subtitle_count += 1

    total = len(analyses)

    return {
        "sample_size": total,
        "trends": {
            "popular_hook_types": sorted(hook_types.items(), key=lambda x: -x[1])[:5],
            "popular_cta_types": sorted(cta_types.items(), key=lambda x: -x[1])[:5],
            "ugc_style_ratio": round(ugc_count / total, 2) if total else 0,
            "subtitle_usage_ratio": round(subtitle_count / total, 2) if total else 0,
        },
    }
