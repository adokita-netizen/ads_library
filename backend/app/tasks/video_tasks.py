"""Video intelligence Celery tasks (D-R2-6)."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.core.storage import get_storage_client
from app.models.ad import Ad
from app.services.thumbnail_selector import ThumbnailSelector
from app.services.video_pipeline import VideoPipeline

logger = structlog.get_logger()

try:
    from app.tasks.worker import celery_app

    def _task_decorator(*args, **kwargs):
        return celery_app.task(*args, **kwargs)
except Exception:  # pragma: no cover
    # Local fallback when Celery dependencies are not installed.
    def _task_decorator(*args, **kwargs):
        def _wrap(func):
            return func

        return _wrap


def _download_video_to_temp(ad: Ad) -> str | None:
    """Download video from storage or URL to a local temp file."""
    tmp_dir = tempfile.mkdtemp(prefix=f"video-intel-{ad.id}-")
    video_path = str(Path(tmp_dir) / "video.mp4")
    try:
        if ad.video_s3_key:
            storage = get_storage_client()
            storage.download_file(ad.video_s3_key, video_path)
            return video_path
        if ad.video_url:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                with client.stream("GET", ad.video_url) as response:
                    response.raise_for_status()
                    with open(video_path, "wb") as f:
                        for chunk in response.iter_bytes(1024 * 512):
                            if chunk:
                                f.write(chunk)
            return video_path
    except Exception as e:
        logger.warning("video_intel_download_failed", ad_id=ad.id, error=str(e))
    return None


def _cleanup_temp_file(video_path: str | None) -> None:
    if not video_path:
        return
    try:
        p = Path(video_path)
        p.unlink(missing_ok=True)
        if p.parent.exists():
            p.parent.rmdir()
    except Exception:
        pass


def _mark_video_analysis_skipped(session, ad: Ad, reason: str) -> None:
    meta = dict(ad.ad_metadata or {})
    meta["video_analyzed"] = False
    meta["video_analysis_status"] = "skipped"
    meta["video_analysis_reason"] = reason
    meta["video_analyzed_at"] = datetime.now(timezone.utc).isoformat()
    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")
    session.commit()


@_task_decorator(bind=True, max_retries=2, default_retry_delay=60)
def analyze_video_task(self=None, ad_id: int | None = None):
    """Analyze video: keyframes, scenes, best thumbnail selection."""
    if ad_id is None:
        return {"status": "skipped", "reason": "missing_ad_id"}
    session = SyncSessionLocal()
    video_path = None
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad or not ad.video_url:
            if ad:
                _mark_video_analysis_skipped(session, ad, "no_video")
            return {"status": "skipped", "reason": "no_video", "ad_id": ad_id}

        video_path = _download_video_to_temp(ad)
        if not video_path or not os.path.exists(video_path):
            _mark_video_analysis_skipped(session, ad, "download_failed")
            return {"status": "skipped", "reason": "download_failed", "ad_id": ad_id}

        pipeline = VideoPipeline()
        selector = ThumbnailSelector()

        frames = pipeline.extract_keyframes(video_path, max_frames=5)
        scenes = pipeline.detect_scenes(video_path)
        best = selector.select_best(frames)

        if best:
            thumb_bytes = selector.encode_thumbnail_bytes(best["frame"])
            if thumb_bytes:
                try:
                    storage = get_storage_client()
                    thumb_key = f"thumbnails/video_intel_{ad.id}.jpg"
                    storage.upload_bytes(thumb_key, thumb_bytes, content_type="image/jpeg")
                    ad.thumbnail_s3_key = thumb_key
                    if not ad.thumbnail_url:
                        ad.thumbnail_url = f"s3://{thumb_key}"
                except Exception as e:
                    logger.warning("video_intel_thumbnail_upload_failed", ad_id=ad_id, error=str(e))

        meta = dict(ad.ad_metadata or {})
        meta["video_analyzed"] = True
        meta["video_analysis_status"] = "completed"
        meta["video_analyzed_at"] = datetime.now(timezone.utc).isoformat()
        meta["frame_count"] = len(frames)
        meta["scene_count"] = len(scenes)
        meta["best_thumbnail_frame"] = int(best["frame_idx"]) if best else None
        meta["video_quality"] = max((float(f.get("quality_score", 0.0)) for f in frames), default=0.0)
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        session.commit()

        return {
            "status": "completed",
            "ad_id": ad_id,
            "frames": len(frames),
            "scenes": len(scenes),
        }
    except Exception as e:
        session.rollback()
        logger.error("video_intel_task_failed", ad_id=ad_id, error=str(e))
        raise self.retry(exc=e)
    finally:
        _cleanup_temp_file(video_path)
        session.close()


@_task_decorator(bind=True, max_retries=1, default_retry_delay=60)
def analyze_new_videos_task(self=None, limit: int = 50):
    """Analyze newly discovered video ads that are not analyzed yet."""
    session = SyncSessionLocal()
    try:
        rows = session.execute(
            text(
                """
                SELECT id
                FROM ads
                WHERE video_url IS NOT NULL
                  AND (
                    metadata IS NULL
                    OR json_extract(metadata, '$.video_analyzed') IS NULL
                    OR json_extract(metadata, '$.video_analyzed') = 0
                  )
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        ).fetchall()
        ad_ids = [int(r[0]) for r in rows]
    finally:
        session.close()

    results = {"status": "completed", "target_count": len(ad_ids), "ok": 0, "skipped": 0, "failed": 0, "ad_ids": ad_ids}
    for ad_id in ad_ids:
        try:
            r = analyze_video_task(ad_id=ad_id)
            if isinstance(r, dict) and r.get("status") == "completed":
                results["ok"] += 1
            elif isinstance(r, dict) and r.get("status") == "skipped":
                results["skipped"] += 1
            else:
                results["failed"] += 1
        except Exception as e:
            logger.error("analyze_new_videos_item_failed", ad_id=ad_id, error=str(e))
            results["failed"] += 1

    return results


