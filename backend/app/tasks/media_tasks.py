"""Media extraction Celery tasks."""

import asyncio
import hashlib
import re
import uuid

import httpx
import structlog
from bs4 import BeautifulSoup

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.tasks.worker import celery_app

logger = structlog.get_logger()


def _build_render_ad_url(ad: "Ad") -> str | None:
    """Build a server-rendered render_ad URL for a Meta ad.

    Prefers the render_ad endpoint (returns static HTML parseable without JS)
    over the SPA library URL (/ads/library/?id=...).
    """
    external_id = ad.external_id
    if not external_id:
        return ad.snapshot_url

    # If snapshot_url already points to render_ad, use as-is
    if ad.snapshot_url and "/ads/archive/render_ad/" in ad.snapshot_url:
        return ad.snapshot_url

    # Try to get access_token from config
    try:
        from app.core.config import get_settings
        settings = get_settings()
        token = settings.meta_access_token
    except Exception:
        token = None

    # Also check DB-stored keys
    if not token:
        try:
            from app.api.endpoints.settings import load_api_keys_from_db
            db_keys = load_api_keys_from_db()
            token = db_keys.get("meta", {}).get("access_token")
        except Exception:
            pass

    if token and external_id:
        return (
            f"https://www.facebook.com/ads/archive/render_ad/"
            f"?id={external_id}&access_token={token}"
        )

    # Fallback: construct library URL
    if not ad.snapshot_url and external_id:
        return f"https://www.facebook.com/ads/library/?id={external_id}"
    return ad.snapshot_url


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
            if not ad.external_id:
                ad.media_extraction_status = "skipped"
                session.commit()
                return {"status": "skipped", "message": "No snapshot_url or external_id"}

        # Build render_ad URL (server-rendered, parseable without JS)
        render_url = _build_render_ad_url(ad)
        if render_url and render_url != ad.snapshot_url:
            ad.snapshot_url = render_url
            session.commit()
            logger.info("snapshot_url_upgraded_to_render_ad", ad_id=ad_id)

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

        # Update text fields if currently missing
        if extracted.ad_text and not ad.description:
            ad.description = extracted.ad_text
        if extracted.ad_title and not ad.title:
            ad.title = extracted.ad_title

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
                    _save_to_local_cache(image_data, "images", ad_id)
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
                    _save_to_local_cache(thumb_data, "thumbnails", ad_id)
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
            _save_to_local_cache(thumb_data, "thumbnails", ad_id)
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


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def enrich_ad_creative_task(self, ad_id: int):
    """Lightweight enrichment: HTTP GET snapshot_url → BS4 parse → extract image + text.

    LIGHT_TASK — runs on Lambda (no Playwright).
    On failure, escalates to extract_media (HEAVY_TASK → ECS + Playwright).

    Flow:
    1. Build render_ad URL from ad's external_id + access_token
    2. HTTP GET → parse OG tags for image, text, title
    3. Download primary image → upload to S3
    4. Update ad record
    5. On failure → set status to "pending_heavy" for extract_media escalation
    """
    logger.info("enrich_ad_creative_started", ad_id=ad_id, task_id=self.request.id)

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            logger.error("enrich_ad_not_found", ad_id=ad_id)
            return {"status": "error", "message": "Ad not found"}

        # Build the best URL for fetching
        url = _build_render_ad_url(ad)
        if not url:
            ad.media_extraction_status = "pending_heavy"
            session.commit()
            _escalate_to_extract_media(ad_id)
            return {"status": "escalated", "reason": "no_url"}

        # HTTP GET + BS4 parse (no Playwright)
        image_url = None
        thumbnail_url = None
        ad_text = None
        ad_title = None

        try:
            with httpx.Client(
                timeout=20.0,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    )
                },
            ) as client:
                response = client.get(url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract image from og:image
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                image_url = og_image["content"]
                thumbnail_url = image_url

            # Extract text from og:description
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                text = og_desc["content"].strip()
                if text and len(text) > 5:
                    ad_text = text

            # Extract title from og:title
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
                if title:
                    ad_title = title

            # Fallback: visible body text
            if not ad_text:
                body = soup.find("body")
                if body:
                    for tag in body.find_all(["script", "style", "nav", "header", "footer", "noscript"]):
                        tag.decompose()
                    visible = body.get_text(separator="\n", strip=True)
                    if visible and len(visible) > 20:
                        ad_text = visible[:2000]

            # Fallback: look for <img> tags if no og:image
            if not image_url:
                for img in soup.find_all("img"):
                    src = img.get("src") or img.get("data-src")
                    if not src or not src.startswith("http"):
                        continue
                    if any(skip in src.lower() for skip in [
                        "pixel", "tracking", "beacon", "1x1", "spacer",
                        "favicon", "logo", ".svg", "emoji",
                    ]):
                        continue
                    image_url = src
                    thumbnail_url = src
                    break

        except Exception as e:
            logger.warning("enrich_http_fetch_failed", ad_id=ad_id, url=url, error=str(e))
            ad.media_extraction_status = "pending_heavy"
            session.commit()
            _escalate_to_extract_media(ad_id)
            return {"status": "escalated", "reason": "http_failed"}

        # Check if we got anything useful
        if not image_url and not ad_text:
            logger.info("enrich_no_data_escalating", ad_id=ad_id)
            ad.media_extraction_status = "pending_heavy"
            session.commit()
            _escalate_to_extract_media(ad_id)
            return {"status": "escalated", "reason": "no_data"}

        # Update ad fields
        if image_url and not ad.image_url:
            ad.image_url = image_url
        if thumbnail_url and not ad.thumbnail_url:
            ad.thumbnail_url = thumbnail_url
        if ad_text and not ad.description:
            ad.description = ad_text
        if ad_title and not ad.title:
            ad.title = ad_title

        # Download and upload primary image to S3
        if image_url:
            try:
                image_data = _download_sync(image_url)
                if image_data:
                    from app.core.storage import get_storage_client
                    storage = get_storage_client()
                    url_hash = hashlib.md5(image_url.encode()).hexdigest()[:12]
                    s3_key = f"images/{uuid.uuid4()}_{url_hash}.jpg"
                    storage.upload_bytes(s3_key, image_data, content_type="image/jpeg")
                    ad.image_s3_key = s3_key
                    _save_to_local_cache(image_data, "images", ad_id)
                    if not ad.thumbnail_s3_key:
                        ad.thumbnail_s3_key = s3_key
                        _save_to_local_cache(image_data, "thumbnails", ad_id)
                    logger.info("enrich_image_uploaded", ad_id=ad_id, s3_key=s3_key)
            except Exception as e:
                logger.warning("enrich_image_upload_failed", ad_id=ad_id, error=str(e))

        ad.media_extraction_status = "enriched"
        session.commit()

        logger.info(
            "enrich_ad_creative_completed",
            ad_id=ad_id,
            has_image=bool(image_url),
            has_text=bool(ad_text),
            has_title=bool(ad_title),
        )
        return {
            "status": "enriched",
            "has_image": bool(image_url),
            "has_text": bool(ad_text),
            "has_title": bool(ad_title),
        }

    except Exception as e:
        logger.error("enrich_ad_creative_failed", ad_id=ad_id, error=str(e))
        try:
            ad = session.query(Ad).filter(Ad.id == ad_id).first()
            if ad:
                ad.media_extraction_status = "pending_heavy"
                session.commit()
        except Exception:
            session.rollback()
        _escalate_to_extract_media(ad_id)
        return {"status": "escalated", "reason": "exception"}
    finally:
        session.close()


def _escalate_to_extract_media(ad_id: int):
    """Escalate to heavy extract_media task (ECS + Playwright)."""
    try:
        from app.tasks.dispatcher import dispatch_task
        dispatch_task("extract_media", ad_id=ad_id)
        logger.info("enrich_escalated_to_extract_media", ad_id=ad_id)
    except Exception as e:
        logger.warning("enrich_escalation_failed", ad_id=ad_id, error=str(e))


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


def _save_to_local_cache(data: bytes, media_type: str, ad_id: int) -> str | None:
    """Save media data to local media_cache/ directory alongside S3 upload.

    Args:
        data: Raw file bytes.
        media_type: 'thumbnails', 'images', or 'videos'.
        ad_id: The ad ID (used as filename).

    Returns:
        Local file path if saved, None on error.
    """
    import os

    ext_map = {"thumbnails": ".jpg", "images": ".jpg", "videos": ".mp4"}
    ext = ext_map.get(media_type, ".bin")

    cache_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "media_cache", media_type)
    )
    try:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, f"{ad_id}{ext}")
        with open(path, "wb") as f:
            f.write(data)
        logger.info("saved_to_local_cache", media_type=media_type, ad_id=ad_id, path=path)
        return path
    except Exception as e:
        logger.warning("local_cache_save_failed", media_type=media_type, ad_id=ad_id, error=str(e))
        return None
