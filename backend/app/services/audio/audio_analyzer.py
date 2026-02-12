"""Unified audio analysis pipeline."""

from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.services.audio.keyword_extractor import KeywordExtractor
from app.services.audio.sentiment_analyzer import AudioSentimentAnalyzer
from app.services.audio.transcriber import Transcriber, TranscriptionResult

logger = structlog.get_logger()


@dataclass
class AudioAnalysisResult:
    """Complete audio analysis result."""

    # Transcription
    transcription: Optional[TranscriptionResult] = None

    # Sentiment
    sentiment_analysis: dict = field(default_factory=dict)
    ad_tone: dict = field(default_factory=dict)

    # Keywords
    keyword_analysis: dict = field(default_factory=dict)

    # Hook text (first 3 seconds)
    hook_text: str = ""
    hook_analysis: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "transcription": {
                "full_text": self.transcription.full_text if self.transcription else "",
                "language": self.transcription.language if self.transcription else "",
                "word_count": self.transcription.word_count if self.transcription else 0,
                "duration_seconds": self.transcription.duration_seconds if self.transcription else 0,
                "segments": [
                    {
                        "text": s.text,
                        "start_time_ms": s.start_time_ms,
                        "end_time_ms": s.end_time_ms,
                        "confidence": s.confidence,
                    }
                    for s in (self.transcription.segments if self.transcription else [])
                ],
            },
            "sentiment": self.sentiment_analysis,
            "ad_tone": self.ad_tone,
            "keywords": self.keyword_analysis,
            "hook_text": self.hook_text,
            "hook_analysis": self.hook_analysis,
        }


class AudioAnalyzer:
    """Unified audio analysis pipeline."""

    def __init__(
        self,
        transcriber: Optional[Transcriber] = None,
        sentiment_analyzer: Optional[AudioSentimentAnalyzer] = None,
        keyword_extractor: Optional[KeywordExtractor] = None,
    ):
        self.transcriber = transcriber or Transcriber()
        self.sentiment_analyzer = sentiment_analyzer or AudioSentimentAnalyzer()
        self.keyword_extractor = keyword_extractor or KeywordExtractor()

    def analyze_audio(
        self,
        audio_path: str,
        language: str | None = None,
    ) -> AudioAnalysisResult:
        """Run full audio analysis pipeline."""
        result = AudioAnalysisResult()

        logger.info("audio_analysis_started", path=audio_path)

        # Step 1: Transcribe
        try:
            result.transcription = self.transcriber.transcribe(
                audio_path,
                language=language,
                initial_prompt="広告動画の音声を文字起こしします。",
            )
        except Exception as e:
            logger.error("transcription_failed", error=str(e))
            return result

        if not result.transcription or not result.transcription.full_text:
            logger.warning("no_transcription_text")
            return result

        # Step 2: Sentiment analysis
        try:
            segments_data = [
                {
                    "text": seg.text,
                    "start_time_ms": seg.start_time_ms,
                    "end_time_ms": seg.end_time_ms,
                }
                for seg in result.transcription.segments
            ]

            sentiment_result = self.sentiment_analyzer.analyze_segments(segments_data)
            result.sentiment_analysis = {
                "overall_sentiment": sentiment_result.overall_sentiment,
                "overall_score": sentiment_result.overall_score,
                "emotion_summary": sentiment_result.emotion_summary,
                "sentiment_arc": sentiment_result.sentiment_arc,
            }
        except Exception as e:
            logger.error("sentiment_analysis_failed", error=str(e))

        # Step 3: Ad tone analysis
        try:
            result.ad_tone = self.sentiment_analyzer.analyze_ad_tone(
                result.transcription.full_text
            )
        except Exception as e:
            logger.error("ad_tone_analysis_failed", error=str(e))

        # Step 4: Keyword extraction
        try:
            segments_for_keywords = [
                {
                    "text": seg.text,
                    "start_time_ms": seg.start_time_ms,
                    "end_time_ms": seg.end_time_ms,
                }
                for seg in result.transcription.segments
            ]
            result.keyword_analysis = self.keyword_extractor.extract_from_segments(
                segments_for_keywords
            )
        except Exception as e:
            logger.error("keyword_extraction_failed", error=str(e))

        # Step 5: Hook analysis (first 3 seconds)
        try:
            result.hook_text = result.transcription.get_first_n_seconds_text(3.0)
            if result.hook_text:
                hook_keywords = self.keyword_extractor.extract_keywords(result.hook_text)
                result.hook_analysis = {
                    "text": result.hook_text,
                    "word_count": len(result.hook_text.split()),
                    "cta_phrases": hook_keywords.cta_phrases,
                    "hook_words": hook_keywords.hook_words,
                    "appeal_axes": hook_keywords.appeal_axes,
                }
        except Exception as e:
            logger.error("hook_analysis_failed", error=str(e))

        logger.info(
            "audio_analysis_completed",
            language=result.transcription.language,
            segments=len(result.transcription.segments),
        )

        return result
