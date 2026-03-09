"""Ad-related Pydantic schemas."""

from datetime import datetime, timedelta, timezone
import re
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

CREATIVE_LIBRARY_REASON_REGISTRY = {
    "missing_creative": "No usable creative or snapshot metadata is available.",
    "download_unavailable": "Creative is viewable but no downloadable asset is currently cached.",
    "snapshot_only": "Only snapshot-based preview information is available.",
    "lp_missing": "No landing-page destination URL is attached to the ad.",
    "lp_unresolved": "Landing-page resolution failed or has not completed successfully.",
    "real": "Metric is backed by an observed value from the source system or persisted contract field.",
    "estimated": "Metric is derived from estimation, aggregation, or heuristic fallback.",
    "missing": "Metric is currently unavailable.",
    "stale": "Metric exists but is older than the freshness threshold.",
}

MEDIA_STATUS_REASON_CODES = set(CREATIVE_LIBRARY_REASON_REGISTRY)

BULK_DOWNLOAD_SKIPPED_REASON_CODES = set(CREATIVE_LIBRARY_REASON_REGISTRY)

DOWNLOAD_FAILURE_REASON_CODES = {
    "no_cached_media",
    "zip_creation_failed",
    "invalid_ad_ids",
    "download_file_missing",
}

LP_STATUS_VOCAB = {
    "alive",
    "redirect",
    "dead",
    "unreachable",
    "unresolved",
}

METRIC_STATUS_VOCAB = {
    "real",
    "estimated",
    "missing",
}

FRESHNESS_STATUS_VOCAB = {
    "fresh",
    "stale",
    "unknown",
}

_METRIC_FRESHNESS_DAYS = 7
_JP_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]")
_KANA_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\uff65-\uff9f]")
_LATIN_RE = re.compile(r"[A-Za-z]")


class MetricProvenanceResponse(BaseModel):
    metric_source: str = ""
    metric_status: str = "missing"
    freshness_status: str = "unknown"
    measured_at: str | None = None
    confidence_label: str = "none"


class LanguageTaxonomyResponse(BaseModel):
    language: str = "unknown"
    language_status: str = "unknown"
    language_confidence: float = 0.0
    language_source: str = "missing"
    product_category: str = "uncategorized"
    product_subcategory: str = ""
    exclude_from_analysis: bool = False
    exclude_reason: str | None = None


class MetaFreshnessResponse(BaseModel):
    metric_source: str = "missing"
    creative_source: str = "missing"
    lp_source: str = "missing"
    metric_status: str = "missing"
    creative_status: str = "missing"
    lp_status: str = "missing"
    freshness_status: str = "unknown"
    last_meta_success_at: str | None = None
    meta_quality_state: str = "missing"
    meta_recovery_reason: str | None = None


class MediaStatusResponse(BaseModel):
    viewable: bool
    downloadable: bool
    has_lp: bool
    primary_type: str
    missing_reasons: list[str] = Field(default_factory=list)


class LPInfoResponse(BaseModel):
    destination_url: str | None = None
    domain: str = ""
    destination_type: str = ""
    lp_status: str = "unresolved"
    lp_score: float | int | None = None
    has_lp: bool = False
    resolved_url: str | None = None
    redirect_chain: list[str] = Field(default_factory=list)
    final_domain: str = ""
    http_status: int | None = None


def _extract_metric_scalar(value):
    if isinstance(value, dict):
        for key in ("score", "value", "amount", "metric"):
            if value.get(key) is not None:
                return value.get(key)
        return None
    return value


def _coerce_metric_datetime(*values) -> datetime | None:
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _serialize_metric_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _status_from_metric_source(metric_source: str | None) -> str | None:
    text = str(metric_source or "").strip().lower()
    if not text:
        return None
    if any(token in text for token in ("estimated", "heuristic", "model", "aggregate")):
        return "estimated"
    if text == "missing":
        return "missing"
    return "real"


def _normalize_metric_source(metric_name: str, metric_status: str, metric_source: str | None) -> str:
    if metric_source:
        return str(metric_source)
    defaults = {
        "spend": "observed_spend" if metric_status == "real" else "estimated_spend",
        "impressions": "observed_impressions" if metric_status == "real" else "estimated_impressions",
        "reach": "observed_reach" if metric_status == "real" else "estimated_reach",
        "lp_score": "lp_analysis",
        "extract_quality_score": "creative_extraction",
    }
    if metric_status == "missing":
        return "missing"
    return defaults.get(metric_name, "observed_metric")


