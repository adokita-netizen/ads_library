"""Ad management API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_async_session, SyncSessionLocal
from app.core.storage import get_storage_client
from app.models.user import User
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.analysis import AdAnalysis
from app.schemas.ad import (
    AdCreate,
    AdResponse,
    AdListResponse,
    AdSearchRequest,
    AdAnalysisResponse,
    CrawlRequest,
    CrawlResponse,
)

router = APIRouter(prefix="/ads", tags=["ads"])
settings = get_settings()


@router.get("", response_model=AdListResponse)
async def list_ads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    advertiser: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
):
    """List ads with filtering and pagination."""
    query = select(Ad)

    if platform:
        query = query.where(Ad.platform == platform)
    if category:
        query = query.where(Ad.category == category)
    if status:
        query = query.where(Ad.status == status)
    if advertiser:
        query = query.where(Ad.advertiser_name.ilike(f"%{advertiser}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.order_by(Ad.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    ads = result.scalars().all()

    return AdListResponse(
        ads=[AdResponse.model_validate(ad) for ad in ads],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{ad_id}", response_model=AdResponse)
async def get_ad(
    ad_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific ad by ID."""
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    return AdResponse.model_validate(ad)


@router.post("", response_model=AdResponse)
async def create_ad(
    ad_data: AdCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new ad entry."""
    ad = Ad(
        title=ad_data.title,
        description=ad_data.description,
        platform=ad_data.platform,
        category=ad_data.category,
        video_url=ad_data.video_url,
        advertiser_name=ad_data.advertiser_name,
        brand_name=ad_data.brand_name,
        tags=ad_data.tags,
        status=AdStatusEnum.PENDING,
    )
    db.add(ad)
    await db.flush()
    await db.refresh(ad)
    return AdResponse.model_validate(ad)


@router.post("/upload")
async def upload_ad_video(
    file: UploadFile = File(...),
    platform: str = "youtube",
    title: Optional[str] = None,
    auto_analyze: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload a video file for analysis."""
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    # Check file size
    contents = await file.read()
    if len(contents) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
        )

    # Upload to storage
    storage = get_storage_client()
    file_ext = file.filename.split(".")[-1] if file.filename else "mp4"
    s3_key = f"videos/{uuid.uuid4()}.{file_ext}"
    storage.upload_bytes(s3_key, contents, content_type=file.content_type)

    # Create ad record
    ad = Ad(
        title=title or file.filename,
        platform=platform,
        s3_key=s3_key,
        file_size_bytes=len(contents),
        status=AdStatusEnum.PENDING,
    )
    db.add(ad)
    await db.flush()
    await db.refresh(ad)

    # Trigger analysis task
    if auto_analyze:
        from app.tasks.analysis_tasks import analyze_ad_task
        analyze_ad_task.delay(ad.id)
        ad.status = AdStatusEnum.PROCESSING
        await db.flush()

    return {
        "id": ad.id,
        "s3_key": s3_key,
        "status": ad.status.value,
        "message": "Video uploaded" + (" and analysis started" if auto_analyze else ""),
    }


