"""Competitive intelligence models - spend estimation, embeddings, LP fingerprinting, alerts, classification, funnels."""

from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ==================== Spend Estimation with Confidence Ranges ====================


class SpendEstimate(Base):
    """Spend estimate with P50/P90 confidence ranges and CPM calibration."""

    __tablename__ = "spend_estimates"
    __table_args__ = (
        Index("idx_se_ad_date", "ad_id", "estimate_date", unique=True),
        Index("idx_se_date", "estimate_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )

    estimate_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Core metrics used for estimation
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    view_count_increase: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # CPM values used
    cpm_platform_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpm_genre_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpm_seasonal_factor: Mapped[float | None] = mapped_column(Float, nullable=True)  # 1.0 = normal
    cpm_user_calibrated: Mapped[float | None] = mapped_column(Float, nullable=True)  # User-provided CPM

    # Point estimate (traditional)
    estimated_spend: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Confidence ranges
    spend_p10: Mapped[float | None] = mapped_column(Float, nullable=True)  # 10th percentile (low)
    spend_p25: Mapped[float | None] = mapped_column(Float, nullable=True)
    spend_p50: Mapped[float | None] = mapped_column(Float, nullable=True)  # Median
    spend_p75: Mapped[float | None] = mapped_column(Float, nullable=True)
    spend_p90: Mapped[float | None] = mapped_column(Float, nullable=True)  # 90th percentile (high)

    # Estimation method metadata
    estimation_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # cpm_model, ml_model, calibrated
    confidence_level: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class CPMCalibration(Base):
    """User-provided CPM calibration data for improving spend estimates."""

    __tablename__ = "cpm_calibrations"
    __table_args__ = (
        Index("idx_cpm_user_platform", "user_id", "platform"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # User-provided actual values
    actual_cpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_cpv: Mapped[float | None] = mapped_column(Float, nullable=True)  # Cost per view
    actual_cpc: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Period the data covers
    data_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # How many ads this covers

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ==================== Multimodal Embeddings for Similarity Search ====================


class AdEmbedding(Base):
    """Multimodal embedding vectors for similarity search.

    Stores embeddings as JSONB arrays (portable) - can be migrated to pgvector later.
    Combines video frame, text (transcript + OCR), and LP content embeddings.
    """

    __tablename__ = "ad_embeddings"
    __table_args__ = (
        Index("idx_ae_ad_id", "ad_id", unique=True),
        Index("idx_ae_type", "embedding_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )

    # Embedding vectors stored as JSON arrays
    visual_embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)   # Video frame features
    text_embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)     # Transcript + OCR combined
    combined_embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # Multimodal fusion

    # Metadata
    embedding_type: Mapped[str] = mapped_column(String(50), default="multimodal", nullable=False)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Auto-tags derived from embeddings
    auto_appeal_axes: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["benefit", "authority"]
    auto_expression_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # UGC, comparison, authority, review
    auto_structure_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # hook→proof→CTA etc.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


# ==================== LP Fingerprinting & Offer Clustering ====================


class LPFingerprint(Base):
    """LP fingerprint for detecting same/similar offers and tracking changes."""

    __tablename__ = "lp_fingerprints"
    __table_args__ = (
        Index("idx_lpf_lp_id", "landing_page_id"),
        Index("idx_lpf_content_hash", "content_hash"),
        Index("idx_lpf_offer_cluster", "offer_cluster_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    landing_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("landing_pages.id", ondelete="CASCADE"), nullable=False
    )

    # Content fingerprints
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256 of normalized text
    structure_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA256 of section types sequence
    offer_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Hash of price+CTA+product

    # Offer clustering
    offer_cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Cluster ID for same offers
    cluster_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1 similarity to cluster center

    # Extracted offer details
    offer_price: Mapped[str | None] = mapped_column(String(100), nullable=True)
    offer_discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    offer_trial_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_guarantee_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_bonus_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tokushoho_company: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 特商法の会社名

    # Change tracking (vs previous version)
    previous_fingerprint_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    changes_detected: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["price_changed", "cta_changed"]
    change_magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


# ==================== Enhanced Alert Detection ====================


class AlertLog(Base):
    """Detected alert events (spend surge, LP swap, appeal change, new competitor ad, etc.)."""

    __tablename__ = "alert_logs"
    __table_args__ = (
        Index("idx_al_type_date", "alert_type", "detected_at"),
        Index("idx_al_entity", "entity_type", "entity_id"),
        Index("idx_al_severity", "severity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Alert classification
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: spend_surge, lp_swap, appeal_change, new_competitor_ad, ranking_jump,
    #        new_offer, category_trend, creative_fatigue, new_advertiser_entry

    severity: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)  # low, medium, high, critical

    # What triggered the alert
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ad, advertiser, genre, lp
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Alert details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Context data
    context_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g., {"old_lp_url": "...", "new_lp_url": "...", "old_appeal": "benefit", "new_appeal": "authority"}

    # Status
    is_notified: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_dismissed: Mapped[bool] = mapped_column(default=False, nullable=False)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


# ==================== Two-Stage Classification ====================


class AdClassificationTag(Base):
    """Two-stage classification: provisional (LIVE) → confirmed (reviewed).

    Each tag has a confidence score and lifecycle status.
    """

    __tablename__ = "ad_classification_tags"
    __table_args__ = (
        Index("idx_act_ad_field", "ad_id", "field_name"),
        Index("idx_act_status", "classification_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )

    # What field this classifies
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Fields: genre, product_name, advertiser_name, appeal_axis, expression_type, target_audience

    # Classification result
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0-1

    # Two-stage lifecycle
    classification_status: Mapped[str] = mapped_column(
        String(20), default="provisional", nullable=False
    )
    # States: provisional (LIVE/fast model), confirmed (full model + optional human review), rejected

    # Source tracking
    classified_by: Mapped[str] = mapped_column(String(50), default="auto_fast", nullable=False)
    # Sources: auto_fast (lightweight LIVE), auto_full (heavy model), human_review, rule_based

    # If confirmed, who/what confirmed
    confirmed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Previous value (if reclassified)
    previous_value: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ==================== LP Funnel Detection ====================


class LPFunnel(Base):
    """Multi-step funnel definition (ad → pre-LP → LP → checkout → upsell)."""

    __tablename__ = "lp_funnels"
    __table_args__ = (
        Index("idx_lpf_root_domain", "root_domain"),
        Index("idx_lpf_advertiser", "advertiser_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Funnel identity
    funnel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    root_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    advertiser_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Funnel topology
    total_steps: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    funnel_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Types: single_lp, article_to_cart, multi_step, quiz_funnel, webinar_funnel

    # Aggregated metrics
    estimated_total_spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    ad_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Number of ads pointing to this funnel
    advertiser_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class FunnelStep(Base):
    """Individual step in a multi-step funnel."""

    __tablename__ = "funnel_steps"
    __table_args__ = (
        Index("idx_fs_funnel_order", "funnel_id", "step_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    funnel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("lp_funnels.id", ondelete="CASCADE"), nullable=False
    )
    landing_page_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("landing_pages.id", ondelete="SET NULL"), nullable=True
    )

    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: ad_click, pre_lp, article_lp, product_lp, cart, checkout, upsell, thank_you

    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Step metrics
    estimated_dropoff_rate: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


# ==================== Trend Prediction Cache ====================


class TrendPrediction(Base):
    """Trend/hit prediction for early detection of rising ads."""

    __tablename__ = "trend_predictions"
    __table_args__ = (
        Index("idx_tp_ad_date", "ad_id", "prediction_date"),
        Index("idx_tp_predicted_hit", "predicted_hit", "prediction_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ads.id", ondelete="CASCADE"), nullable=False
    )

    prediction_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Velocity metrics
    view_velocity_1d: Mapped[float | None] = mapped_column(Float, nullable=True)  # Views/day last 1 day
    view_velocity_3d: Mapped[float | None] = mapped_column(Float, nullable=True)  # Views/day last 3 days
    view_velocity_7d: Mapped[float | None] = mapped_column(Float, nullable=True)  # Views/day last 7 days
    view_acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)  # Rate of velocity change

    spend_velocity_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    spend_velocity_3d: Mapped[float | None] = mapped_column(Float, nullable=True)
    spend_velocity_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    spend_acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)

    # S-curve modeling
    growth_phase: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Phases: launch, growth, peak, plateau, decline
    days_since_first_seen: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_peak_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Genre-specific thresholds
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    genre_avg_velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    genre_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100

    # Prediction output
    predicted_hit: Mapped[bool] = mapped_column(default=False, nullable=False)
    hit_probability: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-1
    predicted_peak_spend: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Momentum scoring (综合)
    momentum_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
