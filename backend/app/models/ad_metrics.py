"""Ad metrics time-series and ranking models."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Date,
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


class AdDailyMetrics(Base):
    """Daily time-series metrics for each ad (view counts, estimated spend, etc.)."""

    __tablename__ = "ad_daily_metrics"
    __table_args__ = (
        Index("idx_adm_ad_date", "ad_id", "metric_date", unique=True),
        Index("idx_adm_date", "metric_date"),
        Index("idx_adm_genre_date", "genre", "metric_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )

    metric_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Core DPro metrics
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    view_count_increase: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)  # 再生増加数
    estimated_spend: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 予想消化額
    estimated_spend_increase: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 予想消化増加額
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    share_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Engagement
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Classification (denormalized for fast ranking queries)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    advertiser_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class ProductRanking(Base):
    """Pre-computed product/genre rankings (updated periodically)."""

    __tablename__ = "product_rankings"
    __table_args__ = (
        Index("idx_pr_period_genre_rank", "period", "genre", "rank_position"),
        Index("idx_pr_period_rank", "period", "rank_position"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Period: daily, weekly, monthly
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Ranked entity
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    advertiser_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Rankings
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_change: Mapped[int | None] = mapped_column(Integer, nullable=True)  # positive = moved up

    # Aggregated metrics for the period
    total_view_increase: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_spend_increase: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cumulative_views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cumulative_spend: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Hit detection
    is_hit: Mapped[bool] = mapped_column(default=False, nullable=False)
    hit_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    trend_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # velocity of growth

    # Extra data
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class NotificationConfig(Base):
    """User notification configuration (Slack/Chatwork webhooks)."""

    __tablename__ = "notification_configs"
    __table_args__ = (
        Index("idx_nc_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Channel type
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)  # slack, chatwork, email
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    room_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # What to notify
    notify_new_hit_ads: Mapped[bool] = mapped_column(default=True, nullable=False)
    notify_competitor_activity: Mapped[bool] = mapped_column(default=True, nullable=False)
    notify_ranking_change: Mapped[bool] = mapped_column(default=False, nullable=False)
    notify_fatigue_warning: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Filters
    watched_genres: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    watched_advertisers: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SavedItem(Base):
    """User's saved/bookmarked items (マイリスト)."""

    __tablename__ = "saved_items"
    __table_args__ = (
        Index("idx_si_user_type", "user_id", "item_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    item_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ad, lp, creative, advertiser
    item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
