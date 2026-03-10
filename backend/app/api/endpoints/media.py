"""Media file serving endpoints.

Serves locally cached thumbnail, image, and video files for ads.
This bypasses expired Facebook CDN URLs by serving from local disk.

Endpoints:
  GET /media/thumbnail/{ad_id}  - serve cached thumbnail (falls back to image)
  GET /media/image/{ad_id}      - serve cached image (falls back to thumbnail)
  GET /media/video/{ad_id}      - serve cached video (streaming for large files)
  GET /media/creative/{ad_id}   - smart endpoint: best available media
  GET /media/download/{ad_id}   - force-download the best creative
  POST /media/bulk-download     - ZIP multiple ads' creatives, return download URL
  GET /media/status/{ad_id}     - media cache status for a specific ad
  GET /media/inventory          - complete media inventory status
  GET /media/stats              - aggregate media statistics (D19)
  GET /media/ad/{ad_id}/all     - all media for a specific ad (D19)
  GET /media/reference/{genre_en}  - reference creative assets for scenario builder
  POST /media/scenario-export      - export scenario as text/HTML/brief
  GET /media/scenario-thumbnail/{archetype} - SVG thumbnail for scenario archetype
"""

import os
import json
import uuid
import zipfile
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.schemas.ad import (
    BULK_DOWNLOAD_SKIPPED_REASON_CODES,
    DOWNLOAD_FAILURE_REASON_CODES,
    build_lp_info_payload,
    build_media_status_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "media_cache")
)

DOWNLOAD_DIR = os.path.join(CACHE_DIR, "downloads")

# Video extensions and MIME types
VIDEO_FORMATS = [("mp4", "video/mp4"), ("webm", "video/webm"), ("mov", "video/quicktime")]

# Threshold for streaming vs direct file response (10 MB)
STREAM_THRESHOLD_BYTES = 10 * 1024 * 1024


# ── Helpers ──────────────────────────────────────────────────────────


def _download_error_detail(code: str, message: str, **extra) -> dict:
    normalized = code if code in DOWNLOAD_FAILURE_REASON_CODES else "download_file_missing"
    payload = {"failure_reason_code": normalized, "message": message}
    if extra:
        payload.update(extra)
    return payload

def _find_video_path(ad_id: int) -> tuple[str, str] | None:
    """Find a cached video file for the given ad ID.

    Returns (path, media_type) or None.
    """
    for ext, mime in VIDEO_FORMATS:
        path = os.path.join(CACHE_DIR, "videos", f"{ad_id}.{ext}")
        if os.path.exists(path):
            return path, mime
    return None


def _find_best_creative(ad_id: int) -> tuple[str, str, str] | None:
    """Find the best available creative for an ad.

    Priority: video > image > thumbnail.
    Returns (path, media_type, creative_kind) or None.
    """
    # 1. Video
    video = _find_video_path(ad_id)
    if video:
        return video[0], video[1], "video"

    # 2. Image
    img_path = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
    if os.path.exists(img_path):
        return img_path, "image/jpeg", "image"

    # 3. Thumbnail
    thumb_path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
    if os.path.exists(thumb_path):
        return thumb_path, "image/jpeg", "thumbnail"

    return None


def _infer_extension(source: str | None, default_ext: str) -> str:
    if not source:
        return default_ext
    path = urlparse(source).path or source
    ext = os.path.splitext(path)[1].lower()
    return ext if ext else default_ext


def _write_cache_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


async def _cache_remote_http(url: str, cache_path: str, expected_type_prefix: str) -> bool:
    try:
        import httpx
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        ) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return False
        ctype = (resp.headers.get("content-type") or "").lower()
        if expected_type_prefix and ctype and not ctype.startswith(expected_type_prefix):
            return False
        _write_cache_file(cache_path, resp.content)
        return True
    except Exception as e:
        logger.warning("cache_remote_http_failed: url=%s err=%s", url, e)
        return False


def _cache_s3_object(s3_key: str, cache_path: str) -> bool:
    try:
        from app.core.storage import get_storage_client
        storage = get_storage_client()
        data = storage.get_bytes(s3_key)
        if not data:
            return False
        _write_cache_file(cache_path, data)
        return True
    except Exception as e:
        logger.warning("cache_s3_object_failed: key=%s err=%s", s3_key, e)
        return False


def _stream_file(path: str, chunk_size: int = 65536):
    """Generator that yields file content in chunks."""
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    except Exception as e:
        logger.error("stream_file_error", extra={"path": path, "error": str(e)})
        raise


def _placeholder_response(ad_id: int):
    """Return a simple SVG placeholder image when no cached media exists."""
    from fastapi.responses import Response
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"'
        ' viewBox="0 0 400 300">'
        '<rect width="400" height="300" fill="#f0f0f0"/>'
        '<text x="200" y="140" text-anchor="middle" font-family="Arial"'
        f' font-size="18" fill="#999">Ad #{ad_id}</text>'
        '<text x="200" y="170" text-anchor="middle" font-family="Arial"'
        ' font-size="14" fill="#bbb">No image cached</text>'
        '</svg>'
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"X-Fallback": "placeholder"},
    )


def _get_cloudfront_settings():
    """Return (enabled, domain) for CloudFront CDN. Cached after first call."""
    if not hasattr(_get_cloudfront_settings, "_cache"):
        try:
            from app.core.config import get_settings
            s = get_settings()
            _get_cloudfront_settings._cache = (
                s.aws_cloudfront_enabled and bool(s.aws_cloudfront_domain),
                s.aws_cloudfront_domain,
            )
        except Exception as e:
            logger.warning("cloudfront_settings_load_failed: %s", e)
            _get_cloudfront_settings._cache = (False, "")
    return _get_cloudfront_settings._cache


def _cloudfront_url(s3_key: str) -> str | None:
    """Build a CloudFront URL for the given S3 key. Returns None if disabled."""
    enabled, domain = _get_cloudfront_settings()
    if not enabled or not domain or not s3_key:
        return None
    scheme = "https"
    return f"{scheme}://{domain}/{s3_key}"


def _s3_presigned_url(s3_key: str) -> str | None:
    """Generate an S3 presigned URL as fallback when CloudFront is not configured."""
    if not s3_key:
        return None
    try:
        from app.core.storage import get_storage_client
        storage = get_storage_client()
        return storage.get_presigned_url(s3_key, expires=3600)
    except Exception as e:
        logger.warning("s3_presigned_url_failed: key=%s err=%s", s3_key, e)
        return None


def _media_redirect_url(s3_key: str) -> str | None:
    """Get redirect URL for an S3 key: CloudFront first, then S3 presigned URL."""
    url = _cloudfront_url(s3_key)
    if url:
        return url
    return _s3_presigned_url(s3_key)


async def _validated_media_redirect_url(
    s3_key: str | None,
    expected_type_prefix: str = "",
) -> str | None:
    """Return redirect URL only when object existence is verified.

    This prevents leaking CloudFront/S3 NoSuchKey responses to the UI.
    """
    url = _media_redirect_url(s3_key or "")
    if not url:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=5.0,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            resp = await client.head(url)
        if not (200 <= resp.status_code < 300):
            return None
        if expected_type_prefix:
            ctype = (resp.headers.get("content-type") or "").lower()
            if ctype and not ctype.startswith(expected_type_prefix):
                # Allow unknown content types, but block clear mismatches.
                if ctype not in ("application/octet-stream",):
                    return None
            # Guard against stale tiny placeholder objects in S3/CloudFront.
            if expected_type_prefix == "image/":
                content_len = (resp.headers.get("content-length") or "").strip()
                if content_len.isdigit() and int(content_len) < 4096:
                    return None
        return url
    except Exception as e:
        logger.warning("media_redirect_validation_failed: key=%s err=%s", s3_key, e)
        return None


def _get_ad_media_info(ad_id: int, media_type: str) -> dict | None:
    """Fetch S3 key and original URLs for an ad from DB.

    Returns dict with s3_key, thumbnail_url, image_url, video_url, snapshot_url.
    """
    try:
        from app.core.database import SyncSessionLocal
        from app.models.ad import Ad
        session = SyncSessionLocal()
        try:
            ad = session.query(Ad).filter(Ad.id == ad_id).first()
            if not ad:
                return None
            s3_key = None
            if media_type == "thumbnail":
                s3_key = ad.thumbnail_s3_key
            elif media_type == "image":
                s3_key = ad.image_s3_key
            elif media_type == "video":
                s3_key = ad.s3_key
            return {
                "s3_key": s3_key,
                "thumbnail_url": ad.thumbnail_url,
                "image_url": ad.image_url,
                "video_url": ad.video_url,
                "snapshot_url": ad.snapshot_url,
            }
        finally:
            session.close()
    except Exception as e:
        logger.warning("ad_media_info_fetch_failed: ad_id=%d type=%s err=%s", ad_id, media_type, e)
        return None


def _get_ad_s3_key(ad_id: int, media_type: str) -> str | None:
    """Fetch S3 key for an ad from DB. media_type: thumbnail, image, video."""
    info = _get_ad_media_info(ad_id, media_type)
    return info["s3_key"] if info else None


async def _ensure_best_creative_cached(ad_id: int) -> tuple[str, str, str] | None:
    existing = _find_best_creative(ad_id)
    if existing:
        return existing

    video_info = _get_ad_media_info(ad_id, "video") or {}
    image_info = _get_ad_media_info(ad_id, "image") or {}
    thumb_info = _get_ad_media_info(ad_id, "thumbnail") or {}

    video_s3_key = video_info.get("s3_key")
    if video_s3_key:
        ext = _infer_extension(video_s3_key, ".mp4")
        cache_path = os.path.join(CACHE_DIR, "videos", f"{ad_id}{ext}")
        if _cache_s3_object(video_s3_key, cache_path):
            mime = dict(VIDEO_FORMATS).get(ext.lstrip("."), "video/mp4")
            return cache_path, mime, "video"

    video_url = video_info.get("video_url")
    if video_url:
        ext = _infer_extension(video_url, ".mp4")
        cache_path = os.path.join(CACHE_DIR, "videos", f"{ad_id}{ext}")
        if await _cache_remote_http(video_url, cache_path, "video/"):
            mime = dict(VIDEO_FORMATS).get(ext.lstrip("."), "video/mp4")
            return cache_path, mime, "video"

    image_s3_key = image_info.get("s3_key")
    image_path = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
    if image_s3_key and _cache_s3_object(image_s3_key, image_path):
        return image_path, "image/jpeg", "image"

    image_url = image_info.get("image_url")
    if image_url:
        for candidate in [_upgrade_fbcdn_image_url(image_url), image_url]:
            if await _cache_remote_http(candidate, image_path, "image/"):
                return image_path, "image/jpeg", "image"

    thumb_s3_key = thumb_info.get("s3_key")
    thumb_path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
    if thumb_s3_key and _cache_s3_object(thumb_s3_key, thumb_path):
        return thumb_path, "image/jpeg", "thumbnail"

    thumb_url = thumb_info.get("thumbnail_url")
    if thumb_url:
        for candidate in [_upgrade_fbcdn_image_url(thumb_url), thumb_url]:
            if await _cache_remote_http(candidate, thumb_path, "image/"):
                return thumb_path, "image/jpeg", "thumbnail"

    extracted = await _try_snapshot_thumbnail_extract(ad_id, thumb_info or image_info)
    if extracted:
        return _find_best_creative(ad_id)

    return None


