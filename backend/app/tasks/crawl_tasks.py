"""Ad crawling Celery tasks."""

import asyncio
import uuid

import structlog

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.services.crawling.crawler_manager import CrawlerManager

try:
    from app.tasks.worker import celery_app
except ImportError:
    # Celery not installed — provide a no-op decorator so the module still loads
    class _FakeCelery:
        def task(self, *a, **kw):
            def decorator(fn):
                fn.delay = lambda *a2, **kw2: None
                fn.apply_async = lambda *a2, **kw2: None
                return fn
            return decorator
    celery_app = _FakeCelery()

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def crawl_ads_task(
    self,
    query: str,
    platforms: list[str],
    category: str | None = None,
    limit_per_platform: int = 20,
    auto_analyze: bool = False,
):
    """Crawl ads from multiple platforms."""
    logger.info(
        "crawl_task_started",
        query=query,
        platforms=platforms,
        task_id=self.request.id,
    )

    # Create or update CrawlJob for progress tracking
    job_id = self.request.id or str(uuid.uuid4())
    progress_session = SyncSessionLocal()
    try:
        from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
        crawl_job = CrawlJob(
            job_id=job_id,
            status=CrawlJobStatusEnum.RUNNING,
            query=query,
            platforms=platforms,
            total_platforms=len(platforms),
            completed_platforms=0,
            total_ads_found=0,
        )
        progress_session.add(crawl_job)
        progress_session.commit()
    except Exception as pex:
        logger.warning("crawl_job_create_failed", error=str(pex))
    finally:
        progress_session.close()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            _crawl_platforms(query, platforms, category, limit_per_platform)
        )
        loop.close()

        # Save results to database
        session = SyncSessionLocal()
        saved_count = 0

        try:
            for platform, crawled_ads in results.items():
                for crawled_ad in crawled_ads:
                    # Check for duplicates
                    if crawled_ad.external_id:
                        existing = session.query(Ad).filter(
                            Ad.external_id == crawled_ad.external_id
                        ).first()
                        if existing:
                            continue

                    platform_enum = _map_platform(platform)

                    # Warn on ads with no media or title
                    has_media = bool(crawled_ad.image_urls or crawled_ad.video_url or crawled_ad.snapshot_url)
                    if not crawled_ad.title and not has_media:
                        logger.warning(
                            "ad_missing_title_and_media",
                            platform=platform,
                            external_id=crawled_ad.external_id,
                            advertiser=crawled_ad.advertiser_name,
                        )

                    # Determine media extraction status:
                    # Skip extraction if crawler already provided direct media URLs
                    has_direct_media = bool(crawled_ad.image_urls or crawled_ad.video_url)
                    if has_direct_media:
                        extraction_status = "skipped"
                    elif crawled_ad.snapshot_url:
                        extraction_status = "pending"
                    else:
                        extraction_status = "skipped"

                    # Extract destination_url from CrawledAd field or metadata
                    dest_url = crawled_ad.destination_url
                    if not dest_url:
                        dest_url = (crawled_ad.metadata or {}).get("destination_url")

                    # Map category string to enum (best effort)
                    ad_category = None
                    if crawled_ad.category:
                        from app.models.ad import AdCategoryEnum
                        try:
                            ad_category = AdCategoryEnum(crawled_ad.category)
                        except ValueError:
                            ad_category = AdCategoryEnum.OTHER

                    ad = Ad(
                        external_id=crawled_ad.external_id,
                        title=crawled_ad.title,
                        description=crawled_ad.description,
                        platform=platform_enum,
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
                        ad_metadata=crawled_ad.metadata,
                        status=AdStatusEnum.PENDING,
                    )
                    session.add(ad)
                    saved_count += 1

            session.commit()

            # Dispatch media extraction for ads that need it
            from app.tasks.dispatcher import dispatch_task
            ads_with_snapshot = session.query(Ad).filter(
                Ad.media_extraction_status == "pending",
                Ad.snapshot_url.isnot(None),
            ).order_by(Ad.created_at.desc()).limit(saved_count).all()
            for ad_to_extract in ads_with_snapshot:
                try:
                    dispatch_task("extract_media", ad_id=ad_to_extract.id)
                except Exception as e:
                    logger.warning("media_extraction_dispatch_failed", ad_id=ad_to_extract.id, error=str(e))

            # Dispatch thumbnail download for ads that have thumbnail_url but skipped extraction
            ads_needing_thumb = session.query(Ad).filter(
                Ad.media_extraction_status == "skipped",
                Ad.thumbnail_url.isnot(None),
                Ad.thumbnail_s3_key.is_(None),
            ).order_by(Ad.created_at.desc()).limit(saved_count).all()
            for ad_thumb in ads_needing_thumb:
                try:
                    dispatch_task("download_thumbnail", ad_id=ad_thumb.id)
                except Exception as e:
                    logger.warning("thumbnail_dispatch_failed", ad_id=ad_thumb.id, error=str(e))

            # Auto-analyze if requested
            if auto_analyze:
                ads_to_analyze = session.query(Ad).filter(
                    Ad.status == AdStatusEnum.PENDING,
                    Ad.video_url.isnot(None),
                ).order_by(Ad.created_at.desc()).limit(limit_per_platform * len(platforms)).all()

                for ad in ads_to_analyze:
                    dispatch_task("analyze_ad", ad_id=ad.id)
                    ad.status = AdStatusEnum.PROCESSING

                session.commit()

            logger.info("crawl_task_completed", query=query, saved_count=saved_count)

            # Update CrawlJob to COMPLETED
            pses = SyncSessionLocal()
            try:
                from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
                cj = pses.query(CrawlJob).filter(CrawlJob.job_id == job_id).first()
                if cj:
                    cj.status = CrawlJobStatusEnum.COMPLETED
                    cj.completed_platforms = len(platforms)
                    cj.total_ads_found = saved_count
                    cj.current_platform = None
                    pses.commit()
            except Exception:
                pass
            finally:
                pses.close()

            return {"status": "completed", "saved_count": saved_count, "job_id": job_id}

        finally:
            session.close()

    except Exception as e:
        logger.error("crawl_task_failed", query=query, error=str(e))
        # Update CrawlJob to FAILED
        fses = SyncSessionLocal()
        try:
            from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
            cj = fses.query(CrawlJob).filter(CrawlJob.job_id == job_id).first()
            if cj:
                cj.status = CrawlJobStatusEnum.FAILED
                cj.error_message = str(e)[:500]
                fses.commit()
        except Exception:
            pass
        finally:
            fses.close()
        raise self.retry(exc=e)


