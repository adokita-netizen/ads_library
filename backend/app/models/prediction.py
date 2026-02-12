"""Prediction and performance models."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PerformancePrediction(Base):
    __tablename__ = "performance_predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False)

    # Predictions
    predicted_ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_cvr: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_cpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    winning_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimal_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Confidence intervals
    ctr_confidence_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr_confidence_high: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Model info
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    feature_importance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Improvement suggestions
    improvement_suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class AdFatigueLog(Base):
    __tablename__ = "ad_fatigue_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False)

    # Fatigue metrics
    fatigue_score: Mapped[float] = mapped_column(Float, nullable=False)
    days_active: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_trend: Mapped[str] = mapped_column(String(50), nullable=False)  # declining, stable, improving
    estimated_remaining_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Recommendation
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    replacement_suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    metrics_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