async def _try_snapshot_thumbnail_extract(ad_id: int, info: dict | None) -> Response | None:
    """Try extracting thumbnail from snapshot_url on-demand.

    This is a last-resort fallback to reduce blank creatives for newly crawled ads.
    """
    if not info:
        return None
    snapshot_url = info.get("snapshot_url")
    if not snapshot_url:
        return None

    try:
        from app.services.media_extraction import MediaExtractor
        extractor = MediaExtractor()
        extracted = await extractor.extract(snapshot_url, use_playwright=False)
        candidate_urls: list[str] = []
        if getattr(extracted, "thumbnail_url", None):
            candidate_urls.append(extracted.thumbnail_url)
        for u in getattr(extracted, "image_urls", []) or []:
            if u:
                candidate_urls.append(u)

        candidate_urls = list(dict.fromkeys([u for u in candidate_urls if isinstance(u, str) and u.startswith("http")]))
        if not candidate_urls:
            return None

        import httpx
        for url in candidate_urls[:3]:
            try:
                async with httpx.AsyncClient(
                    follow_redirects=True,
                    timeout=10.0,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                ) as client:
                    resp = await client.get(url)
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                    cache_path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    with open(cache_path, "wb") as f:
                        f.write(resp.content)

                    # Persist discovered thumbnail URL for future requests.
                    try:
                        from app.core.database import SyncSessionLocal
                        from app.models.ad import Ad
                        session = SyncSessionLocal()
                        try:
                            ad = session.query(Ad).filter(Ad.id == ad_id).first()
                            if ad and not ad.thumbnail_url:
                                ad.thumbnail_url = url
                            if ad and not ad.image_url:
                                ad.image_url = url
                            session.commit()
                        finally:
                            session.close()
                    except Exception as e:
                        logger.warning("thumbnail_url_persist_failed: ad_id=%d err=%s", ad_id, e)

                    return Response(
                        content=resp.content,
                        media_type=resp.headers.get("content-type", "image/jpeg"),
                        headers={"Cache-Control": "public, max-age=86400", "X-Fallback": "snapshot_extract"},
                    )
            except Exception as e:
                logger.debug("snapshot_extract_attempt_failed: ad_id=%d err=%s", ad_id, e)
                continue
    except Exception as e:
        logger.warning("snapshot_thumbnail_extract_failed: ad_id=%d err=%s", ad_id, e)
        return None
    return None


def _file_info(path: str) -> dict:
    """Get file info dict for a cached file. Returns cache status dict."""
    if not os.path.exists(path):
        return {"cached": False}
    size = os.path.getsize(path)
    # Quick validity check: JPEG starts with FF D8, PNG with 89 50
    valid = False
    try:
        with open(path, "rb") as f:
            hdr = f.read(4)
        valid = (
            hdr[:2] == b'\xff\xd8'  # JPEG
            or hdr[:4] == b'\x89PNG'  # PNG
            or hdr[:3] == b'GIF'      # GIF
            or hdr[:4] == b'RIFF'     # WebP
        )
    except Exception as e:
        logger.debug("file_header_check_failed: path=%s err=%s", path, e)
    return {
        "cached": True,
        "size_kb": round(size / 1024, 1),
        "valid": valid,
    }


def _cleanup_file(path: str) -> None:
    """Best-effort file cleanup for temporary exports."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning("temp_file_cleanup_failed: %s", str(e))


def _safe_export_slug(value: str, default: str = "custom") -> str:
    """Return filesystem-safe slug for generated filenames."""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    safe = safe.strip("._")
    if not safe:
        return default
    return safe[:80]


def _upgrade_fbcdn_image_url(url: str) -> str:
    """Remove tiny size restriction from fbcdn URLs when present."""
    if not url or "fbcdn.net" not in url:
        return url
    # e.g. stp=dst-jpg_s60x60_tt6 -> stp=dst-jpg_tt6
    return re.sub(r"_s\d+x\d+", "", url)


# ── Existing endpoints ───────────────────────────────────────────────

@router.get("/thumbnail/{ad_id}")
async def get_thumbnail(ad_id: int):
    """Return cached thumbnail image for the given ad ID.

    Fallback chain: CloudFront CDN → local cache → original URL redirect → placeholder.
    """
    info = _get_ad_media_info(ad_id, "thumbnail")

    # Try CloudFront or S3 presigned URL redirect first
    s3_key = info["s3_key"] if info else None
    redirect_url = await _validated_media_redirect_url(
        s3_key, expected_type_prefix="image/"
    )
    if redirect_url:
        return RedirectResponse(url=redirect_url, status_code=302)

    path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")

    # Fallback: serve full-size image as thumbnail
    img_path = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
    if os.path.exists(img_path):
        return FileResponse(
            img_path,
            media_type="image/jpeg",
            headers={"X-Fallback": "image"},
        )

    # Fallback: fetch image server-side and cache it (avoids CORS/403 from Facebook CDN)
    if info:
        for url_field in ["thumbnail_url", "image_url"]:
            url = info.get(url_field)
            if url and url.startswith("http"):
                candidates = [_upgrade_fbcdn_image_url(url), url]
                seen = set()
                candidates = [u for u in candidates if not (u in seen or seen.add(u))]
                try:
                    import httpx
                    async with httpx.AsyncClient(
                        follow_redirects=True, timeout=10.0,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    ) as client:
                        for candidate_url in candidates:
                            resp = await client.get(candidate_url)
                            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                                # Cache for future requests
                                cache_path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
                                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                                with open(cache_path, "wb") as f:
                                    f.write(resp.content)
                                from fastapi.responses import Response
                                return Response(
                                    content=resp.content,
                                    media_type=resp.headers.get("content-type", "image/jpeg"),
                                    headers={"Cache-Control": "public, max-age=86400", "X-Fallback": url_field},
                                )
                except Exception as e:
                    logger.debug("thumbnail_http_fetch_failed: ad_id=%d field=%s err=%s", ad_id, url_field, e)

    # Last fallback: extract from snapshot_url on demand
    extracted = await _try_snapshot_thumbnail_extract(ad_id, info)
    if extracted:
        return extracted

    # Fallback: placeholder SVG
    return _placeholder_response(ad_id)


@router.get("/image/{ad_id}")
async def get_image(ad_id: int):
    """Return cached full-size image for the given ad ID.

    Fallback chain: CloudFront CDN → local cache → original URL redirect → placeholder.
    """
    info = _get_ad_media_info(ad_id, "image")

    # Try CloudFront or S3 presigned URL redirect first
    s3_key = info["s3_key"] if info else None
    redirect_url = await _validated_media_redirect_url(
        s3_key, expected_type_prefix="image/"
    )
    if redirect_url:
        return RedirectResponse(url=redirect_url, status_code=302)

    path = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/jpeg")

    # Fallback: serve thumbnail as image
    thumb_path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
    if os.path.exists(thumb_path):
        return FileResponse(
            thumb_path,
            media_type="image/jpeg",
            headers={"X-Fallback": "thumbnail"},
        )

    # Fallback: fetch image server-side and cache it
    if info:
        for url_field in ["image_url", "thumbnail_url"]:
            url = info.get(url_field)
            if url and url.startswith("http"):
                candidates = [_upgrade_fbcdn_image_url(url), url]
                seen = set()
                candidates = [u for u in candidates if not (u in seen or seen.add(u))]
                try:
                    import httpx
                    async with httpx.AsyncClient(
                        follow_redirects=True, timeout=10.0,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    ) as client:
                        for candidate_url in candidates:
                            resp = await client.get(candidate_url)
                            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                                cache_path = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
                                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                                with open(cache_path, "wb") as f:
                                    f.write(resp.content)
                                from fastapi.responses import Response
                                return Response(
                                    content=resp.content,
                                    media_type=resp.headers.get("content-type", "image/jpeg"),
                                    headers={"Cache-Control": "public, max-age=86400", "X-Fallback": url_field},
                                )
                except Exception as e:
                    logger.debug("image_http_fetch_failed: ad_id=%d field=%s err=%s", ad_id, url_field, e)

    # Last fallback: try snapshot extraction and reuse cached thumbnail as image.
    extracted = await _try_snapshot_thumbnail_extract(ad_id, info)
    if extracted:
        return extracted

    # Fallback: placeholder SVG
    return _placeholder_response(ad_id)


@router.get("/video/{ad_id}")
async def get_video(ad_id: int):
    """Return cached video file for the given ad ID.

    Fallback chain: CloudFront CDN → local cache → video_url redirect → 404.
    Uses StreamingResponse for files larger than 10 MB to avoid
    loading the entire video into memory.
    """
    info = _get_ad_media_info(ad_id, "video")

    # Try CloudFront or S3 presigned URL redirect first
    s3_key = info["s3_key"] if info else None
    redirect_url = _media_redirect_url(s3_key)
    if redirect_url:
        return RedirectResponse(url=redirect_url, status_code=302)

    result = _find_video_path(ad_id)
    if result:
        path, mime = result
        file_size = os.path.getsize(path)

        if file_size > STREAM_THRESHOLD_BYTES:
            return StreamingResponse(
                _stream_file(path),
                media_type=mime,
                headers={
                    "Content-Length": str(file_size),
                    "Accept-Ranges": "bytes",
                },
            )
        return FileResponse(path, media_type=mime)

    # Fallback: redirect to original video_url from DB
    if info:
        url = info.get("video_url")
        if url and url.startswith("http"):
            return RedirectResponse(url=url, status_code=302, headers={"X-Fallback": "video_url"})

    raise HTTPException(status_code=404, detail="Video not found")


# ── New: Smart creative endpoint ─────────────────────────────────────

@router.get("/creative/{ad_id}")
async def get_creative(ad_id: int):
    """Return the best available media for the given ad.

    Priority: video > image > thumbnail.
    """
    result = _find_best_creative(ad_id)
    if not result:
        result = await _ensure_best_creative_cached(ad_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=_download_error_detail("no_cached_media", "No cached media found for this ad", ad_id=ad_id),
        )

    path, mime, kind = result
    file_size = os.path.getsize(path)

    # Stream large videos
    if kind == "video" and file_size > STREAM_THRESHOLD_BYTES:
        return StreamingResponse(
            _stream_file(path),
            media_type=mime,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
                "X-Creative-Type": kind,
            },
        )

    return FileResponse(
        path,
        media_type=mime,
        headers={"X-Creative-Type": kind},
    )


# ── New: Download endpoint (force Content-Disposition: attachment) ────

@router.get("/download/{ad_id}")
async def download_creative(ad_id: int):
    """Force-download the best available creative for an ad.

    Sets Content-Disposition: attachment so the browser downloads
    instead of displaying inline.
    """
    result = _find_best_creative(ad_id)
    if not result:
        result = await _ensure_best_creative_cached(ad_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=_download_error_detail("no_cached_media", "No cached media found for this ad", ad_id=ad_id),
        )

    path, mime, kind = result

    # Determine filename extension
    ext_map = {
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "image/jpeg": ".jpg",
    }
    ext = ext_map.get(mime, "")
    filename = f"ad_{ad_id}_{kind}{ext}"

    return FileResponse(
        path,
        media_type=mime,
        filename=filename,  # FileResponse sets Content-Disposition: attachment
    )


# ── Creative Intelligence (Rekognition) ──────────────────────────────

@router.get("/intelligence/{ad_id}")
async def get_creative_intelligence(ad_id: int):
    """Return full Rekognition + creative analysis for an ad.

    Combines image analysis (labels, text, faces), video analysis
    (labels/text/faces over time), and existing creative_analysis.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")

        meta = ad.ad_metadata or {}
        result = {"ad_id": ad_id}

        # Rekognition image analysis
        rek = meta.get("rekognition")
        if rek:
            result["image_analysis"] = {
                "labels": rek.get("labels", []),
                "text_detections": rek.get("text_detections", []),
                "faces": rek.get("faces", []),
                "moderation": rek.get("moderation", []),
            }

        # Rekognition video analysis
        rek_video = meta.get("rekognition_video")
        if rek_video:
            result["video_analysis"] = {
                "labels": rek_video.get("labels", []),
                "text_detections": rek_video.get("text_detections", []),
                "face_moments": rek_video.get("face_moments", []),
            }

        # Existing creative analysis
        ca = meta.get("creative_analysis")
        if ca:
            result["creative_analysis"] = ca

        # NLP analysis (from D13)
        nlp = meta.get("nlp")
        if nlp:
            result["nlp"] = nlp

        # Creative intelligence (merged, from D13)
        ci = meta.get("creative_intelligence")
        if ci:
            result["creative_intelligence"] = ci

        # Transcript (from D13)
        transcript = meta.get("transcript")
        if transcript:
            result["transcript"] = {
                "full_text": transcript.get("full_text", ""),
                "language": transcript.get("language", ""),
            }

        if len(result) <= 1:
            raise HTTPException(
                status_code=404,
                detail="No analysis data available for this ad. Run rekognition_analyze.py first.",
            )

        return result

    finally:
        session.close()


