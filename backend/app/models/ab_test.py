"""A/B Test models — experiments and variants for Meta ad testing."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ABTestExperiment(Base):
    """An A/B test experiment for comparing ad variants."""

    __tablename__ = "ab_test_experiments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Test configuration
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)  # draft/running/completed/archived
    test_type: Mapped[str] = mapped_column(String(20), default="creative", nullable=False)  # creative/audience/placement
    primary_metric: Mapped[str] = mapped_column(String(20), default="ctr", nullable=False)  # ctr/cvr/cpa
    confidence_level: Mapped[float] = mapped_column(Float, default=0.95, nullable=False)
    min_sample_size: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)

    # Results
    campaign_meta_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    winner_variant_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    statistical_significance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )

    variants: Mapped[list["ABTestVariant"]] = relationship(
        "ABTestVariant", back_populates="experiment", cascade="all, delete-orphan",
        foreign_keys="[ABTestVariant.experiment_id]",
        primaryjoin="ABTestExperiment.id == ABTestVariant.experiment_id",
    )

    def __repr__(self) -> str:
        return f"<ABTestExperiment(id={self.id}, name={self.name}, status={self.status})>"


class ABTestVariant(Base):
    """A variant in an A/B test experiment."""

    __tablename__ = "ab_test_variants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Control", "Variant A", etc.
    variant_type: Mapped[str] = mapped_column(String(20), default="test", nullable=False)  # control/test

    # Meta entity references
    ad_set_meta_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ad_meta_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    creative_meta_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Variant description
    variation_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creative_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metrics (updated from Meta insights)
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    conversions: Mapped[int] = mapped_column(BigInteger, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    cvr: Mapped[float] = mapped_column(Float, default=0.0)
    cpa: Mapped[float] = mapped_column(Float, default=0.0)

    is_winner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    experiment: Mapped["ABTestExperiment"] = relationship(
        "ABTestExperiment", back_populates="variants",
        foreign_keys=[experiment_id],
        primaryjoin=lambda: ABTestVariant.experiment_id == ABTestExperiment.id,
    )

    def __repr__(self) -> str:
        return f"<ABTestVariant(id={self.id}, name={self.name}, type={self.variant_type})>"
