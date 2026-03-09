"""Media extraction Celery tasks."""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from bs4 import BeautifulSoup
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, MediaExtractionStatus, normalize_creative_fetch_reason
from app.tasks.worker import celery_app

logger = structlog.get_logger()

MEDIA_FETCH_REASON_FALLBACK = "unknown_schema"
_META_DISCLAIMER_TEXTS = {
    "This ad ran without a required disclaimer.",
    "This ad was run by an account or Page we later disabled for not following our Advertising Standards.",
    "This content was removed because it didn't follow our Advertising Standards.",
    "この広告は必要な免責事項なしで配信されました。",
}


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


def _compute_media_completeness_score(ad: "Ad") -> int:
    score = 0
    if ad.video_url or ad.video_s3_key or ad.s3_key:
        score += 35
    if ad.image_url or ad.image_s3_key:
        score += 30
    if ad.thumbnail_url or ad.thumbnail_s3_key:
        score += 20
    if ad.snapshot_url:
        score += 10
    if ad.destination_url:
        score += 5
    return min(score, 100)


def _is_viewable(ad: "Ad") -> bool:
    return bool(ad.thumbnail_url or ad.image_url or ad.video_url or ad.snapshot_url)


def _media_access_tier(ad: "Ad") -> str:
    if _is_downloadable(ad):
        return "downloadable_with_lp" if ad.destination_url else "downloadable"
    if ad.thumbnail_url or ad.image_url or ad.video_url:
        return "viewable_only"
    if ad.snapshot_url:
        return "snapshot_only"
    return "missing"


def _normalize_media_reason(reason: str | None) -> str | None:
    normalized = normalize_creative_fetch_reason(reason)
    return normalized or MEDIA_FETCH_REASON_FALLBACK


def _classify_download_error(message: str | None) -> str:
    text = str(message or "").lower()
    if any(token in text for token in ("403", "forbidden", "expired", "signature", "access denied")):
        return "blocked_or_expired"
    if any(token in text for token in ("404", "not found")):
        return "not_found_in_api"
    if any(token in text for token in ("format", "mime", "content-type", "decode")):
        return "format_mismatch"
    if any(token in text for token in ("timeout", "timed out", "429", "502", "503", "connection")):
        return "download_failed"
    return "download_failed"


def _is_downloadable(ad: "Ad") -> bool:
    return bool(
        ad.video_s3_key or ad.s3_key or ad.image_s3_key or ad.thumbnail_s3_key
    )


def _record_media_recovery_state(
    ad: "Ad",
    *,
    status: str,
    reason: str | None = None,
    source: str | None = None,
    extractor_version: str | None = None,
) -> None:
    meta = dict(ad.ad_metadata or {})
    event_at = datetime.now(timezone.utc).isoformat()
    meta["last_recovery_attempt_at"] = event_at
    completeness_score = _compute_media_completeness_score(ad)
    meta["media_completeness_score"] = completeness_score
    meta["extract_quality_score"] = completeness_score
    meta["extract_quality_score_source"] = "creative_extraction"
    meta["extract_quality_score_measured_at"] = event_at
    meta["downloadable"] = _is_downloadable(ad)
    meta["viewable"] = _is_viewable(ad)
    meta["has_lp"] = bool(ad.destination_url)
    meta["media_access_tier"] = _media_access_tier(ad)
    meta["media_extraction_status"] = ad.media_extraction_status
    if source:
        meta["creative_fetch_source"] = source
        meta["last_recovery_source"] = source
    if extractor_version:
        meta["extractor_version"] = extractor_version
        history = meta.get("extractor_version_history")
        history_items = history if isinstance(history, list) else []
        history_entry = {
            "version": extractor_version,
            "status": status,
            "source": source or "",
            "recorded_at": event_at,
        }
        if not history_items or history_items[-1] != history_entry:
            history_items = [*history_items[-9:], history_entry]
        meta["extractor_version_history"] = history_items
    meta["creative_fetch_status"] = status
    if reason:
        meta["creative_fetch_reason"] = _normalize_media_reason(reason)
    elif status == "success":
        meta["creative_fetch_reason"] = None
        meta["last_meta_retry_error"] = None
    if source:
        meta["extract_source"] = source
        meta["extraction_method"] = source
    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")