# ── New: Presigned URL endpoint ───────────────────────────────────────

@router.get("/signed-url/{ad_id}")
async def get_signed_url(ad_id: int, media_type: str = "image"):
    """Generate a temporary presigned S3 URL for direct download (1h expiry).

    Query params:
      - media_type: "thumbnail", "image", or "video" (default: "image")
    """
    s3_key = _get_ad_s3_key(ad_id, media_type)
    if not s3_key:
        raise HTTPException(
            status_code=404,
            detail=f"No S3 key found for ad {ad_id} ({media_type})",
        )

    try:
        from app.core.storage import get_storage_client
        storage = get_storage_client()
        url = storage.get_presigned_url(s3_key, expires=3600)
        return {"ad_id": ad_id, "media_type": media_type, "url": url, "expires_in": 3600}
    except Exception as e:
        logger.error("signed_url_error: ad=%d type=%s err=%s", ad_id, media_type, e)
        raise HTTPException(status_code=500, detail="Failed to generate presigned URL")


# ── New: Bulk download (ZIP) ─────────────────────────────────────────

class BulkDownloadRequest(BaseModel):
    ad_ids: list[int]


class BulkDownloadResponse(BaseModel):
    download_url: str
    requested_count: int
    downloaded_count: int
    file_count: int
    total_size_bytes: int
    zip_filename: str
    skipped_ids: list[int] = Field(default_factory=list)
    skipped_reasons: dict[str, str] = Field(default_factory=dict)
    skipped_reason_code: str | None = None


def _load_ad_for_contract(ad_id: int):
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        return session.query(Ad).filter(Ad.id == ad_id).first()
    finally:
        session.close()


def _build_bulk_skip_reason(ad_id: int) -> str:
    ad = _load_ad_for_contract(ad_id)
    if not ad:
        return "missing_creative"

    media_status = build_media_status_payload(ad)
    for code in media_status.get("missing_reasons", []):
        if code in BULK_DOWNLOAD_SKIPPED_REASON_CODES:
            return code
    return "missing_creative"


@router.post("/bulk-download", response_model=BulkDownloadResponse)
async def bulk_download(request: BulkDownloadRequest):
    """Create a ZIP archive containing creatives for the requested ad IDs.

    Returns a download URL for the generated ZIP file stored in
    media_cache/downloads/.
    """
    if not request.ad_ids:
        raise HTTPException(
            status_code=400,
            detail=_download_error_detail("invalid_ad_ids", "ad_ids list cannot be empty"),
        )

    if len(request.ad_ids) > 500:
        raise HTTPException(
            status_code=400,
            detail=_download_error_detail("invalid_ad_ids", "Maximum 500 ads per bulk download"),
        )

    # Ensure downloads directory exists
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Generate unique ZIP filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zip_id = uuid.uuid4().hex[:8]
    zip_filename = f"ads_media_{timestamp}_{zip_id}.zip"
    zip_path = os.path.join(DOWNLOAD_DIR, zip_filename)

    file_count = 0
    total_size = 0
    skipped_ids = []
    skipped_reasons: dict[str, str] = {}

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for ad_id in request.ad_ids:
                result = _find_best_creative(ad_id)
                if not result:
                    result = await _ensure_best_creative_cached(ad_id)
                if not result:
                    skipped_ids.append(ad_id)
                    skipped_reasons[str(ad_id)] = _build_bulk_skip_reason(ad_id)
                    continue

                path, mime, kind = result

                # Determine archive filename
                ext_map = {
                    "video/mp4": ".mp4",
                    "video/webm": ".webm",
                    "video/quicktime": ".mov",
                    "image/jpeg": ".jpg",
                }
                ext = ext_map.get(mime, "")
                archive_name = f"ad_{ad_id}_{kind}{ext}"

                zf.write(path, archive_name)
                file_count += 1
                total_size += os.path.getsize(path)

    except Exception as e:
        # Clean up partial ZIP on error
        if os.path.exists(zip_path):
            os.remove(zip_path)
        logger.error("Bulk download ZIP creation failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=_download_error_detail("zip_creation_failed", f"Failed to create ZIP archive: {str(e)}"),
        )

    if file_count == 0:
        # Remove empty ZIP
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise HTTPException(
            status_code=404,
            detail=_download_error_detail(
                "no_cached_media",
                "No cached media found for any of the requested ads",
                ad_ids=request.ad_ids,
            ),
        )

    if skipped_ids:
        logger.info(
            "Bulk download: %d files included, %d ads skipped (no media): %s",
            file_count, len(skipped_ids), skipped_ids[:20],
        )

    download_url = f"/api/v1/media/bulk-download-file/{zip_filename}"

    return BulkDownloadResponse(
        download_url=download_url,
        requested_count=len(request.ad_ids),
        downloaded_count=file_count,
        file_count=file_count,
        total_size_bytes=total_size,
        zip_filename=zip_filename,
        skipped_ids=skipped_ids,
        skipped_reasons=skipped_reasons,
        skipped_reason_code="no_cached_media" if skipped_ids else None,
    )


@router.get("/bulk-download-file/{filename}")
async def serve_bulk_download(filename: str):
    """Serve a previously generated bulk-download ZIP file."""
    # Sanitize filename to prevent path traversal
    safe_name = os.path.basename(filename)
    if safe_name != filename or ".." in filename:
        raise HTTPException(
            status_code=400,
            detail=_download_error_detail("invalid_ad_ids", "Invalid filename"),
        )

    path = os.path.join(DOWNLOAD_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=_download_error_detail("download_file_missing", "Download file not found or expired"),
        )

    file_size = os.path.getsize(path)

    # Stream large ZIP files
    if file_size > STREAM_THRESHOLD_BYTES:
        return StreamingResponse(
            _stream_file(path),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}"',
                "Content-Length": str(file_size),
            },
        )

    return FileResponse(
        path,
        media_type="application/zip",
        filename=safe_name,
    )


# ── Crawl History ────────────────────────────────────────────────────

@router.get("/crawl-history")
async def get_crawl_history(days: int = 30):
    """Return crawl stats over time: daily counts, new vs duplicate.

    Reads from CrawlJob table and Ad creation dates to build a daily
    summary of crawl activity.
    """
    from datetime import timedelta
    from sqlalchemy import func, cast, Date
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Daily ad creation counts
        daily_ads = (
            session.query(
                func.date(Ad.created_at).label("date"),
                func.count(Ad.id).label("total"),
            )
            .filter(Ad.created_at >= cutoff)
            .group_by(func.date(Ad.created_at))
            .order_by(func.date(Ad.created_at))
            .all()
        )

        # Count duplicates per day
        all_recent_ads = session.query(Ad).filter(Ad.created_at >= cutoff).all()
        dup_by_date = {}
        for ad in all_recent_ads:
            meta = ad.ad_metadata or {}
            day_str = ad.created_at.strftime("%Y-%m-%d") if ad.created_at else "unknown"
            if day_str not in dup_by_date:
                dup_by_date[day_str] = {"total": 0, "duplicate": 0, "new": 0}
            dup_by_date[day_str]["total"] += 1
            if meta.get("is_duplicate"):
                dup_by_date[day_str]["duplicate"] += 1
            else:
                dup_by_date[day_str]["new"] += 1

        # Crawl job history
        crawl_jobs_data = []
        try:
            from app.models.crawl_job import CrawlJob
            crawl_jobs = (
                session.query(CrawlJob)
                .filter(CrawlJob.created_at >= cutoff)
                .order_by(CrawlJob.created_at.desc())
                .limit(100)
                .all()
            )
            for cj in crawl_jobs:
                crawl_jobs_data.append({
                    "job_id": cj.job_id,
                    "status": cj.status.value if hasattr(cj.status, "value") else str(cj.status),
                    "query": cj.query,
                    "platforms": cj.platforms,
                    "total_ads_found": cj.total_ads_found,
                    "created_at": cj.created_at.isoformat() if cj.created_at else None,
                })
        except Exception as e:
            logger.warning("crawl_jobs_query_failed: %s", str(e))

        # Build daily timeline
        daily_timeline = []
        for row in daily_ads:
            day_str = str(row.date) if row.date else "unknown"
            day_info = dup_by_date.get(day_str, {"total": row.total, "duplicate": 0, "new": row.total})
            daily_timeline.append({
                "date": day_str,
                "total": day_info["total"],
                "new": day_info["new"],
                "duplicate": day_info["duplicate"],
            })

        # Summary totals
        total_ads = session.query(Ad).count()
        total_dup = sum(1 for ad in session.query(Ad).all()
                         if (ad.ad_metadata or {}).get("is_duplicate"))

        return {
            "period_days": days,
            "total_ads": total_ads,
            "total_duplicates": total_dup,
            "total_unique": total_ads - total_dup,
            "daily_timeline": daily_timeline,
            "recent_crawl_jobs": crawl_jobs_data,
        }

    except Exception as e:
        logger.error("crawl_history_error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to load crawl history: {str(e)}")
    finally:
        session.close()


# ── Frame Serving Endpoints ──────────────────────────────────────────

FRAMES_DIR = os.path.join(CACHE_DIR, "frames")


@router.get("/frames/{ad_id}")
async def get_frame_list(ad_id: int):
    """Return list of available frame URLs for a video ad.

    Frames are stored as media_cache/frames/{ad_id}_frame_{index}.jpg.
    Returns URLs for all available frames.
    """
    if not os.path.isdir(FRAMES_DIR):
        return {"ad_id": ad_id, "frames": [], "count": 0}

    frame_files = []
    for filename in sorted(os.listdir(FRAMES_DIR)):
        if filename.startswith(f"{ad_id}_frame_") and filename.endswith(".jpg"):
            try:
                # Extract frame index from filename: {ad_id}_frame_{index}.jpg
                idx_str = filename.replace(f"{ad_id}_frame_", "").replace(".jpg", "")
                idx = int(idx_str)
                frame_files.append({
                    "index": idx,
                    "filename": filename,
                    "url": f"/api/v1/media/frame/{ad_id}/{idx}",
                    "size_bytes": os.path.getsize(os.path.join(FRAMES_DIR, filename)),
                })
            except (ValueError, OSError):
                continue

    return {
        "ad_id": ad_id,
        "frames": frame_files,
        "count": len(frame_files),
    }


@router.get("/frame/{ad_id}/{frame_index}")
async def get_frame(ad_id: int, frame_index: int):
    """Serve a specific extracted frame image for a video ad.

    Frame files are at: media_cache/frames/{ad_id}_frame_{frame_index}.jpg
    """
    frame_path = os.path.join(FRAMES_DIR, f"{ad_id}_frame_{frame_index}.jpg")

    if not os.path.exists(frame_path):
        raise HTTPException(
            status_code=404,
            detail=f"Frame {frame_index} not found for ad {ad_id}",
        )

    return FileResponse(frame_path, media_type="image/jpeg")


# ── Media Status Endpoint ──────────────────────────────────────────

