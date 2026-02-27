"""Rankings and hit ad detection API endpoints."""

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.utils.db import escape_like as _escape_like
from sqlalchemy import case, func, desc, or_

from app.core.database import SyncSessionLocal, sync_session_scope
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.models.analysis import AdAnalysis, TextDetection, Transcription
from app.services.ranking.ranking_service import RankingService, _today_jst

logger = structlog.get_logger()
router = APIRouter(prefix="/rankings", tags=["Rankings & Search"])

# Meta platform groups "facebook" and "instagram" under a single umbrella.
META_PLATFORMS = ["facebook", "instagram"]


def _resolve_thumbnail_url(ad: Ad) -> str:
    """Resolve a display-ready thumbnail URL for an Ad.

    Priority: presigned S3 URL > thumbnail_url > image_url > snapshot_url > ""
    Mirrors the pattern in ads.py list_ads (lines 86-96).
    """
    if ad.thumbnail_s3_key:
        try:
            from app.core.storage import get_storage_client
            storage = get_storage_client()
            return storage.get_presigned_url(ad.thumbnail_s3_key)
        except Exception:
            pass
    if ad.thumbnail_url:
        return ad.thumbnail_url
    if ad.image_url:
        return ad.image_url
    if ad.snapshot_url:
        return ad.snapshot_url
    return ""


_SPONSOR_RE = re.compile(r"^(.+?)\s*スポンサー[:：]\s*", re.UNICODE)


def _derive_product_name(ad: Ad) -> str:
    """Derive a clean, short product/brand name for display."""
    if ad.brand_name:
        return ad.brand_name.strip()

    adv = (ad.advertiser_name or "").strip()
    if adv:
        m = _SPONSOR_RE.match(adv)
        if m:
            after = adv[m.end():].strip()
            adv = after or m.group(1).strip()

    title = (ad.title or "").strip()
    if title and len(title) <= 40 and "\n" not in title:
        if adv and adv.lower() != title.lower():
            return adv
        return title

    if adv:
        return adv

    if ad.description:
        first_line = ad.description.split("\n")[0].strip()
        if first_line:
            return first_line[:40]

    return "不明"


def _clean_advertiser(name: str | None) -> str:
    """Strip 'Xスポンサー: Y' prefix from advertiser names for display."""
    if not name:
        return ""
    m = _SPONSOR_RE.match(name)
    if m:
        after = name[m.end():].strip()
        return after or m.group(1).strip()
    return name


def _resolve_platform_filter(query, column, platform: str | None):
    """Apply platform filter, resolving 'meta' to both Facebook and Instagram."""
    if not platform:
        return query
    if platform.lower() == "meta":
        return query.filter(column.in_(META_PLATFORMS))
    return query.filter(column == platform)


def _sanitize_csv(value: str | None) -> str:
    """Sanitize value for CSV to prevent formula injection."""
    if not value:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


# ==================== Cleanup ====================


@router.post("/cleanup-non-japanese")
def cleanup_non_japanese(dry_run: bool = Query(True)):
    """Remove non-Japanese ads from the database.

    Uses japanese_text_ratio to identify ads whose title+description
    contain less than 10% Japanese characters.

    - dry_run=true  → list ads that would be deleted (no changes)
    - dry_run=false → actually delete Ad + AdDailyMetrics + ProductRanking rows
    """
    from app.utils.text import japanese_text_ratio

    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        non_jp_ads = []

        for ad in ads:
            text = (ad.title or "") + " " + (ad.description or "")
            ratio = japanese_text_ratio(text)
            if ratio <= 0.1:
                non_jp_ads.append({
                    "id": ad.id,
                    "title": (ad.title or "")[:80],
                    "advertiser": ad.advertiser_name or "",
                    "japanese_ratio": round(ratio, 3),
                })

        if dry_run:
            return {
                "dry_run": True,
                "total_ads": len(ads),
                "non_japanese_count": len(non_jp_ads),
                "ads_to_delete": non_jp_ads,
            }

        # Actually delete
        ids_to_delete = [a["id"] for a in non_jp_ads]
        if ids_to_delete:
            session.query(ProductRanking).filter(
                ProductRanking.ad_id.in_(ids_to_delete)
            ).delete(synchronize_session=False)
            session.query(AdDailyMetrics).filter(
                AdDailyMetrics.ad_id.in_(ids_to_delete)
            ).delete(synchronize_session=False)
            session.query(Ad).filter(
                Ad.id.in_(ids_to_delete)
            ).delete(synchronize_session=False)
            session.commit()

        logger.info(
            "cleanup_non_japanese_done",
            deleted=len(ids_to_delete),
            remaining=len(ads) - len(ids_to_delete),
        )

        return {
            "dry_run": False,
            "deleted_count": len(ids_to_delete),
            "remaining_count": len(ads) - len(ids_to_delete),
        }


