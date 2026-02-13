"""Ad and AdFrame models."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
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


class AdPlatformEnum(str, enum.Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    X_TWITTER = "x_twitter"
    LINE = "line"
    YAHOO = "yahoo"
    PINTEREST = "pinterest"
    SMARTNEWS = "smartnews"
    GOOGLE_ADS = "google_ads"
    GUNOSY = "gunosy"
    OTHER = "other"


class AdStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class AdCategoryEnum(str, enum.Enum):
    EC_D2C = "ec_d2c"
    APP = "app"
    FINANCE = "finance"
    EDUCATION = "education"
    BEAUTY = "beauty"
    FOOD = "food"
    GAMING = "gaming"
    HEALTH = "health"
    TECHNOLOGY = "technology"
    REAL_ESTATE = "real_estate"
    TRAVEL = "travel"
    OTHER = "other"


class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (
        Index("idx_ads_platform_created", "platform", "created_at"),
        Index("idx_ads_advertiser", "advertiser_name"),
        Index("idx_ads_category", "category"),
        Index("idx_ads_status", "status"),
        Index("idx_ads_view_count", "view_count"),
        Index("idx_ads_brand", "brand_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[AdPlatformEnum] = mapped_column(Enum(AdPlatformEnum), nullable=False)
    status: Mapped[AdStatusEnum] = mapped_column(
        Enum(AdStatusEnum), default=AdStatusEnum.PENDING, nullable=False
    )
    category: Mapped[AdCategoryEnum | None] = mapped_column(Enum(AdCategoryEnum), nullable=True)

    # Video metadata
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Advertiser info
    advertiser_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    advertiser_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Performance metrics (estimated or actual)
    estimated_impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estimated_ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cvr: Mapped[float | None] = mapped_column(Float, nullable=True)
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Dates
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Flexible metadata (attribute named ad_metadata to avoid SQLAlchemy reserved word)
    ad_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    frames: Mapped[list["AdFrame"]] = relationship(back_populates="ad", cascade="all, delete-orphan")
    analysis: Mapped["AdAnalysis | None"] = relationship(back_populates="ad", uselist=False, cascade="all, delete-orphan")


class AdFrame(Base):
    __tablename__ = "ad_frames"
    __table_args__ = (
        Index("idx_frames_ad_timestamp", "ad_id", "timestamp_seconds"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False)
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    is_keyframe: Mapped[bool] = mapped_column(default=False, nullable=False)
    scene_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Frame-level analysis
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    contrast: Mapped[float | None] = mapped_column(Float, nullable=True)
    dominant_colors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    composition_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    ad: Mapped["Ad"] = relationship(back_populates="frames")


# Import here to avoid circular imports
from app.models.analysis import AdAnalysis  # noqa: E402