@router.get("/status/{ad_id}")
async def get_media_status(ad_id: int):
    """Return detailed media cache status for a specific ad.

    Reports whether thumbnail, image, and video are cached, their file
    sizes, and validity. Also provides an overall status assessment.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
    finally:
        session.close()

    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    # Thumbnail status
    thumb_path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
    thumb_info = _file_info(thumb_path)

    # Image status
    img_path = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
    img_info = _file_info(img_path)

    # Video status
    video_info = {"cached": False}
    video_result = _find_video_path(ad_id)
    if video_result:
        vpath, vmime = video_result
        vsize = os.path.getsize(vpath)
        video_info = {
            "cached": True,
            "size_kb": round(vsize / 1024, 1),
            "valid": True,  # _find_video_path already confirms existence
            "format": vmime,
        }

    # Frames status
    frame_count = 0
    if os.path.isdir(FRAMES_DIR):
        frame_count = len([
            f for f in os.listdir(FRAMES_DIR)
            if f.startswith(f"{ad_id}_frame_") and f.endswith(".jpg")
        ])

    # Overall assessment
    cached_count = sum(1 for info in [thumb_info, img_info, video_info] if info["cached"])
    if cached_count == 0:
        overall = "none"
    elif cached_count >= 2:
        overall = "full"
    else:
        overall = "partial"

    return {
        "ad_id": ad_id,
        "thumbnail": thumb_info,
        "image": img_info,
        "video": video_info,
        "frames": {"count": frame_count},
        "overall": overall,
        "media_status": build_media_status_payload(ad),
        "lp_info": build_lp_info_payload(ad),
        "media_cache_status": overall,
    }


# ── Genre-Specific Crawl Endpoint ────────────────────────────────────

class GenreCrawlRequest(BaseModel):
    genre_key: str


class GenreCrawlResponse(BaseModel):
    genre_key: str
    label: str
    new_ads: int
    total_found: int
    media_downloaded: dict


@router.post("/genre-crawl", response_model=GenreCrawlResponse)
async def genre_crawl(request: GenreCrawlRequest):
    """Crawl ads for a specific fine genre.

    Accepts a genre key (e.g. "medical_weight_loss") and crawls all
    keywords associated with that genre.  New ads are tagged with
    fine_genre metadata and media is downloaded immediately.

    Returns the number of new ads found and saved.
    """
    import json as _json

    # Import genre crawl logic
    _scripts_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
    )
    _config_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "genre_crawl_keywords.json")
    )

    # Inline import to avoid circular issues at module level
    import sys as _sys
    if _scripts_dir not in _sys.path:
        _sys.path.insert(0, os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        ))

    from scripts.genre_crawl import (
        load_genre_config,
        crawl_genre,
    )
    from app.tasks.crawl_tasks import get_connected_platforms

    # Load genre config
    genres, platforms, limit = load_genre_config()

    genre_key = request.genre_key
    if genre_key not in genres:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown genre '{genre_key}'. Available: {', '.join(genres.keys())}",
        )

    # Check connected platforms
    connected = get_connected_platforms()
    active = [p for p in platforms if p in connected]
    if not active:
        raise HTTPException(
            status_code=503,
            detail="No ad platforms connected. Configure API keys first.",
        )

    genre_info = genres[genre_key]

    # Run the crawl (blocking — may take a while for many keywords)
    import asyncio
    result = crawl_genre(genre_key, genre_info, active, limit)

    return GenreCrawlResponse(
        genre_key=result["genre_key"],
        label=result["label"],
        new_ads=result["total_saved"],
        total_found=result["total_found"],
        media_downloaded=result["media_downloaded"],
    )


# ── Media Inventory Endpoint (D9) ───────────────────────────────────

LP_HTML_DIR = os.path.join(CACHE_DIR, "lp_html")
LP_SCREENSHOT_DIR = os.path.join(CACHE_DIR, "lp_screenshots")


@router.get("/inventory")
async def get_media_inventory():
    """Return complete media inventory status.

    Reports:
      - total_ads, cached_thumbnails, cached_images, cached_videos, cached_frames
      - total_cache_size_mb, orphaned_files
      - missing_media_ads (list of ad_ids with no cached media at all)
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total_ads = len(ads)
        ad_ids = {ad.id for ad in ads}

        # Count cached files
        cached_thumbnails = 0
        cached_images = 0
        cached_videos = 0
        cached_frames = 0
        orphaned_files = 0
        total_cache_bytes = 0
        missing_media_ads = []

        thumb_dir = os.path.join(CACHE_DIR, "thumbnails")
        img_dir = os.path.join(CACHE_DIR, "images")
        vid_dir = os.path.join(CACHE_DIR, "videos")

        # Build sets of cached ad_ids per type
        thumb_ids: set[int] = set()
        img_ids: set[int] = set()
        vid_ids: set[int] = set()

        if os.path.isdir(thumb_dir):
            for f in os.listdir(thumb_dir):
                if f.endswith(".jpg"):
                    fpath = os.path.join(thumb_dir, f)
                    total_cache_bytes += os.path.getsize(fpath)
                    try:
                        fid = int(f.replace(".jpg", ""))
                        if fid in ad_ids:
                            thumb_ids.add(fid)
                            cached_thumbnails += 1
                        else:
                            orphaned_files += 1
                    except ValueError:
                        orphaned_files += 1

        if os.path.isdir(img_dir):
            for f in os.listdir(img_dir):
                if f.endswith(".jpg"):
                    fpath = os.path.join(img_dir, f)
                    total_cache_bytes += os.path.getsize(fpath)
                    try:
                        fid = int(f.replace(".jpg", ""))
                        if fid in ad_ids:
                            img_ids.add(fid)
                            cached_images += 1
                        else:
                            orphaned_files += 1
                    except ValueError:
                        orphaned_files += 1

        if os.path.isdir(vid_dir):
            for f in os.listdir(vid_dir):
                for ext in (".mp4", ".webm", ".mov"):
                    if f.endswith(ext):
                        fpath = os.path.join(vid_dir, f)
                        total_cache_bytes += os.path.getsize(fpath)
                        try:
                            fid = int(f.replace(ext, ""))
                            if fid in ad_ids:
                                vid_ids.add(fid)
                                cached_videos += 1
                            else:
                                orphaned_files += 1
                        except ValueError:
                            orphaned_files += 1

        if os.path.isdir(FRAMES_DIR):
            for f in os.listdir(FRAMES_DIR):
                if f.endswith(".jpg"):
                    fpath = os.path.join(FRAMES_DIR, f)
                    total_cache_bytes += os.path.getsize(fpath)
                    cached_frames += 1

        # Find ads with no cached media at all
        for ad_id in ad_ids:
            if ad_id not in thumb_ids and ad_id not in img_ids and ad_id not in vid_ids:
                missing_media_ads.append(ad_id)

        missing_media_ads.sort()

        total_cache_size_mb = round(total_cache_bytes / (1024 * 1024), 2)

        return {
            "total_ads": total_ads,
            "cached_thumbnails": cached_thumbnails,
            "cached_images": cached_images,
            "cached_videos": cached_videos,
            "cached_frames": cached_frames,
            "orphaned_files": orphaned_files,
            "total_cache_size_mb": total_cache_size_mb,
            "cache_size_mb": total_cache_size_mb,
            "missing_media_count": len(missing_media_ads),
            "missing_media_ads": missing_media_ads[:200],  # Limit to first 200
            "cache_rates": {
                "thumbnail_rate": round(cached_thumbnails / total_ads * 100, 1) if total_ads > 0 else 0,
                "image_rate": round(cached_images / total_ads * 100, 1) if total_ads > 0 else 0,
                "video_rate": round(cached_videos / total_ads * 100, 1) if total_ads > 0 else 0,
            },
        }

    except Exception as e:
        logger.error("media_inventory_error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to compute media inventory: {str(e)}")
    finally:
        session.close()


# ── Aggregate Media Stats (D19) ──────────────────────────────────────