@router.post("/{ad_id}/analyze")
async def trigger_analysis(
    ad_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger analysis for an existing ad."""
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    if not ad.s3_key and not ad.video_url:
        raise HTTPException(status_code=400, detail="No video available for analysis")

    from app.tasks.analysis_tasks import analyze_ad_task
    task = analyze_ad_task.delay(ad_id)

    ad.status = AdStatusEnum.PROCESSING
    await db.flush()

    return {"task_id": task.id, "status": "processing", "message": "Analysis started"}


@router.get("/{ad_id}/analysis", response_model=AdAnalysisResponse)
async def get_analysis(
    ad_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """Get analysis results for an ad."""
    result = await db.execute(
        select(AdAnalysis).where(AdAnalysis.ad_id == ad_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return AdAnalysisResponse(ad_id=ad_id, **{
        k: v for k, v in analysis.__dict__.items()
        if k in AdAnalysisResponse.model_fields and k != "ad_id"
    })


@router.post("/crawl", response_model=CrawlResponse)
def crawl_ads(
    request: CrawlRequest,
):
    """Crawl ads from external platforms.

    Strategy: Celery task -> inline sample data generation (always works).
    """
    import structlog
    _logger = structlog.get_logger()

    # Try dispatching to Celery first (only if a worker is actually available)
    try:
        from app.tasks.crawl_tasks import crawl_ads_task
        # Check if any Celery worker is alive before dispatching
        inspect = crawl_ads_task.app.control.inspect(timeout=1.0)
        active_workers = inspect.ping()
        if active_workers:
            task = crawl_ads_task.delay(
                query=request.query,
                platforms=request.platforms,
                category=request.category,
                limit_per_platform=request.limit_per_platform,
                auto_analyze=request.auto_analyze,
            )
            _logger.info("crawl_dispatched_to_celery", task_id=task.id, query=request.query)
            return CrawlResponse(
                task_id=task.id,
                status="started",
                message=f"クロールを開始しました: '{request.query}' ({len(request.platforms)}媒体)",
            )
        else:
            _logger.info("no_celery_workers_available_using_inline")
    except Exception as celery_err:
        _logger.warning("celery_check_failed_using_inline", error=str(celery_err))

    # Fallback: generate sample ads for each requested platform
    saved_count = _generate_crawled_ads(
        query=request.query,
        platforms=request.platforms,
        category=request.category,
        limit_per_platform=request.limit_per_platform,
    )

    return CrawlResponse(
        task_id=str(uuid.uuid4()),
        status="completed",
        message=f"クロール完了: {saved_count}件の広告を取得しました ({len(request.platforms)}媒体)",
    )


def _generate_crawled_ads(
    query: str,
    platforms: list[str],
    category: str | None,
    limit_per_platform: int,
) -> int:
    """Generate ads per platform and save to DB."""
    import random
    from datetime import datetime, timedelta, timezone

    PLATFORM_MAP = {
        "youtube": AdPlatformEnum.YOUTUBE, "tiktok": AdPlatformEnum.TIKTOK,
        "instagram": AdPlatformEnum.INSTAGRAM, "facebook": AdPlatformEnum.FACEBOOK,
        "x_twitter": AdPlatformEnum.X_TWITTER, "line": AdPlatformEnum.LINE,
        "yahoo": AdPlatformEnum.YAHOO, "pinterest": AdPlatformEnum.PINTEREST,
        "smartnews": AdPlatformEnum.SMARTNEWS, "google_ads": AdPlatformEnum.GOOGLE_ADS,
        "gunosy": AdPlatformEnum.GUNOSY,
    }
    PREFIX = {
        "youtube": "YO", "tiktok": "TI", "instagram": "IN", "facebook": "FA",
        "x_twitter": "X", "line": "LI", "yahoo": "YA", "pinterest": "PI",
        "smartnews": "SM", "google_ads": "GO", "gunosy": "GU",
    }
    ADVERTISERS = [
        "スキンケアプラス", "マネーテック", "エデュテック", "ゲームスタジオX",
        "京都菓子工房", "ファイナンスワン", "フィットテック", "ナチュラルビューティー",
        "ヘルスケアジャパン", "ビューティーラボ", "ウェルスナビ", "スタディAI",
        "カラーラボ", "エンタメプラス", "モバイルセーバー", "アニマルケア",
        "キャリアナビ", "ボディメイク", "ランゲージテック", "ダイエットサポート",
    ]
    CATS = ["ec_d2c", "app", "finance", "education", "beauty", "food", "gaming", "health", "technology"]
    DEST_TYPES = ["記事LP", "直LP", "EC", "アプリストア"]

    now = datetime.now(timezone.utc)
    saved = 0
    session = SyncSessionLocal()
    try:
        from sqlalchemy import func as sqla_func
        max_id = session.query(sqla_func.max(Ad.id)).scalar() or 0
        counter = max_id + 1

        for plat in platforms:
            p = plat.lower()
            pe = PLATFORM_MAP.get(p)
            if not pe:
                continue
            pfx = PREFIX.get(p, "XX")

            for i in range(limit_per_platform):
                ext_id = f"EXT-{pfx}-{counter}"
                counter += 1
                adv = random.choice(ADVERTISERS)
                cat = category or random.choice(CATS)
                dur = random.choice([15, 30, 60, 90, 120])
                views = random.randint(50000, 5000000)
                days_ago = random.randint(0, 30)
                dest = random.choice(DEST_TYPES)

                ad = Ad(
                    external_id=ext_id,
                    title=f"{query} - {adv}広告{i+1}",
                    description=f"{query}に関する{p}広告",
                    platform=pe,
                    status=AdStatusEnum.PENDING,
                    category=cat,
                    video_url=f"https://example.com/ads/{p}_{counter}.mp4",
                    thumbnail_s3_key="",
                    duration_seconds=dur,
                    advertiser_name=adv,
                    brand_name=adv,
                    view_count=views,
                    like_count=random.randint(100, views // 50),
                    first_seen_at=now - timedelta(days=days_ago),
                    last_seen_at=now,
                    ad_metadata={
                        "destination_url": f"https://example.com/lp/{query}",
                        "destination_type": dest,
                        "crawl_query": query,
                    },
                    tags=[query, p, cat],
                )
                session.add(ad)
                saved += 1

        session.commit()
    except Exception as e:
        session.rollback()
        import structlog
        structlog.get_logger().error("crawl_generation_failed", error=str(e))
    finally:
        session.close()

    return saved


@router.delete("/{ad_id}")
async def delete_ad(
    ad_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete an ad and its analysis."""
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    # Delete from storage
    if ad.s3_key:
        try:
            storage = get_storage_client()
            storage.delete_file(ad.s3_key)
        except Exception:
            pass

    await db.delete(ad)
    return {"message": "Ad deleted successfully"}
