"""Brand registry and ad card models.

Provides normalized brand/page master and first-class carousel card entities,
following the Meta Ad Library reference architecture.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import JSON as JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ==================== Brand Registry ====================


class BrandRegistry(Base):
    """Normalized brand/page master — deduplicates advertiser names.

    Maps multiple advertiser_name variants and page handles to a single
    canonical brand entity.  Critical for accurate competitive intelligence
    (one brand can advertise under many page names / slight name variations).
    """

    __tablename__ = "brand_registry"
    __table_args__ = (
        UniqueConstraint("canonical_name", name="uq_brand_canonical"),
        Index("idx_brand_vertical", "vertical"),
        Index("idx_brand_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Pretty name for UI

    # Classification
    vertical: Mapped[str | None] = mapped_column(String(100), nullable=True)  # beauty, health, finance, etc.
    country_codes: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["JP", "US"]

    # Aliases — multiple advertiser_name variants that map to this brand
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["A社", "Aシャ", "CompanyA Inc."]

    # External IDs
    meta_page_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # Facebook/Instagram page IDs
    domains: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["brand-a.jp", "a-shop.com"]

    # Aggregated stats (updated by batch job)
    total_ad_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_active_ads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    avg_hit_proxy_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    brand_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

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
    ad_cards: Mapped[list["AdCard"]] = relationship(
        "AdCard", back_populates="brand", foreign_keys="AdCard.brand_id"
    )


# ==================== Ad Card (Carousel/Multi-card support) ====================


class AdCard(Base):
    """First-class carousel/multi-card entity.

    Meta ads can contain multiple unique cards within a single ad (carousel).
    Each card has its own body text, link title, CTA, destination URL, and media.
    This is the atomic unit for CR analysis — NOT the ad itself.
    """

    __tablename__ = "ad_cards"
    __table_args__ = (
        Index("idx_card_ad", "ad_id"),
        Index("idx_card_brand", "brand_id"),
        Index("idx_card_media_type", "media_type"),
        Index("idx_card_cta", "call_to_action"),
        UniqueConstraint("ad_id", "card_index", name="uq_ad_card_index"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("brand_registry.id", ondelete="SET NULL"), nullable=True
    )
    card_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-based position

    # Card-level copy
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_to_action: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "今すぐ購入", "詳しくはこちら"

    # Media
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # image/video
    aspect_ratio: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "1:1", "9:16"
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    screenshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Destination
    destination_url_initial: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_url_final: Mapped[str | None] = mapped_column(Text, nullable=True)  # After redirects
    destination_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Extracted text (per-card)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    asr_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quality
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100

    card_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    ad: Mapped["Ad"] = relationship("Ad", backref="cards")
    brand: Mapped["BrandRegistry | None"] = relationship("BrandRegistry", back_populates="ad_cards")
    angle_facts: Mapped[list["AngleFact"]] = relationship(
        "AngleFact", back_populates="card", cascade="all, delete-orphan"
    )
    lp_snapshots: Mapped[list["LPSnapshot"]] = relationship(
        "LPSnapshot", back_populates="card", cascade="all, delete-orphan"
    )


# ==================== Angle Fact (Creative Angle Taxonomy) ====================


class AngleFact(Base):
    """Structured creative angle extraction per card/ad.

    Captures the persuasion structure: hook → pain → promise → offer → proof → urgency.
    This is the core data model for competitive creative intelligence.
    """

    __tablename__ = "angle_facts"
    __table_args__ = (
        Index("idx_angle_card", "card_id"),
        Index("idx_angle_family", "family_id"),
        Index("idx_angle_hook_type", "hook_type"),
        Index("idx_angle_confidence", "confidence"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    card_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ad_cards.id", ondelete="CASCADE"), nullable=True
    )
    family_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("creative_families.id", ondelete="SET NULL"), nullable=True
    )
    ad_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=True
    )

    # Hook type — how the ad grabs attention
    hook_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Values: question, shock, empathy, benefit_first, scarcity, authority,
    #         social_proof, comparison, curiosity, storytelling

    # Persuasion elements (arrays for multi-label)
    pain_points: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["肌荒れ", "シミ・くすみ", "年齢肌"]

    promises: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["最短5分で診断", "透明感のある肌に"]

    offer_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["初回限定", "割引", "お試し", "返金保証", "送料無料"]

    proof_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["利用者満足度No.1", "医師監修", "特許取得", "口コミ", "ビフォーアフター"]

    urgency_types: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["本日終了", "残りわずか", "期間限定", "先着○名"]

    audience_hints: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["30代女性", "敏感肌", "ダイエット中"]

    creative_styles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["static", "direct_response", "UGC", "comparison", "before_after"]

    # LP pattern linked to this angle
    lp_pattern: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Values: article_advertorial, long_form_sales, quiz_funnel, lead_form,
    #         ecommerce_pdp, comparison_landing, vsl_landing

    # Extraction metadata
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0-1
    extracted_from: Mapped[str] = mapped_column(String(50), nullable=False, default="ocr")
    # Sources: ocr, asr, body_text, llm, manual

    angle_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    card: Mapped["AdCard | None"] = relationship("AdCard", back_populates="angle_facts")
    family: Mapped["CreativeFamily | None"] = relationship("CreativeFamily", backref="angle_facts")


# ==================== LP Snapshot (Card-linked, time-series) ====================


class LPSnapshot(Base):
    """Point-in-time LP snapshot tied to a specific ad card.

    Unlike LandingPage (which is the canonical LP record), this tracks
    per-observation snapshots — enabling LP change detection over time.
    """

    __tablename__ = "lp_snapshots"
    __table_args__ = (
        Index("idx_lps_card", "card_id"),
        Index("idx_lps_domain", "final_domain"),
        Index("idx_lps_observed", "observed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    card_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ad_cards.id", ondelete="CASCADE"), nullable=True
    )
    landing_page_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("landing_pages.id", ondelete="SET NULL"), nullable=True
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # URLs
    initial_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    redirect_chain: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Screenshots
    mobile_screenshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    desktop_screenshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    fullpage_screenshot_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HTML storage
    mobile_html_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    desktop_html_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extracted content
    dom_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_cta: Mapped[str | None] = mapped_column(String(255), nullable=True)
    form_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., [{"name": "email", "type": "email"}, {"name": "phone", "type": "tel"}]

    # Structured extraction
    extracted_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Contains: hero_headline, pricing_block, testimonials, faq, trust_badges, legal_text

    snapshot_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    card: Mapped["AdCard | None"] = relationship("AdCard", back_populates="lp_snapshots")
    landing_page: Mapped["LandingPage | None"] = relationship("LandingPage", backref="snapshots")


# ==================== Genre Keyword Pack ====================


class GenreKeywordPack(Base):
    """Keyword packs for genre-based ad discovery.

    Each genre has associated seed keywords used by crawlers to find
    relevant ads. Supports both Japanese and English keywords.
    """

    __tablename__ = "genre_keyword_packs"
    __table_args__ = (
        Index("idx_gkp_genre", "genre_code"),
        Index("idx_gkp_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    genre_code: Mapped[str] = mapped_column(String(100), nullable=False)

    # Keywords
    search_keywords_ja: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["無料診断", "初回半額", "医師監修", "返金保証"]
    search_keywords_en: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    appeal_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["before after", "No.1", "限定", "今だけ"]
    negative_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["求人", "採用", "アルバイト"] — filter out non-ad content

    # Usage
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_ads_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    pack_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


# ==================== Video Timeline ====================


class VideoTimeline(Base):
    """Unified OCR+ASR timeline for video ads.

    Stores keyframe-level extraction: OCR text, ASR text, visual tags,
    and derived structures (opening_hook, proof_sequence, cta_endcard).
    """

    __tablename__ = "video_timelines"
    __table_args__ = (
        Index("idx_vt_ad", "ad_id"),
        Index("idx_vt_asset", "asset_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("creative_assets.id", ondelete="SET NULL"), nullable=True
    )

    # Timeline entries: array of {t, ocr, asr, visual_tags}
    timeline: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., [
    #   {"t": 0.0, "ocr": "まだ自己流？", "visual": ["person", "bathroom"]},
    #   {"t": 2.5, "ocr": "医師監修", "visual": ["logo", "text_overlay"]},
    #   {"t": 6.0, "asr": "今なら初回半額です", "visual": ["product", "price_tag"]}
    # ]

    # Derived structure
    opening_hook: Mapped[str | None] = mapped_column(Text, nullable=True)  # First 3-5 sec text
    opening_hook_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Types: question, problem, shock, benefit, authority

    proof_sequence: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # e.g., ["監修", "口コミ", "ビフォーアフター"]

    cta_endcard: Mapped[str | None] = mapped_column(Text, nullable=True)
    # e.g., "今すぐチェック"

    # Stats
    total_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keyframe_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unique_ocr_texts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_asr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    timeline_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    ad: Mapped["Ad"] = relationship("Ad", backref="video_timelines")
    asset: Mapped["CreativeAsset | None"] = relationship("CreativeAsset", backref="video_timelines")


# Avoid circular imports
from app.models.ad import Ad  # noqa: E402
from app.models.creative_asset import CreativeAsset, CreativeFamily  # noqa: E402
from app.models.landing_page import LandingPage  # noqa: E402