@router.get("/stats")
async def get_media_stats():
    """Return aggregate media statistics.

    Returns counts of cached/valid/placeholder thumbnails, images, videos,
    total cache size, and average quality score.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total_ads = len(ads)
        ad_ids = {ad.id for ad in ads}

        thumb_dir = os.path.join(CACHE_DIR, "thumbnails")
        img_dir = os.path.join(CACHE_DIR, "images")
        vid_dir = os.path.join(CACHE_DIR, "videos")

        # Thumbnail stats
        thumb_cached = 0
        thumb_valid = 0
        thumb_placeholder = 0

        if os.path.isdir(thumb_dir):
            for f in os.listdir(thumb_dir):
                if not f.endswith(".jpg"):
                    continue
                try:
                    fid = int(f.replace(".jpg", ""))
                    if fid not in ad_ids:
                        continue
                except ValueError:
                    continue

                fpath = os.path.join(thumb_dir, f)
                thumb_cached += 1
                fsize = os.path.getsize(fpath)

                # Placeholder detection: very small files are likely placeholders
                if fsize < 5120:
                    thumb_placeholder += 1
                else:
                    # Quick header check
                    try:
                        with open(fpath, "rb") as fh:
                            hdr = fh.read(4)
                        if hdr[:2] == b'\xff\xd8' or hdr[:4] == b'\x89PNG':
                            thumb_valid += 1
                        else:
                            thumb_placeholder += 1
                    except Exception as e:
                        logger.debug("thumb_header_check_failed: %s err=%s", f, e)
                        thumb_placeholder += 1

        # Image stats
        img_cached = 0
        img_valid = 0
        img_invalid = 0

        if os.path.isdir(img_dir):
            for f in os.listdir(img_dir):
                if not f.endswith(".jpg"):
                    continue
                try:
                    fid = int(f.replace(".jpg", ""))
                    if fid not in ad_ids:
                        continue
                except ValueError:
                    continue

                fpath = os.path.join(img_dir, f)
                img_cached += 1
                fsize = os.path.getsize(fpath)

                if fsize < 5120:
                    img_invalid += 1
                else:
                    try:
                        with open(fpath, "rb") as fh:
                            hdr = fh.read(4)
                        if hdr[:2] == b'\xff\xd8' or hdr[:4] == b'\x89PNG':
                            img_valid += 1
                        else:
                            img_invalid += 1
                    except Exception as e:
                        logger.debug("img_header_check_failed: %s err=%s", f, e)
                        img_invalid += 1

        # Video stats
        video_with_url = 0
        video_cached = 0

        for ad in ads:
            if ad.video_url:
                video_with_url += 1

        if os.path.isdir(vid_dir):
            for f in os.listdir(vid_dir):
                for ext in (".mp4", ".webm", ".mov"):
                    if f.endswith(ext):
                        try:
                            fid = int(f.replace(ext, ""))
                            if fid in ad_ids:
                                video_cached += 1
                        except ValueError:
                            pass

        # Cache size
        total_cache_bytes = 0
        for dirpath, _dirnames, filenames in os.walk(CACHE_DIR):
            for fn in filenames:
                try:
                    total_cache_bytes += os.path.getsize(os.path.join(dirpath, fn))
                except OSError:
                    pass

        cache_size_mb = round(total_cache_bytes / (1024 * 1024), 2)

        # Average quality score from ad_metadata.thumbnail_quality.score
        quality_scores = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            tq = meta.get("thumbnail_quality")
            if isinstance(tq, dict) and "score" in tq:
                try:
                    quality_scores.append(float(tq["score"]))
                except (ValueError, TypeError):
                    pass

        quality_score_avg = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0

        return {
            "total_ads": total_ads,
            "thumbnails": {
                "cached": thumb_cached,
                "valid": thumb_valid,
                "placeholder": thumb_placeholder,
            },
            "images": {
                "cached": img_cached,
                "valid": img_valid,
                "invalid": img_invalid,
            },
            "videos": {
                "with_url": video_with_url,
                "cached": video_cached,
            },
            "cache_size_mb": cache_size_mb,
            "quality_score_avg": quality_score_avg,
        }

    except Exception as e:
        logger.error("media_stats_error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to compute media stats: {str(e)}")
    finally:
        session.close()


# ── v1.5: Auto CR Extraction API ─────────────────────────────────────


class AutoExtractRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    use_playwright: bool = True


@router.post("/auto-extract")
async def trigger_auto_extract(req: AutoExtractRequest):
    """Trigger automatic media extraction for pending ads.

    Extracts images and videos (CR) for ads missing media.
    Uses Playwright + network intercept for reliable extraction.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad, MediaExtractionStatus
    from sqlalchemy import or_, func

    session = SyncSessionLocal()
    try:
        # Count pending
        pending_count = (
            session.query(func.count(Ad.id))
            .filter(
                Ad.snapshot_url.isnot(None),
                or_(Ad.image_url.is_(None), Ad.thumbnail_url.is_(None)),
                Ad.media_extraction_status.in_([
                    MediaExtractionStatus.PENDING,
                    MediaExtractionStatus.FAILED,
                    MediaExtractionStatus.ENRICHED,
                ]),
            )
            .scalar()
        )

        if pending_count == 0:
            return {
                "status": "no_pending",
                "message": "All ads already have media extracted",
                "pending_count": 0,
            }

        # Try Celery dispatch first, fallback to inline
        try:
            from app.tasks.media_tasks import auto_extract_pending_media_task
            result = auto_extract_pending_media_task.delay(
                limit=req.limit, use_playwright=req.use_playwright
            )
            return {
                "status": "dispatched",
                "message": f"Auto-extraction dispatched for up to {req.limit} ads",
                "pending_count": pending_count,
                "task_id": str(getattr(result, "id", None)),
            }
        except Exception:
            # Inline fallback
            from app.tasks.media_tasks import auto_extract_pending_media_task
            result = auto_extract_pending_media_task(
                limit=min(req.limit, 10),  # Limit inline to avoid timeout
                use_playwright=req.use_playwright,
            )
            return {
                "status": "completed_inline",
                "pending_count": pending_count,
                **result,
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/extraction-progress")
async def get_extraction_progress():
    """Real-time extraction progress for the UI dashboard."""
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad, MediaExtractionStatus
    from sqlalchemy import func, or_

    session = SyncSessionLocal()
    try:
        total = session.query(func.count(Ad.id)).scalar()

        # Media coverage
        with_image = session.query(func.count(Ad.id)).filter(Ad.image_url.isnot(None)).scalar()
        with_thumb = session.query(func.count(Ad.id)).filter(Ad.thumbnail_url.isnot(None)).scalar()
        with_video = session.query(func.count(Ad.id)).filter(Ad.video_url.isnot(None)).scalar()

        # Status breakdown
        status_counts = dict(
            session.query(Ad.media_extraction_status, func.count(Ad.id))
            .group_by(Ad.media_extraction_status)
            .all()
        )

        # Type breakdown
        type_counts = dict(
            session.query(Ad.creative_type, func.count(Ad.id))
            .group_by(Ad.creative_type)
            .all()
        )

        # Pending extraction (missing image or thumbnail)
        pending = (
            session.query(func.count(Ad.id))
            .filter(
                Ad.snapshot_url.isnot(None),
                or_(Ad.image_url.is_(None), Ad.thumbnail_url.is_(None)),
                Ad.media_extraction_status.in_([
                    MediaExtractionStatus.PENDING,
                    MediaExtractionStatus.FAILED,
                    MediaExtractionStatus.ENRICHED,
                ]),
            )
            .scalar()
        )

        # Recent extractions (last 24h)
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_count = (
            session.query(func.count(Ad.id))
            .filter(Ad.updated_at >= cutoff, Ad.image_url.isnot(None))
            .scalar()
        )

        return {
            "total_ads": total,
            "coverage": {
                "image": with_image,
                "image_rate": round(with_image / total * 100, 1) if total else 0,
                "thumbnail": with_thumb,
                "thumbnail_rate": round(with_thumb / total * 100, 1) if total else 0,
                "video": with_video,
            },
            "pending_extraction": pending,
            "recent_extractions_24h": recent_count,
            "status_breakdown": status_counts,
            "type_breakdown": type_counts,
            "auto_schedule": "Every 2 hours (xx:30)",
        }
    finally:
        session.close()


# ── Per-Ad Media Composite (D19) ─────────────────────────────────────

@router.get("/ad/{ad_id}/all")
async def get_ad_all_media(ad_id: int):
    """Return all media info for a specific ad.

    Includes thumbnail, image, video, and LP screenshot status,
    quality scores, and availability.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")

        meta = ad.ad_metadata or {}
        result: dict = {"ad_id": ad_id}

        # -- Thumbnail --
        thumb_path = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
        thumb_info: dict = {
            "url": f"/api/v1/media/thumbnail/{ad_id}",
            "cached": os.path.exists(thumb_path),
        }
        if thumb_info["cached"]:
            tq = meta.get("thumbnail_quality")
            if isinstance(tq, dict) and "score" in tq:
                thumb_info["quality"] = tq["score"]
            else:
                # Quick quality estimate from file size
                fsize = os.path.getsize(thumb_path)
                thumb_info["quality"] = min(100, max(0, int(fsize / 1024)))
        result["thumbnail"] = thumb_info

        # -- Image --
        img_path = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
        img_info: dict = {
            "url": f"/api/v1/media/image/{ad_id}",
            "cached": os.path.exists(img_path),
        }
        if img_info["cached"]:
            fsize = os.path.getsize(img_path)
            # Basic quality from file validation
            try:
                with open(img_path, "rb") as fh:
                    hdr = fh.read(4)
                is_valid = hdr[:2] == b'\xff\xd8' or hdr[:4] == b'\x89PNG'
                img_info["quality"] = 90 if is_valid else 20
            except Exception as e:
                logger.debug("image_quality_check_failed: ad_id=%d err=%s", ad_id, e)
                img_info["quality"] = 0
        result["image"] = img_info

        # -- Video --
        video_info: dict = {
            "url": ad.video_url,
            "cached": False,
        }
        video_result = _find_video_path(ad_id)
        if video_result:
            video_info["cached"] = True

        # Add video analysis data if available
        va = meta.get("video_analysis")
        if isinstance(va, dict):
            if "duration_sec" in va:
                video_info["duration_sec"] = va["duration_sec"]
            if "format" in va:
                video_info["format"] = va["format"]
        elif ad.duration_seconds:
            video_info["duration_sec"] = ad.duration_seconds

        result["video"] = video_info

        # -- LP Screenshot --
        lp_screenshot_path = os.path.join(CACHE_DIR, "lp_screenshots", f"{ad_id}.png")
        lp_info: dict = {
            "url": f"/api/v1/media/lp-screenshot/{ad_id}",
            "available": os.path.exists(lp_screenshot_path),
        }
        result["lp_screenshot"] = lp_info

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("media_ad_all_error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get media info: {str(e)}")
    finally:
        session.close()


# ── LP Screenshot & HTML Serving Endpoints (D12) ────────────────────

@router.get("/lp-screenshot/{ad_id}")
async def get_lp_screenshot(ad_id: int):
    """Serve the cached LP screenshot for the given ad ID.

    Screenshots are stored as media_cache/lp_screenshots/{ad_id}.png.
    Returns 404 if no screenshot is available.
    """
    screenshot_path = os.path.join(LP_SCREENSHOT_DIR, f"{ad_id}.png")
    if not os.path.exists(screenshot_path):
        raise HTTPException(
            status_code=404,
            detail=f"No LP screenshot cached for ad {ad_id}",
        )

    return FileResponse(screenshot_path, media_type="image/png")


@router.get("/lp-html/{ad_id}")
async def get_lp_html(ad_id: int):
    """Serve the cached LP HTML for the given ad ID.

    HTML files are stored as media_cache/lp_html/{ad_id}.html.
    Served with text/html content type so it can be viewed in an iframe.
    Returns 404 if no HTML is available.
    """
    html_path = os.path.join(LP_HTML_DIR, f"{ad_id}.html")
    if not os.path.exists(html_path):
        raise HTTPException(
            status_code=404,
            detail=f"No LP HTML cached for ad {ad_id}",
        )

    return FileResponse(
        html_path,
        media_type="text/html",
        headers={
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "frame-ancestors 'self'",
        },
    )


# ── Reference Media for Scenario Builder (D16) ──────────────────

REFERENCE_DIR = os.path.join(CACHE_DIR, "reference")
SCENARIO_THUMB_DIR = os.path.join(CACHE_DIR, "scenario_thumbnails")


@router.get("/reference/{genre_en}")
async def get_reference_media(genre_en: str):
    """Return reference creative assets for a genre.

    Reads from the pre-generated reference_media.json index created
    by scripts/collect_reference_media.py.  Returns thumbnail URLs,
    scores, titles, and archetype tags for the top ads in a genre.
    Used by the scenario builder UI to show example creatives.
    """
    index_path = os.path.join(REFERENCE_DIR, "reference_media.json")

    if not os.path.exists(index_path):
        # If no index file, try to build response from database directly
        return await _build_reference_from_db(genre_en)

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("reference_media_index_read_error: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to read reference media index",
        )

    genres = index_data.get("genres", {})

    if genre_en not in genres:
        # Try database fallback
        return await _build_reference_from_db(genre_en)

    genre_data = genres[genre_en]
    return {
        "genre_en": genre_en,
        "label": genre_data.get("label", genre_en),
        "reference_ads": genre_data.get("reference_ads", []),
        "generated_at": index_data.get("generated_at"),
    }


async def _build_reference_from_db(genre_en: str):
    """Fallback: build reference data directly from database.

    Used when reference_media.json does not exist or does not contain
    the requested genre.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        all_ads = session.query(Ad).all()

        # Filter by genre and collect scores
        genre_ads = []
        for ad in all_ads:
            meta = ad.ad_metadata or {}
            fg_en = meta.get("fine_genre_en", "")
            if fg_en == genre_en:
                try:
                    score = float(meta.get("latest_hit_score", 0) or 0)
                except (ValueError, TypeError):
                    score = 0
                genre_ads.append((ad, score))

        if not genre_ads:
            return {
                "genre_en": genre_en,
                "label": genre_en,
                "reference_ads": [],
                "generated_at": None,
                "note": "No ads found for this genre",
            }

        # Sort by score descending, take top 5
        genre_ads.sort(key=lambda x: x[1], reverse=True)
        top_ads = genre_ads[:5]

        reference_ads = []
        for ad, score in top_ads:
            # Check cached media existence
            has_thumb = os.path.exists(
                os.path.join(CACHE_DIR, "thumbnails", f"{ad.id}.jpg")
            )
            has_image = os.path.exists(
                os.path.join(CACHE_DIR, "images", f"{ad.id}.jpg")
            )

            if not has_thumb and not has_image:
                continue

            entry = {
                "ad_id": ad.id,
                "thumbnail": f"/api/v1/media/thumbnail/{ad.id}",
                "image": f"/api/v1/media/image/{ad.id}",
                "score": round(score, 1),
                "title": ad.title or "",
                "archetype": "storytelling",
                "platform": ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform),
                "advertiser": ad.advertiser_name or "",
            }
            reference_ads.append(entry)

        return {
            "genre_en": genre_en,
            "label": genre_en,
            "reference_ads": reference_ads,
            "generated_at": None,
            "note": "Built from database (no pre-generated index)",
        }

    except Exception as e:
        logger.error("reference_from_db_error: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build reference data: {str(e)}",
        )
    finally:
        session.close()


# ── Scenario Export Endpoint (D16) ───────────────────────────────

class ScenarioExportRequest(BaseModel):
    scenario: dict
    format: str = "text"  # "text", "html", or "brief"


@router.post("/scenario-export")
async def scenario_export(request: ScenarioExportRequest):
    """Export a scenario as a downloadable file.

    Accepts a scenario JSON object and a format string.
    Generates formatted output and returns it as a downloadable file.

    Formats:
      - "text": Plain text with clear section headers
      - "html": Formatted HTML with color-coded sections
      - "brief": Creative brief format (concise, action-oriented)
    """
    scenario = request.scenario
    fmt = request.format.lower()

    if fmt not in ("text", "html", "brief"):
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Must be 'text', 'html', or 'brief'.",
        )

    # Extract scenario fields with safe defaults
    title = scenario.get("title", "Untitled Scenario")
    archetype = scenario.get("archetype", "custom")
    target_audience = scenario.get("target_audience", "")
    genre = scenario.get("genre", "")
    steps = scenario.get("steps", [])
    notes = scenario.get("notes", "")
    duration = scenario.get("duration", "")
    tone = scenario.get("tone", "")
    key_message = scenario.get("key_message", "")
    cta_text = scenario.get("cta_text", "")

    if fmt == "text":
        content, media_type, ext = _export_text(
            title, archetype, target_audience, genre, steps,
            notes, duration, tone, key_message, cta_text,
        )
    elif fmt == "html":
        content, media_type, ext = _export_html(
            title, archetype, target_audience, genre, steps,
            notes, duration, tone, key_message, cta_text,
        )
    else:  # brief
        content, media_type, ext = _export_brief(
            title, archetype, target_audience, genre, steps,
            notes, duration, tone, key_message, cta_text,
        )

    # Write to temp file for download
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_archetype = _safe_export_slug(archetype)
    filename = f"scenario_{safe_archetype}_{timestamp}{ext}"

    # Store in downloads dir
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
        background=BackgroundTask(_cleanup_file, file_path),
    )


