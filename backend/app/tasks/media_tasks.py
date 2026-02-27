"""Media extraction Celery tasks."""

import asyncio
import hashlib
import uuid

import httpx
import structlog

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.tasks.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def extract_media_task(self, ad_id: int, use_playwright: bool = True):
    """Extract media from an ad's snapshot_url, download images, and update DB.

    Flow:
    1. Load ad from DB
    2. Extract media URLs from snapshot_url via MediaExtractor
    3. Download first image and upload to S3
    4. Update ad record with results
    """
    logger.info("media_extraction_started", ad_id=ad_id, task_id=self.request.id)

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            logger.error("media_extraction_ad_not_found", ad_id=ad_id)
            return {"status": "error", "message": "Ad not found"}

        if not ad.snapshot_url:
            # Try to construct snapshot_url from external_id (Facebook Ad Library)
            if ad.external_id:
                ad.snapshot_url = f"https://www.facebook.com/ads/library/?id={ad.external_id}"
                session.commit()
                logger.info("snapshot_url_constructed", ad_id=ad_id, external_id=ad.external_id)
            else:
                ad.media_extraction_status = "skipped"
                session.commit()
                return {"status": "skipped", "message": "No snapshot_url or external_id"}

        ad.media_extraction_status = "pending"
        session.commit()

        # Run async extraction in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            from app.services.media_extraction import MediaExtractor
            extractor = MediaExtractor()
            extracted = loop.run_until_complete(
                extractor.extract(ad.snapshot_url, use_playwright=use_playwright)
            )
        finally:
            loop.close()

        # Update ad with extracted data
        ad.creative_type = extracted.creative_type

        if extracted.image_urls:
            ad.image_url = extracted.image_urls[0]

        if extracted.video_urls and not ad.video_url:
            ad.video_url = extracted.video_urls[0]

        # Try to download and store the primary image
        if extracted.image_urls:
            try:
                image_data = _download_sync(extracted.image_urls[0])
                if image_data:
                    from app.core.storage import get_storage_client
                    storage = get_storage_client()
                    url_hash = hashlib.md5(extracted.image_urls[0].encode()).hexdigest()[:12]
                    s3_key = f"images/{uuid.uuid4()}_{url_hash}.jpg"
                    storage.upload_bytes(s3_key, image_data, content_type="image/jpeg")
                    ad.image_s3_key = s3_key
                    logger.info("image_uploaded_to_storage", ad_id=ad_id, s3_key=s3_key)
            except Exception as e:
                logger.warning("image_upload_failed", ad_id=ad_id, error=str(e))

        # Auto-set thumbnail_url from extracted images when missing
        if not ad.thumbnail_url and extracted.image_urls:
            ad.thumbnail_url = extracted.image_urls[0]

        # Reuse image_s3_key as thumbnail if no dedicated thumbnail exists
        if not ad.thumbnail_s3_key and ad.image_s3_key:
            ad.thumbnail_s3_key = ad.image_s3_key

        # Store carousel image URLs if multiple
        if len(extracted.image_urls) > 1:
            ad.image_s3_keys = {"urls": extracted.image_urls}

        # Download and store thumbnail
        if ad.thumbnail_url and not ad.thumbnail_s3_key:
            try:
                thumb_data = _download_sync(ad.thumbnail_url)
                if thumb_data:
                    from app.core.storage import get_storage_client
                    storage = get_storage_client()
                    thumb_hash = hashlib.md5(ad.thumbnail_url.encode()).hexdigest()[:12]
                    thumb_key = f"thumbnails/{uuid.uuid4()}_{thumb_hash}.jpg"
                    storage.upload_bytes(thumb_key, thumb_data, content_type="image/jpeg")
                    ad.thumbnail_s3_key = thumb_key
                    logger.info("thumbnail_uploaded_to_storage", ad_id=ad_id, s3_key=thumb_key)
            except Exception as e:
                logger.warning("thumbnail_upload_failed", ad_id=ad_id, error=str(e))

        ad.media_extraction_status = "completed"
        session.commit()

        logger.info("media_extraction_completed", ad_id=ad_id,
                     creative_type=extracted.creative_type,
                     images=len(extracted.image_urls),
                     videos=len(extracted.video_urls))

        return {
            "status": "completed",
            "creative_type": extracted.creative_type,
            "image_count": len(extracted.image_urls),
            "video_count": len(extracted.video_urls),
        }

    except Exception as e:
        logger.error("media_extraction_failed", ad_id=ad_id, error=str(e))
        try:
            ad = session.query(Ad).filter(Ad.id == ad_id).first()
            if ad:
                ad.media_extraction_status = "failed"
                session.commit()
        except Exception:
            session.rollback()
        raise self.retry(exc=e)
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def download_thumbnail_task(self, ad_id: int):
    """Download thumbnail from thumbnail_url and upload to S3.

    Lightweight task for ads that already have direct media URLs
    (skipped full media extraction) but need thumbnail stored in S3.
    """
    logger.info("thumbnail_download_started", ad_id=ad_id)

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return {"status": "error", "message": "Ad not found"}

        if not ad.thumbnail_url or ad.thumbnail_s3_key:
            return {"status": "skipped", "message": "No thumbnail_url or already stored"}

        thumb_data = _download_sync(ad.thumbnail_url)
        if thumb_data:
            from app.core.storage import get_storage_client
            storage = get_storage_client()
            thumb_hash = hashlib.md5(ad.thumbnail_url.encode()).hexdigest()[:12]
            thumb_key = f"thumbnails/{uuid.uuid4()}_{thumb_hash}.jpg"
            storage.upload_bytes(thumb_key, thumb_data, content_type="image/jpeg")
            ad.thumbnail_s3_key = thumb_key
            session.commit()
            logger.info("thumbnail_downloaded", ad_id=ad_id, s3_key=thumb_key)
            return {"status": "completed", "s3_key": thumb_key}
        else:
            logger.warning("thumbnail_download_empty", ad_id=ad_id, url=ad.thumbnail_url)
            return {"status": "failed", "message": "Download returned no data"}

    except Exception as e:
        logger.error("thumbnail_download_failed", ad_id=ad_id, error=str(e))
        session.rollback()
        raise self.retry(exc=e)
    finally:
        session.close()


def _download_sync(url: str, timeout: float = 15.0) -> bytes | None:
    """Download a URL synchronously."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content
    except Exception as e:
        logger.warning("download_failed", url=url, error=str(e))
        return None
