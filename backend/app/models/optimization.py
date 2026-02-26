"""Optimization recommendation model — AI-driven ad performance suggestions."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OptimizationRecommendation(Base):
    """An AI-generated optimization recommendation for Meta ad operations."""

    __tablename__ = "optimization_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Target entity
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # campaign/adset/ad
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Recommendation details
    recommendation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # budget_increase, budget_decrease, pause_ad, scale_ad, creative_refresh, bid_adjust
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    # low, medium, high, critical

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Impact prediction
    predicted_impact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # {metric, current, predicted, change_percent}

    # Action payload for Meta API execution
    action_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # {endpoint, method, data}

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending, accepted, rejected, expired, applied

    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_impact: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OptimizationRecommendation(id={self.id}, type={self.recommendation_type}, status={self.status})>"
