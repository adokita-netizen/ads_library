"""Landing Page analysis models."""

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


class LPTypeEnum(str, enum.Enum):
    ARTICLE = "article"       # 記事LP
    EC_DIRECT = "ec_direct"   # EC直接
    LEAD_GEN = "lead_gen"     # リード獲得
    APP_STORE = "app_store"   # アプリストア
    BRAND = "brand"           # ブランドサイト
    OTHER = "other"


class LPStatusEnum(str, enum.Enum):
    PENDING = "pending"
    CRAWLING = "crawling"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class AppealAxisEnum(str, enum.Enum):
    BENEFIT = "benefit"             # 効果・ベネフィット訴求
    PROBLEM_SOLUTION = "problem_solution"  # 悩み解決型
    AUTHORITY = "authority"         # 権威性（医師監修、特許等）
    SOCIAL_PROOF = "social_proof"   # 社会的証明（口コミ、実績）
    URGENCY = "urgency"            # 緊急性（限定、期間）
    PRICE = "price"                # 価格訴求
    COMPARISON = "comparison"       # 比較優位性
    EMOTIONAL = "emotional"         # 感情訴求
    FEAR = "fear"                  # 恐怖訴求（放置するとこうなる）
    NOVELTY = "novelty"            # 新規性・話題性


class LandingPage(Base):
    """Crawled and analyzed landing page."""

    __tablename__ = "landing_pages"
    __table_args__ = (
        Index("idx_lp_url_hash", "url_hash", unique=True),
        Index("idx_lp_ad_id", "ad_id"),
        Index("idx_lp_advertiser", "advertiser_name"),
        Index("idx_lp_genre", "genre"),
        Index("idx_lp_type", "lp_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="SET NULL"), nullable=True
    )

    # URL info
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # After redirects
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Basic info
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    full_page_screenshot_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Classification
    lp_type: Mapped[LPTypeEnum] = mapped_column(
        Enum(LPTypeEnum), default=LPTypeEnum.ARTICLE, nullable=False
    )
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    advertiser_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Content metrics
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_embed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    form_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cta_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    testimonial_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_read_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Page structure metrics
    total_sections: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scroll_depth_px: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Extracted text
    hero_headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    hero_subheadline: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_cta_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_text_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pricing
    has_pricing: Mapped[bool | None] = mapped_column(nullable=True)
    price_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Ownership: is_own=True means this is our own LP (not competitor)
    is_own: Mapped[bool] = mapped_column(default=False, nullable=False)
    own_lp_label: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g., "セラムV3_記事LP_A案"
    own_lp_version: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Version tracking

    # Status
    status: Mapped[LPStatusEnum] = mapped_column(
        Enum(LPStatusEnum), default=LPStatusEnum.PENDING, nullable=False
    )
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Raw data
    raw_html_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

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
    ad: Mapped["Ad | None"] = relationship(foreign_keys=[ad_id])
    sections: Mapped[list["LPSection"]] = relationship(
        back_populates="landing_page", cascade="all, delete-orphan"
    )
    usp_patterns: Mapped[list["USPPattern"]] = relationship(
        back_populates="landing_page", cascade="all, delete-orphan"
    )
    appeal_analyses: Mapped[list["AppealAxisAnalysis"]] = relationship(
        back_populates="landing_page", cascade="all, delete-orphan"
    )
    lp_analysis: Mapped["LPAnalysis | None"] = relationship(
        back_populates="landing_page", uselist=False, cascade="all, delete-orphan"
    )


class LPSection(Base):
    """Individual section of a landing page (structured breakdown)."""

    __tablename__ = "lp_sections"
    __table_args__ = (
        Index("idx_lp_sections_lp_order", "landing_page_id", "section_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    landing_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("landing_pages.id", ondelete="CASCADE"), nullable=False
    )

    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Types: hero, problem, solution, features, benefits, testimonials,
    #        authority, comparison, pricing, faq, cta, footer, etc.

    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_image: Mapped[bool] = mapped_column(default=False, nullable=False)
    has_video: Mapped[bool] = mapped_column(default=False, nullable=False)
    has_cta: Mapped[bool] = mapped_column(default=False, nullable=False)
    cta_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Position on page
    position_y_percent: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100

    # Extracted data
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    landing_page: Mapped["LandingPage"] = relationship(back_populates="sections")


class USPPattern(Base):
    """Extracted USP (Unique Selling Proposition) from landing page."""

    __tablename__ = "usp_patterns"
    __table_args__ = (
        Index("idx_usp_lp_id", "landing_page_id"),
        Index("idx_usp_category", "usp_category"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    landing_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("landing_pages.id", ondelete="CASCADE"), nullable=False
    )

    # USP classification
    usp_category: Mapped[str] = mapped_column(String(100), nullable=False)
    # Categories: efficacy, ingredient, price, guarantee, authority,
    #             uniqueness, convenience, speed, safety, experience

    usp_text: Mapped[str] = mapped_column(Text, nullable=False)
    usp_headline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supporting_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Strength/prominence
    prominence_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    position_in_page: Mapped[str | None] = mapped_column(String(50), nullable=True)  # above_fold, middle, bottom

    # Keywords
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    landing_page: Mapped["LandingPage"] = relationship(back_populates="usp_patterns")


class AppealAxisAnalysis(Base):
    """Appeal axis (訴求軸) analysis for a landing page."""

    __tablename__ = "appeal_axis_analyses"
    __table_args__ = (
        Index("idx_appeal_lp_id", "landing_page_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    landing_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("landing_pages.id", ondelete="CASCADE"), nullable=False
    )

    appeal_axis: Mapped[AppealAxisEnum] = mapped_column(
        Enum(AppealAxisEnum), nullable=False
    )
    strength_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    evidence_texts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    section_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    landing_page: Mapped["LandingPage"] = relationship(back_populates="appeal_analyses")


class LPAnalysis(Base):
    """Aggregated LP analysis result (LLM-powered deep analysis)."""

    __tablename__ = "lp_analyses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    landing_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("landing_pages.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    # Overall scoring
    overall_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    conversion_potential_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    urgency_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Structure analysis
    page_flow_pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # e.g., "hero→problem→solution→authority→testimonial→pricing→cta"
    structure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Target persona
    inferred_target_gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inferred_target_age_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inferred_target_concerns: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    target_persona_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Primary appeal
    primary_appeal_axis: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secondary_appeal_axis: Mapped[str | None] = mapped_column(String(100), nullable=True)
    appeal_strategy_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Competitor context
    competitive_positioning: Mapped[str | None] = mapped_column(Text, nullable=True)
    differentiation_points: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Copywriting analysis
    headline_effectiveness: Mapped[float | None] = mapped_column(Float, nullable=True)
    cta_effectiveness: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotional_triggers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    power_words: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Recommendations for own LP creation
    strengths: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    weaknesses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    reusable_patterns: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    improvement_suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Full AI analysis text
    full_analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Raw data
    raw_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    landing_page: Mapped["LandingPage"] = relationship(back_populates="lp_analysis")


# Avoid circular import
from app.models.ad import Ad  # noqa: E402
