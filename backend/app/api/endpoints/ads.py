"""Ad management API endpoints."""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

# Video file magic bytes for upload validation
_VIDEO_MAGIC_BYTES = {
    b"\x00\x00\x00": "mp4/mov",       # ftyp box (check further bytes)
    b"\x1a\x45\xdf": "webm/mkv",      # EBML header
    b"\x00\x00\x01": "mpeg",           # MPEG start code
    b"\x46\x4c\x56": "flv",           # FLV
    b"\x52\x49\x46": "avi/webp",       # RIFF (AVI)
}

ALLOWED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
}


import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user
from app.utils.db import escape_like as _escape_like
from app.core.config import get_settings
from app.core.database import get_async_session, SyncSessionLocal
from app.core.storage import get_storage_client
from app.models.user import User
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, MediaExtractionStatus
from app.models.analysis import AdAnalysis
from app.schemas.ad import (
    AdCreate,
    AdResponse,
    AdListResponse,
    AdSearchRequest,
    AdAnalysisResponse,
    CrawlRequest,
    CrawlResponse,
    LPKeywordExtractionRequest,
    LPKeywordExtractionResponse,
    build_media_status_payload,
    build_lp_info_payload,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/ads", tags=["ads"])
settings = get_settings()


def _classify_destination_type(url: str | None) -> str:
    if not url:
        return ""
    lowered = str(url).lower()
    if "apps.apple.com" in lowered or "play.google.com" in lowered:
        return "app_download"
    if "line.me" in lowered or "lin.ee" in lowered:
        return "line_add"
    if any(token in lowered for token in ("/cart", "/checkout", "/buy", "/purchase")):
        return "purchase"
    return "lp"


def _build_media_status(ad: Ad) -> dict:
    return build_media_status_payload(ad)


def _build_lp_info(ad: Ad) -> dict:
    return build_lp_info_payload(ad)


@router.get("", response_model=AdListResponse)
async def list_ads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = Query(None, max_length=200),
    advertiser: Optional[str] = Query(None, max_length=200),
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List ads with filtering and pagination."""
    query = select(Ad)

    if platform:
        if platform.lower() == "meta":
            query = query.where(Ad.platform.in_(["facebook", "instagram"]))
        else:
            query = query.where(Ad.platform == platform)
    if category:
        query = query.where(Ad.category == category)
    if status:
        query = query.where(Ad.status == status)
    if q:
        escaped = f"%{_escape_like(q)}%"
        query = query.where(
            or_(
                Ad.title.ilike(escaped),
                Ad.description.ilike(escaped),
                Ad.advertiser_name.ilike(escaped),
                cast(Ad.ad_metadata, String).ilike(escaped),
            )
        )
    if advertiser:
        query = query.where(Ad.advertiser_name.ilike(f"%{_escape_like(advertiser)}%"))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.order_by(Ad.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    ads = result.scalars().all()

    # Build response with presigned thumbnail URLs
    ad_responses = []
    for ad in ads:
        resp = AdResponse.model_validate(ad)
        # Resolve thumbnail: presigned S3 URL > original thumbnail_url > first image_url
        if ad.thumbnail_s3_key:
            try:
                storage = get_storage_client()
                resp.thumbnail_url = storage.get_presigned_url(ad.thumbnail_s3_key)
            except Exception as e:
                logger.warning("presigned_url_failed", ad_id=ad.id, s3_key=ad.thumbnail_s3_key, error=str(e))
        if not resp.thumbnail_url and ad.thumbnail_url:
            resp.thumbnail_url = ad.thumbnail_url
        if not resp.thumbnail_url and ad.image_url:
            resp.thumbnail_url = ad.image_url
        ad_responses.append(resp)

    return AdListResponse(
        ads=ad_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/connected-platforms")
def get_connected_platforms_endpoint():
    """Return list of platforms that have API keys configured."""
    from app.tasks.crawl_tasks import get_connected_platforms
    connected = get_connected_platforms()
    return {"connected": connected}


@router.get("/crawl/{job_id}/status")
async def crawl_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Get crawl job progress status."""
    from app.models.crawl_job import CrawlJob
    result = await db.execute(select(CrawlJob).where(CrawlJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found")

    progress_percent = 0
    if job.total_platforms > 0:
        progress_percent = round(job.completed_platforms / job.total_platforms * 100)
    if job.status.value == "completed":
        progress_percent = 100

    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress_percent": progress_percent,
        "total_platforms": job.total_platforms,
        "completed_platforms": job.completed_platforms,
        "current_platform": job.current_platform,
        "total_ads_found": job.total_ads_found,
        "error_message": job.error_message,
        "platforms": job.platforms,
    }


@router.get("/health/data-integrity")
async def ad_data_integrity(
    db: AsyncSession = Depends(get_async_session),
):
    """Check data integrity of crawled ads."""
    # Total ads
    total_result = await db.execute(select(func.count()).select_from(Ad))
    total_ads = total_result.scalar() or 0

    # Ads missing all media (no image, no video, no snapshot)
    no_media_result = await db.execute(
        select(func.count()).select_from(Ad).where(
            Ad.image_url.is_(None),
            Ad.video_url.is_(None),
            Ad.snapshot_url.is_(None),
        )
    )
    no_media_count = no_media_result.scalar() or 0

    # Ads missing title
    no_title_result = await db.execute(
        select(func.count()).select_from(Ad).where(
            (Ad.title.is_(None)) | (Ad.title == "")
        )
    )
    no_title_count = no_title_result.scalar() or 0

    # Ads with pending media extraction
    pending_media_result = await db.execute(
        select(func.count()).select_from(Ad).where(
            Ad.media_extraction_status == MediaExtractionStatus.PENDING
        )
    )
    pending_media_count = pending_media_result.scalar() or 0

    # Ads missing thumbnail
    no_thumb_result = await db.execute(
        select(func.count()).select_from(Ad).where(
            Ad.thumbnail_url.is_(None),
            Ad.thumbnail_s3_key.is_(None),
        )
    )
    no_thumbnail_count = no_thumb_result.scalar() or 0

    # Calculate health score (0-100)
    if total_ads == 0:
        health_score = 100.0
    else:
        issue_count = no_media_count + no_title_count
        health_score = round(max(0, (1 - issue_count / total_ads)) * 100, 1)

    return {
        "total_ads": total_ads,
        "no_media_count": no_media_count,
        "no_title_count": no_title_count,
        "no_thumbnail_count": no_thumbnail_count,
        "pending_media_extraction": pending_media_count,
        "health_score": health_score,
        "details": {
            "no_media_percent": round(no_media_count / total_ads * 100, 1) if total_ads else 0,
            "no_title_percent": round(no_title_count / total_ads * 100, 1) if total_ads else 0,
            "no_thumbnail_percent": round(no_thumbnail_count / total_ads * 100, 1) if total_ads else 0,
        },
    }


@router.post("/thumbnails/fetch-all")
async def fetch_all_thumbnails(
    use_playwright: bool = True,
    batch_size: int = Query(10, ge=1, le=50),
):
    """Batch-fetch thumbnails for all ads missing thumbnail_url.

    3-stage fallback per ad:
    1. Build snapshot_url from external_id if missing
    2. Meta Graph API ad_snapshot_url (authenticated URL)
    3. MediaExtractor (HTTP+BS4 → Playwright)
    """
    # Load Meta access_token from DB
    meta_token = None
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        keys = load_api_keys_from_db()
        meta_keys = keys.get("meta", keys.get("facebook", {}))
        meta_token = meta_keys.get("access_token")
    except Exception as e:
        logger.warning("meta_token_load_failed", error=str(e))

    from app.services.thumbnail_fetcher import ThumbnailFetcher

    def _run():
        fetcher = ThumbnailFetcher(
            meta_access_token=meta_token,
            use_playwright=use_playwright,
        )
        session = SyncSessionLocal()
        try:
            return fetcher.fetch_all(session, batch_size=batch_size)
        finally:
            session.close()

    try:
        stats = await asyncio.wait_for(asyncio.to_thread(_run), timeout=600)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Thumbnail fetch timed out after 600 seconds",
        ) from exc

    return stats


@router.get("/{ad_id}", response_model=AdResponse)
async def get_ad(
    ad_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a specific ad by ID."""
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    resp = AdResponse.model_validate(ad)
    # Resolve thumbnail URL
    if ad.thumbnail_s3_key:
        try:
            storage = get_storage_client()
            resp.thumbnail_url = storage.get_presigned_url(ad.thumbnail_s3_key)
        except Exception as e:
            logger.warning("presigned_url_failed", ad_id=ad_id, s3_key=ad.thumbnail_s3_key, error=str(e))
    if not resp.thumbnail_url and ad.thumbnail_url:
        resp.thumbnail_url = ad.thumbnail_url
    if not resp.thumbnail_url and ad.image_url:
        resp.thumbnail_url = ad.image_url

    # Fetch cumulative metrics from AdDailyMetrics
    try:
        from app.models.ad_metrics import AdDailyMetrics
        metrics_result = await db.execute(
            select(
                func.max(AdDailyMetrics.view_count).label("cumulative_views"),
                func.max(AdDailyMetrics.estimated_spend).label("cumulative_spend"),
            ).where(AdDailyMetrics.ad_id == ad_id)
        )
        row = metrics_result.one_or_none()
        if row:
            resp.cumulative_views = row.cumulative_views or resp.view_count or 0
            resp.cumulative_spend = round(row.cumulative_spend or resp.spend or 0)
    except Exception as e:
        logger.warning("cumulative_metrics_fetch_failed", ad_id=ad_id, error=str(e))

    return resp


@router.post("", response_model=AdResponse)
async def create_ad(
    ad_data: AdCreate,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new ad entry."""
    ad = Ad(
        title=ad_data.title,
        description=ad_data.description,
        platform=ad_data.platform,
        category=ad_data.category,
        creative_type=ad_data.creative_type,
        video_url=ad_data.video_url,
        image_url=ad_data.image_url,
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
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Upload a video file for analysis."""
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_VIDEO_MIME_TYPES:
        allowed_types = ", ".join(sorted(ALLOWED_VIDEO_MIME_TYPES))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Allowed: {allowed_types}",
        )

    # Read file in chunks to avoid loading entire file into memory
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    chunks: list[bytes] = []
    total_size = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {settings.max_upload_size_mb}MB",
            )
        chunks.append(chunk)
    contents = b"".join(chunks)

    # Validate file magic bytes (prevent polyglot/non-video uploads)
    if len(contents) >= 12:
        header = contents[:3]
        is_valid_video = any(contents.startswith(magic) for magic in _VIDEO_MAGIC_BYTES)
        # Also accept ftyp box (MP4/MOV): bytes 4-7 == "ftyp"
        if contents[4:8] == b"ftyp":
            is_valid_video = True
        if not is_valid_video:
            raise HTTPException(
                status_code=400,
                detail="ファイルのフォーマットが動画ではありません",
            )

    # Upload to storage
    storage = get_storage_client()
    file_ext = file.filename.split(".")[-1] if file.filename else "mp4"
    s3_key = f"videos/{uuid.uuid4()}.{file_ext}"
    try:
        storage.upload_bytes(s3_key, contents, content_type=file.content_type)
    except Exception as e:
        logger.error("storage_upload_failed", s3_key=s3_key, error=str(e))
        raise HTTPException(status_code=500, detail="ストレージへのアップロードに失敗しました")

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
        try:
            from app.tasks.dispatcher import dispatch_task
            dispatch_task("analyze_ad", ad_id=ad.id)
            ad.status = AdStatusEnum.PROCESSING
            await db.flush()
        except Exception as e:
            logger.warning("auto_analyze_dispatch_failed", ad_id=ad.id, error=str(e))

    return {
        "id": ad.id,
        "s3_key": s3_key,
        "status": ad.status.value,
        "message": "Video uploaded" + (" and analysis started" if auto_analyze else ""),
    }


@router.post("/{ad_id}/analyze")
async def trigger_analysis(
    ad_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger analysis for an existing ad."""
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    if not ad.s3_key and not ad.video_url:
        raise HTTPException(status_code=400, detail="No video available for analysis")

    from app.tasks.dispatcher import dispatch_task
    result = dispatch_task("analyze_ad", ad_id=ad_id)

    ad.status = AdStatusEnum.PROCESSING
    await db.flush()

    return {"task_id": result.id, "status": "processing", "message": "Analysis started"}


@router.get("/{ad_id}/analysis", response_model=AdAnalysisResponse)
async def get_analysis(
    ad_id: int,
    _user: Optional[User] = Depends(get_optional_user),
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
    """Crawl ads from external platforms (connected platforms only)."""
    import structlog
    _logger = structlog.get_logger()

    # Filter to only platforms with API keys configured
    from app.tasks.crawl_tasks import get_connected_platforms
    connected = get_connected_platforms()
    active_platforms = [p for p in request.platforms if p in connected]

    if not active_platforms:
        return CrawlResponse(
            task_id=str(uuid.uuid4()),
            status="completed",
            message=f"APIキーが設定されている媒体がありません。設定画面からAPIキーを登録してください。(連携済み: {', '.join(connected) if connected else 'なし'})",
        )

    skipped = [p for p in request.platforms if p not in connected]

    # Try dispatching to task backend (Celery or SQS)
    try:
        from app.tasks.dispatcher import dispatch_task, TASK_BACKEND
        if TASK_BACKEND == "sqs":
            result = dispatch_task(
                "crawl_ads",
                query=request.query,
                platforms=active_platforms,
                category=request.category,
                limit_per_platform=request.limit_per_platform,
                auto_analyze=request.auto_analyze,
                country=request.country,
                trigger_source=request.trigger_source,
                schedule_window=request.schedule_window,
                priority=request.priority,
            )
            _logger.info("crawl_dispatched_to_sqs", task_id=result.id, query=request.query, platforms=active_platforms)
            msg = f"クロールを開始しました: '{request.query}' ({len(active_platforms)}媒体: {', '.join(active_platforms)})"
            if skipped:
                msg += f" ※スキップ: {', '.join(skipped)}(APIキー未設定)"
            return CrawlResponse(task_id=result.id, status="started", message=msg)
        else:
            from app.tasks.crawl_tasks import crawl_ads_task
            inspect = crawl_ads_task.app.control.inspect(timeout=1.0)
            active_workers = inspect.ping()
            if active_workers:
                result = dispatch_task(
                    "crawl_ads",
                    query=request.query,
                    platforms=active_platforms,
                    category=request.category,
                    limit_per_platform=request.limit_per_platform,
                    auto_analyze=request.auto_analyze,
                    country=request.country,
                    trigger_source=request.trigger_source,
                    schedule_window=request.schedule_window,
                    priority=request.priority,
                )
                _logger.info("crawl_dispatched_to_celery", task_id=result.id, query=request.query)
                return CrawlResponse(task_id=result.id, status="started", message=f"クロールを開始しました: '{request.query}' ({len(active_platforms)}媒体)")
            else:
                _logger.info("no_celery_workers_available_using_inline")
    except Exception as celery_err:
        _logger.warning("task_dispatch_failed_using_inline", error=str(celery_err))

    # Fallback: run real crawlers inline
    inline_job_id = str(uuid.uuid4())

    # Create CrawlJob record for inline crawl
    from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
    inline_session = SyncSessionLocal()
    try:
        crawl_job = CrawlJob(
            job_id=inline_job_id,
            status=CrawlJobStatusEnum.RUNNING,
            query=request.query,
            platforms=active_platforms,
            total_platforms=len(active_platforms),
            completed_platforms=0,
            total_ads_found=0,
        )
        inline_session.add(crawl_job)
        inline_session.commit()
    except Exception as e:
        logger.warning("crawl_job_create_failed", job_id=inline_job_id, error=str(e))
    finally:
        inline_session.close()

    try:
        saved_count = _inline_crawl(
            query=request.query,
            platforms=active_platforms,
            category=request.category,
            limit_per_platform=request.limit_per_platform,
            country=request.country,
            trigger_source=request.trigger_source,
            schedule_window=request.schedule_window,
            priority=request.priority,
        )

        # Update CrawlJob to COMPLETED
        done_session = SyncSessionLocal()
        try:
            cj = done_session.query(CrawlJob).filter(CrawlJob.job_id == inline_job_id).first()
            if cj:
                cj.status = CrawlJobStatusEnum.COMPLETED
                cj.completed_platforms = len(active_platforms)
                cj.total_ads_found = saved_count
                cj.current_platform = None
                done_session.commit()
        except Exception as e:
            logger.warning("crawl_job_complete_update_failed", job_id=inline_job_id, error=str(e))
        finally:
            done_session.close()

        msg = f"クロール完了: {saved_count}件の広告を取得しました ({', '.join(active_platforms)})"
        if skipped:
            msg += f" ※スキップ: {', '.join(skipped)}(APIキー未設定)"
        return CrawlResponse(
            task_id=inline_job_id,
            status="completed",
            message=msg,
        )
    except Exception as crawl_err:
        _logger.warning("inline_crawl_error", error=str(crawl_err))

        # Update CrawlJob to FAILED
        fail_session = SyncSessionLocal()
        try:
            cj = fail_session.query(CrawlJob).filter(CrawlJob.job_id == inline_job_id).first()
            if cj:
                cj.status = CrawlJobStatusEnum.FAILED
                cj.error_message = str(crawl_err)[:500]
                fail_session.commit()
        except Exception as e:
            logger.warning("crawl_job_fail_update_failed", job_id=inline_job_id, error=str(e))
        finally:
            fail_session.close()

        return CrawlResponse(
            task_id=inline_job_id,
            status="failed",
            message=f"クロールエラー: {str(crawl_err)}",
        )


def _inline_crawl(
    query: str,
    platforms: list[str],
    category: str | None,
    limit_per_platform: int,
    country: str = "JP",
    trigger_source: str = "manual",
    schedule_window: str | None = None,
    priority: str = "normal",
) -> int:
    """Run the real crawlers inline (same logic as Celery task, but synchronous)."""
    import asyncio
    import concurrent.futures
    from app.tasks.crawl_tasks import _crawl_platforms, _map_platform

    # Run async crawlers in a thread to avoid event loop conflicts with FastAPI
    def _run():
        return asyncio.run(
            _crawl_platforms(query, platforms, category, limit_per_platform, country)
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        results = future.result(timeout=120)

    # Save to DB
    saved = 0
    saved_ids: list[int] = []
    session = SyncSessionLocal()
    try:
        for platform, crawled_ads in results.items():
            for crawled_ad in crawled_ads:
                if crawled_ad.external_id:
                    existing = session.query(Ad).filter(
                        Ad.external_id == crawled_ad.external_id
                    ).first()
                    if existing:
                        # Update metrics and metadata for existing ads
                        if crawled_ad.spend is not None:
                            existing.spend = crawled_ad.spend
                        if crawled_ad.impressions is not None:
                            existing.impressions = crawled_ad.impressions
                        if crawled_ad.view_count is not None:
                            existing.view_count = crawled_ad.view_count
                        if crawled_ad.last_seen_at is not None:
                            existing.last_seen_at = crawled_ad.last_seen_at
                        # Merge new metadata keys
                        old_meta = dict(existing.ad_metadata or {})
                        new_meta = dict(crawled_ad.metadata or {})
                        old_meta.update({k: v for k, v in new_meta.items() if v is not None})
                        existing.ad_metadata = old_meta
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(existing, "ad_metadata")
                        saved += 1
                        continue

                # Determine media extraction status
                has_direct_media = bool(crawled_ad.image_urls or crawled_ad.video_url)
                if has_direct_media:
                    extraction_status = MediaExtractionStatus.SKIPPED
                elif crawled_ad.snapshot_url:
                    extraction_status = MediaExtractionStatus.PENDING
                else:
                    extraction_status = MediaExtractionStatus.SKIPPED

                # Reuse crawl task helpers to avoid URL extraction drift.
                from app.tasks.crawl_tasks import _extract_destination_url, _extract_text_fallback
                dest_url = _extract_destination_url(crawled_ad)
                title, description = _extract_text_fallback(crawled_ad)
                meta = dict(crawled_ad.metadata or {})
                if dest_url:
                    meta["destination_url"] = dest_url
                    meta.setdefault("destination_type", "LP")

                # Map category string to enum
                ad_category = None
                if crawled_ad.category:
                    from app.models.ad import AdCategoryEnum
                    try:
                        ad_category = AdCategoryEnum(crawled_ad.category)
                    except ValueError:
                        ad_category = AdCategoryEnum.OTHER

                ad = Ad(
                    external_id=crawled_ad.external_id,
                    title=title,
                    description=description,
                    platform=_map_platform(platform),
                    creative_type=crawled_ad.creative_type,
                    video_url=crawled_ad.video_url,
                    snapshot_url=crawled_ad.snapshot_url,
                    thumbnail_url=crawled_ad.thumbnail_url,
                    image_url=crawled_ad.image_urls[0] if crawled_ad.image_urls else None,
                    image_s3_keys={"urls": crawled_ad.image_urls} if len(crawled_ad.image_urls) > 1 else None,
                    destination_url=dest_url,
                    category=ad_category,
                    media_extraction_status=extraction_status,
                    advertiser_name=crawled_ad.advertiser_name,
                    advertiser_url=crawled_ad.advertiser_url,
                    brand_name=crawled_ad.brand_name,
                    duration_seconds=crawled_ad.duration_seconds,
                    view_count=crawled_ad.view_count,
                    like_count=crawled_ad.like_count,
                    spend=crawled_ad.spend,
                    impressions=crawled_ad.impressions,
                    reach=crawled_ad.reach,
                    cpc=crawled_ad.cpc,
                    cpm=crawled_ad.cpm,
                    frequency=crawled_ad.frequency,
                    first_seen_at=crawled_ad.first_seen_at,
                    last_seen_at=crawled_ad.last_seen_at,
                    tags=crawled_ad.tags,
                    ad_metadata=meta,
                    status=AdStatusEnum.PENDING,
                )
                session.add(ad)
                session.flush()
                saved_ids.append(ad.id)
                saved += 1

        session.commit()

        # Generate initial AdDailyMetrics for newly saved ads
        if saved > 0:
            try:
                from app.tasks.metrics_tasks import collect_metrics_for_ads
                from datetime import date, datetime, timedelta, timezone as _tz
                _JST = _tz(timedelta(hours=9))
                today_jst = datetime.now(_JST).date()
                metrics_created = collect_metrics_for_ads(session, target_date=today_jst)
                session.commit()
                _logger = structlog.get_logger()
                _logger.info("inline_crawl_initial_metrics", metrics_created=metrics_created)
            except Exception as metrics_err:
                _logger = structlog.get_logger()
                _logger.warning("inline_crawl_metrics_failed", error=str(metrics_err))
                session.rollback()

        try:
            from app.tasks.crawl_tasks import _run_post_crawl_knowledge_pipeline, _schedule_window_label

            _run_post_crawl_knowledge_pipeline(
                session,
                ad_ids=saved_ids,
                query=query,
                trigger_source=trigger_source,
                trigger_job_id=f"inline-{uuid.uuid4().hex[:8]}",
                schedule_window=schedule_window or ("manual" if trigger_source == "manual" else _schedule_window_label()),
                priority=priority,
            )
            session.commit()
        except Exception as knowledge_err:
            _logger = structlog.get_logger()
            _logger.warning("inline_crawl_knowledge_pipeline_failed", error=str(knowledge_err))
            session.rollback()

        # Dispatch media extraction for ads with snapshot_url
        try:
            from app.tasks.dispatcher import dispatch_task
            ads_with_snapshot = session.query(Ad).filter(
                Ad.media_extraction_status == MediaExtractionStatus.PENDING,
                Ad.snapshot_url.isnot(None),
            ).order_by(Ad.created_at.desc()).limit(saved).all()
            for ad_to_extract in ads_with_snapshot:
                dispatch_task("extract_media", ad_id=ad_to_extract.id)
        except Exception as dispatch_err:
            _logger = structlog.get_logger()
            _logger.warning("media_extraction_dispatch_failed", error=str(dispatch_err))

        # Dispatch thumbnail download for ads that have thumbnail_url but skipped extraction
        try:
            from app.tasks.dispatcher import dispatch_task as _dispatch
            ads_needing_thumb = session.query(Ad).filter(
                Ad.media_extraction_status == MediaExtractionStatus.SKIPPED,
                Ad.thumbnail_url.isnot(None),
                Ad.thumbnail_s3_key.is_(None),
            ).order_by(Ad.created_at.desc()).limit(saved).all()
            for ad_thumb in ads_needing_thumb:
                try:
                    _dispatch("download_thumbnail", ad_id=ad_thumb.id)
                except Exception as e:
                    _logger = structlog.get_logger()
                    _logger.warning("thumbnail_dispatch_failed", ad_id=ad_thumb.id, error=str(e))
        except Exception as dispatch_err:
            _logger = structlog.get_logger()
            _logger.warning("thumbnail_download_dispatch_failed", error=str(dispatch_err))

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return saved




@router.get("/{ad_id}/media")
async def get_ad_media(
    ad_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get media information for an ad with presigned URLs."""
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    media_info: dict = {
        "ad_id": ad_id,
        "creative_type": ad.creative_type,
        "media_extraction_status": ad.media_extraction_status,
        "image_url": ad.image_url,
        "video_url": ad.video_url,
        "snapshot_url": ad.snapshot_url,
        "download_url": f"/api/v1/media/download/{ad_id}",
    }
    media_info["media_status"] = _build_media_status(ad)
    media_info["lp_info"] = _build_lp_info(ad)

    # Generate presigned URLs for stored media
    try:
        storage = get_storage_client()
        if ad.image_s3_key:
            media_info["image_presigned_url"] = storage.get_presigned_url(ad.image_s3_key)
        if ad.s3_key:
            media_info["video_presigned_url"] = storage.get_presigned_url(ad.s3_key)
        if ad.thumbnail_s3_key:
            media_info["thumbnail_presigned_url"] = storage.get_presigned_url(ad.thumbnail_s3_key)

        # Carousel images
        if ad.image_s3_keys and isinstance(ad.image_s3_keys, dict):
            carousel_urls = ad.image_s3_keys.get("urls", [])
            if carousel_urls:
                media_info["carousel_image_urls"] = carousel_urls
    except Exception as e:
        logger.warning("presigned_url_generation_failed", ad_id=ad_id, error=str(e))

    return media_info


@router.post("/{ad_id}/extract-media")
async def trigger_media_extraction(
    ad_id: int,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Manually trigger media extraction for an ad."""
    result = await db.execute(select(Ad).where(Ad.id == ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    if not ad.snapshot_url:
        raise HTTPException(status_code=400, detail="No snapshot URL available for this ad")

    from app.tasks.dispatcher import dispatch_task
    try:
        dispatch_result = dispatch_task("extract_media", ad_id=ad_id)
    except Exception as e:
        # Fallback: run extraction inline
        import asyncio
        import concurrent.futures
        from app.services.media_extraction import MediaExtractor

        def _run():
            extractor = MediaExtractor()
            return asyncio.run(extractor.extract(ad.snapshot_url, use_playwright=True))

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_run)
                extracted = future.result(timeout=45)

            meta = dict(ad.ad_metadata or {})
            has_any_media = bool(extracted.image_urls or extracted.video_urls or extracted.thumbnail_url)
            if extracted.creative_type and extracted.creative_type != "unknown":
                ad.creative_type = extracted.creative_type
            if extracted.image_urls:
                ad.image_url = extracted.image_urls[0]
                if not ad.thumbnail_url:
                    ad.thumbnail_url = extracted.image_urls[0]
            elif extracted.thumbnail_url and not ad.thumbnail_url:
                ad.thumbnail_url = extracted.thumbnail_url
            if extracted.video_urls and not ad.video_url:
                ad.video_url = extracted.video_urls[0]
            if extracted.destination_url and not ad.destination_url:
                ad.destination_url = extracted.destination_url
                meta.setdefault("destination_url", extracted.destination_url)
                meta.setdefault("destination_type", _classify_destination_type(extracted.destination_url))
            if extracted.destination_domain:
                meta["destination_domain"] = extracted.destination_domain
            if extracted.ad_title and not ad.title:
                ad.title = extracted.ad_title[:500]
            if extracted.ad_text and not ad.description:
                ad.description = extracted.ad_text[:5000]

            meta["creative_fetch_status"] = "success" if has_any_media else "failed"
            meta["creative_fetch_source"] = extracted.extraction_method or "inline_extract"
            meta["creative_fetch_reason"] = None if has_any_media else "media_url_missing"
            recorded_at = datetime.now(timezone.utc).isoformat()
            meta["creative_fetched_at"] = recorded_at
            extractor_version = getattr(extracted, "extractor_version", "")
            meta["extractor_version"] = extractor_version
            history = meta.get("extractor_version_history")
            history_items = history if isinstance(history, list) else []
            history_items = [
                *history_items[-9:],
                {
                    "version": extractor_version,
                    "status": meta["creative_fetch_status"],
                    "source": meta["creative_fetch_source"],
                    "recorded_at": recorded_at,
                },
            ]
            meta["extractor_version_history"] = history_items
            ad.ad_metadata = meta
            ad.media_extraction_status = MediaExtractionStatus.COMPLETED if has_any_media else MediaExtractionStatus.FAILED
            await db.commit()
            await db.refresh(ad)

            return {
                "status": "completed" if has_any_media else "failed",
                "creative_type": extracted.creative_type,
                "image_count": len(extracted.image_urls),
                "video_count": len(extracted.video_urls),
                "image_url": ad.image_url,
                "thumbnail_url": ad.thumbnail_url,
                "video_url": ad.video_url,
                "destination_url": ad.destination_url,
                "destination_type": meta.get("destination_type", ""),
                "media_status": _build_media_status(ad),
                "message": "メディア抽出が完了しました（インライン実行）" if has_any_media else "LP遷移先は取得できましたが、保存可能な素材は不足しています",
            }
        except Exception as inline_err:
            logger.error("inline_media_extraction_failed", ad_id=ad_id, error=str(inline_err))
            raise HTTPException(status_code=500, detail="メディア抽出に失敗しました")

    ad.media_extraction_status = MediaExtractionStatus.PENDING
    await db.flush()

    return {
        "task_id": dispatch_result.id,
        "status": "started",
        "message": "メディア抽出を開始しました",
    }


@router.post("/batch-extract-media")
def batch_extract_media(
    limit: int = Query(20, ge=1, le=100),
):
    """Dispatch media extraction for ads that need it.

    Finds ads with snapshot_url but no extracted media and dispatches
    extract_media tasks to ECS via SQS.
    """
    from app.tasks.dispatcher import dispatch_task

    session = SyncSessionLocal()
    try:
        ads = (
            session.query(Ad)
            .filter(
                Ad.snapshot_url.isnot(None),
                Ad.media_extraction_status.in_([MediaExtractionStatus.PENDING, None, MediaExtractionStatus.FAILED]),
            )
            .order_by(Ad.created_at.desc())
            .limit(limit)
            .all()
        )

        dispatched = 0
        for ad in ads:
            try:
                dispatch_task("extract_media", ad_id=ad.id)
                ad.media_extraction_status = MediaExtractionStatus.DISPATCHED
                dispatched += 1
            except Exception as e:
                logger.warning("batch_extract_dispatch_failed", ad_id=ad.id, error=str(e))

        session.commit()
        return {
            "dispatched": dispatched,
            "total_found": len(ads),
            "message": f"{dispatched}件のメディア抽出タスクをキューに追加しました",
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/enrich-metrics")
def enrich_metrics_batch(
    limit: int = Query(50, ge=1, le=200),
    use_playwright: bool = True,
):
    """Batch-enrich ads missing metrics (impressions/spend) by visiting
    individual Ad Library pages via Playwright.

    This is for commercial ads where the Meta API doesn't return spend/impressions.
    """
    import asyncio
    import concurrent.futures

    from app.services.crawling.meta_crawler import (
        MetaAdLibraryCrawler,
        _estimate_ad_metrics,
    )

    # Load Meta access_token
    meta_token = None
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        keys = load_api_keys_from_db()
        meta_keys = keys.get("meta", keys.get("facebook", {}))
        meta_token = meta_keys.get("access_token")
    except Exception as e:
        logger.warning("meta_token_load_failed", error=str(e))
    if not meta_token:
        meta_token = settings.meta_access_token

    session = SyncSessionLocal()
    try:
        # Find ads missing metrics
        from sqlalchemy import or_
        ads_to_enrich = (
            session.query(Ad)
            .filter(
                or_(
                    Ad.impressions.is_(None),
                    Ad.spend.is_(None),
                ),
                Ad.external_id.isnot(None),
                Ad.platform.in_(["FACEBOOK", "INSTAGRAM", "facebook", "instagram"]),
            )
            .order_by(Ad.created_at.desc())
            .limit(limit)
            .all()
        )

        if not ads_to_enrich:
            return {"status": "completed", "message": "補完が必要な広告はありません", "enriched": 0}

        # Build CrawledAd objects for enrichment
        from app.services.crawling.base_crawler import CrawledAd
        crawled_ads = []
        ad_id_map = {}  # external_id → Ad model
        for ad in ads_to_enrich:
            crawled = CrawledAd(
                external_id=ad.external_id,
                platform=str(ad.platform.value) if hasattr(ad.platform, "value") else str(ad.platform),
                title=ad.title,
                description=ad.description,
                advertiser_name=ad.advertiser_name,
                thumbnail_url=ad.thumbnail_url,
                image_urls=[ad.image_url] if ad.image_url else [],
                snapshot_url=ad.snapshot_url,
                impressions=ad.impressions,
                spend=ad.spend,
                view_count=ad.view_count,
                metadata=ad.ad_metadata or {},
            )
            crawled_ads.append(crawled)
            ad_id_map[ad.external_id] = ad

        # Phase 1: Playwright-based thumbnail enrichment (only for ads with bad thumbnails)
        needs_thumb = [
            c for c in crawled_ads
            if not c.thumbnail_url
            or "s200x200" in (c.thumbnail_url or "")
            or "favicons" in (c.thumbnail_url or "")
        ]

        if needs_thumb and use_playwright:
            crawler = MetaAdLibraryCrawler(access_token=meta_token)

            def _run():
                return asyncio.run(
                    crawler._enrich_thumbnails_via_playwright(needs_thumb)
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_run)
                future.result(timeout=600)

        # Phase 2: Estimate metrics for all ads missing impressions/spend
        for crawled in crawled_ads:
            if crawled.impressions is None and crawled.spend is None:
                _estimate_ad_metrics(crawled)

        # Update database with enriched data
        from sqlalchemy.orm.attributes import flag_modified

        enriched_count = 0
        for crawled in crawled_ads:
            ad = ad_id_map.get(crawled.external_id)
            if not ad:
                continue

            changed = False
            if crawled.impressions is not None and ad.impressions is None:
                ad.impressions = crawled.impressions
                ad.view_count = crawled.view_count
                changed = True
                logger.info("enrich_impressions_saved", ad_id=ad.id, impressions=crawled.impressions)
            if crawled.spend is not None and ad.spend is None:
                ad.spend = crawled.spend
                changed = True
                logger.info("enrich_spend_saved", ad_id=ad.id, spend=crawled.spend)
            if crawled.thumbnail_url and (
                not ad.thumbnail_url
                or "s200x200" in (ad.thumbnail_url or "")
                or "favicons" in (ad.thumbnail_url or "")
            ):
                ad.thumbnail_url = crawled.thumbnail_url
                if not ad.image_url:
                    ad.image_url = crawled.thumbnail_url
                changed = True
                logger.info("enrich_thumbnail_saved", ad_id=ad.id)

            # Merge metadata (use new dict to ensure SQLAlchemy detects change)
            enrichment_keys = (
                "page_enriched", "detected_platforms",
                "metrics_estimated", "estimated_days_running",
                "estimated_daily_impressions", "estimated_cpm_jpy",
            )
            if any(k in crawled.metadata for k in enrichment_keys):
                meta = dict(ad.ad_metadata or {})
                for key in enrichment_keys:
                    if key in crawled.metadata:
                        meta[key] = crawled.metadata[key]
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                changed = True

            if changed:
                enriched_count += 1

        session.commit()

        return {
            "status": "completed",
            "total_candidates": len(ads_to_enrich),
            "enriched": enriched_count,
            "message": f"{enriched_count}件の広告のメトリクス・サムネイルを補完しました",
        }

    except Exception as e:
        session.rollback()
        logger.error("batch_enrich_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"エンリッチメント失敗: {str(e)}")
    finally:
        session.close()


@router.delete("/{ad_id}")
async def delete_ad(
    ad_id: int,
    _user: Optional[User] = Depends(get_optional_user),
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
        except Exception as e:
            logger.warning("storage_delete_failed", ad_id=ad_id, s3_key=ad.s3_key, error=str(e))

    await db.delete(ad)
    return {"message": "Ad deleted successfully"}


@router.post("/extract-lp-keywords", response_model=LPKeywordExtractionResponse)
async def extract_lp_keywords(
    body: LPKeywordExtractionRequest,
    _user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Extract brand/product keywords from landing pages of crawled ads.

    Scans destination_url of recent ads and extracts product names,
    brand names (katakana), and known product matches from LP content.
    """
    from app.services.crawling.keyword_expander import extract_keywords_from_lp

    # Fetch ads that have a destination_url, ordered by most recent
    result = await db.execute(
        select(Ad)
        .where(Ad.destination_url.isnot(None))
        .where(Ad.destination_url != "")
        .order_by(Ad.created_at.desc())
        .limit(body.max_ads)
    )
    ads = result.scalars().all()

    all_keywords: list[str] = []
    sources: list[dict] = []
    seen_keywords: set[str] = set()

    for ad in ads:
        url = ad.destination_url
        if not url:
            continue
        try:
            keywords = await extract_keywords_from_lp(url)
            new_kws = [kw for kw in keywords if kw not in seen_keywords]
            if new_kws:
                all_keywords.extend(new_kws)
                seen_keywords.update(new_kws)
                sources.append({
                    "ad_id": ad.id,
                    "url": url,
                    "keywords": new_kws,
                })
        except Exception as e:
            logger.warning("lp_keyword_extraction_error", ad_id=ad.id, url=url, error=str(e))

    return LPKeywordExtractionResponse(
        keywords=all_keywords,
        sources=sources,
        total_ads_scanned=len(ads),
    )
