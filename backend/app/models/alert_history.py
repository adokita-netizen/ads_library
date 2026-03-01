"""Alert history model — records triggered alerts."""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Index
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AlertHistory(Base):
    """Record of a triggered alert."""

    __tablename__ = "alert_history"
    __table_args__ = (
        Index("idx_ah_rule_triggered", "rule_id", "triggered_at"),
        Index("idx_ah_unread", "is_read", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    ad_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ads.id"), nullable=True)

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)  # info, warning, critical
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    old_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alert_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