def _metric_confidence_label(metric_status: str, freshness_status: str) -> str:
    if metric_status == "missing":
        return "none"
    if metric_status == "real" and freshness_status == "fresh":
        return "high"
    if metric_status == "real":
        return "medium"
    if freshness_status == "fresh":
        return "medium"
    return "low"


def _build_metric_provenance(metric_name: str, value, *, metric_source: str | None = None, measured_at: datetime | None = None) -> dict:
    normalized_value = _extract_metric_scalar(value)
    inferred_status = _status_from_metric_source(metric_source)
    if normalized_value is None:
        metric_status = "missing"
    else:
        metric_status = inferred_status or "real"
    freshness_status = "unknown"
    if normalized_value is not None and measured_at is not None:
        freshness_status = "stale" if measured_at < datetime.now(timezone.utc) - timedelta(days=_METRIC_FRESHNESS_DAYS) else "fresh"
    metric_source = _normalize_metric_source(metric_name, metric_status, metric_source)
    return MetricProvenanceResponse(
        metric_source=metric_source,
        metric_status=metric_status,
        freshness_status=freshness_status,
        measured_at=_serialize_metric_datetime(measured_at),
        confidence_label=_metric_confidence_label(metric_status, freshness_status),
    ).model_dump()


def build_real_metrics_payload(ad, overrides: dict | None = None, source_overrides: dict | None = None) -> dict:
    """Return normalized metric values plus provenance siblings."""
    overrides = overrides or {}
    source_overrides = source_overrides or {}
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}

    updated_at = getattr(ad, "updated_at", None)
    last_crawled_at = _coerce_metric_datetime(meta.get("last_crawled_at"), meta.get("metrics_measured_at"), updated_at)

    lp_score_value = overrides.get("lp_score", meta.get("lp_score"))
    extract_quality_value = overrides.get("extract_quality_score", meta.get("extract_quality_score"))

    values = {
        "spend": overrides.get("spend", getattr(ad, "spend", None) if ad is not None else None),
        "impressions": overrides.get("impressions", getattr(ad, "impressions", None) if ad is not None else None),
        "reach": overrides.get("reach", getattr(ad, "reach", None) if ad is not None else None),
        "lp_score": _extract_metric_scalar(lp_score_value),
        "extract_quality_score": _extract_metric_scalar(extract_quality_value),
    }

    metric_sources = {
        "spend": source_overrides.get("spend")
        or meta.get("spend_metric_source")
        or meta.get("spend_source")
        or ("observed_spend" if getattr(ad, "spend", None) is not None else "estimated_spend" if values["spend"] is not None else "missing"),
        "impressions": source_overrides.get("impressions")
        or meta.get("impressions_metric_source")
        or meta.get("impressions_source")
        or ("observed_impressions" if getattr(ad, "impressions", None) is not None else "estimated_impressions" if values["impressions"] is not None else "missing"),
        "reach": source_overrides.get("reach")
        or meta.get("reach_metric_source")
        or meta.get("reach_source")
        or ("observed_reach" if getattr(ad, "reach", None) is not None else "estimated_reach" if values["reach"] is not None else "missing"),
        "lp_score": source_overrides.get("lp_score") or meta.get("lp_score_source") or ("lp_analysis" if values["lp_score"] is not None else "missing"),
        "extract_quality_score": source_overrides.get("extract_quality_score")
        or meta.get("extract_quality_score_source")
        or ("creative_extraction" if values["extract_quality_score"] is not None else "missing"),
    }

    metric_timestamps = {
        "spend": _coerce_metric_datetime(meta.get("spend_measured_at"), last_crawled_at),
        "impressions": _coerce_metric_datetime(meta.get("impressions_measured_at"), last_crawled_at),
        "reach": _coerce_metric_datetime(meta.get("reach_measured_at"), last_crawled_at),
        "lp_score": _coerce_metric_datetime(meta.get("lp_score_measured_at"), meta.get("lp_analyzed_at"), updated_at, last_crawled_at),
        "extract_quality_score": _coerce_metric_datetime(meta.get("extract_quality_score_measured_at"), meta.get("creative_extracted_at"), updated_at, last_crawled_at),
    }

    payload = {}
    for metric_name, metric_value in values.items():
        payload[metric_name] = metric_value
        payload[f"{metric_name}_provenance"] = _build_metric_provenance(
            metric_name,
            metric_value,
            metric_source=metric_sources[metric_name],
            measured_at=metric_timestamps[metric_name],
        )
    return payload