# ==================== Manual Compute ====================


@router.post("/compute")
def compute_rankings_now():
    """Manually trigger metrics collection + ranking computation.

    This runs inline (no Celery required) and returns the results.
    """
    from app.tasks.metrics_tasks import collect_metrics_for_ads

    with sync_session_scope() as session:
        # Step 1: Collect daily metrics for recent days (backfill if missing)
        today = _today_jst()
        metrics_created = 0
        for days_ago in range(7, -1, -1):  # 7 days ago → today
            d = today - timedelta(days=days_ago)
            metrics_created += collect_metrics_for_ads(session, target_date=d)
        session.commit()

        # Step 2: Compute rankings for all periods
        svc = RankingService()
        ranking_summary = svc.compute_all_rankings(session)
        session.commit()

        logger.info(
            "manual_compute_complete",
            metrics_created=metrics_created,
            rankings=ranking_summary,
        )

        return {
            "status": "completed",
            "metrics_created": metrics_created,
            "rankings": ranking_summary,
        }


# ==================== Rankings ====================


@router.get("/products")
def get_product_rankings(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get product rankings by spend/views for a period."""
    from fastapi.responses import JSONResponse

    with sync_session_scope() as session:
        svc = RankingService()
        rankings, total = svc.get_rankings(
            session,
            period=period,
            genre=genre,
            platform=platform,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        # If no pre-computed rankings exist, fall back to listing ads directly
        if total == 0:
            return _fallback_ad_list(session, genre, platform, page, page_size, period)

        # Single batch query for Ad details (avoid N+1)
        ad_ids = [r.ad_id for r in rankings]
        ads_map = {}
        if ad_ids:
            ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
            for ad in ads:
                metadata = ad.ad_metadata or {}
                ads_map[ad.id] = {
                    "thumbnail": _resolve_thumbnail_url(ad),
                    "duration_seconds": ad.duration_seconds or 0,
                    "management_id": ad.external_id or f"AD-{ad.id}",
                    "ad_url": ad.video_url or "",
                    "image_url": ad.image_url or "",
                    "snapshot_url": ad.snapshot_url or "",
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
                "advertiser_name": _clean_advertiser(r.advertiser_name),
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
                "image_url": ad_info.get("image_url", ""),
                "snapshot_url": ad_info.get("snapshot_url", ""),
                "destination_url": ad_info.get("destination_url", ""),
                "destination_type": ad_info.get("destination_type", ""),
                "published_date": ad_info.get("published_date", ""),
            })

        data = {
            "period": period,
            "genre": genre,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

        # Cache rankings for 5 minutes (pre-computed data, updates infrequently)
        return JSONResponse(
            content=data,
            headers={"Cache-Control": "public, max-age=300, s-maxage=300"},
        )


def _fallback_ad_list(session, genre, platform, page, page_size, period):
    """When no pre-computed rankings exist, rank ads using AdDailyMetrics.

    Queries actual spend/view increase data from AdDailyMetrics and marks
    demo ads so the frontend can distinguish real vs demo data.
    """
    from sqlalchemy.orm import aliased

    yesterday = _today_jst() - timedelta(days=1)
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
    start = yesterday - timedelta(days=days - 1)

    # Subquery: aggregate metrics per ad for the period
    metrics_sq = (
        session.query(
            AdDailyMetrics.ad_id,
            func.sum(AdDailyMetrics.view_count_increase).label("view_increase"),
            func.sum(AdDailyMetrics.estimated_spend_increase).label("spend_increase"),
            func.max(AdDailyMetrics.view_count).label("cumulative_views"),
            func.max(AdDailyMetrics.estimated_spend).label("cumulative_spend"),
        )
        .filter(
            AdDailyMetrics.metric_date >= start,
            AdDailyMetrics.metric_date <= yesterday,
        )
        .group_by(AdDailyMetrics.ad_id)
        .subquery()
    )

    query = (
        session.query(Ad, metrics_sq)
        .outerjoin(metrics_sq, Ad.id == metrics_sq.c.ad_id)
    )

    query = _resolve_platform_filter(query, Ad.platform, platform)
    if genre:
        query = query.filter(Ad.category == genre)

    total = query.count()
    rows = (
        query.order_by(
            case((metrics_sq.c.spend_increase.is_(None), 0), else_=1).desc(),
            desc(metrics_sq.c.spend_increase),
            case((Ad.view_count.is_(None), 0), else_=1).desc(),
            desc(Ad.view_count),
            desc(Ad.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Compute max view_count for relative scoring
    max_views = max((ad.view_count or 0 for ad, *_ in rows), default=1) or 1

    items = []
    for rank_idx, row in enumerate(rows):
        ad = row[0]
        view_increase = row[1] or 0
        spend_increase = row[2] or 0
        cumulative_views = row[3] or (ad.view_count or 0)
        cumulative_spend = row[4] or 0

        rank = (page - 1) * page_size + rank_idx + 1
        metadata = ad.ad_metadata or {}
        views = ad.view_count or 0
        likes = ad.like_count or 0

        # Basic hit_score: normalized view count (0-100)
        hit_score = round(min(100, (views / max_views) * 100))
        # Basic trend_score: engagement rate proxy (likes/views ratio, scaled)
        engagement = (likes / views * 100) if views > 0 else 0
        trend_score = round(min(100, engagement * 10))

        is_demo = bool(metadata.get("is_demo"))
        items.append({
            "rank": rank,
            "previous_rank": None,
            "rank_change": None,
            "ad_id": ad.id,
            "product_name": _derive_product_name(ad),
            "advertiser_name": _clean_advertiser(ad.advertiser_name),
            "genre": str(ad.category.value) if ad.category else "",
            "platform": str(ad.platform.value) if ad.platform else "",
            "view_increase": view_increase,
            "spend_increase": round(spend_increase),
            "cumulative_views": cumulative_views,
            "cumulative_spend": round(cumulative_spend),
            "is_hit": hit_score >= 80,
            "hit_score": hit_score,
            "trend_score": trend_score,
            "is_demo": is_demo,
            "thumbnail": _resolve_thumbnail_url(ad),
            "duration_seconds": ad.duration_seconds or 0,
            "management_id": ad.external_id or f"AD-{ad.id}",
            "ad_url": ad.video_url or "",
            "image_url": ad.image_url or "",
            "snapshot_url": ad.snapshot_url or "",
            "destination_url": metadata.get("destination_url", ""),
            "destination_type": metadata.get("destination_type", ""),
            "published_date": (
                ad.first_seen_at.isoformat() if ad.first_seen_at else
                ad.created_at.isoformat() if ad.created_at else ""
            ),
        })

    return {
        "period": period,
        "genre": genre,
        "total": total,
        "page": page,
        "page_size": page_size,
        "is_fallback": True,
        "items": items,
    }


@router.get("/hit-ads")
def get_hit_ads(
    genre: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Get currently trending/hit ads (high velocity growth)."""
    with sync_session_scope() as session:
        svc = RankingService()
        hits = svc.get_hit_ads(session, genre=genre, limit=limit)

        # Batch-fetch Ad details for thumbnails and extra info
        ad_ids = [h.ad_id for h in hits]
        ads_map: dict[int, Ad] = {}
        if ad_ids:
            ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
            ads_map = {ad.id: ad for ad in ads}

        items = []
        for h in hits:
            ad = ads_map.get(h.ad_id)
            thumbnail = _resolve_thumbnail_url(ad) if ad else ""
            items.append({
                "rank": h.rank_position,
                "ad_id": h.ad_id,
                "product_name": h.product_name,
                "advertiser_name": _clean_advertiser(h.advertiser_name),
                "genre": h.genre,
                "platform": h.platform,
                "view_increase": h.total_view_increase,
                "spend_increase": round(h.total_spend_increase),
                "cumulative_views": h.cumulative_views,
                "cumulative_spend": round(h.cumulative_spend),
                "is_hit": h.is_hit,
                "hit_score": h.hit_score,
                "trend_score": h.trend_score,
                "rank_change": h.rank_change,
                "previous_rank": h.previous_rank,
                "thumbnail": thumbnail,
                "duration_seconds": ad.duration_seconds if ad else 0,
                "image_url": ad.image_url if ad else "",
                "snapshot_url": ad.snapshot_url if ad else "",
            })

        return {
            "total": len(items),
            "items": items,
        }


@router.get("/advertiser/{advertiser_name}")
def get_advertiser_analytics(
    advertiser_name: str,
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
):
    """Get detailed analytics for a specific advertiser."""
    with sync_session_scope() as session:
        svc = RankingService()
        return svc.get_advertiser_rankings(session, advertiser_name, period)


@router.get("/genre-summary")
def get_genre_summary(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
):
    """Get summary statistics per genre (market overview)."""
    with sync_session_scope() as session:
        yesterday = _today_jst() - timedelta(days=1)
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
        start = yesterday - timedelta(days=days - 1)

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
                AdDailyMetrics.metric_date <= yesterday,
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


# ==================== Pro-Search ====================


@router.get("/search")
def pro_search(
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
    with sync_session_scope() as session:
        results = []
        total_count = 0
        offset = (page - 1) * page_size

        # Search in ads (title, description, advertiser, brand)
        if search_scope in ("all", "ads"):
            ad_query = session.query(Ad).filter(
                or_(
                    Ad.title.ilike(f"%{_escape_like(q)}%"),
                    Ad.description.ilike(f"%{_escape_like(q)}%"),
                    Ad.advertiser_name.ilike(f"%{_escape_like(q)}%"),
                    Ad.brand_name.ilike(f"%{_escape_like(q)}%"),
                )
            )
            if genre:
                ad_query = ad_query.filter(Ad.category == genre)
            ad_query = _resolve_platform_filter(ad_query, Ad.platform, platform)
            if advertiser:
                ad_query = ad_query.filter(Ad.advertiser_name.ilike(f"%{_escape_like(advertiser)}%"))

            total_count += ad_query.count()
            ads = ad_query.order_by(Ad.created_at.desc()).offset(offset).limit(page_size).all()
            for ad in ads:
                results.append({
                    "type": "ad",
                    "id": ad.id,
                    "title": ad.title,
                    "description": ad.description,
                    "platform": str(ad.platform.value) if hasattr(ad.platform, 'value') else str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "brand_name": ad.brand_name,
                    "category": str(ad.category.value) if ad.category and hasattr(ad.category, 'value') else str(ad.category) if ad.category else None,
                    "match_field": "title/description",
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

        # Search in transcripts (audio text from videos)
        if search_scope in ("all", "transcript"):
            transcript_query = (
                session.query(Transcription, Ad)
                .join(AdAnalysis, Transcription.analysis_id == AdAnalysis.id)
                .join(Ad, AdAnalysis.ad_id == Ad.id)
                .filter(Transcription.text.ilike(f"%{_escape_like(q)}%"))
            )
            transcript_query = _resolve_platform_filter(transcript_query, Ad.platform, platform)

            total_count += transcript_query.count()
            transcripts = transcript_query.offset(offset).limit(page_size).all()
            for t, ad in transcripts:
                results.append({
                    "type": "transcript",
                    "id": ad.id,
                    "title": ad.title,
                    "matched_text": t.text,
                    "timestamp_ms": t.start_time_ms,
                    "platform": str(ad.platform.value) if hasattr(ad.platform, 'value') else str(ad.platform),
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
                .filter(TextDetection.text.ilike(f"%{_escape_like(q)}%"))
            )
            text_query = _resolve_platform_filter(text_query, Ad.platform, platform)

            total_count += text_query.count()
            texts = text_query.offset(offset).limit(page_size).all()
            for td, ad in texts:
                results.append({
                    "type": "text_detection",
                    "id": ad.id,
                    "title": ad.title,
                    "matched_text": td.text,
                    "timestamp_seconds": td.timestamp_seconds,
                    "platform": str(ad.platform.value) if hasattr(ad.platform, 'value') else str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "match_field": "video_text",
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

        # Search in LP content
        if search_scope in ("all", "lp"):
            from app.models.landing_page import LandingPage

            lp_query = session.query(LandingPage).filter(
                or_(
                    LandingPage.title.ilike(f"%{_escape_like(q)}%"),
                    LandingPage.hero_headline.ilike(f"%{_escape_like(q)}%"),
                    LandingPage.full_text_content.ilike(f"%{_escape_like(q)}%"),
                    LandingPage.product_name.ilike(f"%{_escape_like(q)}%"),
                )
            )
            if genre:
                lp_query = lp_query.filter(LandingPage.genre == genre)

            total_count += lp_query.count()
            lps = lp_query.offset(offset).limit(page_size).all()
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
            "total_results": total_count,
            "page": page,
            "page_size": page_size,
            "results": results,
        }


# ==================== CSV Export ====================


@router.get("/export/rankings")
def export_rankings_csv(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
    genre: Optional[str] = None,
):
    """Export rankings as CSV file."""
    with sync_session_scope() as session:
        svc = RankingService()
        rankings, total = svc.get_rankings(session, period=period, genre=genre, limit=500)

        output = io.StringIO()
        writer = csv.writer(output)

        if total > 0:
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
                    _sanitize_csv(r.product_name),
                    _sanitize_csv(r.advertiser_name),
                    _sanitize_csv(r.genre),
                    _sanitize_csv(r.platform),
                    r.total_view_increase,
                    round(r.total_spend_increase),
                    r.cumulative_views,
                    round(r.cumulative_spend),
                    "HIT" if r.is_hit else "",
                    r.hit_score or 0,
                    r.trend_score or 0,
                ])
        else:
            # Fallback: export ads ranked by view_count
            ad_query = session.query(Ad)
            if genre:
                ad_query = ad_query.filter(Ad.category == genre)
            ads = ad_query.order_by(
                case((Ad.view_count.is_(None), 0), else_=1).desc(),
                desc(Ad.view_count),
            ).limit(500).all()

            writer.writerow([
                "順位", "商材名", "広告主", "媒体", "カテゴリ",
                "再生数", "いいね数", "秒数", "初出日", "動画URL",
            ])
            for rank, ad in enumerate(ads, start=1):
                writer.writerow([
                    rank,
                    _sanitize_csv(ad.title),
                    _sanitize_csv(ad.advertiser_name),
                    str(ad.platform.value) if ad.platform and hasattr(ad.platform, 'value') else str(ad.platform or ""),
                    str(ad.category.value) if ad.category and hasattr(ad.category, 'value') else str(ad.category or ""),
                    ad.view_count or 0,
                    ad.like_count or 0,
                    ad.duration_seconds or "",
                    ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                    _sanitize_csv(ad.video_url),
                ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=rankings_{period}_{genre or 'all'}.csv"
            },
        )


@router.get("/export/ads")
def export_ads_csv(
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    advertiser: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
):
    """Export ad list as CSV file."""
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        if advertiser:
            query = query.filter(Ad.advertiser_name.ilike(f"%{_escape_like(advertiser)}%"))

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
                _sanitize_csv(ad.title),
                str(ad.platform.value) if ad.platform and hasattr(ad.platform, 'value') else str(ad.platform or ""),
                str(ad.category.value) if ad.category and hasattr(ad.category, 'value') else str(ad.category or ""),
                _sanitize_csv(ad.advertiser_name),
                _sanitize_csv(ad.brand_name),
                ad.view_count or 0,
                ad.like_count or 0,
                ad.estimated_ctr or "",
                ad.duration_seconds or "",
                str(ad.status.value) if ad.status and hasattr(ad.status, 'value') else str(ad.status or ""),
                ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                ad.last_seen_at.isoformat() if ad.last_seen_at else "",
                _sanitize_csv(ad.video_url),
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ads_export.csv"},
        )