def _export_text(title, archetype, target_audience, genre, steps,
                 notes, duration, tone, key_message, cta_text):
    """Generate plain text scenario export."""
    lines = []
    lines.append("=" * 60)
    lines.append("AD SCENARIO: %s" % title)
    lines.append("=" * 60)
    lines.append("")
    lines.append("Archetype:       %s" % archetype)
    if genre:
        lines.append("Genre:           %s" % genre)
    if target_audience:
        lines.append("Target Audience: %s" % target_audience)
    if duration:
        lines.append("Duration:        %s" % duration)
    if tone:
        lines.append("Tone:            %s" % tone)
    if key_message:
        lines.append("Key Message:     %s" % key_message)
    lines.append("")
    lines.append("-" * 60)
    lines.append("SCENARIO FLOW")
    lines.append("-" * 60)
    lines.append("")

    for i, step in enumerate(steps, 1):
        step_name = step.get("name", "Step %d" % i)
        step_content = step.get("content", "")
        step_duration = step.get("duration", "")
        step_visual = step.get("visual", "")

        lines.append("[Step %d] %s" % (i, step_name))
        if step_duration:
            lines.append("  Duration: %s" % step_duration)
        if step_content:
            lines.append("  Content:  %s" % step_content)
        if step_visual:
            lines.append("  Visual:   %s" % step_visual)
        lines.append("")

    if cta_text:
        lines.append("-" * 60)
        lines.append("CTA: %s" % cta_text)
        lines.append("")

    if notes:
        lines.append("-" * 60)
        lines.append("NOTES")
        lines.append("-" * 60)
        lines.append(notes)
        lines.append("")

    lines.append("=" * 60)
    lines.append("Generated: %s" % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    lines.append("=" * 60)

    return "\n".join(lines), "text/plain; charset=utf-8", ".txt"


def _export_html(title, archetype, target_audience, genre, steps,
                 notes, duration, tone, key_message, cta_text):
    """Generate HTML scenario export with color-coded sections."""
    # Step colors for visual distinction
    step_colors = [
        "#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336",
        "#00BCD4", "#795548", "#607D8B", "#E91E63", "#3F51B5",
    ]

    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append('<html lang="en">')
    html_parts.append("<head>")
    html_parts.append('<meta charset="UTF-8">')
    html_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    html_parts.append("<title>Scenario: %s</title>" % _html_escape(title))
    html_parts.append("<style>")
    html_parts.append("""
        body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #fafafa; color: #333; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 24px; }
        .header h1 { margin: 0 0 8px 0; font-size: 24px; }
        .header .meta { opacity: 0.85; font-size: 14px; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }
        .info-item { background: white; padding: 12px 16px; border-radius: 8px; border-left: 4px solid #667eea; }
        .info-item .label { font-size: 11px; text-transform: uppercase; color: #999; margin-bottom: 4px; }
        .info-item .value { font-size: 14px; font-weight: 500; }
        .flow-title { font-size: 18px; font-weight: 600; margin: 24px 0 16px; }
        .step { background: white; border-radius: 10px; padding: 20px; margin-bottom: 16px; border-left: 5px solid; position: relative; }
        .step .step-num { position: absolute; top: -8px; left: -8px; width: 28px; height: 28px; border-radius: 50%; color: white; font-size: 13px; font-weight: bold; display: flex; align-items: center; justify-content: center; }
        .step h3 { margin: 0 0 8px 24px; font-size: 16px; }
        .step .content { margin-left: 24px; color: #555; line-height: 1.6; }
        .step .visual { margin-top: 8px; margin-left: 24px; font-style: italic; color: #888; font-size: 13px; }
        .step .dur { margin-left: 24px; font-size: 12px; color: #aaa; margin-top: 4px; }
        .cta-box { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; margin: 24px 0; }
        .cta-box h3 { margin: 0 0 4px; font-size: 14px; opacity: 0.8; }
        .cta-box .cta-text { font-size: 20px; font-weight: 700; }
        .notes { background: #fff9c4; padding: 16px; border-radius: 8px; margin-top: 16px; }
        .notes h3 { margin: 0 0 8px; font-size: 14px; }
        .footer { text-align: center; color: #bbb; font-size: 12px; margin-top: 32px; }
    """)
    html_parts.append("</style>")
    html_parts.append("</head>")
    html_parts.append("<body>")

    # Header
    html_parts.append('<div class="header">')
    html_parts.append("<h1>%s</h1>" % _html_escape(title))
    html_parts.append('<div class="meta">Archetype: %s</div>' % _html_escape(archetype))
    html_parts.append("</div>")

    # Info grid
    info_items = []
    if genre:
        info_items.append(("Genre", genre))
    if target_audience:
        info_items.append(("Target Audience", target_audience))
    if duration:
        info_items.append(("Duration", duration))
    if tone:
        info_items.append(("Tone", tone))
    if key_message:
        info_items.append(("Key Message", key_message))

    if info_items:
        html_parts.append('<div class="info-grid">')
        for label, value in info_items:
            html_parts.append(
                '<div class="info-item">'
                '<div class="label">%s</div>'
                '<div class="value">%s</div>'
                '</div>' % (_html_escape(label), _html_escape(value))
            )
        html_parts.append("</div>")

    # Flow steps
    html_parts.append('<div class="flow-title">Scenario Flow</div>')
    for i, step in enumerate(steps):
        color = step_colors[i % len(step_colors)]
        step_name = step.get("name", "Step %d" % (i + 1))
        step_content = step.get("content", "")
        step_duration = step.get("duration", "")
        step_visual = step.get("visual", "")

        html_parts.append(
            '<div class="step" style="border-left-color: %s;">' % color
        )
        html_parts.append(
            '<div class="step-num" style="background: %s;">%d</div>' % (color, i + 1)
        )
        html_parts.append("<h3>%s</h3>" % _html_escape(step_name))
        if step_content:
            html_parts.append(
                '<div class="content">%s</div>' % _html_escape(step_content)
            )
        if step_visual:
            html_parts.append(
                '<div class="visual">Visual: %s</div>' % _html_escape(step_visual)
            )
        if step_duration:
            html_parts.append(
                '<div class="dur">Duration: %s</div>' % _html_escape(step_duration)
            )
        html_parts.append("</div>")

    # CTA
    if cta_text:
        html_parts.append('<div class="cta-box">')
        html_parts.append("<h3>Call to Action</h3>")
        html_parts.append('<div class="cta-text">%s</div>' % _html_escape(cta_text))
        html_parts.append("</div>")

    # Notes
    if notes:
        html_parts.append('<div class="notes">')
        html_parts.append("<h3>Notes</h3>")
        html_parts.append("<p>%s</p>" % _html_escape(notes))
        html_parts.append("</div>")

    # Footer
    html_parts.append('<div class="footer">')
    html_parts.append("Generated: %s" % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    html_parts.append("</div>")

    html_parts.append("</body>")
    html_parts.append("</html>")

    return "\n".join(html_parts), "text/html; charset=utf-8", ".html"


def _export_brief(title, archetype, target_audience, genre, steps,
                  notes, duration, tone, key_message, cta_text):
    """Generate creative brief format (concise, action-oriented)."""
    lines = []
    lines.append("CREATIVE BRIEF")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Project: %s" % title)
    lines.append("Format:  %s" % archetype)
    if duration:
        lines.append("Length:  %s" % duration)
    lines.append("")

    if target_audience or genre:
        lines.append("AUDIENCE")
        lines.append("-" * 20)
        if genre:
            lines.append("Category: %s" % genre)
        if target_audience:
            lines.append("Target:   %s" % target_audience)
        lines.append("")

    if key_message or tone:
        lines.append("MESSAGING")
        lines.append("-" * 20)
        if key_message:
            lines.append("Key Message: %s" % key_message)
        if tone:
            lines.append("Tone & Feel: %s" % tone)
        lines.append("")

    if steps:
        lines.append("CREATIVE DIRECTION")
        lines.append("-" * 20)
        for i, step in enumerate(steps, 1):
            step_name = step.get("name", "Step %d" % i)
            step_content = step.get("content", "")
            step_visual = step.get("visual", "")

            action_line = "%d. %s" % (i, step_name)
            if step_content:
                action_line += " -- %s" % step_content
            lines.append(action_line)

            if step_visual:
                lines.append("   [Visual: %s]" % step_visual)
        lines.append("")

    if cta_text:
        lines.append("CTA")
        lines.append("-" * 20)
        lines.append("Action: %s" % cta_text)
        lines.append("")

    if notes:
        lines.append("ADDITIONAL NOTES")
        lines.append("-" * 20)
        lines.append(notes)
        lines.append("")

    lines.append("---")
    lines.append("Date: %s" % datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    return "\n".join(lines), "text/plain; charset=utf-8", ".txt"


def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# ── Scenario Thumbnail Serving (D16) ────────────────────────────

@router.get("/scenario-thumbnail/{archetype}")
async def get_scenario_thumbnail(archetype: str):
    """Serve a scenario archetype SVG thumbnail.

    SVG thumbnails are generated by scripts/generate_scenario_thumbnails.py
    and stored in media_cache/scenario_thumbnails/{archetype}.svg.
    """
    # Sanitize archetype name
    safe_name = "".join(c for c in archetype if c.isalnum() or c == "_")
    if safe_name != archetype:
        raise HTTPException(status_code=400, detail="Invalid archetype name")

    svg_path = os.path.join(SCENARIO_THUMB_DIR, f"{safe_name}.svg")

    if not os.path.exists(svg_path):
        # Return a simple placeholder SVG
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" '
            'viewBox="0 0 320 200">'
            '<rect width="320" height="200" rx="8" fill="#f0f0f0" stroke="#e0e0e0"/>'
            '<text x="160" y="90" text-anchor="middle" font-family="Arial" '
            'font-size="14" fill="#999">%s</text>'
            '<text x="160" y="115" text-anchor="middle" font-family="Arial" '
            'font-size="12" fill="#ccc">No thumbnail generated</text>'
            '</svg>' % safe_name
        )
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"X-Fallback": "placeholder"},
        )

    return FileResponse(svg_path, media_type="image/svg+xml")


# ── Scenario Archetypes Index (D16) ─────────────────────────────

@router.get("/scenario-archetypes")
async def get_scenario_archetypes():
    """Return the list of available scenario archetypes with metadata.

    Reads from the scenario_archetypes.json index generated by
    scripts/generate_scenario_thumbnails.py.
    """
    index_path = os.path.join(SCENARIO_THUMB_DIR, "scenario_archetypes.json")

    if not os.path.exists(index_path):
        # Return built-in defaults if index hasn't been generated
        return {
            "archetypes": {
                "before_after": {
                    "title": "Before / After",
                    "steps": ["Hook", "Before", "After", "Proof", "CTA"],
                    "color": "#4CAF50",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/before_after",
                },
                "testimonial": {
                    "title": "Testimonial",
                    "steps": ["Hook", "Problem", "Voice", "Result", "CTA"],
                    "color": "#2196F3",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/testimonial",
                },
                "problem_solution": {
                    "title": "Problem-Solution",
                    "steps": ["Hook", "Problem", "Solution", "Proof", "CTA"],
                    "color": "#FF9800",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/problem_solution",
                },
                "demonstration": {
                    "title": "Demonstration",
                    "steps": ["Hook", "Setup", "Demo", "Result", "CTA"],
                    "color": "#9C27B0",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/demonstration",
                },
                "urgency_scarcity": {
                    "title": "Urgency / Scarcity",
                    "steps": ["Hook", "Value", "Urgency", "Offer", "CTA"],
                    "color": "#F44336",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/urgency_scarcity",
                },
                "educational": {
                    "title": "Educational",
                    "steps": ["Hook", "Question", "Lesson", "Insight", "CTA"],
                    "color": "#00BCD4",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/educational",
                },
                "comparison": {
                    "title": "Comparison",
                    "steps": ["Hook", "Option A", "Option B", "Winner", "CTA"],
                    "color": "#795548",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/comparison",
                },
                "storytelling": {
                    "title": "Storytelling",
                    "steps": ["Hook", "Setup", "Conflict", "Resolution", "CTA"],
                    "color": "#607D8B",
                    "thumbnail_url": "/api/v1/media/scenario-thumbnail/storytelling",
                },
            },
            "note": "Default archetypes (run generate_scenario_thumbnails.py to generate SVGs)",
        }

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("scenario_archetypes_read_error: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to read scenario archetypes index",
        )


