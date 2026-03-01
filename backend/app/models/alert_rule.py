"""Alert rule model — defines conditions that trigger alerts."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AlertRule(Base):
    """Condition-based alert rule definition.

    condition_type values:
      - score_threshold: hit_score crosses a threshold
      - score_change: hit_score changed by more than threshold %
      - new_hit: new ad detected as HIT
      - data_quality: NULL rate exceeds threshold
      - crawl_failure: crawl failure count exceeds threshold
    """

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_field: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(10), nullable=True)  # gt, lt, eq, change_gt
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)

    genre_filter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_channel: Mapped[str] = mapped_column(String(50), default="in_app", nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    rule_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