def _parsed_domain(url: str | None) -> str:
    if not url:
        return ""
    return urlparse(str(url)).netloc


def _normalize_language_tag(value: object) -> str | None:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    if raw in {"ja", "ja-jp", "jp", "japanese"} or raw.startswith("ja-"):
        return "ja"
    return raw


def _is_japanese_text(text: str | None) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    jp_count = len(_JP_RE.findall(raw))
    if jp_count == 0:
        return False
    kana_count = len(_KANA_RE.findall(raw))
    if kana_count < 2:
        return False
    if (kana_count / jp_count) < 0.2:
        return False
    latin_count = len(_LATIN_RE.findall(raw))
    if latin_count == 0:
        return True
    return (jp_count / (jp_count + latin_count)) >= 0.1


def _ad_language_detection_text(ad) -> str:
    return " ".join(
        filter(
            None,
            [
                getattr(ad, "title", None),
                getattr(ad, "description", None),
                getattr(ad, "advertiser_name", None),
                getattr(ad, "brand_name", None),
            ],
        )
    )


def build_language_taxonomy_payload(ad) -> dict:
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}
    normalized_language = _normalize_language_tag(meta.get("language"))
    language_source = str(meta.get("language_source") or "missing")
    text = _ad_language_detection_text(ad)
    inferred_is_jp = _is_japanese_text(text)

    if normalized_language == "ja":
        language = "ja"
        language_status = "ja"
    elif normalized_language:
        language = normalized_language
        language_status = "non-ja"
    elif inferred_is_jp:
        language = "ja"
        language_status = "ja"
        language_source = "rule_text"
    elif text:
        language = "unknown"
        language_status = "non-ja"
        if language_source == "missing":
            language_source = "rule_text"
    else:
        language = "unknown"
        language_status = "unknown"

    raw_confidence = meta.get("language_confidence")
    try:
        language_confidence = round(float(raw_confidence), 4) if raw_confidence is not None else (0.9 if language_status == "ja" and language_source != "missing" else 0.6 if language_status == "non-ja" else 0.0)
    except (TypeError, ValueError):
        language_confidence = 0.0

    product_category = str(
        meta.get("product_category")
        or meta.get("product_name")
        or (getattr(getattr(ad, "category", None), "value", None) or getattr(ad, "category", None) or "uncategorized")
    )
    product_subcategory = str(meta.get("product_subcategory") or meta.get("topic_label") or "")
    exclude_from_analysis = bool(meta.get("exclude_from_analysis") is True or language_status == "non-ja")
    exclude_reason = str(meta.get("exclude_reason") or ("non_japanese" if language_status == "non-ja" else "")) or None

    return LanguageTaxonomyResponse(
        language=language,
        language_status=language_status,
        language_confidence=language_confidence,
        language_source=language_source,
        product_category=product_category,
        product_subcategory=product_subcategory,
        exclude_from_analysis=exclude_from_analysis,
        exclude_reason=exclude_reason,
    ).model_dump()


def _normalize_meta_source(source_kind: str, value) -> str:
    raw = str(value or "").strip().lower()
    allowed = {
        "metric": {"api", "estimated", "missing", "stale"},
        "creative": {"api", "browser", "playwright_render_ad", "missing"},
        "lp": {"api", "browser", "httpx", "missing"},
    }
    if raw in allowed[source_kind]:
        return raw
    if source_kind == "metric":
        if any(token in raw for token in ("estimated", "heuristic", "model", "aggregate")):
            return "estimated"
        if "stale" in raw:
            return "stale"
    if source_kind == "creative":
        if "playwright" in raw:
            return "playwright_render_ad"
        if "browser" in raw:
            return "browser"
    if source_kind == "lp":
        if "httpx" in raw:
            return "httpx"
        if "browser" in raw:
            return "browser"
    if "api" in raw:
        return "api"
    return "missing"