def _build_meta_library_url(ad: "Ad") -> str | None:
    """Build a URL for extracting media from a Meta ad.

    NOTE:
    - `render_ad` is a Meta endpoint name, not Render.com.
    - Infrastructure is AWS-only; this function always targets Meta public URLs.
    - Prefer public Ads Library page (no token needed, stable on AWS/ECS egress).
    """
    external_id = ad.external_id
    if not external_id:
        return ad.snapshot_url

    # Use public Ads Library page (works without token, needs Playwright for JS)
    return f"https://www.facebook.com/ads/library/?id={external_id}"


# Backward-compatible alias (old name remained in logs/docs)
def _build_render_ad_url(ad: "Ad") -> str | None:
    return _build_meta_library_url(ad)


def _metadata_image_fallback(ad: "Ad") -> str | None:
    meta = dict(ad.ad_metadata or {})
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    lp_data = meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}
    lp_analysis = meta.get("lp_analysis") if isinstance(meta.get("lp_analysis"), dict) else {}

    candidates = (
        lp_info.get("og_image"),
        lp_data.get("og_image"),
        lp_data.get("og_image_url"),
        lp_analysis.get("og_image"),
        lp_analysis.get("og_image_url"),
        meta.get("lp_og_image"),
        meta.get("og_image"),
        meta.get("og_image_url"),
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return None


def _metadata_destination_fallback(ad: "Ad") -> str | None:
    meta = dict(ad.ad_metadata or {})
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    lp_data = meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}
    lp_analysis = meta.get("lp_analysis") if isinstance(meta.get("lp_analysis"), dict) else {}

    candidates = (
        lp_info.get("final_url"),
        lp_data.get("final_url"),
        lp_analysis.get("final_url"),
        meta.get("lp_final_url"),
        meta.get("final_url"),
        meta.get("destination_url"),
    )
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value.startswith(("http://", "https://")) and "facebook.com" not in value and "instagram.com" not in value:
            return value
    return None