@_task_decorator(bind=True, max_retries=0)
def report_video_analysis_task(self=None, sample_limit: int = 20):
    """Return summary metrics for video analysis coverage and skip reasons."""
    session = SyncSessionLocal()
    try:
        totals = session.execute(
            text(
                """
                SELECT
                  SUM(CASE WHEN video_url IS NOT NULL THEN 1 ELSE 0 END) AS total_video_ads,
                  SUM(CASE WHEN json_extract(metadata,'$.video_analyzed') = 1 THEN 1 ELSE 0 END) AS analyzed_true,
                  SUM(CASE WHEN json_extract(metadata,'$.video_analysis_status') = 'skipped' THEN 1 ELSE 0 END) AS skipped_count
                FROM ads
                """
            )
        ).fetchone()

        reasons = session.execute(
            text(
                """
                SELECT json_extract(metadata,'$.video_analysis_reason') AS reason, COUNT(*) AS cnt
                FROM ads
                WHERE json_extract(metadata,'$.video_analysis_reason') IS NOT NULL
                GROUP BY json_extract(metadata,'$.video_analysis_reason')
                ORDER BY cnt DESC
                """
            )
        ).fetchall()

        samples = session.execute(
            text(
                """
                SELECT id, external_id, json_extract(metadata,'$.video_analysis_reason') AS reason
                FROM ads
                WHERE json_extract(metadata,'$.video_analysis_reason') IS NOT NULL
                ORDER BY id DESC
                LIMIT :limit
                """
            ),
            {"limit": int(sample_limit)},
        ).fetchall()
    finally:
        session.close()

    total_video_ads = int(totals[0] or 0)
    analyzed_true = int(totals[1] or 0)
    skipped_count = int(totals[2] or 0)
    coverage = (analyzed_true / total_video_ads * 100.0) if total_video_ads else 0.0

    return {
        "status": "completed",
        "total_video_ads": total_video_ads,
        "video_analyzed_true": analyzed_true,
        "video_skipped_count": skipped_count,
        "analysis_coverage_pct": round(coverage, 2),
        "skip_reasons": [{"reason": r[0], "count": int(r[1])} for r in reasons],
        "recent_skipped_samples": [
            {"ad_id": int(r[0]), "external_id": r[1], "reason": r[2]} for r in samples
        ],
    }


@_task_decorator(bind=True, max_retries=0)
def daily_video_ops_task(self=None, analyze_limit: int = 50, sample_limit: int = 20):
    """Daily operation: analyze new videos then emit coverage report."""
    analyze_result = analyze_new_videos_task(limit=analyze_limit)
    report_result = report_video_analysis_task(sample_limit=sample_limit)
    return {
        "status": "completed",
        "analyze_new_videos": analyze_result,
        "report_video_analysis": report_result,
    }