def _meta_status_from_source(source_kind: str, source_value: str) -> str:
    source = _normalize_meta_source(source_kind, source_value)
    if source == "estimated":
        return "estimated"
    if source == "stale":
        return "stale"
    if source == "missing":
        return "missing"
    return "real"


def build_meta_freshness_payload(ad) -> dict:
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}
    updated_at = getattr(ad, "updated_at", None)

    metric_source = _normalize_meta_source("metric", meta.get("metric_source"))
    creative_source = _normalize_meta_source("creative", meta.get("creative_source"))
    lp_source = _normalize_meta_source("lp", meta.get("lp_source"))

    last_meta_success_at = _coerce_metric_datetime(
        meta.get("last_meta_success_at"),
        meta.get("last_crawled_at"),
        meta.get("metrics_measured_at"),
        updated_at,
    )
    freshness_status = "unknown"
    if last_meta_success_at is not None:
        freshness_status = "stale" if last_meta_success_at < datetime.now(timezone.utc) - timedelta(days=_METRIC_FRESHNESS_DAYS) else "fresh"

    metric_status = _meta_status_from_source("metric", metric_source)
    creative_status = _meta_status_from_source("creative", creative_source)
    lp_status = _meta_status_from_source("lp", lp_source)

    raw_quality_state = str(meta.get("meta_quality_state") or "").strip().lower()
    if raw_quality_state in {"real", "estimated", "missing", "stale"}:
        meta_quality_state = raw_quality_state
    elif freshness_status == "stale" and any(status == "real" for status in (metric_status, creative_status, lp_status)):
        meta_quality_state = "stale"
    elif metric_status == "estimated":
        meta_quality_state = "estimated"
    elif any(status == "real" for status in (metric_status, creative_status, lp_status)):
        meta_quality_state = "real"
    else:
        meta_quality_state = "missing"

    return MetaFreshnessResponse(
        metric_source=metric_source,
        creative_source=creative_source,
        lp_source=lp_source,
        metric_status=metric_status,
        creative_status=creative_status,
        lp_status=lp_status,
        freshness_status=freshness_status,
        last_meta_success_at=_serialize_metric_datetime(last_meta_success_at),
        meta_quality_state=meta_quality_state,
        meta_recovery_reason=str(meta.get("meta_recovery_reason") or "") or None,
    ).model_dump()


