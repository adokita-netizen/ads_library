"""Rankings and hit ad detection API endpoints."""

import csv
import io
from datetime import date, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, desc, or_

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.models.analysis import AdAnalysis, TextDetection, Transcription
from app.services.ranking.ranking_service import RankingService

logger = structlog.get_logger()
router = APIRouter(prefix="/rankings", tags=["Rankings & Search"])


# ==================== Rankings ====================


@router.get("/products")
async def get_product_rankings(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get product rankings by spend/views for a period."""
    session = SyncSessionLocal()
    try:
        svc = RankingService()
        rankings, total = svc.get_rankings(
            session,
            period=period,
            genre=genre,
            platform=platform,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        # Join with Ad table to get ad-level details
        ad_ids = [r.ad_id for r in rankings]
        ads_map = {}
        if ad_ids:
            ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
            for ad in ads:
                metadata = ad.ad_metadata or {}
                ads_map[ad.id] = {
                    "thumbnail": ad.thumbnail_s3_key or "",
                    "duration_seconds": ad.duration_seconds or 0,
                    "management_id": ad.external_id or f"AD-{ad.id}",
                    "ad_url": ad.video_url or "",
                    "destination_url": metadata.get("destination_url", ""),
                    "destination_type": metadata.get("destination_type", ""),
                    "published_date": (
                        ad.first_seen_at.isoformat() if ad.first_seen_at else
                        ad.created_at.isoformat() if ad.created_at else ""
                    ),
                }

        items = []
        for r in rankings:
            ad_info = ads_map.get(r.ad_id, {})
            items.append({
                "rank": r.rank_position,
                "previous_rank": r.previous_rank,
                "rank_change": r.rank_change,
                "ad_id": r.ad_id,
                "product_name": r.product_name,
                "advertiser_name": r.advertiser_name,
                "genre": r.genre,
                "platform": r.platform,
                "view_increase": r.total_view_increase,
                "spend_increase": round(r.total_spend_increase),
                "cumulative_views": r.cumulative_views,
                "cumulative_spend": round(r.cumulative_spend),
                "is_hit": r.is_hit,
                "hit_score": r.hit_score,
                "trend_score": r.trend_score,
                # Ad-level fields from join
                "thumbnail": ad_info.get("thumbnail", ""),
                "duration_seconds": ad_info.get("duration_seconds", 0),
                "management_id": ad_info.get("management_id", f"AD-{r.ad_id}"),
                "ad_url": ad_info.get("ad_url", ""),
                "destination_url": ad_info.get("destination_url", ""),
                "destination_type": ad_info.get("destination_type", ""),
                "published_date": ad_info.get("published_date", ""),
            })

        return {
            "period": period,
            "genre": genre,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }
    finally:
        session.close()


@router.get("/hit-ads")
async def get_hit_ads(
    genre: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Get currently trending/hit ads (high velocity growth)."""
    session = SyncSessionLocal()
    try:
        svc = RankingService()
        hits = svc.get_hit_ads(session, genre=genre, limit=limit)

        return {
            "total": len(hits),
            "items": [
                {
                    "rank": h.rank_position,
                    "ad_id": h.ad_id,
                    "product_name": h.product_name,
                    "advertiser_name": h.advertiser_name,
                    "genre": h.genre,
                    "platform": h.platform,
                    "view_increase": h.total_view_increase,
                    "spend_increase": round(h.total_spend_increase),
                    "hit_score": h.hit_score,
                    "trend_score": h.trend_score,
                    "rank_change": h.rank_change,
                }
                for h in hits
            ],
        }
    finally:
        session.close()


@router.get("/advertiser/{advertiser_name}")
async def get_advertiser_analytics(
    advertiser_name: str,
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
):
    """Get detailed analytics for a specific advertiser."""
    session = SyncSessionLocal()
    try:
        svc = RankingService()
        return svc.get_advertiser_rankings(session, advertiser_name, period)
    finally:
        session.close()


@router.get("/genre-summary")
async def get_genre_summary(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
):
    """Get summary statistics per genre (market overview)."""
    session = SyncSessionLocal()
    try:
        today = date.today()
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
        start = today - timedelta(days=days)

        results = (
            session.query(
                AdDailyMetrics.genre,
                func.count(func.distinct(AdDailyMetrics.ad_id)).label("ad_count"),
                func.count(func.distinct(AdDailyMetrics.advertiser_name)).label("advertiser_count"),
                func.sum(AdDailyMetrics.view_count_increase).label("total_views"),
                func.sum(AdDailyMetrics.estimated_spend_increase).label("total_spend"),
            )
            .filter(
                AdDailyMetrics.metric_date >= start,
                AdDailyMetrics.genre.isnot(None),
            )
            .group_by(AdDailyMetrics.genre)
            .order_by(desc("total_spend"))
            .all()
        )

        return {
            "period": period,
            "genres": [
                {
                    "genre": r.genre,
                    "ad_count": r.ad_count,
                    "advertiser_count": r.advertiser_count,
                    "total_views": r.total_views or 0,
                    "total_spend": round(r.total_spend or 0),
                }
                for r in results
            ],
        }
    finally:
        session.close()


# ==================== Pro-Search ====================


@router.get("/search")
async def pro_search(
    q: str = Query(..., min_length=1, description="検索キーワード"),
    search_scope: str = Query("all", description="検索範囲: all, ads, lp, transcript, text"),
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    advertiser: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Pro-Search: Full-text search across ads, LP text, transcripts, and OCR text."""
    session = SyncSessionLocal()
    try:
        results = []
        offset = (page - 1) * page_size

        # Search in ads (title, description, advertiser, brand)
        if search_scope in ("all", "ads"):
            ad_query = session.query(Ad).filter(
                or_(
                    Ad.title.ilike(f"%{q}%"),
                    Ad.description.ilike(f"%{q}%"),
                    Ad.advertiser_name.ilike(f"%{q}%"),
                    Ad.brand_name.ilike(f"%{q}%"),
                )
            )
            if genre:
                ad_query = ad_query.filter(Ad.category == genre)
            if platform:
                ad_query = ad_query.filter(Ad.platform == platform)
            if advertiser:
                ad_query = ad_query.filter(Ad.advertiser_name.ilike(f"%{advertiser}%"))

            ads = ad_query.order_by(Ad.created_at.desc()).offset(offset).limit(page_size).all()
            for ad in ads:
                results.append({
                    "type": "ad",
                    "id": ad.id,
                    "title": ad.title,
                    "description": ad.description,
                    "platform": str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "brand_name": ad.brand_name,
                    "category": str(ad.category) if ad.category else None,
                    "match_field": "title/description",
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

        # Search in transcripts (audio text from videos)
        if search_scope in ("all", "transcript"):
            transcript_query = (
                session.query(Transcription, Ad)
                .join(AdAnalysis, Transcription.analysis_id == AdAnalysis.id)
                .join(Ad, AdAnalysis.ad_id == Ad.id)
                .filter(Transcription.text.ilike(f"%{q}%"))
            )
            if platform:
                transcript_query = transcript_query.filter(Ad.platform == platform)

            transcripts = transcript_query.limit(page_size).all()
            for t, ad in transcripts:
                results.append({
                    "type": "transcript",
                    "id": ad.id,
                    "title": ad.title,
                    "matched_text": t.text,
                    "timestamp_ms": t.start_time_ms,
                    "platform": str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "match_field": "transcript",
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

        # Search in OCR text detections (text from video frames)
        if search_scope in ("all", "text"):
            text_query = (
                session.query(TextDetection, Ad)
                .join(AdAnalysis, TextDetection.analysis_id == AdAnalysis.id)
                .join(Ad, AdAnalysis.ad_id == Ad.id)
                .filter(TextDetection.text.ilike(f"%{q}%"))
            )
            if platform:
                text_query = text_query.filter(Ad.platform == platform)

            texts = text_query.limit(page_size).all()
            for td, ad in texts:
                results.append({
                    "type": "text_detection",
                    "id": ad.id,
                    "title": ad.title,
                    "matched_text": td.text,
                    "timestamp_seconds": td.timestamp_seconds,
                    "platform": str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "match_field": "video_text",
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

        # Search in LP content
        if search_scope in ("all", "lp"):
            from app.models.landing_page import LandingPage

            lp_query = session.query(LandingPage).filter(
                or_(
                    LandingPage.title.ilike(f"%{q}%"),
                    LandingPage.hero_headline.ilike(f"%{q}%"),
                    LandingPage.full_text_content.ilike(f"%{q}%"),
                    LandingPage.product_name.ilike(f"%{q}%"),
                )
            )
            if genre:
                lp_query = lp_query.filter(LandingPage.genre == genre)

            lps = lp_query.limit(page_size).all()
            for lp in lps:
                results.append({
                    "type": "landing_page",
                    "id": lp.id,
                    "title": lp.title,
                    "url": lp.url,
                    "domain": lp.domain,
                    "genre": lp.genre,
                    "product_name": lp.product_name,
                    "hero_headline": lp.hero_headline,
                    "match_field": "lp_content",
                    "created_at": lp.created_at.isoformat() if lp.created_at else None,
                })

        return {
            "query": q,
            "search_scope": search_scope,
            "total_results": len(results),
            "page": page,
            "results": results,
        }
    finally:
        session.close()


# ==================== CSV Export ====================


@router.get("/export/rankings")
async def export_rankings_csv(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
    genre: Optional[str] = None,
):
    """Export rankings as CSV file."""
    session = SyncSessionLocal()
    try:
        svc = RankingService()
        rankings, _ = svc.get_rankings(session, period=period, genre=genre, limit=500)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "順位", "前回順位", "変動", "商材名", "広告主", "ジャンル", "媒体",
            "再生増加数", "予想消化増加額", "累計再生回数", "累計予想消化額",
            "HIT", "ヒットスコア", "トレンドスコア",
        ])

        for r in rankings:
            writer.writerow([
                r.rank_position,
                r.previous_rank or "-",
                r.rank_change if r.rank_change is not None else "-",
                r.product_name or "",
                r.advertiser_name or "",
                r.genre or "",
                r.platform or "",
                r.total_view_increase,
                round(r.total_spend_increase),
                r.cumulative_views,
                round(r.cumulative_spend),
                "HIT" if r.is_hit else "",
                r.hit_score or 0,
                r.trend_score or 0,
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=rankings_{period}_{genre or 'all'}.csv"
            },
        )
    finally:
        session.close()


@router.get("/export/ads")
async def export_ads_csv(
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    advertiser: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
):
    """Export ad list as CSV file."""
    session = SyncSessionLocal()
    try:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        if platform:
            query = query.filter(Ad.platform == platform)
        if advertiser:
            query = query.filter(Ad.advertiser_name.ilike(f"%{advertiser}%"))

        ads = query.order_by(Ad.created_at.desc()).limit(limit).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "タイトル", "媒体", "カテゴリ", "広告主", "ブランド",
            "再生数", "いいね数", "推定CTR", "秒数", "ステータス",
            "初出日", "最終確認日", "動画URL",
        ])

        for ad in ads:
            writer.writerow([
                ad.id,
                ad.title or "",
                str(ad.platform),
                str(ad.category) if ad.category else "",
                ad.advertiser_name or "",
                ad.brand_name or "",
                ad.view_count or 0,
                ad.like_count or 0,
                ad.estimated_ctr or "",
                ad.duration_seconds or "",
                str(ad.status),
                ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                ad.last_seen_at.isoformat() if ad.last_seen_at else "",
                ad.video_url or "",
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ads_export.csv"},
        )
    finally:
        session.close()
