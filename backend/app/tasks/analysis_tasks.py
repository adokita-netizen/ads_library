"""Video analysis Celery tasks."""

import tempfile
from pathlib import Path

import structlog

from app.core.config import get_settings
from app.core.database import SyncSessionLocal
from app.core.storage import get_storage_client
from app.models.ad import Ad, AdStatusEnum
from app.models.analysis import (
    AdAnalysis,
    DetectedObject,
    SceneBoundary,
    TextDetection,
    Transcription,
)
from app.tasks.worker import celery_app

logger = structlog.get_logger()
settings = get_settings()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_ad_task(self, ad_id: int):
    """Full analysis pipeline for a single ad."""
    logger.info("analysis_task_started", ad_id=ad_id, task_id=self.request.id)

    session = SyncSessionLocal()
    try:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            logger.error("ad_not_found", ad_id=ad_id)
            return {"error": "Ad not found"}

        ad.status = AdStatusEnum.PROCESSING
        session.commit()

        # Download video to temp file
        video_path = _download_video(ad)
        if not video_path:
            ad.status = AdStatusEnum.FAILED
            session.commit()
            return {"error": "Could not download video"}

        try:
            # Run video analysis
            video_result = _run_video_analysis(video_path)

            # Run audio analysis
            audio_result = _run_audio_analysis(video_path)

            # Save analysis results
            _save_analysis(session, ad, video_result, audio_result)

            ad.status = AdStatusEnum.ANALYZED
            if video_result.get("metadata"):
                ad.duration_seconds = video_result["metadata"].get("duration_seconds")
                ad.resolution_width = video_result["metadata"].get("width")
                ad.resolution_height = video_result["metadata"].get("height")

            session.commit()

            logger.info("analysis_task_completed", ad_id=ad_id)
            return {"status": "completed", "ad_id": ad_id}

        finally:
            # Cleanup temp files
            if video_path and Path(video_path).exists():
                Path(video_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error("analysis_task_failed", ad_id=ad_id, error=str(e))
        session.rollback()

        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if ad:
            ad.status = AdStatusEnum.FAILED
            session.commit()

        raise self.retry(exc=e)

    finally:
        session.close()


def _download_video(ad: Ad) -> str | None:
    """Download video from storage or URL."""
    try:
        if ad.s3_key:
            storage = get_storage_client()
            temp_dir = tempfile.mkdtemp()
            video_path = str(Path(temp_dir) / "video.mp4")
            storage.download_file(ad.s3_key, video_path)
            return video_path

        elif ad.video_url:
            import httpx
            response = httpx.get(ad.video_url, timeout=60, follow_redirects=True)
            response.raise_for_status()

            temp_dir = tempfile.mkdtemp()
            video_path = str(Path(temp_dir) / "video.mp4")
            Path(video_path).write_bytes(response.content)
            return video_path

    except Exception as e:
        logger.error("video_download_failed", ad_id=ad.id, error=str(e))

    return None


def _run_video_analysis(video_path: str) -> dict:
    """Run video analysis pipeline."""
    try:
        from app.services.cv.video_analyzer import VideoAnalyzer
        analyzer = VideoAnalyzer()
        result = analyzer.analyze_video(video_path)
        return result.to_dict()
    except Exception as e:
        logger.error("video_analysis_failed", error=str(e))
        return {}


def _run_audio_analysis(video_path: str) -> dict:
    """Run audio analysis pipeline."""
    try:
        from app.services.cv.frame_extractor import FrameExtractor
        from app.services.audio.audio_analyzer import AudioAnalyzer

        extractor = FrameExtractor()
        audio_path = extractor.extract_audio(video_path)

        analyzer = AudioAnalyzer()
        result = analyzer.analyze_audio(audio_path)

        # Cleanup audio file
        Path(audio_path).unlink(missing_ok=True)

        return result.to_dict()
    except Exception as e:
        logger.error("audio_analysis_failed", error=str(e))
        return {}


def _save_analysis(session, ad: Ad, video_result: dict, audio_result: dict):
    """Save analysis results to database."""
    # Check for existing analysis
    existing = session.query(AdAnalysis).filter(AdAnalysis.ad_id == ad.id).first()
    if existing:
        session.delete(existing)
        session.flush()

    scene_data = video_result.get("scene_analysis", {})
    person_data = video_result.get("person_analysis", {})
    product_data = video_result.get("product_analysis", {})
    text_data = video_result.get("text_analysis", {})
    comp_data = video_result.get("composition_summary", {})
    color_data = video_result.get("color_summary", {})
    hook_data = video_result.get("hook_analysis", {})

    transcript_data = audio_result.get("transcription", {})
    sentiment_data = audio_result.get("sentiment", {})
    keyword_data = audio_result.get("keywords", {})
    tone_data = audio_result.get("ad_tone", {})

    analysis = AdAnalysis(
        ad_id=ad.id,
        total_scenes=scene_data.get("total_scenes"),
        avg_scene_duration=scene_data.get("avg_scene_duration"),
        scene_transitions=scene_data.get("transition_counts"),
        face_closeup_ratio=person_data.get("face_closeup_ratio"),
        text_overlay_ratio=text_data.get("avg_text_overlay_ratio"),
        product_display_ratio=product_data.get("product_display_ratio"),
        is_ugc_style=None,
        has_narration=bool(transcript_data.get("full_text")),
        has_subtitles=text_data.get("has_subtitles"),
        hook_type=hook_data.get("hook_pacing"),
        hook_score=None,
        cta_text=", ".join(keyword_data.get("cta_phrases", [])) or None,
        overall_sentiment=sentiment_data.get("overall_sentiment"),
        sentiment_score=sentiment_data.get("overall_score"),
        emotion_breakdown=sentiment_data.get("emotion_summary"),
        dominant_color_palette=color_data.get("dominant_palette"),
        color_temperature=color_data.get("color_temperature"),
        full_transcript=transcript_data.get("full_text"),
        keywords=keyword_data.get("keywords"),
        raw_analysis={
            "video_analysis": video_result,
            "audio_analysis": audio_result,
        },
    )

    session.add(analysis)
    session.flush()

    # Save detected objects
    for obj in video_result.get("detected_objects", []):
        detected = DetectedObject(
            analysis_id=analysis.id,
            frame_number=obj.get("frame_number", 0),
            timestamp_seconds=obj.get("timestamp_seconds", 0),
            class_name=obj.get("class_name", ""),
            confidence=obj.get("confidence", 0),
            bbox_x=obj.get("bbox_x", 0),
            bbox_y=obj.get("bbox_y", 0),
            bbox_width=obj.get("bbox_width", 0),
            bbox_height=obj.get("bbox_height", 0),
        )
        session.add(detected)

    # Save transcriptions
    for seg in transcript_data.get("segments", []):
        transcription = Transcription(
            analysis_id=analysis.id,
            text=seg.get("text", ""),
            language=transcript_data.get("language"),
            start_time_ms=seg.get("start_time_ms", 0),
            end_time_ms=seg.get("end_time_ms", 0),
            confidence=seg.get("confidence", 0),
        )
        session.add(transcription)

    # Save scene boundaries
    for scene in scene_data.get("scenes", []):
        boundary = SceneBoundary(
            analysis_id=analysis.id,
            scene_number=scene.get("scene_number", 0),
            start_time_seconds=scene.get("start", 0),
            end_time_seconds=scene.get("end", 0),
            duration_seconds=scene.get("duration", 0),
        )
        session.add(boundary)