def _normalize_redirect_chain(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def _coerce_http_status(*values) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            status = int(value)
        except (TypeError, ValueError):
            continue
        if status > 0:
            return status
    return None


def _classify_destination_type(url: str | None) -> str:
    if not url:
        return ""
    lowered = str(url).lower()
    if "apps.apple.com" in lowered or "play.google.com" in lowered:
        return "app_download"
    if "line.me" in lowered or "lin.ee" in lowered:
        return "line_add"
    if any(token in lowered for token in ("/cart", "/checkout", "/buy", "/purchase")):
        return "purchase"
    return "lp"


def normalize_lp_status(
    raw_status,
    *,
    http_status: int | None = None,
    redirect_chain: list[str] | None = None,
    resolved_url: str | None = None,
    destination_url: str | None = None,
) -> str:
    text = str(raw_status or "").strip().lower()
    redirects = redirect_chain or []

    if text in LP_STATUS_VOCAB:
        return text
    if http_status is not None:
        if 200 <= http_status < 300:
            if redirects or (resolved_url and destination_url and resolved_url != destination_url):
                return "redirect"
            return "alive"
        if 300 <= http_status < 400:
            return "redirect"
        if 400 <= http_status < 600:
            return "dead"
    if text in {"200", "success", "ok", "completed"}:
        return "redirect" if redirects else "alive"
    if text in {"301", "302", "303", "307", "308", "redirect"}:
        return "redirect"
    if text in {"404", "410", "dead", "failed"}:
        return "dead"
    if any(token in text for token in ("timeout", "dns", "connect", "refused", "ssl", "unreachable")):
        return "unreachable"
    if redirects or (resolved_url and destination_url and resolved_url != destination_url):
        return "redirect"
    if resolved_url:
        return "alive"
    return "unresolved"


def build_lp_info_payload(ad) -> dict:
    """Return a normalized LP contract payload for an ad-like object."""
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}

    destination_url = getattr(ad, "destination_url", None) or meta.get("destination_url")
    redirect_chain = _normalize_redirect_chain(meta.get("redirect_chain") or meta.get("lp_redirect_chain"))
    resolved_url = (
        meta.get("resolved_url")
        or meta.get("lp_resolved_url")
        or meta.get("lp_final_url")
        or meta.get("final_url")
        or (redirect_chain[-1] if redirect_chain else None)
    )
    http_status = _coerce_http_status(
        meta.get("lp_http_status"),
        meta.get("http_status"),
        meta.get("lp_status"),
        meta.get("lp_fetch_status"),
    )
    lp_status = normalize_lp_status(
        meta.get("lp_status") or meta.get("lp_fetch_status"),
        http_status=http_status,
        redirect_chain=redirect_chain,
        resolved_url=resolved_url,
        destination_url=destination_url,
    )

    if not resolved_url and lp_status == "alive" and destination_url:
        resolved_url = destination_url

    final_domain = _parsed_domain(resolved_url) or (redirect_chain and _parsed_domain(redirect_chain[-1])) or ""

    return LPInfoResponse(
        destination_url=destination_url,
        domain=_parsed_domain(destination_url),
        destination_type=str(meta.get("destination_type") or _classify_destination_type(destination_url)),
        lp_status=lp_status,
        lp_score=_extract_metric_scalar(meta.get("lp_score")),
        has_lp=bool(destination_url),
        resolved_url=resolved_url,
        redirect_chain=redirect_chain,
        final_domain=final_domain,
        http_status=http_status,
    ).model_dump()


def build_media_status_payload(ad) -> dict:
    """Return the fixed creative-library media_status contract for an ad-like object."""
    meta = getattr(ad, "ad_metadata", None)
    meta = meta if isinstance(meta, dict) else {}
    lp_info = build_lp_info_payload(ad)

    viewable = bool(
        getattr(ad, "thumbnail_url", None)
        or getattr(ad, "image_url", None)
        or getattr(ad, "video_url", None)
        or getattr(ad, "thumbnail_s3_key", None)
        or getattr(ad, "image_s3_key", None)
        or getattr(ad, "s3_key", None)
        or getattr(ad, "snapshot_url", None)
    )
    downloadable = bool(
        getattr(ad, "image_s3_key", None)
        or getattr(ad, "thumbnail_s3_key", None)
        or getattr(ad, "s3_key", None)
        or meta.get("local_cached_file")
        or meta.get("local_cache_path")
        or meta.get("thumbnail_local_path")
        or meta.get("image_local_path")
        or meta.get("video_local_path")
    )
    has_lp = bool(lp_info["has_lp"])
    snapshot_only = bool(
        getattr(ad, "snapshot_url", None)
        and not any(
            [
                getattr(ad, "thumbnail_url", None),
                getattr(ad, "image_url", None),
                getattr(ad, "video_url", None),
                getattr(ad, "thumbnail_s3_key", None),
                getattr(ad, "image_s3_key", None),
                getattr(ad, "s3_key", None),
            ]
        )
    )
    primary_type = (
        getattr(ad, "creative_type", None)
        or (
            "video" if getattr(ad, "video_url", None) or getattr(ad, "s3_key", None)
            else "image" if getattr(ad, "image_url", None) or getattr(ad, "image_s3_key", None)
            else "thumbnail" if getattr(ad, "thumbnail_url", None) or getattr(ad, "thumbnail_s3_key", None)
            else "unknown"
        )
    )

    missing_reasons: list[str] = []
    if not viewable:
        missing_reasons.append("missing_creative")
    if snapshot_only:
        missing_reasons.append("snapshot_only")
    if viewable and not downloadable:
        missing_reasons.append("download_unavailable")
    if not has_lp:
        missing_reasons.append("lp_missing")
    elif lp_info["lp_status"] in {"dead", "unreachable", "unresolved"}:
        missing_reasons.append("lp_unresolved")

    return MediaStatusResponse(
        viewable=viewable,
        downloadable=downloadable,
        has_lp=has_lp,
        primary_type=str(primary_type).lower(),
        missing_reasons=list(dict.fromkeys([reason for reason in missing_reasons if reason in MEDIA_STATUS_REASON_CODES])),
    ).model_dump()


class AdCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    platform: str
    category: Optional[str] = None
    creative_type: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    advertiser_name: Optional[str] = None
    brand_name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class AdResponse(BaseModel):
    id: int
    external_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    platform: str
    status: str
    category: Optional[str] = None
    creative_type: Optional[str] = None
    video_url: Optional[str] = None
    s3_key: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None
    image_s3_key: Optional[str] = None
    all_image_urls: Optional[list[str]] = None
    snapshot_url: Optional[str] = None
    media_extraction_status: Optional[str] = None
    duration_seconds: Optional[float] = None
    advertiser_name: Optional[str] = None
    brand_name: Optional[str] = None
    estimated_ctr: Optional[float] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    spend: Optional[float] = None
    spend_provenance: MetricProvenanceResponse = Field(default_factory=MetricProvenanceResponse)
    impressions: Optional[int] = None
    impressions_provenance: MetricProvenanceResponse = Field(default_factory=MetricProvenanceResponse)
    cumulative_views: Optional[int] = None
    cumulative_spend: Optional[float] = None
    reach: Optional[int] = None
    reach_provenance: MetricProvenanceResponse = Field(default_factory=MetricProvenanceResponse)
    cpc: Optional[float] = None
    cpm: Optional[float] = None
    frequency: Optional[float] = None
    lp_score: Optional[float | int] = None
    lp_score_provenance: MetricProvenanceResponse = Field(default_factory=MetricProvenanceResponse)
    extract_quality_score: Optional[float | int] = None
    extract_quality_score_provenance: MetricProvenanceResponse = Field(default_factory=MetricProvenanceResponse)
    language: str = "unknown"
    language_status: str = "unknown"
    language_confidence: float = 0.0
    language_source: str = "missing"
    product_category: str = "uncategorized"
    product_subcategory: str = ""
    exclude_from_analysis: bool = False
    exclude_reason: Optional[str] = None
    metric_source: str = "missing"
    creative_source: str = "missing"
    lp_source: str = "missing"
    metric_status: str = "missing"
    creative_status: str = "missing"
    lp_status: str = "missing"
    freshness_status: str = "unknown"
    last_meta_success_at: Optional[str] = None
    meta_quality_state: str = "missing"
    meta_recovery_reason: Optional[str] = None
    tags: Optional[list[str]] = None
    destination_url: Optional[str] = None
    destination_type: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    # Fields extracted from ad_metadata by model_validator
    estimation_method: Optional[str] = None
    days_running: Optional[int] = None
    is_still_running: Optional[bool] = None
    delivery_start_time: Optional[str] = None
    crawl_query: Optional[str] = None
    expanded_from: Optional[str] = None
    ad_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_metadata_fields(cls, data):
        """Extract extra fields from ad_metadata JSONB and resolve thumbnail/image URLs."""
        if hasattr(data, "__dict__"):
            metadata = getattr(data, "ad_metadata", None) or {}
            d = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
            # destination_url: prefer column value, fallback to metadata
            if not d.get("destination_url"):
                d["destination_url"] = metadata.get("destination_url")
            d["destination_type"] = metadata.get("destination_type")
            # Expose ad_metadata for frontend fallback access
            d["ad_metadata"] = metadata
            d.update(build_real_metrics_payload(data))
            d.update(build_language_taxonomy_payload(data))
            d.update(build_meta_freshness_payload(data))
            # Extract key fields from metadata for frontend
            d["estimation_method"] = metadata.get("estimation_method")
            d["delivery_start_time"] = metadata.get("delivery_start_time")
            d["is_still_running"] = metadata.get("is_still_running")
            d["crawl_query"] = metadata.get("crawl_query")
            d["expanded_from"] = metadata.get("expanded_from")
            # Compute days_running from metadata or timestamps
            days = metadata.get("days_running", 0)
            if not days:
                first = getattr(data, "first_seen_at", None)
                if first:
                    from datetime import timezone as _tz
                    now = datetime.now(_tz.utc)
                    if first.tzinfo is None:
                        first = first.replace(tzinfo=_tz.utc)
                    days = max(1, (now - first).days)
            d["days_running"] = days or None
            # all_image_urls: expand from image_s3_keys JSONB
            image_s3_keys = d.get("image_s3_keys")
            if isinstance(image_s3_keys, dict):
                d["all_image_urls"] = image_s3_keys.get("urls", [])
            return d
        if isinstance(data, dict):
            metadata = data.get("ad_metadata") or data.get("metadata") or {}
            if isinstance(metadata, dict):
                if not data.get("destination_url"):
                    data["destination_url"] = metadata.get("destination_url")
                data.setdefault("destination_type", metadata.get("destination_type"))
                data.setdefault("ad_metadata", metadata)
                data.setdefault("estimation_method", metadata.get("estimation_method"))
                data.setdefault("delivery_start_time", metadata.get("delivery_start_time"))
                data.setdefault("is_still_running", metadata.get("is_still_running"))
                data.setdefault("days_running", metadata.get("days_running"))
                data.setdefault("crawl_query", metadata.get("crawl_query"))
                data.setdefault("expanded_from", metadata.get("expanded_from"))
            data.update(build_real_metrics_payload(type("AdLike", (), {"ad_metadata": metadata, "updated_at": data.get("updated_at"), "spend": data.get("spend"), "impressions": data.get("impressions"), "reach": data.get("reach")})()))
            data.update(build_language_taxonomy_payload(type("AdLike", (), {"ad_metadata": metadata, "title": data.get("title"), "description": data.get("description"), "advertiser_name": data.get("advertiser_name"), "brand_name": data.get("brand_name"), "category": data.get("category")})()))
            data.update(build_meta_freshness_payload(type("AdLike", (), {"ad_metadata": metadata, "updated_at": data.get("updated_at")})()))
            image_s3_keys = data.get("image_s3_keys")
            if isinstance(image_s3_keys, dict):
                data["all_image_urls"] = image_s3_keys.get("urls", [])
        return data


