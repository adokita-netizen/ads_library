"""Ad crawling Celery tasks."""

import asyncio

import structlog

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.services.crawling.crawler_manager import CrawlerManager
from app.tasks.worker import celery_app

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

                    ad = Ad(
                        external_id=crawled_ad.external_id,
                        title=crawled_ad.title,
                        description=crawled_ad.description,
                        platform=platform_enum,
                        video_url=crawled_ad.video_url,
                        advertiser_name=crawled_ad.advertiser_name,
                        advertiser_url=crawled_ad.advertiser_url,
                        brand_name=crawled_ad.brand_name,
                        duration_seconds=crawled_ad.duration_seconds,
                        view_count=crawled_ad.view_count,
                        like_count=crawled_ad.like_count,
                        first_seen_at=crawled_ad.first_seen_at,
                        last_seen_at=crawled_ad.last_seen_at,
                        tags=crawled_ad.tags,
                        ad_metadata=crawled_ad.metadata,
                        status=AdStatusEnum.PENDING,
                    )
                    session.add(ad)
                    saved_count += 1

            session.commit()

            # Auto-analyze if requested
            if auto_analyze:
                ads_to_analyze = session.query(Ad).filter(
                    Ad.status == AdStatusEnum.PENDING,
                    Ad.video_url.isnot(None),
                ).order_by(Ad.created_at.desc()).limit(limit_per_platform * len(platforms)).all()

                from app.tasks.analysis_tasks import analyze_ad_task
                for ad in ads_to_analyze:
                    analyze_ad_task.delay(ad.id)
                    ad.status = AdStatusEnum.PROCESSING

                session.commit()

            logger.info("crawl_task_completed", query=query, saved_count=saved_count)
            return {"status": "completed", "saved_count": saved_count}

        finally:
            session.close()

    except Exception as e:
        logger.error("crawl_task_failed", query=query, error=str(e))
        raise self.retry(exc=e)


async def _crawl_platforms(
    query: str,
    platforms: list[str],
    category: str | None,
    limit_per_platform: int,
) -> dict:
    """Run async crawling with all platform tokens from config."""
    from app.core.config import get_settings
    settings = get_settings()

    manager = CrawlerManager.create_default(
        meta_token=settings.meta_access_token,
        tiktok_token=settings.tiktok_access_token,
        youtube_api_key=settings.youtube_api_key,
        x_twitter_bearer=settings.x_twitter_bearer_token,
        line_token=settings.line_api_access_token,
        yahoo_api_key=settings.yahoo_ads_api_key,
        yahoo_api_secret=settings.yahoo_ads_api_secret,
        pinterest_token=settings.pinterest_access_token,
        smartnews_api_key=settings.smartnews_ads_api_key,
        google_ads_developer_token=settings.google_ads_developer_token,
        google_ads_client_id=settings.google_ads_client_id,
        google_ads_client_secret=settings.google_ads_client_secret,
        google_ads_refresh_token=settings.google_ads_refresh_token,
        gunosy_api_key=settings.gunosy_ads_api_key,
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
