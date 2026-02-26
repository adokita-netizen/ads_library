"""Meta campaign hierarchy models — Campaign, AdSet, Ad, and Insight."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MetaCampaign(Base):
    """A Meta advertising campaign synced from the Marketing API."""

    __tablename__ = "meta_campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    meta_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PAUSED")
    effective_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PAUSED")
    objective: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    daily_budget: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    lifetime_budget: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    budget_remaining: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    buying_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    special_ad_categories: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )

    ad_sets: Mapped[list["MetaAdSet"]] = relationship(
        "MetaAdSet", back_populates="campaign", lazy="selectin",
        foreign_keys="[MetaAdSet.campaign_meta_id]",
        primaryjoin="MetaCampaign.meta_id == MetaAdSet.campaign_meta_id",
    )

    def __repr__(self) -> str:
        return f"<MetaCampaign(meta_id={self.meta_id}, name={self.name})>"


class MetaAdSet(Base):
    """A Meta ad set within a campaign."""

    __tablename__ = "meta_ad_sets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    meta_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    campaign_meta_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PAUSED")
    effective_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PAUSED")
    daily_budget: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    lifetime_budget: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    bid_strategy: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bid_amount: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    billing_event: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    optimization_goal: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    targeting: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )

    campaign: Mapped["MetaCampaign"] = relationship(
        "MetaCampaign", back_populates="ad_sets",
        foreign_keys=[campaign_meta_id],
        primaryjoin=lambda: MetaAdSet.campaign_meta_id == MetaCampaign.meta_id,
    )
    ads: Mapped[list["MetaAd"]] = relationship(
        "MetaAd", back_populates="ad_set", lazy="selectin",
        foreign_keys="[MetaAd.ad_set_meta_id]",
        primaryjoin="MetaAdSet.meta_id == MetaAd.ad_set_meta_id",
    )

    def __repr__(self) -> str:
        return f"<MetaAdSet(meta_id={self.meta_id}, name={self.name})>"


class MetaAd(Base):
    """A Meta ad within an ad set, including creative details."""

    __tablename__ = "meta_ads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    meta_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    ad_set_meta_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PAUSED")
    effective_status: Mapped[str] = mapped_column(String(30), nullable=False, default="PAUSED")

    # Creative fields
    creative_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    creative_thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creative_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creative_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    creative_link_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creative_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creative_video_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    creative_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Link to internal Ad model for analysis pipeline
    linked_ad_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )

    ad_set: Mapped["MetaAdSet"] = relationship(
        "MetaAdSet", back_populates="ads",
        foreign_keys=[ad_set_meta_id],
        primaryjoin=lambda: MetaAd.ad_set_meta_id == MetaAdSet.meta_id,
    )

    def __repr__(self) -> str:
        return f"<MetaAd(meta_id={self.meta_id}, name={self.name})>"


class MetaInsight(Base):
    """Daily performance metrics for a Meta entity (campaign/adset/ad)."""

    __tablename__ = "meta_insights"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "date_start", name="uq_meta_insight_entity_date"),
        Index("ix_meta_insight_account_date", "account_id", "date_start"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # campaign / adset / ad
    entity_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date_start: Mapped[str] = mapped_column(String(10), nullable=False)
    date_stop: Mapped[str] = mapped_column(String(10), nullable=False)

    # Core metrics
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    reach: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0.0)
    ctr: Mapped[float] = mapped_column(Float, default=0.0)
    cpc: Mapped[float] = mapped_column(Float, default=0.0)
    cpm: Mapped[float] = mapped_column(Float, default=0.0)
    cpp: Mapped[float] = mapped_column(Float, default=0.0)
    frequency: Mapped[float] = mapped_column(Float, default=0.0)

    # Conversion metrics
    conversions: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    conversion_values: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_per_conversion: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Video metrics
    video_views: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    video_thruplay: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    video_p25_watched: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    video_p50_watched: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    video_p75_watched: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    video_p95_watched: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    video_p100_watched: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Additional
    inline_link_clicks: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    social_spend: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<MetaInsight({self.entity_type}:{self.entity_id}, {self.date_start})>"
