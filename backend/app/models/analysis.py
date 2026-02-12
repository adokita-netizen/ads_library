"""Analysis result models."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AdAnalysis(Base):
    """Aggregated analysis results for an ad."""

    __tablename__ = "ad_analyses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Scene analysis summary
    total_scenes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_scene_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    scene_transitions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Composition analysis
    face_closeup_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_overlay_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    product_display_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ui_display_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Content classification
    is_ugc_style: Mapped[bool | None] = mapped_column(nullable=True)
    has_narration: Mapped[bool | None] = mapped_column(nullable=True)
    has_bgm: Mapped[bool | None] = mapped_column(nullable=True)
    has_subtitles: Mapped[bool | None] = mapped_column(nullable=True)

    # Hook analysis (first 3 seconds)
    hook_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hook_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hook_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # CTA analysis
    cta_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cta_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    cta_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Overall sentiment
    overall_sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotion_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Color analysis
    dominant_color_palette: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    color_temperature: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Full transcript
    full_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Keywords and topics
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    topics: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Winning pattern score (0-100)
    winning_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Raw analysis data
    raw_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="analysis")
    detected_objects: Mapped[list["DetectedObject"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    text_detections: Mapped[list["TextDetection"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    transcriptions: Mapped[list["Transcription"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    scene_boundaries: Mapped[list["SceneBoundary"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    sentiment_results: Mapped[list["SentimentResult"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class DetectedObject(Base):
    """Objects detected in video frames."""

    __tablename__ = "detected_objects"
    __table_args__ = (
        Index("idx_detected_objects_analysis_class", "analysis_id", "class_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ad_analyses.id", ondelete="CASCADE"), nullable=False
    )
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Bounding box (normalized 0-1)
    bbox_x: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_width: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_height: Mapped[float] = mapped_column(Float, nullable=False)

    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    analysis: Mapped["AdAnalysis"] = relationship(back_populates="detected_objects")


class TextDetection(Base):
    """OCR text detected in video frames."""

    __tablename__ = "text_detections"
    __table_args__ = (
        Index("idx_text_detections_analysis", "analysis_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ad_analyses.id", ondelete="CASCADE"), nullable=False
    )
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Bounding box
    bbox_x: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_y: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_width: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_height: Mapped[float] = mapped_column(Float, nullable=False)

    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    analysis: Mapped["AdAnalysis"] = relationship(back_populates="text_detections")


class Transcription(Base):
    """Audio transcription segments."""

    __tablename__ = "transcriptions"
    __table_args__ = (
        Index("idx_transcriptions_analysis_time", "analysis_id", "start_time_ms"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ad_analyses.id", ondelete="CASCADE"), nullable=False
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    analysis: Mapped["AdAnalysis"] = relationship(back_populates="transcriptions")


class SceneBoundary(Base):
    """Scene/shot boundaries detected in video."""

    __tablename__ = "scene_boundaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ad_analyses.id", ondelete="CASCADE"), nullable=False
    )
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    # Scene characteristics
    scene_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dominant_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    has_text_overlay: Mapped[bool | None] = mapped_column(nullable=True)
    has_person: Mapped[bool | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    extra_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    analysis: Mapped["AdAnalysis"] = relationship(back_populates="scene_boundaries")


class SentimentResult(Base):
    """Sentiment analysis results per segment."""

    __tablename__ = "sentiment_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ad_analyses.id", ondelete="CASCADE"), nullable=False
    )

    segment_type: Mapped[str] = mapped_column(String(50), nullable=False)  # text, audio, visual
    segment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    sentiment: Mapped[str] = mapped_column(String(50), nullable=False)  # positive, negative, neutral
    score: Mapped[float] = mapped_column(Float, nullable=False)
    emotion_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    analysis: Mapped["AdAnalysis"] = relationship(back_populates="sentiment_results")


# Avoid circular import
from app.models.ad import Ad  # noqa: E402
