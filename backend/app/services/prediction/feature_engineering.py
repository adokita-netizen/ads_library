"""Feature engineering for ad performance prediction."""

from dataclasses import dataclass, field

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class AdFeatures:
    """Engineered features for an ad."""

    # Video features
    duration_seconds: float = 0.0
    total_scenes: int = 0
    avg_scene_duration: float = 0.0
    pacing_score: float = 0.0

    # Visual features
    face_closeup_ratio: float = 0.0
    product_display_ratio: float = 0.0
    text_overlay_ratio: float = 0.0
    avg_brightness: float = 0.0
    avg_contrast: float = 0.0
    visual_complexity: float = 0.0
    color_temperature_warm: float = 0.0

    # Audio features
    has_narration: bool = False
    has_bgm: bool = False
    word_count: int = 0
    speech_speed_wpm: float = 0.0
    sentiment_score: float = 0.0

    # Hook features (first 3 seconds)
    hook_has_text: bool = False
    hook_has_person: bool = False
    hook_has_question: bool = False
    hook_scene_count: int = 0

    # CTA features
    has_cta: bool = False
    cta_position_ratio: float = 0.0  # position in video (0-1)
    cta_keyword_count: int = 0

    # Content features
    is_ugc_style: bool = False
    has_subtitles: bool = False
    unique_object_types: int = 0
    appeal_axis_count: int = 0

    # Platform
    platform_youtube: bool = False
    platform_tiktok: bool = False
    platform_instagram: bool = False
    platform_facebook: bool = False

    def to_array(self) -> np.ndarray:
        """Convert features to numpy array for model input."""
        return np.array([
            self.duration_seconds,
            self.total_scenes,
            self.avg_scene_duration,
            self.pacing_score,
            self.face_closeup_ratio,
            self.product_display_ratio,
            self.text_overlay_ratio,
            self.avg_brightness,
            self.avg_contrast,
            self.visual_complexity,
            self.color_temperature_warm,
            float(self.has_narration),
            float(self.has_bgm),
            self.word_count,
            self.speech_speed_wpm,
            self.sentiment_score,
            float(self.hook_has_text),
            float(self.hook_has_person),
            float(self.hook_has_question),
            self.hook_scene_count,
            float(self.has_cta),
            self.cta_position_ratio,
            self.cta_keyword_count,
            float(self.is_ugc_style),
            float(self.has_subtitles),
            self.unique_object_types,
            self.appeal_axis_count,
            float(self.platform_youtube),
            float(self.platform_tiktok),
            float(self.platform_instagram),
            float(self.platform_facebook),
        ], dtype=np.float32)

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "duration_seconds", "total_scenes", "avg_scene_duration", "pacing_score",
            "face_closeup_ratio", "product_display_ratio", "text_overlay_ratio",
            "avg_brightness", "avg_contrast", "visual_complexity", "color_temperature_warm",
            "has_narration", "has_bgm", "word_count", "speech_speed_wpm", "sentiment_score",
            "hook_has_text", "hook_has_person", "hook_has_question", "hook_scene_count",
            "has_cta", "cta_position_ratio", "cta_keyword_count",
            "is_ugc_style", "has_subtitles", "unique_object_types", "appeal_axis_count",
            "platform_youtube", "platform_tiktok", "platform_instagram", "platform_facebook",
        ]


class FeatureEngineer:
    """Extract and engineer features from analysis results."""

    def extract_features(
        self,
        video_analysis: dict,
        audio_analysis: dict,
        platform: str = "youtube",
    ) -> AdFeatures:
        """Extract features from combined analysis results."""
        features = AdFeatures()

        # Video features
        metadata = video_analysis.get("metadata", {})
        features.duration_seconds = metadata.get("duration_seconds", 0)

        scene_info = video_analysis.get("scene_analysis", {})
        features.total_scenes = scene_info.get("total_scenes", 0)
        features.avg_scene_duration = scene_info.get("avg_scene_duration", 0)
        features.pacing_score = scene_info.get("pacing_score", 0)

        # Visual features
        person_info = video_analysis.get("person_analysis", {})
        features.face_closeup_ratio = person_info.get("face_closeup_ratio", 0)

        product_info = video_analysis.get("product_analysis", {})
        features.product_display_ratio = product_info.get("product_display_ratio", 0)

        comp_info = video_analysis.get("composition_summary", {})
        features.avg_brightness = comp_info.get("avg_brightness", 128) / 255.0
        features.avg_contrast = comp_info.get("avg_contrast", 50) / 127.0
        features.visual_complexity = comp_info.get("avg_visual_complexity", 0.5)

        text_info = video_analysis.get("text_analysis", {})
        features.text_overlay_ratio = text_info.get("avg_text_overlay_ratio", 0)
        features.has_subtitles = text_info.get("has_subtitles", False)

        # Color features
        color_info = video_analysis.get("color_summary", {})
        temp_dist = color_info.get("temperature_distribution", {})
        total_temp = sum(temp_dist.values()) or 1
        features.color_temperature_warm = temp_dist.get("warm", 0) / total_temp

        # Hook features
        hook_info = video_analysis.get("hook_analysis", {})
        features.hook_scene_count = hook_info.get("hook_scene_count", 0)
        hook_texts = text_info.get("hook_text_candidates", [])
        features.hook_has_text = len(hook_texts) > 0
        features.hook_has_question = any("?" in t.get("text", "") or "？" in t.get("text", "") for t in hook_texts)

        # Audio features
        transcription = audio_analysis.get("transcription", {})
        features.has_narration = bool(transcription.get("full_text", ""))
        features.word_count = transcription.get("word_count", 0)
        duration = transcription.get("duration_seconds", 1) or 1
        features.speech_speed_wpm = (features.word_count / duration) * 60

        sentiment = audio_analysis.get("sentiment", {})
        features.sentiment_score = sentiment.get("overall_score", 0)

        # CTA features
        keywords = audio_analysis.get("keywords", {})
        cta_phrases = keywords.get("cta_phrases", [])
        features.has_cta = len(cta_phrases) > 0 or len(text_info.get("cta_candidates", [])) > 0
        features.cta_keyword_count = len(cta_phrases)

        # Appeal features
        features.appeal_axis_count = len(keywords.get("appeal_axes", []))

        # Object features
        object_info = video_analysis.get("object_analysis", {})
        if "object_type_counts" in product_info:
            features.unique_object_types = len(product_info["object_type_counts"])

        # Person in hook
        features.hook_has_person = person_info.get("person_present_ratio", 0) > 0.3

        # Platform one-hot
        platform_lower = platform.lower()
        features.platform_youtube = platform_lower == "youtube"
        features.platform_tiktok = platform_lower == "tiktok"
        features.platform_instagram = platform_lower == "instagram"
        features.platform_facebook = platform_lower == "facebook"

        return features
