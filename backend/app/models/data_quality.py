"""Daily data quality snapshot model."""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataQualitySnapshot(Base):
    """Stores daily aggregate data quality metrics for trend monitoring."""

    __tablename__ = "data_quality_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", name="uq_data_quality_snapshot_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_ads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    null_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fill_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    field_fill_rates: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
