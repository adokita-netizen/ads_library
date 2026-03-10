"""Creative asset, family, and genre taxonomy models.

Reference architecture tables for production-grade ad creative management.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GenreTaxonomy(Base):
    """Hierarchical genre taxonomy with JP/EN labels."""
    __tablename__ = "genre_taxonomy"
    __table_args__ = (
        UniqueConstraint("code", name="uq_genre_code"),
        Index("idx_genre_parent", "parent_genre_id"),
        Index("idx_genre_level", "level"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_genre_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("genre_taxonomy.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ja: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Self-referential relationship
    parent: Mapped["GenreTaxonomy | None"] = relationship(
        "GenreTaxonomy", remote_side="GenreTaxonomy.id", backref="children"
    )


class CreativeAsset(Base):
    """Extracted creative asset (image/video) with quality metadata."""
    __tablename__ = "creative_assets"
    __table_args__ = (
        Index("idx_asset_ad", "ad_id"),
        Index("idx_asset_type", "asset_type"),
        Index("idx_asset_sha256", "sha256"),
        Index("idx_asset_aspect", "aspect_ratio"),
        Index("idx_asset_quality", "quality_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # image/video/thumbnail
    storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)  # S3 or local path
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # Original URL (may expire)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Perceptual hash

    # Media dimensions
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "1:1", "9:16", "16:9"
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Video duration
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    has_audio: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Extracted text
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    asr_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quality & classification
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    is_representative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Family clustering
    family_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("creative_families.id", ondelete="SET NULL"), nullable=True
    )
    family_membership_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    asset_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    ad: Mapped["Ad"] = relationship("Ad", backref="creative_assets")
    family: Mapped["CreativeFamily | None"] = relationship("CreativeFamily", backref="members")


class CreativeFamily(Base):
    """Group of visually/semantically similar ad creatives."""
    __tablename__ = "creative_families"
    __table_args__ = (
        Index("idx_family_advertiser", "canonical_advertiser_name"),
        Index("idx_family_genre", "primary_genre_code"),
        Index("idx_family_hit_proxy", "hit_proxy_score"),
        Index("idx_family_active_days", "active_days"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_advertiser_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    family_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_genre_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Temporal
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Scale
    platform_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    variant_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Hit proxy scoring (reference architecture formula)
    hit_proxy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # pending/approved/rejected

    family_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AdGenreTag(Base):
    """Multi-label genre classification for ads."""
    __tablename__ = "ad_genre_tags"
    __table_args__ = (
        UniqueConstraint("ad_id", "genre_code", name="uq_ad_genre"),
        Index("idx_adgenre_ad", "ad_id"),
        Index("idx_adgenre_code", "genre_code"),
        Index("idx_adgenre_primary", "is_primary"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )
    genre_code: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="keyword")  # keyword/ml/manual
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {matched_keywords, lp_cues, etc.}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    ad: Mapped["Ad"] = relationship("Ad", backref="genre_tags")
