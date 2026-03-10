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
from sqlalchemy import JSON as JSONB  # Use generic JSON (renders as JSONB on PG, JSON on SQLite)
from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

CREATIVE_FETCH_REASON_CODES = {
    "not_found_in_api",
    "media_url_missing",
    "download_failed",
    "format_mismatch",
    "blocked_or_expired",
    "login_required",
    "unknown_schema",
}

CREATIVE_ORIENTATIONS = {"vertical", "horizontal", "square", "unknown"}
LP_FETCH_ERROR_CODES = {
    "timeout",
    "dns_error",
    "blocked",
    "invalid_html",
    "redirect_loop",
    "http_error",
    "unknown",
}

CREATIVE_FETCH_ID_KEYS = (
    "creative_ad_id",
    "fetched_ad_id",
    "source_ad_id",
    "material_ad_id",
)


def normalize_creative_fetch_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    value = str(reason).strip()
    if not value:
        return None
    return value if value in CREATIVE_FETCH_REASON_CODES else "unknown_schema"


def _normalize_iso8601(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _normalize_crawl_source(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if "quick" in raw:
        return "quick_crawl"
    if any(token in raw for token in ("scheduled", "daily", "batch", "cron")):
        return "scheduled_crawl"
    return raw


def normalize_lp_fetch_error_code(value: object) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    mapping = {
        "timeout": "timeout",
        "connect_error": "dns_error",
        "dns_error": "dns_error",
        "name_not_resolved": "dns_error",
        "blocked": "blocked",
        "forbidden": "blocked",
        "access_denied": "blocked",
        "invalid_html": "invalid_html",
        "parse_error": "invalid_html",
        "empty_html": "invalid_html",
        "tiny_body": "invalid_html",
        "redirect_loop": "redirect_loop",
        "too_many_redirects": "redirect_loop",
        "http_error": "http_error",
        "404": "http_error",
        "500": "http_error",
        "unknown": "unknown",
    }
    if raw in LP_FETCH_ERROR_CODES:
        return raw
    if raw in mapping:
        return mapping[raw]
    if raw.isdigit() and raw.startswith(("4", "5")):
        return "http_error"
    for token, normalized in mapping.items():
        if token in raw:
            return normalized
    return "unknown"


def _coalesce_lp_info(meta: dict, ad: "Ad") -> dict:
    lp_data = meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}
    lp_analysis = meta.get("lp_analysis") if isinstance(meta.get("lp_analysis"), dict) else {}
    lp_normalized = meta.get("lp_normalized") if isinstance(meta.get("lp_normalized"), dict) else {}
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    merged = {
        "final_url": (
            lp_info.get("final_url")
            or lp_data.get("final_url")
            or lp_analysis.get("final_url")
            or lp_normalized.get("final_url")
            or meta.get("lp_final_url")
            or meta.get("final_url")
            or getattr(ad, "destination_url", None)
        ),
        "http_status": (
            lp_info.get("http_status")
            or lp_data.get("http_status")
            or lp_analysis.get("http_status")
            or meta.get("lp_status_code")
            or meta.get("http_status")
        ),
        "title": (
            lp_info.get("title")
            or lp_data.get("title")
            or lp_analysis.get("title")
            or lp_normalized.get("title")
            or meta.get("title")
        ),
        "description": (
            lp_info.get("description")
            or lp_data.get("description")
            or lp_analysis.get("description")
            or lp_data.get("meta_description")
            or lp_analysis.get("meta_description")
            or meta.get("description")
            or meta.get("meta_description")
        ),
        "canonical": (
            lp_info.get("canonical")
            or lp_data.get("canonical")
            or lp_analysis.get("canonical")
            or lp_normalized.get("canonical")
            or meta.get("canonical")
        ),
        "og_image": (
            lp_info.get("og_image")
            or lp_data.get("og_image")
            or lp_data.get("og_image_url")
            or lp_analysis.get("og_image")
            or lp_analysis.get("og_image_url")
            or meta.get("og_image")
            or meta.get("og_image_url")
        ),
        "lang": (
            lp_info.get("lang")
            or lp_data.get("lang")
            or lp_analysis.get("lang")
            or lp_normalized.get("lang")
            or meta.get("lang")
        ),
        "fetched_at": _normalize_iso8601(
            lp_info.get("fetched_at")
            or lp_data.get("fetched_at")
            or lp_analysis.get("fetched_at")
            or lp_normalized.get("normalized_at")
            or meta.get("lp_snapshot_at")
        ),
    }
    return {key: value for key, value in merged.items() if value not in (None, "", [])}


def normalize_operational_metadata(ad: "Ad") -> None:
    meta = dict(ad.ad_metadata or {})
    if not meta:
        ad.ad_metadata = meta
        return

    last_crawled_at = _normalize_iso8601(
        meta.get("last_crawled_at")
        or meta.get("crawl_completed_at")
        or meta.get("last_checked_at")
        or getattr(ad, "updated_at", None)
    )
    if last_crawled_at:
        meta["last_crawled_at"] = last_crawled_at

    crawl_source = _normalize_crawl_source(meta.get("crawl_source") or meta.get("source"))
    if crawl_source:
        meta["crawl_source"] = crawl_source

    ttl = meta.get("freshness_ttl_sec")
    if ttl in (None, "") and last_crawled_at:
        meta["freshness_ttl_sec"] = 72 * 60 * 60
    else:
        try:
            meta["freshness_ttl_sec"] = int(ttl)
        except (TypeError, ValueError):
            pass

    lp_snapshot_at = _normalize_iso8601(
        meta.get("lp_snapshot_at")
        or meta.get("lp_fetched_at")
        or meta.get("final_url_checked_at")
        or meta.get("last_lp_fetch_at")
    )
    if lp_snapshot_at:
        meta["lp_snapshot_at"] = lp_snapshot_at

    lp_info = _coalesce_lp_info(meta, ad)
    if lp_info:
        meta["lp_info"] = lp_info
        if "fetched_at" in lp_info and "lp_snapshot_at" not in meta:
            meta["lp_snapshot_at"] = lp_info["fetched_at"]

    lp_error_code = normalize_lp_fetch_error_code(
        meta.get("lp_fetch_error_code")
        or meta.get("lp_fetch_reason")
        or meta.get("lp_quality_issue")
        or meta.get("lp_status")
        or meta.get("lp_fetch_status")
    )
    if lp_error_code:
        meta["lp_fetch_error_code"] = lp_error_code

    ad.ad_metadata = meta


def enforce_creative_fetch_policy(ad: "Ad") -> None:
    """A-0303-P1/P2 policy enforcement before saving ad metadata."""
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else None
    if meta is None:
        return

    normalize_operational_metadata(ad)
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else None
    if meta is None:
        return

    has_fetch_context = any(
        key in meta
        for key in (
            "creative_fetch_status",
            "creative_fetch_source",
            "creative_fetch_reason",
            "orientation",
            "aspect_ratio",
            *CREATIVE_FETCH_ID_KEYS,
        )
    )
    if not has_fetch_context:
        return

    source = meta.get("creative_fetch_source")
    if source is None or (isinstance(source, str) and not source.strip()):
        raise ValueError("creative_fetch_source is required when creative fetch metadata is present")

    orientation = meta.get("orientation")
    if orientation is not None:
        orientation_value = str(orientation).strip().lower()
        if orientation_value not in CREATIVE_ORIENTATIONS:
            raise ValueError(f"invalid orientation: {orientation}")
        meta["orientation"] = orientation_value

    for id_key in CREATIVE_FETCH_ID_KEYS:
        if id_key in meta and meta[id_key] is not None and str(meta[id_key]) != str(ad.id):
            raise ValueError(f"ad_id mismatch: {id_key}={meta[id_key]} expected={ad.id}")

    if "creative_fetch_reason" in meta:
        meta["creative_fetch_reason"] = normalize_creative_fetch_reason(meta.get("creative_fetch_reason"))

    ad.ad_metadata = meta


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


class MediaExtractionStatus(str, enum.Enum):
    """Status of media extraction for an ad."""
    PENDING = "pending"
    PENDING_HEAVY = "pending_heavy"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    ENRICHED = "enriched"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class Ad(Base):
    __tablename__ = "ads"
    __table_args__ = (
        Index("idx_ads_platform_created", "platform", "created_at"),
        Index("idx_ads_advertiser", "advertiser_name"),
        Index("idx_ads_category", "category"),
        Index("idx_ads_status", "status"),
        Index("idx_ads_view_count", "view_count"),
        Index("idx_ads_brand", "brand_name"),
        Index("idx_ads_created_desc", "created_at"),
        Index("idx_ads_platform_status", "platform", "status"),
        Index("idx_ads_creative_type", "creative_type"),
        # CI-016: Added for common query patterns
        Index("idx_ads_media_extraction_status", "media_extraction_status"),
        Index("idx_ads_first_seen", "first_seen_at"),
        Index("idx_ads_last_seen", "last_seen_at"),
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

    # Creative type & media metadata
    creative_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # video/image/carousel/unknown
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # original thumbnail source URL
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_s3_keys: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # carousel multiple images
    video_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    snapshot_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # platform preview URL
    destination_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # CTA destination URL
    media_extraction_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # pending/completed/failed/skipped
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

    # Operational metrics
    spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reach: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cpc: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Dates
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Flexible metadata (attribute named ad_metadata to avoid SQLAlchemy reserved word)
    ad_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, default=list, nullable=True)

    # Hit proxy score (reference architecture)
    hit_proxy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    active_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Brand registry link
    brand_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("brand_registry.id", ondelete="SET NULL"), nullable=True
    )

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


# SQLAlchemy requires this runtime import to register AdAnalysis with Base.metadata
# so that the Ad.analysis relationship can resolve. Do NOT move to TYPE_CHECKING.
from app.models.analysis import AdAnalysis  # noqa: E402


@event.listens_for(Ad, "before_insert")
def _ad_before_insert(mapper, connection, target):  # noqa: ANN001,ARG001
    enforce_creative_fetch_policy(target)


@event.listens_for(Ad, "before_update")
def _ad_before_update(mapper, connection, target):  # noqa: ANN001,ARG001
    enforce_creative_fetch_policy(target)
