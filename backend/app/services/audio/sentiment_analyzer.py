"""Sentiment and emotion analysis for audio/text content."""

from dataclasses import dataclass, field

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class SentimentScore:
    """Sentiment analysis result."""

    text: str
    sentiment: str  # positive, negative, neutral
    score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    emotions: dict[str, float] = field(default_factory=dict)


@dataclass
class SentimentAnalysisResult:
    """Aggregated sentiment analysis."""

    overall_sentiment: str
    overall_score: float
    segment_sentiments: list[SentimentScore] = field(default_factory=list)
    emotion_summary: dict[str, float] = field(default_factory=dict)
    sentiment_arc: list[dict] = field(default_factory=list)  # sentiment over time


class AudioSentimentAnalyzer:
    """Analyze sentiment and emotions in text/audio content."""

    def __init__(self):
        self._sentiment_pipeline = None
        self._emotion_pipeline = None

    def _get_sentiment_pipeline(self):
        if self._sentiment_pipeline is None:
            try:
                from transformers import pipeline
                self._sentiment_pipeline = pipeline(
                    "sentiment-analysis",
                    model="nlptown/bert-base-multilingual-uncased-sentiment",
                    truncation=True,
                    max_length=512,
                )
                logger.info("sentiment_pipeline_loaded")
            except Exception as e:
                logger.error("sentiment_pipeline_load_failed", error=str(e))
                raise
        return self._sentiment_pipeline

    def _get_emotion_pipeline(self):
        if self._emotion_pipeline is None:
            try:
                from transformers import pipeline
                self._emotion_pipeline = pipeline(
                    "text-classification",
                    model="j-hartmann/emotion-english-distilroberta-base",
                    top_k=None,
                    truncation=True,
                    max_length=512,
                )
                logger.info("emotion_pipeline_loaded")
            except Exception as e:
                logger.warning("emotion_pipeline_load_failed", error=str(e))
                self._emotion_pipeline = "unavailable"
        return self._emotion_pipeline

    def analyze_text(self, text: str) -> SentimentScore:
        """Analyze sentiment of a single text."""
        if not text or not text.strip():
            return SentimentScore(
                text=text, sentiment="neutral", score=0.0, confidence=0.0
            )

        pipeline = self._get_sentiment_pipeline()

        try:
            result = pipeline(text[:512])[0]
            label = result["label"]
            raw_score = result["score"]

            # Convert star rating to sentiment
            if "1" in label or "2" in label:
                sentiment = "negative"
                score = -raw_score
            elif "4" in label or "5" in label:
                sentiment = "positive"
                score = raw_score
            else:
                sentiment = "neutral"
                score = 0.0

            # Get emotions if available
            emotions = {}
            emotion_pipeline = self._get_emotion_pipeline()
            if emotion_pipeline != "unavailable":
                try:
                    emotion_results = emotion_pipeline(text[:512])
                    if emotion_results and isinstance(emotion_results[0], list):
                        emotions = {
                            e["label"]: round(e["score"], 3)
                            for e in emotion_results[0]
                        }
                except Exception:
                    pass

            return SentimentScore(
                text=text,
                sentiment=sentiment,
                score=round(score, 3),
                confidence=round(raw_score, 3),
                emotions=emotions,
            )
        except Exception as e:
            logger.error("sentiment_analysis_failed", error=str(e))
            return SentimentScore(
                text=text, sentiment="neutral", score=0.0, confidence=0.0
            )

    def analyze_segments(
        self,
        segments: list[dict],
    ) -> SentimentAnalysisResult:
        """Analyze sentiment across multiple text segments with timing."""
        segment_sentiments: list[SentimentScore] = []
        sentiment_arc: list[dict] = []

        for seg in segments:
            text = seg.get("text", "")
            result = self.analyze_text(text)
            segment_sentiments.append(result)

            sentiment_arc.append({
                "start_time_ms": seg.get("start_time_ms", 0),
                "end_time_ms": seg.get("end_time_ms", 0),
                "sentiment": result.sentiment,
                "score": result.score,
            })

        # Calculate overall sentiment
        if segment_sentiments:
            scores = [s.score for s in segment_sentiments]
            avg_score = float(np.mean(scores))

            if avg_score > 0.1:
                overall_sentiment = "positive"
            elif avg_score < -0.1:
                overall_sentiment = "negative"
            else:
                overall_sentiment = "neutral"

            # Aggregate emotions
            all_emotions: dict[str, list[float]] = {}
            for seg in segment_sentiments:
                for emotion, score in seg.emotions.items():
                    if emotion not in all_emotions:
                        all_emotions[emotion] = []
                    all_emotions[emotion].append(score)

            emotion_summary = {
                emotion: round(float(np.mean(scores)), 3)
                for emotion, scores in all_emotions.items()
            }
        else:
            overall_sentiment = "neutral"
            avg_score = 0.0
            emotion_summary = {}

        return SentimentAnalysisResult(
            overall_sentiment=overall_sentiment,
            overall_score=round(avg_score, 3),
            segment_sentiments=segment_sentiments,
            emotion_summary=emotion_summary,
            sentiment_arc=sentiment_arc,
        )

    def analyze_ad_tone(self, full_text: str) -> dict:
        """Analyze the overall tone/style of ad content."""
        sentiment = self.analyze_text(full_text)

        # Detect tone categories
        text_lower = full_text.lower()

        urgency_words = ["今すぐ", "限定", "急いで", "残り", "本日", "now", "hurry", "limited", "last chance"]
        trust_words = ["実績", "No.1", "満足度", "口コミ", "証明", "proven", "trusted", "#1", "guarantee"]
        benefit_words = ["無料", "お得", "割引", "特典", "ボーナス", "free", "save", "discount", "bonus"]
        fear_words = ["危険", "注意", "失う", "後悔", "リスク", "warning", "danger", "risk", "lose"]

        tone_scores = {
            "urgency": sum(1 for w in urgency_words if w in text_lower) / len(urgency_words),
            "trust": sum(1 for w in trust_words if w in text_lower) / len(trust_words),
            "benefit": sum(1 for w in benefit_words if w in text_lower) / len(benefit_words),
            "fear": sum(1 for w in fear_words if w in text_lower) / len(fear_words),
        }

        dominant_tone = max(tone_scores, key=tone_scores.get)

        return {
            "sentiment": sentiment.sentiment,
            "sentiment_score": sentiment.score,
            "emotions": sentiment.emotions,
            "tone_scores": tone_scores,
            "dominant_tone": dominant_tone if tone_scores[dominant_tone] > 0 else "informational",
        }