# ── D20: Creative Intelligence & Visual Analysis ─────────────────────

@router.get("/compare/{ad_id_1}/{ad_id_2}")
async def compare_ads(ad_id_1: int, ad_id_2: int):
    """Return visual comparison data between two ads.

    Compares format, color scheme, and computes a visual similarity score
    from stored analysis metadata.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        ad1 = session.query(Ad).filter(Ad.id == ad_id_1).first()
        ad2 = session.query(Ad).filter(Ad.id == ad_id_2).first()

        if not ad1:
            raise HTTPException(status_code=404, detail="Ad %d not found" % ad_id_1)
        if not ad2:
            raise HTTPException(status_code=404, detail="Ad %d not found" % ad_id_2)

        def _extract_info(ad: Ad) -> dict:
            meta = ad.ad_metadata or {}
            cf = meta.get("creative_format", {})
            ca = meta.get("color_analysis", {})
            return {
                "id": ad.id,
                "thumbnail": "/api/v1/media/thumbnail/%d" % ad.id,
                "format": cf.get("type", ad.creative_type or "unknown"),
                "subtype": cf.get("subtype", "unknown"),
                "colors": ca.get("dominant_colors", []),
                "color_scheme": ca.get("scheme", "unknown"),
                "has_text": ca.get("has_text", False),
            }

        info1 = _extract_info(ad1)
        info2 = _extract_info(ad2)

        # Compute visual similarity
        similarity = 0.0
        checks = 0

        # Same format type
        same_format = info1["format"] == info2["format"]
        if same_format:
            similarity += 0.3
        checks += 1

        # Same subtype
        if info1["subtype"] == info2["subtype"]:
            similarity += 0.2
        checks += 1

        # Same color scheme
        same_scheme = info1["color_scheme"] == info2["color_scheme"]
        if same_scheme:
            similarity += 0.25
        checks += 1

        # Color overlap
        colors1 = set(info1["colors"])
        colors2 = set(info2["colors"])
        if colors1 and colors2:
            overlap = len(colors1 & colors2) / max(len(colors1 | colors2), 1)
            similarity += overlap * 0.15
        checks += 1

        # Text overlay match
        if info1["has_text"] == info2["has_text"]:
            similarity += 0.1
        checks += 1

        return {
            "ad1": info1,
            "ad2": info2,
            "visual_similarity": round(similarity, 2),
            "same_format": same_format,
            "same_color_scheme": same_scheme,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("compare_ads_error: %s", str(e))
        raise HTTPException(status_code=500, detail="Comparison failed: %s" % str(e))
    finally:
        session.close()


@router.get("/gallery")
async def media_gallery(
    genre: str | None = None,
    format: str | None = None,
    sort_by: str = "recency",
    page: int = 1,
    page_size: int = 20,
):
    """Return a paginated media gallery.

    Query params:
      - genre: filter by fine_genre_en
      - format: filter by creative format type (video|image)
      - sort_by: 'quality' or 'recency' (default)
      - page, page_size: pagination
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()

        items = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            fg = meta.get("fine_genre_en", "")
            cf = meta.get("creative_format", {})
            fmt_type = cf.get("type", ad.creative_type or "unknown") if isinstance(cf, dict) else "unknown"

            # Apply filters
            if genre and fg != genre:
                continue
            if format and fmt_type != format:
                continue

            # Quality score
            tq = meta.get("thumbnail_quality", {})
            quality_score = 0
            if isinstance(tq, dict) and "score" in tq:
                try:
                    quality_score = int(float(tq["score"]))
                except (ValueError, TypeError):
                    pass

            items.append({
                "ad_id": ad.id,
                "thumbnail_url": "/api/v1/media/thumbnail/%d" % ad.id,
                "title": ad.title or "",
                "genre": fg,
                "quality_score": quality_score,
                "format": fmt_type,
                "created_at": ad.created_at.isoformat() if ad.created_at else None,
            })

        # Sort
        if sort_by == "quality":
            items.sort(key=lambda x: x["quality_score"], reverse=True)
        else:
            items.sort(key=lambda x: x["created_at"] or "", reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
        }

    except Exception as e:
        logger.error("gallery_error: %s", str(e))
        raise HTTPException(status_code=500, detail="Gallery failed: %s" % str(e))
    finally:
        session.close()


# ── D21: Advanced Crawling & Data Collection ─────────────────────────

DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
)
CRAWL_CONFIG_PATH = os.path.join(DATA_DIR, "crawl_config.json")

_DEFAULT_CRAWL_CONFIG = {
    "schedule": "daily",
    "max_pages": 10,
    "platforms": ["facebook", "instagram"],
    "filters": {
        "min_impressions": 0,
        "categories": [],
    },
    "media_download": True,
    "dedup_enabled": True,
}


