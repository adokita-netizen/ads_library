"""Ad management API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session
from app.core.storage import get_storage_client
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
async def crawl_ads(request: CrawlRequest):
    """Crawl ads from external platforms."""
    from app.tasks.crawl_tasks import crawl_ads_task
    task = crawl_ads_task.delay(
        query=request.query,
        platforms=request.platforms,
        category=request.category,
        limit_per_platform=request.limit_per_platform,
        auto_analyze=request.auto_analyze,
    )

    return CrawlResponse(
        task_id=task.id,
        status="started",
        message=f"Crawling started for '{request.query}' on {len(request.platforms)} platforms",
    )


@router.delete("/{ad_id}")
async def delete_ad(
    ad_id: int,
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
