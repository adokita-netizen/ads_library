"""Media extraction Celery tasks."""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import time
import uuid

import httpx
import structlog
from bs4 import BeautifulSoup

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, MediaExtractionStatus
from app.tasks.worker import celery_app

logger = structlog.get_logger()


# ── CI-135: Media Pipeline Metrics ────────────────────────────
class MediaPipelineMetrics:
    """In-process metrics collector for media extraction pipeline."""

    def __init__(self):
        self.extraction_count = 0
        self.extraction_success = 0
        self.extraction_failed = 0
        self.extraction_skipped = 0
        self.image_downloads = 0
        self.image_download_failures = 0
        self.video_downloads = 0
        self.video_download_failures = 0
        self.total_extraction_time = 0.0
        self.total_download_time = 0.0
        self._error_types: dict[str, int] = {}

    def record_extraction(self, success: bool, duration: float, error_type: str = ""):
        self.extraction_count += 1
        self.total_extraction_time += duration
        if success:
            self.extraction_success += 1
        else:
            self.extraction_failed += 1
            if error_type:
                self._error_types[error_type] = self._error_types.get(error_type, 0) + 1

    def record_download(self, media_type: str, success: bool, duration: float = 0.0):
        self.total_download_time += duration
        if media_type == "image":
            self.image_downloads += 1
            if not success:
                self.image_download_failures += 1
        elif media_type == "video":
            self.video_downloads += 1
            if not success:
                self.video_download_failures += 1

    def record_skip(self):
        self.extraction_skipped += 1

    @property
    def success_rate(self) -> float:
        total = self.extraction_success + self.extraction_failed
        return self.extraction_success / total if total > 0 else 0.0

    @property
    def avg_extraction_time(self) -> float:
        return self.total_extraction_time / self.extraction_count if self.extraction_count > 0 else 0.0

    def summary(self) -> dict:
        return {
            "extractions": self.extraction_count,
            "success": self.extraction_success,
            "failed": self.extraction_failed,
            "skipped": self.extraction_skipped,
            "success_rate": round(self.success_rate, 3),
            "avg_extraction_time_s": round(self.avg_extraction_time, 2),
            "image_downloads": self.image_downloads,
            "image_failures": self.image_download_failures,
            "video_downloads": self.video_downloads,
            "video_failures": self.video_download_failures,
            "error_types": dict(self._error_types),
        }


# Global metrics instance — reset per worker process
_metrics = MediaPipelineMetrics()


def get_pipeline_metrics() -> dict:
    """Return current pipeline metrics summary."""
    return _metrics.summary()


def _sanitize_url_for_log(url: str) -> str:
    """Strip access_token and other sensitive query params before logging."""
    import re as _re
    return _re.sub(r'access_token=[^&]+', 'access_token=***', url)


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
        # NOTE: Meta's render_ad endpoint requires token in URL query param.
        # This URL may appear in logs — ensure log sanitization is in place.
        return (
            f"https://www.facebook.com/ads/archive/render_ad/"
            f"?id={external_id}&access_token={token}"
        )

    # Fallback: construct library URL
    if not ad.snapshot_url and external_id:
        return f"https://www.facebook.com/ads/library/?id={external_id}"
    return ad.snapshot_url