def _is_placeholder_text(value: str | None) -> bool:
    raw = str(value or "").strip()
    return raw in _META_DISCLAIMER_TEXTS


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
        download_failures: list[str] = []
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
        if extracted.creative_type and extracted.creative_type != "unknown":
            ad.creative_type = extracted.creative_type

        if not extracted.image_urls:
            metadata_image = _metadata_image_fallback(ad)
            if metadata_image:
                extracted.image_urls = [metadata_image]
                if not extracted.thumbnail_url:
                    extracted.thumbnail_url = metadata_image
                if extracted.creative_type == "unknown":
                    extracted.creative_type = "image"

        if not getattr(extracted, "destination_url", None):
            extracted.destination_url = _metadata_destination_fallback(ad)

        if extracted.image_urls:
            ad.image_url = extracted.image_urls[0]

        if extracted.video_urls and not ad.video_url:
            ad.video_url = extracted.video_urls[0]

        # Update text fields if currently missing
        if extracted.ad_text and not ad.description and not _is_placeholder_text(extracted.ad_text):
            ad.description = extracted.ad_text
        if extracted.ad_title and not ad.title and not _is_placeholder_text(extracted.ad_title):
            ad.title = extracted.ad_title
        if getattr(extracted, "destination_url", None) and not ad.destination_url:
            ad.destination_url = extracted.destination_url

        # Fallback: if extraction found nothing but ad has thumbnail_url from API, use it
        if not extracted.image_urls and not extracted.video_urls and ad.thumbnail_url:
            # Try multiple URL variants (larger size first, original as fallback)
            url_variants = _fbcdn_url_variants(ad.thumbnail_url)
            logger.info("media_extraction_fallback_to_thumbnail", ad_id=ad_id,
                        variants=len(url_variants))
            for variant_url in url_variants:
                try:
                    thumb_data = _download_sync(variant_url)
                    if thumb_data and len(thumb_data) > 200:
                        from app.core.storage import get_storage_client
                        storage = get_storage_client()
                        url_hash = hashlib.md5(ad.thumbnail_url.encode()).hexdigest()[:12]
                        s3_key = f"images/{uuid.uuid4()}_{url_hash}.jpg"
                        storage.upload_bytes(s3_key, thumb_data, content_type="image/jpeg")
                        ad.image_s3_key = s3_key
                        ad.thumbnail_s3_key = s3_key
                        ad.image_url = variant_url
                        ad.creative_type = "image"
                        extracted.creative_type = "image"
                        extracted.image_urls = [variant_url]
                        _save_to_local_cache(thumb_data, "images", ad_id)
                        logger.info("media_fallback_thumbnail_uploaded", ad_id=ad_id, s3_key=s3_key,
                                    size_bytes=len(thumb_data), variant=variant_url[:60])
                        break  # Success, stop trying variants
                except Exception as e:
                    download_failures.append(_classify_download_error(e))
                    logger.warning("media_fallback_variant_failed", ad_id=ad_id,
                                   variant=_sanitize_url_for_log(variant_url)[:60], error=str(e))

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
                download_failures.append(_classify_download_error(e))
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
                    ad.s3_key = video_key
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
                            meta = dict(ad.ad_metadata or {})
                            meta["video_codec"] = video_meta.get("codec", "")
                            meta["video_bitrate"] = video_meta.get("bitrate", 0)
                            meta["video_fps"] = video_meta.get("fps", 0)
                            ad.ad_metadata = meta
                            flag_modified(ad, "ad_metadata")
                            logger.info("video_metadata_extracted", ad_id=ad_id,
                                        duration=video_meta.get("duration_seconds"))
            except Exception as e:
                download_failures.append(_classify_download_error(e))
                logger.warning("video_upload_failed", ad_id=ad_id, error=str(e))

        # CI-042: Optimized thumbnail fallback order
        # Priority: 1) existing thumbnail_url  2) extracted images  3) og:image  4) video poster
        if not ad.thumbnail_url:
            thumb_candidates = []
            if extracted.image_urls:
                thumb_candidates.extend(extracted.image_urls[:3])
            if extracted.thumbnail_url:
                thumb_candidates.insert(0, extracted.thumbnail_url)
            metadata_image = _metadata_image_fallback(ad)
            if metadata_image:
                thumb_candidates.append(metadata_image)
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
                download_failures.append(_classify_download_error(e))
                logger.warning("thumbnail_upload_failed", ad_id=ad_id, error=str(e))

        downloadable = _is_downloadable(ad)
        has_any_media = bool(ad.thumbnail_url or ad.image_url or ad.video_url)
        failure_reason = download_failures[0] if download_failures else None
        if downloadable:
            ad.media_extraction_status = MediaExtractionStatus.COMPLETED
            _record_media_recovery_state(
                ad,
                status="success",
                source=getattr(extracted, "extraction_method", "") or ("playwright" if use_playwright else "http_bs4"),
                extractor_version=getattr(extracted, "extractor_version", ""),
            )
        elif has_any_media:
            ad.media_extraction_status = MediaExtractionStatus.ENRICHED
            _record_media_recovery_state(
                ad,
                status="partial",
                reason=failure_reason or "download_failed",
                source=getattr(extracted, "extraction_method", "") or ("playwright" if use_playwright else "http_bs4"),
                extractor_version=getattr(extracted, "extractor_version", ""),
            )
        else:
            failure_reason = (
                getattr(extracted, "restriction_reason", None)
                or failure_reason
                or ("media_url_missing" if ad.snapshot_url else "download_failed")
            )
            ad.media_extraction_status = (
                MediaExtractionStatus.FAILED
                if getattr(extracted, "restriction_reason", None) == "login_required"
                else (MediaExtractionStatus.PENDING_HEAVY if ad.snapshot_url else MediaExtractionStatus.FAILED)
            )
            _record_media_recovery_state(
                ad,
                status="failed",
                reason=failure_reason,
                source=getattr(extracted, "extraction_method", "") or ("playwright" if use_playwright else "http_bs4"),
                extractor_version=getattr(extracted, "extractor_version", ""),
            )
        session.commit()

        _duration = time.time() - _start_time
        _metrics.record_extraction(True, _duration)
        logger.info("media_extraction_completed", ad_id=ad_id,
                     creative_type=extracted.creative_type,
                     images=len(extracted.image_urls),
                     videos=len(extracted.video_urls),
                     duration_s=round(_duration, 2))

        return {
            "status": "completed" if downloadable else ("enriched" if has_any_media else "failed"),
            "creative_type": extracted.creative_type,
            "image_count": len(extracted.image_urls),
            "video_count": len(extracted.video_urls),
            "duration_s": round(_duration, 2),
            "downloadable": downloadable,
            "reason": (
                None
                if downloadable
                else (
                    getattr(extracted, "restriction_reason", None)
                    or
                    failure_reason
                    or ("media_url_missing" if ad.snapshot_url else "download_failed")
                )
            ),
            "extraction_method": getattr(extracted, "extraction_method", "") or ("playwright" if use_playwright else "http_bs4"),
            "restriction_reason": getattr(extracted, "restriction_reason", None),
            "debug_title": getattr(extracted, "debug_title", None),
            "debug_excerpt": getattr(extracted, "debug_excerpt", None),
            "debug_dialog_count": int(getattr(extracted, "debug_dialog_count", 0) or 0),
            "debug_stage": getattr(extracted, "debug_stage", None),
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
                    meta = dict(ad.ad_metadata or {})
                    meta["extraction_failure_type"] = "permanent" if is_permanent else "max_retries"
                    meta["extraction_error"] = str(e)[:200]
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")
                    _record_media_recovery_state(
                        ad,
                        status="failed",
                        reason=_classify_download_error(str(e)) if is_transient or is_permanent else "media_url_missing",
                        source="extract_media_task",
                        extractor_version=str((ad.ad_metadata or {}).get("extractor_version") or ""),
                    )
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
            if not ad.image_s3_key and ad.image_url == ad.thumbnail_url:
                ad.image_s3_key = thumb_key
            ad.media_extraction_status = MediaExtractionStatus.COMPLETED if _is_downloadable(ad) else MediaExtractionStatus.ENRICHED
            _record_media_recovery_state(ad, status="success" if _is_downloadable(ad) else "partial", source="download_thumbnail_task")
            session.commit()
            logger.info("thumbnail_downloaded", ad_id=ad_id, s3_key=thumb_key)
            return {"status": "completed", "s3_key": thumb_key, "downloadable": _is_downloadable(ad)}
        else:
            logger.warning("thumbnail_download_empty", ad_id=ad_id, url=ad.thumbnail_url)
            _record_media_recovery_state(ad, status="failed", reason="download_failed", source="download_thumbnail_task")
            session.commit()
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

        ad.media_extraction_status = (
            MediaExtractionStatus.COMPLETED
            if _is_downloadable(ad)
            else MediaExtractionStatus.ENRICHED
        )
        _record_media_recovery_state(
            ad,
            status="success" if _is_downloadable(ad) else "partial",
            reason=None if _is_downloadable(ad) else "download_failed",
            source="enrich_ad_creative_task",
        )
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
                _record_media_recovery_state(ad, status="failed", reason="download_failed", source="enrich_ad_creative_task")
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


def _upgrade_fbcdn_thumbnail(url: str) -> str:
    """Try to get a larger image from fbcdn thumbnail URL.

    Facebook CDN URLs contain 'stp=dst-jpg_s60x60' size params.
    Returns a list of URLs to try: [larger_size, original].
    Stripping size entirely returns 403 from AWS IPs, so we request
    a larger explicit size instead.
    """
    if not url or "fbcdn" not in url:
        return url
    # Request 600x600 instead of stripping size (stripping causes 403 from AWS)
    upgraded = re.sub(r'(stp=dst-jpg)_s\d+x\d+', r'\1_s600x600', url)
    # Also remove _tt6 suffix which may cause issues
    upgraded = re.sub(r'_tt\d+', '', upgraded)
    return upgraded


def _fbcdn_url_variants(url: str) -> list[str]:
    """Return fbcdn URL variants to try, from best to worst quality."""
    if not url:
        return []
    variants = []
    upgraded = _upgrade_fbcdn_thumbnail(url)
    if upgraded != url:
        variants.append(upgraded)
    # Always include original URL as last resort (60x60 but works reliably)
    variants.append(url)
    return variants


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