def get_connected_platforms() -> list[str]:
    """Return list of platform names that have at least one API key configured."""
    from app.core.config import get_settings
    settings = get_settings()

    db_keys: dict[str, dict[str, str]] = {}
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        db_keys = load_api_keys_from_db()
    except Exception:
        pass

    def _has(platform: str, key_name: str, env_fallback: str | None) -> bool:
        val = db_keys.get(platform, {}).get(key_name) or env_fallback
        return bool(val and val.strip())

    connected = []
    # Meta covers both facebook and instagram
    if _has("meta", "access_token", settings.meta_access_token):
        connected.extend(["facebook", "instagram"])
    if _has("youtube", "api_key", settings.youtube_api_key):
        connected.append("youtube")
    if _has("tiktok", "access_token", settings.tiktok_access_token):
        connected.append("tiktok")
    if _has("x_twitter", "bearer_token", settings.x_twitter_bearer_token):
        connected.append("x_twitter")
    if _has("line", "access_token", settings.line_api_access_token):
        connected.append("line")
    if _has("yahoo", "api_key", settings.yahoo_ads_api_key):
        connected.append("yahoo")
    if _has("pinterest", "access_token", settings.pinterest_access_token):
        connected.append("pinterest")
    if _has("smartnews", "api_key", settings.smartnews_ads_api_key):
        connected.append("smartnews")
    if _has("google_ads", "developer_token", settings.google_ads_developer_token):
        connected.append("google_ads")
    if _has("gunosy", "api_key", settings.gunosy_ads_api_key):
        connected.append("gunosy")

    return connected


async def _crawl_platforms(
    query: str,
    platforms: list[str],
    category: str | None,
    limit_per_platform: int,
) -> dict:
    """Run async crawling with API keys from DB (fallback to env vars)."""
    from app.core.config import get_settings
    settings = get_settings()

    # Load UI-configured keys from DB, fall back to env vars
    db_keys: dict[str, dict[str, str]] = {}
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        db_keys = load_api_keys_from_db()
    except Exception:
        logger.warning("db_keys_load_failed_using_env_vars", exc_info=True)

    def _get(platform: str, key_name: str, env_fallback: str | None) -> str | None:
        """Get key from DB first, then from env."""
        return (db_keys.get(platform, {}).get(key_name) or env_fallback) or None

    manager = CrawlerManager.create_default(
        meta_token=_get("meta", "access_token", settings.meta_access_token),
        tiktok_token=_get("tiktok", "access_token", settings.tiktok_access_token),
        youtube_api_key=_get("youtube", "api_key", settings.youtube_api_key),
        x_twitter_bearer=_get("x_twitter", "bearer_token", settings.x_twitter_bearer_token),
        line_token=_get("line", "access_token", settings.line_api_access_token),
        yahoo_api_key=_get("yahoo", "api_key", settings.yahoo_ads_api_key),
        yahoo_api_secret=_get("yahoo", "api_secret", settings.yahoo_ads_api_secret),
        pinterest_token=_get("pinterest", "access_token", settings.pinterest_access_token),
        smartnews_api_key=_get("smartnews", "api_key", settings.smartnews_ads_api_key),
        google_ads_developer_token=_get("google_ads", "developer_token", settings.google_ads_developer_token),
        google_ads_client_id=_get("google_ads", "client_id", settings.google_ads_client_id),
        google_ads_client_secret=_get("google_ads", "client_secret", settings.google_ads_client_secret),
        google_ads_refresh_token=_get("google_ads", "refresh_token", settings.google_ads_refresh_token),
        gunosy_api_key=_get("gunosy", "api_key", settings.gunosy_ads_api_key),
    )
    try:
        results = await manager.search_all_platforms(
            query=query,
            platforms=platforms,
            category=category,
            limit_per_platform=limit_per_platform,
        )
        return results
    finally:
        await manager.close_all()


def _map_platform(platform: str) -> AdPlatformEnum:
    mapping = {
        "facebook": AdPlatformEnum.FACEBOOK,
        "instagram": AdPlatformEnum.INSTAGRAM,
        "youtube": AdPlatformEnum.YOUTUBE,
        "tiktok": AdPlatformEnum.TIKTOK,
        "x_twitter": AdPlatformEnum.X_TWITTER,
        "line": AdPlatformEnum.LINE,
        "yahoo": AdPlatformEnum.YAHOO,
        "pinterest": AdPlatformEnum.PINTEREST,
        "smartnews": AdPlatformEnum.SMARTNEWS,
        "google_ads": AdPlatformEnum.GOOGLE_ADS,
        "gunosy": AdPlatformEnum.GUNOSY,
    }
    return mapping.get(platform, AdPlatformEnum.OTHER)
