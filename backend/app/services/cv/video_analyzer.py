"""Unified video analysis pipeline orchestrating all CV modules."""

from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.services.cv.color_analyzer import ColorAnalyzer
from app.services.cv.composition_analyzer import CompositionAnalyzer
from app.services.cv.frame_extractor import ExtractedFrame, FrameExtractor, VideoMetadata
from app.services.cv.object_detector import ObjectDetector
from app.services.cv.ocr_engine import OCREngine
from app.services.cv.scene_detector import SceneDetector

logger = structlog.get_logger()


@dataclass
class VideoAnalysisResult:
    """Complete video analysis result from all CV modules."""

    # Video metadata
    metadata: Optional[VideoMetadata] = None

    # Scene analysis
    scene_analysis: dict = field(default_factory=dict)
    hook_analysis: dict = field(default_factory=dict)

    # Object detection
    object_analysis: dict = field(default_factory=dict)
    person_analysis: dict = field(default_factory=dict)
    product_analysis: dict = field(default_factory=dict)

    # OCR / Text
    text_analysis: dict = field(default_factory=dict)

    # Composition
    composition_summary: dict = field(default_factory=dict)

    # Color
    color_summary: dict = field(default_factory=dict)

    # Frames info
    total_frames_extracted: int = 0
    total_keyframes: int = 0

    def to_dict(self) -> dict:
        return {
            "metadata": {
                "duration_seconds": self.metadata.duration_seconds,
                "fps": self.metadata.fps,
                "resolution": f"{self.metadata.width}x{self.metadata.height}",
                "file_size_bytes": self.metadata.file_size_bytes,
            } if self.metadata else None,
            "scene_analysis": self.scene_analysis,
            "hook_analysis": self.hook_analysis,
            "object_analysis": self.object_analysis,
            "person_analysis": self.person_analysis,
            "product_analysis": self.product_analysis,
            "text_analysis": self.text_analysis,
            "composition_summary": self.composition_summary,
            "color_summary": self.color_summary,
            "total_frames_extracted": self.total_frames_extracted,
            "total_keyframes": self.total_keyframes,
        }


class VideoAnalyzer:
    """Unified video analysis pipeline."""

    def __init__(
        self,
        frame_extractor: Optional[FrameExtractor] = None,
        scene_detector: Optional[SceneDetector] = None,
        object_detector: Optional[ObjectDetector] = None,
        ocr_engine: Optional[OCREngine] = None,
        composition_analyzer: Optional[CompositionAnalyzer] = None,
        color_analyzer: Optional[ColorAnalyzer] = None,
    ):
        self.frame_extractor = frame_extractor or FrameExtractor()
        self.scene_detector = scene_detector or SceneDetector()
        self.object_detector = object_detector or ObjectDetector()
        self.ocr_engine = ocr_engine or OCREngine()
        self.composition_analyzer = composition_analyzer or CompositionAnalyzer()
        self.color_analyzer = color_analyzer or ColorAnalyzer()

    def analyze_video(
        self,
        video_path: str,
        enable_object_detection: bool = True,
        enable_ocr: bool = True,
        enable_composition: bool = True,
        enable_color: bool = True,
    ) -> VideoAnalysisResult:
        """Run full video analysis pipeline."""
        result = VideoAnalysisResult()

        logger.info("video_analysis_started", path=video_path)

        # Step 1: Get video metadata
        try:
            result.metadata = self.frame_extractor.get_video_metadata(video_path)
            logger.info("metadata_extracted", duration=result.metadata.duration_seconds)
        except Exception as e:
            logger.error("metadata_extraction_failed", error=str(e))
            return result

        # Step 2: Extract frames
        frames = self.frame_extractor.extract_frames(video_path)
        result.total_frames_extracted = len(frames)

        # Step 3: Extract keyframes
        keyframes = self.frame_extractor.extract_keyframes(video_path)
        result.total_keyframes = len(keyframes)

        # Step 4: Scene detection
        try:
            scenes = self.scene_detector.detect_scenes(video_path)
            result.scene_analysis = self.scene_detector.analyze_scene_pacing(scenes)
            result.hook_analysis = self.scene_detector.get_hook_analysis(scenes)
        except Exception as e:
            logger.error("scene_detection_failed", error=str(e))

        # Prepare frame tuples for batch processing
        frame_tuples = [
            (f.image, f.frame_number, f.timestamp_seconds) for f in frames
        ]

        # Step 5: Object detection
        if enable_object_detection and frame_tuples:
            try:
                detection_results = self.object_detector.detect_batch(frame_tuples)
                result.person_analysis = self.object_detector.analyze_person_presence(detection_results)
                result.product_analysis = self.object_detector.analyze_product_display(detection_results)
                result.object_analysis = {
                    "total_detections": sum(
                        len(r.detections) for r in detection_results
                    ),
                    "frames_with_detections": sum(
                        1 for r in detection_results if r.detections
                    ),
                }
            except Exception as e:
                logger.error("object_detection_failed", error=str(e))

        # Step 6: OCR
        if enable_ocr and frame_tuples:
            try:
                ocr_results = self.ocr_engine.detect_batch(frame_tuples)
                result.text_analysis = self.ocr_engine.analyze_text_patterns(ocr_results)
            except Exception as e:
                logger.error("ocr_failed", error=str(e))

        # Step 7: Composition analysis
        if enable_composition and frame_tuples:
            try:
                comp_results = self.composition_analyzer.analyze_batch(frame_tuples)
                result.composition_summary = self.composition_analyzer.summarize(comp_results)
            except Exception as e:
                logger.error("composition_analysis_failed", error=str(e))

        # Step 8: Color analysis
        if enable_color and frame_tuples:
            try:
                color_results = self.color_analyzer.analyze_batch(frame_tuples)
                result.color_summary = self.color_analyzer.summarize(color_results)
            except Exception as e:
                logger.error("color_analysis_failed", error=str(e))

        logger.info(
            "video_analysis_completed",
            path=video_path,
            frames=result.total_frames_extracted,
            scenes=result.scene_analysis.get("total_scenes", 0),
        )

        return result

    def analyze_hook(self, video_path: str, seconds: float = 3.0) -> dict:
        """Analyze just the first N seconds (hook section)."""
        hook_frames = self.frame_extractor.extract_first_n_seconds(video_path, seconds=seconds)

        if not hook_frames:
            return {"error": "Could not extract hook frames"}

        frame_tuples = [(f.image, f.frame_number, f.timestamp_seconds) for f in hook_frames]

        # OCR for hook text
        ocr_results = self.ocr_engine.detect_batch(frame_tuples)
        text_analysis = self.ocr_engine.analyze_text_patterns(ocr_results)

        # Object detection
        detection_results = self.object_detector.detect_batch(frame_tuples)

        # Composition
        comp_results = self.composition_analyzer.analyze_batch(frame_tuples)

        return {
            "hook_duration_seconds": seconds,
            "frames_analyzed": len(hook_frames),
            "text": {
                "hook_texts": text_analysis.get("hook_text_candidates", []),
                "all_texts": text_analysis.get("unique_texts", []),
            },
            "has_person": any(r.has_person for r in detection_results),
            "has_product": any(r.has_product for r in detection_results),
            "composition": self.composition_analyzer.summarize(comp_results),
            "colors": self.color_analyzer.summarize(
                self.color_analyzer.analyze_batch(frame_tuples)
            ),
        }