@router.get("/crawl-config")
async def get_crawl_config():
    """Return current crawl configuration from files."""
    if not os.path.exists(CRAWL_CONFIG_PATH):
        return {"config": _DEFAULT_CRAWL_CONFIG, "source": "default"}

    try:
        with open(CRAWL_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return {"config": config, "source": "file"}
    except (json.JSONDecodeError, OSError) as e:
        logger.error("crawl_config_read_error: %s", str(e))
        return {"config": _DEFAULT_CRAWL_CONFIG, "source": "default_fallback"}


class CrawlConfigUpdate(BaseModel):
    schedule: str | None = None
    max_pages: int | None = None
    platforms: list[str] | None = None
    filters: dict | None = None
    media_download: bool | None = None
    dedup_enabled: bool | None = None


@router.put("/crawl-config")
async def update_crawl_config(request: CrawlConfigUpdate):
    """Update crawl settings.

    Merges provided fields into the existing configuration
    and saves to data/crawl_config.json.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load existing config
    current = dict(_DEFAULT_CRAWL_CONFIG)
    if os.path.exists(CRAWL_CONFIG_PATH):
        try:
            with open(CRAWL_CONFIG_PATH, "r", encoding="utf-8") as f:
                current = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Merge updates
    update_data = request.model_dump(exclude_none=True)
    for key, value in update_data.items():
        current[key] = value

    current["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        with open(CRAWL_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
    except OSError as e:
        raise HTTPException(status_code=500, detail="Failed to save config: %s" % str(e))

    return {"config": current, "status": "updated"}


# ── D22: Media API Enhancement & Asset Pipeline ─────────────────────

@router.get("/search")
async def media_search(
    q: str | None = None,
    genre: str | None = None,
    format: str | None = None,
    quality_min: int = 0,
    page: int = 1,
    page_size: int = 20,
):
    """Search across all ads with media.

    Query params:
      - q: text search in titles
      - genre: filter by fine_genre_en
      - format: 'video' or 'image'
      - quality_min: minimum quality score (0-100)
      - page, page_size: pagination
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        items = []

        q_lower = q.lower() if q else None

        for ad in ads:
            meta = ad.ad_metadata or {}
            fg = meta.get("fine_genre_en", "")

            # Text search filter
            if q_lower:
                title_lower = (ad.title or "").lower()
                desc_lower = (ad.description or "").lower()
                if q_lower not in title_lower and q_lower not in desc_lower:
                    continue

            # Genre filter
            if genre and fg != genre:
                continue

            # Format filter
            cf = meta.get("creative_format", {})
            fmt_type = cf.get("type", ad.creative_type or "unknown") if isinstance(cf, dict) else "unknown"
            if format and fmt_type != format:
                continue

            # Quality filter
            tq = meta.get("thumbnail_quality", {})
            quality_score = 0
            if isinstance(tq, dict) and "score" in tq:
                try:
                    quality_score = int(float(tq["score"]))
                except (ValueError, TypeError):
                    pass
            if quality_score < quality_min:
                continue

            # Hit score
            try:
                hit_score = float(meta.get("latest_hit_score", 0) or 0)
            except (ValueError, TypeError):
                hit_score = 0

            has_video = bool(ad.video_url) or fmt_type == "video"

            items.append({
                "ad_id": ad.id,
                "title": ad.title or "",
                "genre": fg,
                "thumbnail_url": "/api/v1/media/thumbnail/%d" % ad.id,
                "image_url": "/api/v1/media/image/%d" % ad.id,
                "has_video": has_video,
                "quality_score": quality_score,
                "hit_score": round(hit_score, 1),
            })

        # Sort by hit_score descending
        items.sort(key=lambda x: x["hit_score"], reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except Exception as e:
        logger.error("media_search_error: %s", str(e))
        raise HTTPException(status_code=500, detail="Search failed: %s" % str(e))
    finally:
        session.close()


class MediaBatchRequest(BaseModel):
    ad_ids: list[int]
    include: list[str] | None = None  # ["thumbnail", "image", "video_url"]


@router.post("/batch")
async def media_batch(request: MediaBatchRequest):
    """Return all media URLs for given ads in one request.

    Body:
      - ad_ids: list of ad IDs
      - include: optional list of media types to include
        (thumbnail, image, video_url). Defaults to all.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    if not request.ad_ids:
        raise HTTPException(status_code=400, detail="ad_ids cannot be empty")
    if len(request.ad_ids) > 200:
        raise HTTPException(status_code=400, detail="Maximum 200 ads per batch")

    include = set(request.include or ["thumbnail", "image", "video_url"])

    session = SyncSessionLocal()
    try:
        ads = (
            session.query(Ad)
            .filter(Ad.id.in_(request.ad_ids))
            .all()
        )
        ad_map = {ad.id: ad for ad in ads}

        results = []
        for ad_id in request.ad_ids:
            ad = ad_map.get(ad_id)
            entry: dict = {"ad_id": ad_id}

            if "thumbnail" in include:
                thumb_path = os.path.join(CACHE_DIR, "thumbnails", "%d.jpg" % ad_id)
                entry["thumbnail_url"] = (
                    "/api/v1/media/thumbnail/%d" % ad_id
                    if os.path.exists(thumb_path) else None
                )

            if "image" in include:
                img_path = os.path.join(CACHE_DIR, "images", "%d.jpg" % ad_id)
                entry["image_url"] = (
                    "/api/v1/media/image/%d" % ad_id
                    if os.path.exists(img_path) else None
                )

            if "video_url" in include:
                entry["video_url"] = None
                if ad and ad.video_url:
                    entry["video_url"] = "/api/v1/media/video/%d" % ad_id
                else:
                    video = _find_video_path(ad_id)
                    if video:
                        entry["video_url"] = "/api/v1/media/video/%d" % ad_id

            entry["found"] = ad is not None
            results.append(entry)

        return {"items": results, "count": len(results)}

    except Exception as e:
        logger.error("media_batch_error: %s", str(e))
        raise HTTPException(status_code=500, detail="Batch failed: %s" % str(e))
    finally:
        session.close()


class AssetPackageRequest(BaseModel):
    ad_ids: list[int]
    format: str = "zip_manifest"


@router.post("/asset-package")
async def asset_package(request: AssetPackageRequest):
    """Return manifest of all downloadable assets for given ads.

    Includes thumbnails, images, LP screenshots if available.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    if not request.ad_ids:
        raise HTTPException(status_code=400, detail="ad_ids cannot be empty")
    if len(request.ad_ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 ads per package")

    session = SyncSessionLocal()
    try:
        ads = (
            session.query(Ad)
            .filter(Ad.id.in_(request.ad_ids))
            .all()
        )
        ad_map = {ad.id: ad for ad in ads}

        assets = []
        total_size = 0

        for ad_id in request.ad_ids:
            ad = ad_map.get(ad_id)
            if not ad:
                continue

            ad_assets: dict = {"ad_id": ad_id, "title": ad.title or "", "files": []}

            # Thumbnail
            thumb_path = os.path.join(CACHE_DIR, "thumbnails", "%d.jpg" % ad_id)
            if os.path.exists(thumb_path):
                size = os.path.getsize(thumb_path)
                total_size += size
                ad_assets["files"].append({
                    "type": "thumbnail",
                    "url": "/api/v1/media/thumbnail/%d" % ad_id,
                    "download_url": "/api/v1/media/download/%d" % ad_id,
                    "size_bytes": size,
                    "filename": "ad_%d_thumbnail.jpg" % ad_id,
                })

            # Image
            img_path = os.path.join(CACHE_DIR, "images", "%d.jpg" % ad_id)
            if os.path.exists(img_path):
                size = os.path.getsize(img_path)
                total_size += size
                ad_assets["files"].append({
                    "type": "image",
                    "url": "/api/v1/media/image/%d" % ad_id,
                    "size_bytes": size,
                    "filename": "ad_%d_image.jpg" % ad_id,
                })

            # Video
            video = _find_video_path(ad_id)
            if video:
                vpath, vmime = video
                size = os.path.getsize(vpath)
                total_size += size
                ext = vpath.rsplit(".", 1)[-1] if "." in vpath else "mp4"
                ad_assets["files"].append({
                    "type": "video",
                    "url": "/api/v1/media/video/%d" % ad_id,
                    "size_bytes": size,
                    "filename": "ad_%d_video.%s" % (ad_id, ext),
                })

            # LP Screenshot
            lp_path = os.path.join(CACHE_DIR, "lp_screenshots", "%d.png" % ad_id)
            if os.path.exists(lp_path):
                size = os.path.getsize(lp_path)
                total_size += size
                ad_assets["files"].append({
                    "type": "lp_screenshot",
                    "url": "/api/v1/media/lp-screenshot/%d" % ad_id,
                    "size_bytes": size,
                    "filename": "ad_%d_lp_screenshot.png" % ad_id,
                })

            if ad_assets["files"]:
                assets.append(ad_assets)

        return {
            "ads": assets,
            "total_ads": len(assets),
            "total_files": sum(len(a["files"]) for a in assets),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "bulk_download_url": "/api/v1/media/bulk-download",
        }

    except Exception as e:
        logger.error("asset_package_error: %s", str(e))
        raise HTTPException(status_code=500, detail="Asset package failed: %s" % str(e))
    finally:
        session.close()


@router.get("/timeline")
async def media_timeline(days: int = 30):
    """Return daily media cache statistics over a time period.

    Query params:
      - days: number of days to look back (default 30)
    """
    from datetime import timedelta

    if days < 1 or days > 365:
        days = 30

    now = datetime.now(timezone.utc)
    timeline = []

    thumb_dir = os.path.join(CACHE_DIR, "thumbnails")
    img_dir = os.path.join(CACHE_DIR, "images")

    # Collect file modification dates
    thumb_by_date: dict[str, int] = {}
    img_by_date: dict[str, int] = {}

    for dir_path, date_map, ext_filter in [
        (thumb_dir, thumb_by_date, ".jpg"),
        (img_dir, img_by_date, ".jpg"),
    ]:
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith(ext_filter):
                continue
            fpath = os.path.join(dir_path, fname)
            try:
                mtime = os.path.getmtime(fpath)
                day_str = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
                date_map[day_str] = date_map.get(day_str, 0) + 1
            except OSError:
                continue

    # Build timeline for requested period
    total_cached = 0
    for i in range(days, -1, -1):
        day = now - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")

        new_thumbs = thumb_by_date.get(day_str, 0)
        new_images = img_by_date.get(day_str, 0)
        total_cached += new_thumbs + new_images

        timeline.append({
            "date": day_str,
            "new_thumbnails": new_thumbs,
            "new_images": new_images,
            "total_cached": total_cached,
        })

    return {"timeline": timeline, "days": days}


# ── D23: Smart Thumbnail & Visual Content Pipeline ──────────────────

PLACEHOLDER_SVG_DIR = os.path.join(CACHE_DIR, "placeholders")
GRID_DIR = os.path.join(CACHE_DIR, "grids")


@router.get("/placeholder/{ad_id}")
async def get_smart_placeholder(ad_id: int):
    """Return smart SVG placeholder for ads without thumbnails.

    Includes title, genre color, and score info embedded in the SVG.
    Falls back to a generic placeholder if no pre-generated SVG exists.
    """
    # Check if pre-generated placeholder exists
    svg_path = os.path.join(PLACEHOLDER_SVG_DIR, "%d.svg" % ad_id)
    if os.path.exists(svg_path):
        return FileResponse(svg_path, media_type="image/svg+xml")

    # Generate on-the-fly from DB data
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")

        meta = ad.ad_metadata or {}
        genre = meta.get("fine_genre_en", "default")
        title = ad.title or "Untitled"
        advertiser = ad.advertiser_name or ""
        platform = ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform)

        try:
            score = float(meta.get("latest_hit_score", 0) or 0)
        except (ValueError, TypeError):
            score = 0

        # Genre colors
        genre_color_map = {
            "skincare": ("#FFF0F5", "#E91E63"),
            "supplement": ("#F1F8E9", "#8BC34A"),
            "diet": ("#E8F5E9", "#4CAF50"),
            "cosmetics": ("#FCE4EC", "#F06292"),
            "fitness": ("#FFF3E0", "#FF9800"),
        }
        bg, accent = genre_color_map.get(genre, ("#F5F5F5", "#9E9E9E"))

        # Truncate title
        title_display = _html_escape(title[:35] + "..." if len(title) > 35 else title)
        adv_display = _html_escape(advertiser[:30]) if advertiser else ""
        genre_display = _html_escape(genre.replace("_", " ").title()[:20])

        # Score badge
        score_svg = ""
        if score > 0:
            badge_color = "#4CAF50" if score >= 70 else "#FF9800" if score >= 40 else "#F44336"
            score_svg = (
                '<rect x="340" y="12" width="48" height="24" rx="12" fill="%s"/>'
                '<text x="364" y="29" text-anchor="middle" font-family="Arial" '
                'font-size="11" font-weight="bold" fill="white">%.0f</text>'
                % (badge_color, score)
            )

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" '
            'viewBox="0 0 400 300">'
            '<rect width="400" height="300" rx="8" fill="%s"/>'
            '<rect width="400" height="4" fill="%s"/>'
            '%s'
            '<text x="200" y="70" text-anchor="middle" font-family="Arial" '
            'font-size="12" fill="%s" opacity="0.7">%s</text>'
            '<rect x="160" y="90" width="80" height="60" rx="8" fill="none" '
            'stroke="%s" stroke-width="2" opacity="0.3"/>'
            '<text x="200" y="185" text-anchor="middle" font-family="Arial" '
            'font-size="14" font-weight="600" fill="#424242">%s</text>'
            '<text x="200" y="210" text-anchor="middle" font-family="Arial" '
            'font-size="11" fill="#666" opacity="0.6">%s</text>'
            '<text x="200" y="291" text-anchor="middle" font-family="Arial" '
            'font-size="10" fill="#999">Ad #%d | %s</text>'
            '</svg>'
            % (bg, accent, score_svg, accent, genre_display,
               accent, title_display, adv_display, ad_id, platform)
        )

        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"X-Source": "generated"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("placeholder_error: %s", str(e))
        raise HTTPException(status_code=500, detail="Placeholder failed: %s" % str(e))
    finally:
        session.close()


@router.get("/grid/{genre}")
async def get_genre_grid(genre: str):
    """Return composite thumbnail grid for a genre.

    First checks for a pre-generated image grid (JPG), then falls
    back to an SVG grid.
    """
    # Sanitize
    safe_genre = "".join(c for c in genre if c.isalnum() or c == "_")
    if safe_genre != genre:
        raise HTTPException(status_code=400, detail="Invalid genre name")

    # Try JPG grid first (from Pillow)
    jpg_path = os.path.join(GRID_DIR, "%s.jpg" % safe_genre)
    if os.path.exists(jpg_path):
        return FileResponse(jpg_path, media_type="image/jpeg")

    # Try SVG grid
    svg_path = os.path.join(GRID_DIR, "%s.svg" % safe_genre)
    if os.path.exists(svg_path):
        return FileResponse(svg_path, media_type="image/svg+xml")

    raise HTTPException(
        status_code=404,
        detail="No grid available for genre '%s'. Run generate_thumbnail_grid.py first." % genre,
    )


@router.get("/thumbnail-strip/{genre}")
async def get_thumbnail_strip(genre: str):
    """Return horizontal strip of top 5 thumbnails for a genre.

    Generates an SVG strip showing the top-scoring ads' thumbnails
    for genre preview cards.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    safe_genre = "".join(c for c in genre if c.isalnum() or c == "_")

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()

        # Filter and score
        genre_ads = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            if meta.get("fine_genre_en", "") != safe_genre:
                continue
            try:
                score = float(meta.get("latest_hit_score", 0) or 0)
            except (ValueError, TypeError):
                score = 0
            genre_ads.append((ad, score))

        if not genre_ads:
            raise HTTPException(
                status_code=404,
                detail="No ads found for genre '%s'" % genre,
            )

        # Sort by score, take top 5
        genre_ads.sort(key=lambda x: x[1], reverse=True)
        top5 = genre_ads[:5]

        cell_w = 120
        cell_h = 90
        gap = 8
        total_w = len(top5) * (cell_w + gap) - gap + 20
        total_h = cell_h + 20

        genre_colors = {
            "skincare": "#E91E63", "supplement": "#8BC34A",
            "diet": "#4CAF50", "cosmetics": "#F06292",
            "fitness": "#FF9800", "dental": "#5C6BC0",
        }
        accent = genre_colors.get(safe_genre, "#9E9E9E")

        parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="%d" height="%d" viewBox="0 0 %d %d">'
            % (total_w, total_h, total_w, total_h),
            '<rect width="%d" height="%d" rx="8" fill="#fafafa"/>'
            % (total_w, total_h),
        ]

        for i, (ad, score) in enumerate(top5):
            x = 10 + i * (cell_w + gap)
            y = 10

            # Check if thumbnail exists
            has_thumb = os.path.exists(
                os.path.join(CACHE_DIR, "thumbnails", "%d.jpg" % ad.id)
            )

            # Cell background
            parts.append(
                '<rect x="%d" y="%d" width="%d" height="%d" rx="6" '
                'fill="%s" stroke="%s" stroke-width="1"/>'
                % (x, y, cell_w, cell_h,
                   "#ffffff" if has_thumb else "#f5f5f5",
                   accent if has_thumb else "#e0e0e0")
            )

            # Content
            title = _html_escape((ad.title or "")[:15])
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" '
                'font-size="9" fill="#666">%s</text>'
                % (x + cell_w // 2, y + cell_h // 2 - 5, title)
            )

            if has_thumb:
                parts.append(
                    '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" '
                    'font-size="8" fill="%s">[cached]</text>'
                    % (x + cell_w // 2, y + cell_h // 2 + 8, accent)
                )

            # Score badge
            if score > 0:
                badge_color = "#4CAF50" if score >= 70 else "#FF9800" if score >= 40 else "#F44336"
                parts.append(
                    '<rect x="%d" y="%d" width="28" height="16" rx="8" fill="%s"/>'
                    % (x + cell_w - 34, y + 4, badge_color)
                )
                parts.append(
                    '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" '
                    'font-size="9" font-weight="bold" fill="white">%.0f</text>'
                    % (x + cell_w - 20, y + 15, score)
                )

        parts.append('</svg>')
        svg_content = '\n'.join(parts)

        return Response(
            content=svg_content,
            media_type="image/svg+xml",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("thumbnail_strip_error: %s", str(e))
        raise HTTPException(status_code=500, detail="Strip failed: %s" % str(e))
    finally:
        session.close()