def extract_video_metadata(video_path: str) -> dict:
    """Extract video metadata using ffprobe.

    Returns dict with duration_seconds, resolution_width/height,
    file_size_bytes, codec, bitrate, fps. Empty dict on failure.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}

        data = json.loads(result.stdout)
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )

        fps = 0.0
        r_frame_rate = video_stream.get("r_frame_rate", "")
        if r_frame_rate and "/" in r_frame_rate:
            num, den = r_frame_rate.split("/", 1)
            try:
                fps = float(num) / float(den) if float(den) != 0 else 0.0
            except (ValueError, ZeroDivisionError):
                fps = 0.0

        return {
            "duration_seconds": float(data.get("format", {}).get("duration", 0)),
            "resolution_width": int(video_stream.get("width", 0)),
            "resolution_height": int(video_stream.get("height", 0)),
            "codec": video_stream.get("codec_name", ""),
            "file_size_bytes": int(data.get("format", {}).get("size", 0)),
            "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
            "fps": fps,
        }
    except FileNotFoundError:
        logger.debug("ffprobe_not_installed")
        return {}
    except Exception as e:
        logger.warning("ffprobe_failed", path=video_path, error=str(e))
        return {}


@celery_app.task(bind=True, max_retries=3, retry_backoff=True, retry_backoff_max=300)
def extract_media_task(self, ad_id: int, use_playwright: bool = True):
    """Extract media from an ad's snapshot_url, download images, and update DB.

    Flow:
    1. Load ad from DB
    2. Extract media URLs from snapshot_url via MediaExtractor
    3. Download first image and upload to S3
    4. Update ad record with results

    Retry: exponential backoff (10s, 20s, 40s... max 300s), 3 retries.
    Each retry gets a fresh DB session.
    """
    _start_time = time.time()
    logger.info("media_extraction_started", ad_id=ad_id,
                task_id=getattr(self.request, 'id', None),
                retry=self.request.retries if hasattr(self.request, 'retries') else 0)

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            logger.error("media_extraction_ad_not_found", ad_id=ad_id)
            return {"status": "error", "message": "Ad not found"}

        if not ad.snapshot_url:
            if not ad.external_id:
                ad.media_extraction_status = MediaExtractionStatus.SKIPPED
                session.commit()
                return {"status": "skipped", "message": "No snapshot_url or external_id"}

        # Build render_ad URL (server-rendered, parseable without JS)
        render_url = _build_render_ad_url(ad)
        if render_url and render_url != ad.snapshot_url:
            ad.snapshot_url = render_url
            session.commit()
            logger.info("snapshot_url_upgraded_to_render_ad", ad_id=ad_id)

        ad.media_extraction_status = MediaExtractionStatus.PENDING
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

                    # Inline quality check
                    try:
                        from PIL import Image
                        import io as _io
                        img = Image.open(_io.BytesIO(image_data))
                        w, h = img.size
                        if w < 200 or h < 200 or len(image_data) < 5000:
                            from sqlalchemy.orm.attributes import flag_modified
                            meta = dict(ad.ad_metadata or {})
                            meta["media_quality_issues"] = [f"low_quality_{w}x{h}_{len(image_data)}B"]
                            ad.ad_metadata = meta
                            flag_modified(ad, "ad_metadata")
                            logger.warning("low_quality_image", ad_id=ad_id, width=w, height=h)
                    except Exception as qe:
                        logger.debug("image_quality_check_skipped", ad_id=ad_id, error=str(qe))
            except Exception as e:
                logger.warning("image_upload_failed", ad_id=ad_id, error=str(e))

        # Download and store video to S3
        if extracted.video_urls and not ad.video_s3_key:
            try:
                video_data = _download_sync(extracted.video_urls[0], timeout=60.0)
                if video_data and len(video_data) < 100 * 1024 * 1024:  # 100MB limit
                    from app.core.storage import get_storage_client
                    storage = get_storage_client()
                    url_hash = hashlib.md5(extracted.video_urls[0].encode()).hexdigest()[:12]
                    video_key = f"videos/{uuid.uuid4()}_{url_hash}.mp4"
                    storage.upload_bytes(video_key, video_data, content_type="video/mp4")
                    ad.video_s3_key = video_key
                    local_path = _save_to_local_cache(video_data, "videos", ad_id)
                    logger.info("video_uploaded_to_storage", ad_id=ad_id, s3_key=video_key,
                                size_mb=round(len(video_data) / 1024 / 1024, 1))

                    # Extract video metadata via ffprobe
                    if local_path and os.path.exists(local_path):
                        video_meta = extract_video_metadata(local_path)
                        if video_meta:
                            if video_meta.get("duration_seconds"):
                                ad.duration_seconds = video_meta["duration_seconds"]
                            if video_meta.get("resolution_width"):
                                ad.resolution_width = video_meta["resolution_width"]
                            if video_meta.get("resolution_height"):
                                ad.resolution_height = video_meta["resolution_height"]
                            if video_meta.get("file_size_bytes"):
                                ad.file_size_bytes = video_meta["file_size_bytes"]
                            from sqlalchemy.orm.attributes import flag_modified
                            meta = dict(ad.ad_metadata or {})
                            meta["video_codec"] = video_meta.get("codec", "")
                            meta["video_bitrate"] = video_meta.get("bitrate", 0)
                            meta["video_fps"] = video_meta.get("fps", 0)
                            ad.ad_metadata = meta
                            flag_modified(ad, "ad_metadata")
                            logger.info("video_metadata_extracted", ad_id=ad_id,
                                        duration=video_meta.get("duration_seconds"))
            except Exception as e:
                logger.warning("video_upload_failed", ad_id=ad_id, error=str(e))

        # CI-042: Optimized thumbnail fallback order
        # Priority: 1) existing thumbnail_url  2) extracted images  3) og:image  4) video poster
        if not ad.thumbnail_url:
            thumb_candidates = []
            if extracted.image_urls:
                thumb_candidates.extend(extracted.image_urls[:3])
            if extracted.thumbnail_url:
                thumb_candidates.insert(0, extracted.thumbnail_url)
            for candidate in thumb_candidates:
                if candidate and candidate.startswith("http"):
                    ad.thumbnail_url = candidate
                    break

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

        ad.media_extraction_status = MediaExtractionStatus.COMPLETED
        session.commit()

        _duration = time.time() - _start_time
        _metrics.record_extraction(True, _duration)
        logger.info("media_extraction_completed", ad_id=ad_id,
                     creative_type=extracted.creative_type,
                     images=len(extracted.image_urls),
                     videos=len(extracted.video_urls),
                     duration_s=round(_duration, 2))

        return {
            "status": "completed",
            "creative_type": extracted.creative_type,
            "image_count": len(extracted.image_urls),
            "video_count": len(extracted.video_urls),
            "duration_s": round(_duration, 2),
        }

    except Exception as e:
        _duration = time.time() - _start_time
        _metrics.record_extraction(False, _duration, error_type=type(e).__name__)
        logger.error("media_extraction_failed", ad_id=ad_id, error=str(e),
                     retry=self.request.retries if hasattr(self.request, 'retries') else 0,
                     duration_s=round(_duration, 2))

        # CI-058: Classify error for smarter retry decisions
        err_str = str(e).lower()
        is_permanent = any(k in err_str for k in ("404", "not found", "401", "403", "gone"))
        is_transient = any(k in err_str for k in ("timeout", "429", "502", "503", "connection"))

        # Mark as failed/retrying with a clean session state
        try:
            session.rollback()
            ad = session.query(Ad).filter(Ad.id == ad_id).first()
            if ad:
                retries = getattr(self.request, 'retries', 0)
                max_retries = self.max_retries or 3
                if is_permanent or retries >= max_retries:
                    ad.media_extraction_status = MediaExtractionStatus.FAILED
                    from sqlalchemy.orm.attributes import flag_modified
                    meta = dict(ad.ad_metadata or {})
                    meta["extraction_failure_type"] = "permanent" if is_permanent else "max_retries"
                    meta["extraction_error"] = str(e)[:200]
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")
                else:
                    ad.media_extraction_status = MediaExtractionStatus.RETRYING
                session.commit()
        except Exception:
            session.rollback()
        # Close session before retry to ensure fresh state
        session.close()
        # CI-058: Skip retry for permanent errors
        if is_permanent:
            logger.info("media_extraction_permanent_failure", ad_id=ad_id, error_type=type(e).__name__)
            return {"status": "failed", "permanent": True, "error": str(e)[:200]}
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
            ad.media_extraction_status = MediaExtractionStatus.PENDING_HEAVY
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
            logger.warning("enrich_http_fetch_failed", ad_id=ad_id, url=_sanitize_url_for_log(url), error=str(e))
            ad.media_extraction_status = MediaExtractionStatus.PENDING_HEAVY
            session.commit()
            _escalate_to_extract_media(ad_id)
            return {"status": "escalated", "reason": "http_failed"}

        # Check if we got anything useful
        if not image_url and not ad_text:
            logger.info("enrich_no_data_escalating", ad_id=ad_id)
            ad.media_extraction_status = MediaExtractionStatus.PENDING_HEAVY
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

        ad.media_extraction_status = MediaExtractionStatus.ENRICHED
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
                ad.media_extraction_status = MediaExtractionStatus.PENDING_HEAVY
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
        logger.warning("download_failed", url=_sanitize_url_for_log(url), error=str(e))
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