class AdListResponse(BaseModel):
    ads: list[AdResponse]
    total: int
    page: int
    page_size: int


class AdSearchRequest(BaseModel):
    query: str
    platforms: Optional[list[str]] = None
    category: Optional[str] = None
    advertiser: Optional[str] = None
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = 1
    page_size: int = 20


class AdAnalysisResponse(BaseModel):
    ad_id: int
    total_scenes: Optional[int] = None
    avg_scene_duration: Optional[float] = None
    face_closeup_ratio: Optional[float] = None
    product_display_ratio: Optional[float] = None
    text_overlay_ratio: Optional[float] = None
    is_ugc_style: Optional[bool] = None
    has_narration: Optional[bool] = None
    has_subtitles: Optional[bool] = None
    hook_type: Optional[str] = None
    hook_text: Optional[str] = None
    hook_score: Optional[float] = None
    cta_text: Optional[str] = None
    overall_sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    full_transcript: Optional[str] = None
    keywords: Optional[list] = None
    dominant_color_palette: Optional[list] = None
    winning_score: Optional[float] = None

    model_config = {"from_attributes": True}


class CrawlRequest(BaseModel):
    query: str
    platforms: list[str] = Field(
        default=[
            "facebook", "instagram", "youtube", "tiktok",
            "yahoo", "x_twitter", "line", "pinterest",
            "smartnews", "google_ads", "gunosy",
        ]
    )
    category: Optional[str] = None
    country: str = Field(default="JP", description="ISO country code for ad targeting filter")
    limit_per_platform: int = Field(default=20, ge=1, le=100)
    auto_analyze: bool = False
    trigger_source: str = Field(default="manual", description="manual or scheduled crawl trigger")
    schedule_window: Optional[str] = Field(default=None, description="morning/noon/night/manual")
    priority: str = Field(default="normal", description="crawl priority hint")


class CrawlResponse(BaseModel):
    task_id: str
    status: str
    message: str


class LPKeywordExtractionRequest(BaseModel):
    max_ads: int = Field(default=5, ge=1, le=50)


class LPKeywordExtractionResponse(BaseModel):
    keywords: list[str]
    sources: list[dict]
    total_ads_scanned: int
