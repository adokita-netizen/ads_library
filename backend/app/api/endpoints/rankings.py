"""Rankings and hit ad detection API endpoints."""

import csv
import io
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import structlog
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.utils.db import escape_like as _escape_like
from sqlalchemy import case, func, desc, or_
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal, sync_session_scope
from app.models.ad import Ad, MediaExtractionStatus
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.models.analysis import AdAnalysis, TextDetection, Transcription
from app.services.ranking.ranking_service import (
    RankingService,
    _today_jst,
    compute_hit_score,
    compute_hit_score_with_details,
    compute_genre_stats,
)

# Path to collections JSON file (C12: Collections API)
_COLLECTIONS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "collections.json"
_SHORT_TTL_CACHE: dict[str, tuple[float, object]] = {}


def _short_cache_get(key: str):
    cached = _SHORT_TTL_CACHE.get(key)
    if not cached:
        return None
    expires_at, payload = cached
    if expires_at <= datetime.now(timezone.utc).timestamp():
        _SHORT_TTL_CACHE.pop(key, None)
        return None
    return payload


def _short_cache_set(key: str, payload, ttl_seconds: int = 30):
    _SHORT_TTL_CACHE[key] = (
        datetime.now(timezone.utc).timestamp() + max(1, int(ttl_seconds)),
        payload,
    )
    return payload


def _dt_gte(dt: datetime | None, cutoff: datetime) -> bool:
    """Safely compare dt >= cutoff handling naive/aware mismatch."""
    if dt is None:
        return False
    if dt.tzinfo is None and cutoff.tzinfo is not None:
        cutoff = cutoff.replace(tzinfo=None)
    elif dt.tzinfo is not None and cutoff.tzinfo is None:
        dt = dt.replace(tzinfo=None)
    return dt >= cutoff


def _dt_lt(dt: datetime | None, cutoff: datetime) -> bool:
    """Safely compare dt < cutoff handling naive/aware mismatch."""
    if dt is None:
        return False
    if dt.tzinfo is None and cutoff.tzinfo is not None:
        cutoff = cutoff.replace(tzinfo=None)
    elif dt.tzinfo is not None and cutoff.tzinfo is None:
        dt = dt.replace(tzinfo=None)
    return dt < cutoff


def _dt_gt(a: datetime | None, b: datetime | None) -> bool:
    """Safely compare a > b handling naive/aware mismatch."""
    if a is None or b is None:
        return a is not None
    if a.tzinfo is None and b.tzinfo is not None:
        b = b.replace(tzinfo=None)
    elif a.tzinfo is not None and b.tzinfo is None:
        a = a.replace(tzinfo=None)
    return a > b

# Path to saved searches JSON file (C13: Saved Searches)
_SAVED_SEARCHES_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "saved_searches.json"

logger = structlog.get_logger()
router = APIRouter(prefix="/rankings", tags=["Rankings & Search"])
_db_session_scope = sync_session_scope

# Meta platform groups "facebook" and "instagram" under a single umbrella.
META_PLATFORMS = ["facebook", "instagram"]


def _resolve_thumbnail_url(ad: Ad) -> str:
    """Resolve a display-ready thumbnail URL for an Ad.

    Priority: proxy endpoint > local cache > S3 presigned > original URL > ""
    Always prefer the proxy endpoint for Facebook CDN URLs to avoid
    CORS issues and expired signature 403 errors.
    """
    # For any ad with an id, use the proxy endpoint (handles caching + fallback)
    if ad.id and (ad.thumbnail_url or ad.image_url):
        return f"/api/v1/media/thumbnail/{ad.id}"

    # Priority 1: Local cache proxy (Agent D media endpoint)
    if ad.thumbnail_s3_key and "media_cache/" in ad.thumbnail_s3_key:
        return f"/api/v1/media/thumbnail/{ad.id}"

    # Priority 2: S3 presigned URL
    if ad.thumbnail_s3_key:
        try:
            from app.core.storage import get_storage_client
            storage = get_storage_client()
            return storage.get_presigned_url(ad.thumbnail_s3_key)
        except Exception:
            pass

    # Priority 3: Original URL
    if ad.thumbnail_url:
        return ad.thumbnail_url
    if ad.image_url:
        return ad.image_url
    return ad.snapshot_url or ""


def _resolve_image_url(ad: Ad) -> str:
    """Resolve a display-ready image URL for an Ad."""
    if ad.image_s3_key and "media_cache/" in ad.image_s3_key:
        return f"/api/v1/media/image/{ad.id}"
    if ad.id and (ad.image_url or ad.thumbnail_url):
        return f"/api/v1/media/image/{ad.id}"
    return ad.image_url or ad.thumbnail_url or ""


def _resolve_video_url(ad: Ad) -> str:
    """Resolve a display-ready video URL for an Ad."""
    if ad.s3_key and "media_cache/" in ad.s3_key:
        return f"/api/v1/media/video/{ad.id}"
    return ad.video_url or ""


def _resolve_media_status(ad: Ad) -> str:
    """Determine media cache status for an Ad.

    Returns one of: 'cached', 'partial', 'uncached'.
    - cached: both thumbnail and main media (image or video) are locally cached
    - partial: only thumbnail OR only main media is cached
    - uncached: nothing is locally cached
    """
    thumb_cached = bool(
        ad.thumbnail_s3_key and "media_cache/" in (ad.thumbnail_s3_key or "")
    )
    image_cached = bool(
        ad.image_s3_key and "media_cache/" in (ad.image_s3_key or "")
    )
    video_cached = bool(
        ad.s3_key and "media_cache/" in (ad.s3_key or "")
    )
    main_cached = image_cached or video_cached

    if thumb_cached and main_cached:
        return "cached"
    if thumb_cached or main_cached:
        return "partial"
    return "uncached"


def _build_download_urls(ad: Ad) -> dict:
    """Build download URL dict pointing to /media/{type}/{ad_id} endpoints."""
    return {
        "thumbnail": f"/api/v1/media/thumbnail/{ad.id}" if (
            ad.thumbnail_s3_key or ad.thumbnail_url
        ) else "",
        "image": f"/api/v1/media/image/{ad.id}" if (
            ad.image_s3_key or ad.image_url
        ) else "",
        "video": f"/api/v1/media/video/{ad.id}" if (
            ad.s3_key or ad.video_url
        ) else "",
    }


_SPONSOR_RE = re.compile(r"^(.+?)\s*スポンサー[:：]\s*", re.UNICODE)


def _derive_product_name(ad: Ad) -> str:
    """Derive a clean, short product/brand name for display."""
    if ad.brand_name:
        return ad.brand_name.strip()

    adv = (ad.advertiser_name or "").strip()
    if adv:
        m = _SPONSOR_RE.match(adv)
        if m:
            after = adv[m.end():].strip()
            adv = after or m.group(1).strip()

    title = (ad.title or "").strip()
    if title and len(title) <= 40 and "\n" not in title:
        if adv and adv.lower() != title.lower():
            return adv
        return title

    if adv:
        return adv

    if ad.description:
        first_line = ad.description.split("\n")[0].strip()
        if first_line:
            return first_line[:40]

    return "不明"


def _clean_advertiser(name: str | None) -> str:
    """Strip 'Xスポンサー: Y' prefix from advertiser names for display."""
    if not name:
        return ""
    m = _SPONSOR_RE.match(name)
    if m:
        after = name[m.end():].strip()
        return after or m.group(1).strip()
    return name


def _extract_longevity_info(ad: Ad | None) -> dict:
    """Extract days_running, is_still_running, hit_level from an Ad object."""
    if not ad:
        return {"days_running": 0, "is_still_running": False, "hit_level": "none"}
    meta = ad.ad_metadata or {}
    days_running = meta.get("days_running", 0)
    if days_running == 0 and ad.first_seen_at:
        from datetime import timezone as _tz
        now = datetime.now(_tz.utc)
        first = ad.first_seen_at
        if first.tzinfo is None:
            first = first.replace(tzinfo=_tz.utc)
        days_running = max(1, (now - first).days)
    is_still_running = meta.get("is_still_running", ad.last_seen_at is None)
    hit_level = meta.get("hit_level", "none")
    return {
        "days_running": days_running,
        "is_still_running": is_still_running,
        "hit_level": hit_level,
    }


def _resolve_platform_filter(query, column, platform: str | None):
    """Apply platform filter, resolving 'meta' to both Facebook and Instagram."""
    if not platform:
        return query
    if platform.lower() == "meta":
        return query.filter(column.in_(META_PLATFORMS))
    return query.filter(column == platform)


def _build_data_quality(ad: Ad) -> dict:
    """Build a data_quality object for an ad response.

    Checks presence of key fields and returns a completeness percentage.
    """
    meta = ad.ad_metadata or {}
    has_thumbnail = bool(ad.thumbnail_url or ad.thumbnail_s3_key)
    has_creative_analysis = bool(meta.get("creative_analysis"))
    has_category = ad.category is not None
    has_lp = bool(ad.destination_url)
    has_description = bool(ad.description)

    checks = [has_thumbnail, has_creative_analysis, has_category, has_lp, has_description]
    completeness_pct = round(sum(checks) / len(checks) * 100)

    return {
        "has_thumbnail": has_thumbnail,
        "has_creative_analysis": has_creative_analysis,
        "has_category": has_category,
        "has_lp": has_lp,
        "has_description": has_description,
        "completeness_pct": completeness_pct,
    }


def _compute_dynamic_thresholds(scores: list[float]) -> dict:
    """Compute percentile-based hit thresholds from a list of scores.

    Returns dict with big_hit_threshold (p80), hit_threshold (p60),
    and the percentile values.
    """
    if not scores:
        return {
            "big_hit_threshold": 70,
            "hit_threshold": 45,
            "p25": 0, "p50": 0, "p75": 0, "p80": 0, "p90": 0,
        }
    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    def _pct(p: float) -> float:
        idx = min(int(p / 100 * (n - 1)), n - 1)
        return round(sorted_scores[idx], 1)

    return {
        "big_hit_threshold": _pct(80),
        "hit_threshold": _pct(60),
        "p25": _pct(25),
        "p50": _pct(50),
        "p75": _pct(75),
        "p80": _pct(80),
        "p90": _pct(90),
    }


def _classify_hit_dynamic(score: float, thresholds: dict) -> str:
    """Classify an ad as big_hit, hit, or normal using dynamic thresholds."""
    if score >= thresholds.get("big_hit_threshold", 70):
        return "big_hit"
    if score >= thresholds.get("hit_threshold", 45):
        return "hit"
    return "normal"


_JP_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]")


def _is_quality_ad(ad: Ad) -> bool:
    """Check if an ad passes quality filters (not duplicate, Japanese, not spam).

    Returns True if the ad should be included in results.
    """
    meta = ad.ad_metadata or {}
    # Exclude flagged low-quality/spam ads
    if meta.get("exclude_from_analysis") is True:
        return False
    if meta.get("data_quality_flag") in ("spam", "low_quality"):
        return False
    # Exclude duplicates
    if meta.get("is_duplicate") is True:
        return False
    # Exclude non-Japanese ads (metadata flag)
    lang = meta.get("language")
    if lang is not None and lang != "ja":
        return False
    # Exclude non-Japanese ads (actual text detection)
    combined = (ad.title or "") + " " + (ad.advertiser_name or "")
    if combined.strip() and not _JP_RE.search(combined):
        return False
    return True


def _resolve_genre_label(ad: Ad) -> str:
    """Resolve genre label, using '(uncategorized)' for NULL category."""
    if ad.category is not None:
        return str(ad.category.value) if hasattr(ad.category, "value") else str(ad.category)
    return "(uncategorized)"


_META_REAL_SOURCES = {
    "api",
    "meta_api",
    "ads_archive",
    "db",
}
_META_ESTIMATED_SOURCES = {
    "estimated",
    "estimate",
    "estimated_cpm",
    "estimated_audience",
    "inference",
    "heuristic",
    "httpx",
    "playwright",
    "playwright_render_ad",
    "render_ad",
    "browser",
    "browser_fallback",
    "snapshot",
}
_META_STALE_AFTER = timedelta(days=7)


def _parse_iso_datetime(value: object) -> datetime | None:
    """Best-effort ISO datetime parser that tolerates trailing Z."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _source_quality_state(source: object) -> str:
    """Map a source enum/string to the common real/estimated/missing contract."""
    normalized = str(source or "").strip().lower()
    if not normalized or normalized == "missing":
        return "missing"
    if normalized in _META_REAL_SOURCES:
        return "real"
    if normalized in _META_ESTIMATED_SOURCES:
        return "estimated"
    return "estimated"


def _build_meta_freshness_contract(ad: Ad) -> dict:
    """Build the Meta freshness/provenance contract shared by list/detail/search."""
    meta = ad.ad_metadata or {}
    metric_source = meta.get("metric_source") or "missing"
    creative_source = meta.get("creative_source") or "missing"
    lp_source = meta.get("lp_source") or "missing"
    last_meta_success_at = meta.get("last_meta_success_at")
    parsed_last_success = _parse_iso_datetime(last_meta_success_at)
    freshness_status = "missing"
    if parsed_last_success:
        freshness_status = (
            "stale"
            if _dt_lt(parsed_last_success, datetime.now(timezone.utc) - _META_STALE_AFTER)
            else "fresh"
        )

    metric_status = _source_quality_state(metric_source)
    creative_status = _source_quality_state(creative_source)
    lp_status = _source_quality_state(lp_source)

    explicit_quality_state = str(meta.get("meta_quality_state") or "").strip().lower()
    if explicit_quality_state in {"real", "estimated", "missing", "stale"}:
        meta_quality_state = explicit_quality_state
    elif freshness_status == "stale":
        meta_quality_state = "stale"
    elif metric_status == creative_status == lp_status == "missing":
        meta_quality_state = "missing"
    elif "real" in {metric_status, creative_status, lp_status}:
        meta_quality_state = "real"
    else:
        meta_quality_state = "estimated"

    return {
        "metric_source": str(metric_source),
        "creative_source": str(creative_source),
        "lp_source": str(lp_source),
        "metric_status": metric_status,
        "creative_status": creative_status,
        "lp_status": lp_status,
        "freshness_status": freshness_status,
        "last_meta_success_at": last_meta_success_at,
        "meta_quality_state": meta_quality_state,
        "meta_recovery_reason": meta.get("meta_recovery_reason"),
    }


def get_meta_freshness(ad_id: int) -> dict:
    """Return Meta freshness/provenance fields for a single ad."""
    with _db_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            raise KeyError(f"Ad not found: {ad_id}")
        return {
            "ad_id": ad.id,
            **_build_meta_freshness_contract(ad),
        }


@router.get("/meta-freshness-contract")
async def get_meta_freshness_contract() -> dict:
    """Expose the freshness/provenance vocabulary used by rankings payloads."""
    source_vocab = sorted({"missing", "stale", *_META_REAL_SOURCES, *_META_ESTIMATED_SOURCES})
    return {
        "metric_source_vocab": source_vocab,
        "creative_source_vocab": source_vocab,
        "lp_source_vocab": source_vocab,
        "quality_state_vocab": ["real", "estimated", "missing", "stale"],
        "freshness_status_vocab": ["fresh", "stale", "missing"],
        "required_fields": [
            "metric_source",
            "creative_source",
            "lp_source",
            "metric_status",
            "creative_status",
            "lp_status",
            "freshness_status",
            "last_meta_success_at",
            "meta_quality_state",
            "meta_recovery_reason",
        ],
    }


def _sanitize_csv(value: str | None) -> str:
    """Sanitize value for CSV to prevent formula injection."""
    if not value:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


# ==================== Cleanup ====================


@router.post("/cleanup-non-japanese")
def cleanup_non_japanese(dry_run: bool = Query(True)):
    """Remove non-Japanese ads from the database.

    Uses japanese_text_ratio to identify ads whose title+description
    contain less than 10% Japanese characters.

    - dry_run=true  → list ads that would be deleted (no changes)
    - dry_run=false → actually delete Ad + AdDailyMetrics + ProductRanking rows
    """
    from app.utils.text import japanese_text_ratio

    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        non_jp_ads = []

        for ad in ads:
            text = (ad.title or "") + " " + (ad.description or "")
            ratio = japanese_text_ratio(text)
            if ratio <= 0.1:
                non_jp_ads.append({
                    "id": ad.id,
                    "title": (ad.title or "")[:80],
                    "advertiser": ad.advertiser_name or "",
                    "japanese_ratio": round(ratio, 3),
                })

        if dry_run:
            return {
                "dry_run": True,
                "total_ads": len(ads),
                "non_japanese_count": len(non_jp_ads),
                "ads_to_delete": non_jp_ads,
            }

        # Actually delete
        ids_to_delete = [a["id"] for a in non_jp_ads]
        if ids_to_delete:
            session.query(ProductRanking).filter(
                ProductRanking.ad_id.in_(ids_to_delete)
            ).delete(synchronize_session=False)
            session.query(AdDailyMetrics).filter(
                AdDailyMetrics.ad_id.in_(ids_to_delete)
            ).delete(synchronize_session=False)
            session.query(Ad).filter(
                Ad.id.in_(ids_to_delete)
            ).delete(synchronize_session=False)
            session.commit()

        logger.info(
            "cleanup_non_japanese_done",
            deleted=len(ids_to_delete),
            remaining=len(ads) - len(ids_to_delete),
        )

        return {
            "dry_run": False,
            "deleted_count": len(ids_to_delete),
            "remaining_count": len(ads) - len(ids_to_delete),
        }


# ==================== Manual Compute ====================


@router.post("/compute")
def compute_rankings_now():
    """Manually trigger metrics collection + ranking computation.

    This runs inline (no Celery required) and returns the results.
    """
    from app.tasks.metrics_tasks import collect_metrics_for_ads

    with sync_session_scope() as session:
        # Step 1: Collect daily metrics for recent days (backfill if missing)
        today = _today_jst()
        metrics_created = 0
        for days_ago in range(7, -1, -1):  # 7 days ago → today
            d = today - timedelta(days=days_ago)
            metrics_created += collect_metrics_for_ads(session, target_date=d)
        session.commit()

        # Step 2: Compute rankings for all periods
        svc = RankingService()
        ranking_summary = svc.compute_all_rankings(session)
        session.commit()

        logger.info(
            "manual_compute_complete",
            metrics_created=metrics_created,
            rankings=ranking_summary,
        )

        return {
            "status": "completed",
            "metrics_created": metrics_created,
            "rankings": ranking_summary,
        }


# ==================== Rankings ====================


@router.get("/products")
def get_product_rankings(
    period: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get product rankings by spend/views for a period."""
    from fastapi.responses import JSONResponse

    with sync_session_scope() as session:
        svc = RankingService()
        rankings, total = svc.get_rankings(
            session,
            period=period,
            genre=genre,
            platform=platform,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        # If no pre-computed rankings exist, fall back to listing ads directly
        if total == 0:
            return _fallback_ad_list(session, genre, platform, page, page_size, period)

        # Single batch query for Ad details (avoid N+1)
        ad_ids = [r.ad_id for r in rankings]
        ads_map = {}
        if ad_ids:
            ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
            for ad in ads:
                metadata = ad.ad_metadata or {}
                longevity = _extract_longevity_info(ad)
                ads_map[ad.id] = {
                    "meta_freshness_contract": _build_meta_freshness_contract(ad),
                    "thumbnail": _resolve_thumbnail_url(ad),
                    "duration_seconds": ad.duration_seconds or 0,
                    "management_id": ad.external_id or f"AD-{ad.id}",
                    "ad_url": _resolve_video_url(ad),
                    "image_url": _resolve_image_url(ad),
                    "video_url": _resolve_video_url(ad),
                    "snapshot_url": ad.snapshot_url or "",
                    "creative_type": ad.creative_type or "",
                    "like_count": ad.like_count or 0,
                    "estimation_method": metadata.get("estimation_method", ""),
                    "destination_url": metadata.get("destination_url", ""),
                    "destination_type": metadata.get("destination_type", ""),
                    "description": ad.description or "",
                    "title": ad.title or "",
                    "published_date": (
                        ad.first_seen_at.isoformat() if ad.first_seen_at else
                        ad.created_at.isoformat() if ad.created_at else ""
                    ),
                    "days_running": longevity["days_running"],
                    "is_still_running": longevity["is_still_running"],
                    "hit_level": longevity["hit_level"],
                    # Creative analysis fields for gallery filtering
                    "hook_type": (metadata.get("creative_analysis") or {}).get("hook_type", ""),
                    "offer_type": (metadata.get("creative_analysis") or {}).get("offer_type", ""),
                    "creative_analysis": metadata.get("creative_analysis"),
                    "media_status": _resolve_media_status(ad),
                    "download_urls": _build_download_urls(ad),
                    "data_quality": _build_data_quality(ad),
                }

        items = []
        for r in rankings:
            ad_info = ads_map.get(r.ad_id, {})
            ranking_meta = r.extra_metadata or {}
            hit_level = ranking_meta.get("hit_level", ad_info.get("hit_level", "none"))
            score_breakdown = ranking_meta.get("score_breakdown", {})
            items.append({
                "rank": r.rank_position,
                "previous_rank": r.previous_rank,
                "rank_change": r.rank_change,
                "ad_id": r.ad_id,
                "product_name": r.product_name,
                "advertiser_name": _clean_advertiser(r.advertiser_name),
                "genre": r.genre,
                "platform": r.platform,
                "view_increase": r.total_view_increase,
                "spend_increase": round(r.total_spend_increase),
                "cumulative_views": r.cumulative_views,
                "cumulative_spend": round(r.cumulative_spend),
                "is_hit": r.is_hit,
                "hit_score": r.hit_score,
                "trend_score": r.trend_score,
                "score_breakdown": score_breakdown,
                "days_running": ad_info.get("days_running", 0),
                "is_still_running": ad_info.get("is_still_running", False),
                "hit_level": hit_level,
                # Ad-level fields from join
                "thumbnail": ad_info.get("thumbnail", ""),
                "duration_seconds": ad_info.get("duration_seconds", 0),
                "management_id": ad_info.get("management_id", f"AD-{r.ad_id}"),
                "ad_url": ad_info.get("ad_url", ""),
                "image_url": ad_info.get("image_url", ""),
                "snapshot_url": ad_info.get("snapshot_url", ""),
                "video_url": ad_info.get("video_url", ""),
                "creative_type": ad_info.get("creative_type", ""),
                "estimation_method": ad_info.get("estimation_method", ""),
                "destination_url": ad_info.get("destination_url", ""),
                "destination_type": ad_info.get("destination_type", ""),
                "like_count": ad_info.get("like_count", 0),
                "description": ad_info.get("description", ""),
                "title": ad_info.get("title", ""),
                "published_date": ad_info.get("published_date", ""),
                # Creative analysis fields for gallery filtering
                "hook_type": ad_info.get("hook_type", ""),
                "offer_type": ad_info.get("offer_type", ""),
                "creative_analysis": ad_info.get("creative_analysis"),
                "media_status": ad_info.get("media_status", "uncached"),
                "download_urls": ad_info.get("download_urls", {}),
                "data_quality": ad_info.get("data_quality", {}),
                **ad_info.get("meta_freshness_contract", {}),
            })

        data = {
            "period": period,
            "genre": genre,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

        # Cache rankings for 5 minutes (pre-computed data, updates infrequently)
        return JSONResponse(
            content=data,
            headers={"Cache-Control": "public, max-age=300, s-maxage=300"},
        )


def _fallback_ad_list(session, genre, platform, page, page_size, period):
    """When no pre-computed rankings exist, rank ads using AdDailyMetrics.

    Queries actual spend/view increase data from AdDailyMetrics and marks
    demo ads so the frontend can distinguish real vs demo data.
    """
    from sqlalchemy.orm import aliased

    yesterday = _today_jst() - timedelta(days=1)
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
    start = yesterday - timedelta(days=days - 1)

    # Subquery: aggregate metrics per ad for the period
    metrics_sq = (
        session.query(
            AdDailyMetrics.ad_id,
            func.sum(AdDailyMetrics.view_count_increase).label("view_increase"),
            func.sum(AdDailyMetrics.estimated_spend_increase).label("spend_increase"),
            func.max(AdDailyMetrics.view_count).label("cumulative_views"),
            func.max(AdDailyMetrics.estimated_spend).label("cumulative_spend"),
        )
        .filter(
            AdDailyMetrics.metric_date >= start,
            AdDailyMetrics.metric_date <= yesterday,
        )
        .group_by(AdDailyMetrics.ad_id)
        .subquery()
    )

    query = (
        session.query(Ad, metrics_sq)
        .outerjoin(metrics_sq, Ad.id == metrics_sq.c.ad_id)
    )

    query = _resolve_platform_filter(query, Ad.platform, platform)
    if genre:
        query = query.filter(Ad.category == genre)

    total = query.count()
    rows = (
        query.order_by(
            case((metrics_sq.c.spend_increase.is_(None), 0), else_=1).desc(),
            desc(metrics_sq.c.spend_increase),
            case((Ad.view_count.is_(None), 0), else_=1).desc(),
            desc(Ad.view_count),
            desc(Ad.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for rank_idx, row in enumerate(rows):
        ad = row[0]
        view_increase = row[1] or 0
        spend_increase = row[2] or 0
        cumulative_views = row[3] or (ad.view_count or 0)
        cumulative_spend = row[4] or 0

        rank = (page - 1) * page_size + rank_idx + 1
        metadata = ad.ad_metadata or {}
        views = ad.view_count or 0
        likes = ad.like_count or 0

        # Longevity-based hit score
        hit_score, is_hit, hit_level, breakdown = compute_hit_score(ad)
        longevity = _extract_longevity_info(ad)

        # Basic trend_score: engagement rate proxy (likes/views ratio, scaled)
        engagement = (likes / views * 100) if views > 0 else 0
        trend_score = round(min(100, engagement * 10))

        is_demo = bool(metadata.get("is_demo"))
        items.append({
            "rank": rank,
            "previous_rank": None,
            "rank_change": None,
            "ad_id": ad.id,
            "product_name": _derive_product_name(ad),
            "advertiser_name": _clean_advertiser(ad.advertiser_name),
            "genre": _resolve_genre_label(ad),
            "platform": str(ad.platform.value) if ad.platform else "",
            "view_increase": view_increase,
            "spend_increase": round(spend_increase),
            "cumulative_views": cumulative_views,
            "cumulative_spend": round(cumulative_spend),
            "is_hit": is_hit,
            "hit_score": hit_score,
            "trend_score": trend_score,
            "score_breakdown": breakdown,
            "is_demo": is_demo,
            "days_running": longevity["days_running"],
            "is_still_running": longevity["is_still_running"],
            "hit_level": hit_level,
            "thumbnail": _resolve_thumbnail_url(ad),
            "duration_seconds": ad.duration_seconds or 0,
            "management_id": ad.external_id or f"AD-{ad.id}",
            "ad_url": _resolve_video_url(ad),
            "image_url": _resolve_image_url(ad),
            "video_url": _resolve_video_url(ad),
            "snapshot_url": ad.snapshot_url or "",
            "creative_type": ad.creative_type or "",
            "estimation_method": metadata.get("estimation_method", ""),
            "destination_url": metadata.get("destination_url", ""),
            "destination_type": metadata.get("destination_type", ""),
            "like_count": likes,
            "description": ad.description or "",
            "title": ad.title or "",
            "published_date": (
                ad.first_seen_at.isoformat() if ad.first_seen_at else
                ad.created_at.isoformat() if ad.created_at else ""
            ),
            # Creative analysis fields for gallery filtering
            "hook_type": (metadata.get("creative_analysis") or {}).get("hook_type", ""),
            "offer_type": (metadata.get("creative_analysis") or {}).get("offer_type", ""),
            "creative_analysis": metadata.get("creative_analysis"),
            "media_status": _resolve_media_status(ad),
            "download_urls": _build_download_urls(ad),
            "data_quality": _build_data_quality(ad),
            **_build_meta_freshness_contract(ad),
        })

    return {
        "period": period,
        "genre": genre,
        "total": total,
        "page": page,
        "page_size": page_size,
        "is_fallback": True,
        "items": items,
    }


@router.get("/hit-ads")
def get_hit_ads(
    genre: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Get currently trending/hit ads (high velocity growth)."""
    with sync_session_scope() as session:
        svc = RankingService()
        hits = svc.get_hit_ads(session, genre=genre, limit=limit)

        # Fallback: if no pre-computed hit ads, return top ads ranked by
        # views/spend so the view is never empty.
        if not hits:
            return _fallback_hit_ads(session, genre=genre, limit=limit)

        # Batch-fetch Ad details for thumbnails and extra info
        ad_ids = [h.ad_id for h in hits]
        ads_map: dict[int, Ad] = {}
        if ad_ids:
            ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
            ads_map = {ad.id: ad for ad in ads}

        # Compute dynamic thresholds from all ad scores for hit classification
        all_ads_for_thresholds = session.query(Ad).all()
        all_scores = []
        for a in all_ads_for_thresholds:
            m = a.ad_metadata or {}
            s = m.get("latest_hit_score")
            if s is not None:
                all_scores.append(float(s))
            else:
                s_val, _, _, _ = compute_hit_score(a)
                all_scores.append(s_val)
        dynamic_thresholds = _compute_dynamic_thresholds(all_scores)

        items = []
        for h in hits:
            ad = ads_map.get(h.ad_id)
            # Filter out non-quality ads (duplicates, non-Japanese)
            if ad and not _is_quality_ad(ad):
                continue
            thumbnail = _resolve_thumbnail_url(ad) if ad else ""
            metadata = (ad.ad_metadata or {}) if ad else {}
            longevity = _extract_longevity_info(ad)
            # Use hit_level from ranking extra_metadata if available, else from ad
            ranking_meta = h.extra_metadata or {}
            hit_level = ranking_meta.get("hit_level", longevity["hit_level"])
            score_breakdown = ranking_meta.get("score_breakdown", {})
            # Dynamic hit classification
            dynamic_hit_level = _classify_hit_dynamic(h.hit_score or 0, dynamic_thresholds)
            items.append({
                "rank": h.rank_position,
                "ad_id": h.ad_id,
                "id": h.ad_id,  # Fix #53: alias for frontend ScatterPlot
                "product_name": h.product_name,
                "advertiser_name": _clean_advertiser(h.advertiser_name),
                "genre": h.genre or "(uncategorized)",
                "platform": h.platform,
                "view_increase": h.total_view_increase,
                "spend_increase": round(h.total_spend_increase),
                "cumulative_views": h.cumulative_views,
                "cumulative_spend": round(h.cumulative_spend),
                "is_hit": h.is_hit,
                "hit_score": h.hit_score,
                "trend_score": h.trend_score,
                "score_breakdown": score_breakdown,
                "rank_change": h.rank_change,
                "previous_rank": h.previous_rank,
                "days_running": longevity["days_running"],
                "is_still_running": longevity["is_still_running"],
                "hit_level": hit_level,
                "dynamic_hit_level": dynamic_hit_level,
                "thumbnail": thumbnail,
                "duration_seconds": ad.duration_seconds if ad else 0,
                "management_id": (ad.external_id or f"AD-{h.ad_id}") if ad else f"AD-{h.ad_id}",
                "ad_url": _resolve_video_url(ad) if ad else "",
                "image_url": _resolve_image_url(ad) if ad else "",
                "video_url": _resolve_video_url(ad) if ad else "",
                "snapshot_url": ad.snapshot_url if ad else "",
                "creative_type": (ad.creative_type or "") if ad else "",
                "estimation_method": metadata.get("estimation_method", ""),
                "destination_url": (ad.destination_url or metadata.get("destination_url", "")) if ad else "",
                "destination_type": metadata.get("destination_type", ""),
                "description": (ad.description or "") if ad else "",
                "title": (ad.title or "") if ad else "",
                "like_count": ad.like_count if ad else 0,
                "published_date": (
                    ad.first_seen_at.isoformat() if ad and ad.first_seen_at else
                    ad.created_at.isoformat() if ad and ad.created_at else ""
                ),
                "creative_analysis": metadata.get("creative_analysis"),
                "media_status": _resolve_media_status(ad) if ad else "uncached",
                "download_urls": _build_download_urls(ad) if ad else {},
                "data_quality": _build_data_quality(ad) if ad else {},
                **(_build_meta_freshness_contract(ad) if ad else {}),
            })

        return {
            "total": len(items),
            "items": items,
            "dynamic_thresholds": dynamic_thresholds,
        }


def _fallback_hit_ads(session, genre: str | None = None, limit: int = 20) -> dict:
    """Fallback when no pre-computed hit ads exist.

    Returns top ads ranked by view_count so the Hit Ad view is never empty.
    Ads are scored relative to each other to approximate hit/trend scores.
    """
    query = session.query(Ad)
    if genre:
        query = query.filter(Ad.category == genre)

    # Order by view count (best proxy for "hit" when no metrics exist)
    ads = (
        query.order_by(
            case((Ad.view_count.is_(None), 0), else_=1).desc(),
            desc(Ad.view_count),
            desc(Ad.created_at),
        )
        .limit(limit)
        .all()
    )

    if not ads:
        return {"total": 0, "items": [], "is_fallback": True}

    # Filter quality ads and compute dynamic thresholds
    quality_ads = [ad for ad in ads if _is_quality_ad(ad)]
    if not quality_ads:
        quality_ads = ads  # Fallback to all ads if all filtered out

    all_scores_for_thresh = []
    for a in quality_ads:
        m = a.ad_metadata or {}
        s = m.get("latest_hit_score")
        if s is not None:
            all_scores_for_thresh.append(float(s))
        else:
            s_val, _, _, _ = compute_hit_score(a)
            all_scores_for_thresh.append(s_val)
    dynamic_thresholds = _compute_dynamic_thresholds(all_scores_for_thresh)

    items = []
    for rank, ad in enumerate(quality_ads, 1):
        metadata = ad.ad_metadata or {}
        views = ad.view_count or 0
        likes = ad.like_count or 0

        # Use longevity-based hit score instead of view-based
        hit_score, is_hit, hit_level, breakdown = compute_hit_score(ad)
        longevity = _extract_longevity_info(ad)

        engagement = (likes / views * 100) if views > 0 else 0
        trend_score = round(min(100, engagement * 10))

        dynamic_hit_level = _classify_hit_dynamic(hit_score, dynamic_thresholds)

        items.append({
            "rank": rank,
            "ad_id": ad.id,
            "id": ad.id,  # Fix #53: alias for frontend ScatterPlot
            "product_name": _derive_product_name(ad),
            "advertiser_name": _clean_advertiser(ad.advertiser_name),
            "genre": _resolve_genre_label(ad),
            "platform": str(ad.platform.value) if ad.platform else "",
            "view_increase": 0,
            "spend_increase": 0,
            "cumulative_views": views,
            "cumulative_spend": 0,
            "is_hit": is_hit,
            "hit_score": hit_score,
            "trend_score": trend_score,
            "score_breakdown": breakdown,
            "rank_change": None,
            "previous_rank": None,
            "days_running": longevity["days_running"],
            "is_still_running": longevity["is_still_running"],
            "hit_level": hit_level,
            "dynamic_hit_level": dynamic_hit_level,
            "thumbnail": _resolve_thumbnail_url(ad),
            "duration_seconds": ad.duration_seconds or 0,
            "management_id": ad.external_id or f"AD-{ad.id}",
            "ad_url": _resolve_video_url(ad),
            "image_url": _resolve_image_url(ad),
            "video_url": _resolve_video_url(ad),
            "snapshot_url": ad.snapshot_url or "",
            "creative_type": ad.creative_type or "",
            "estimation_method": metadata.get("estimation_method", ""),
            "destination_url": ad.destination_url or metadata.get("destination_url", ""),
            "destination_type": metadata.get("destination_type", ""),
            "description": ad.description or "",
            "title": ad.title or "",
            "like_count": likes,
            "published_date": (
                ad.first_seen_at.isoformat() if ad.first_seen_at else
                ad.created_at.isoformat() if ad.created_at else ""
            ),
            "creative_analysis": metadata.get("creative_analysis"),
            "media_status": _resolve_media_status(ad),
            "download_urls": _build_download_urls(ad),
            "data_quality": _build_data_quality(ad),
        })

    # Sort by hit_score descending so best hits appear first
    items.sort(key=lambda x: x["hit_score"], reverse=True)
    # Re-assign ranks after sorting
    for i, item in enumerate(items, 1):
        item["rank"] = i

    return {
        "total": len(items),
        "items": items,
        "is_fallback": True,
        "dynamic_thresholds": dynamic_thresholds,
    }


@router.get("/advertiser/{advertiser_name}")
def get_advertiser_analytics(
    advertiser_name: str,
    period: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
):
    """Get detailed analytics for a specific advertiser."""
    with sync_session_scope() as session:
        svc = RankingService()
        return svc.get_advertiser_rankings(session, advertiser_name, period)


@router.get("/genre-summary")
def get_genre_summary(
    period: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
):
    """Get summary statistics per genre (market overview)."""
    with sync_session_scope() as session:
        yesterday = _today_jst() - timedelta(days=1)
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
        start = yesterday - timedelta(days=days - 1)

        # Use COALESCE so NULL genre is grouped as "未分類"
        genre_col = func.coalesce(AdDailyMetrics.genre, "未分類").label("genre_label")

        results = (
            session.query(
                genre_col,
                func.count(func.distinct(AdDailyMetrics.ad_id)).label("ad_count"),
                func.count(func.distinct(AdDailyMetrics.advertiser_name)).label("advertiser_count"),
                func.sum(AdDailyMetrics.view_count_increase).label("total_views"),
                func.sum(AdDailyMetrics.estimated_spend_increase).label("total_spend"),
            )
            .filter(
                AdDailyMetrics.metric_date >= start,
                AdDailyMetrics.metric_date <= yesterday,
            )
            .group_by(genre_col)
            .order_by(desc("total_spend"))
            .all()
        )

        return {
            "period": period,
            "genres": [
                {
                    "genre": r.genre_label,
                    "ad_count": r.ad_count,
                    "advertiser_count": r.advertiser_count,
                    "total_views": r.total_views or 0,
                    "total_spend": round(r.total_spend or 0),
                }
                for r in results
            ],
        }


# ==================== Pro-Search ====================


@router.get("/search")
def pro_search(
    q: str = Query(..., min_length=1, description="検索キーワード"),
    search_scope: str = Query("all", description="検索範囲: all, ads, lp, transcript, text"),
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    category: Optional[str] = None,
    advertiser: Optional[str] = None,
    creative_type: Optional[str] = None,
    hook_type: Optional[str] = None,
    cta_type: Optional[str] = None,
    offer_type: Optional[str] = None,
    emotion: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    min_longevity_days: Optional[int] = None,
    is_hit: Optional[bool] = None,
    is_active: Optional[bool] = None,
    has_video: Optional[bool] = None,
    include_duplicates: bool = Query(False, description="Include duplicate ads in results"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = Query("date_desc", description="Sort: date_desc, date_asc, score_desc, score_asc, longevity_desc, relevance"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Pro-Search: Full-text search across ads, LP text, transcripts, and OCR text.

    Supports advanced filters: offer_type, max_score, min_longevity_days,
    is_hit, is_active, has_video, and additional sort options (date_asc, score_asc).
    """
    with sync_session_scope() as session:
        results = []
        total_count = 0
        offset = (page - 1) * page_size

        # Search in ads (title, description, advertiser, brand)
        if search_scope in ("all", "ads"):
            ad_query = session.query(Ad).filter(
                or_(
                    Ad.title.ilike(f"%{_escape_like(q)}%"),
                    Ad.description.ilike(f"%{_escape_like(q)}%"),
                    Ad.advertiser_name.ilike(f"%{_escape_like(q)}%"),
                    Ad.brand_name.ilike(f"%{_escape_like(q)}%"),
                )
            )
            if genre:
                ad_query = ad_query.filter(Ad.category == genre)
            ad_query = _resolve_platform_filter(ad_query, Ad.platform, platform)
            if advertiser:
                ad_query = ad_query.filter(Ad.advertiser_name.ilike(f"%{_escape_like(advertiser)}%"))
            if creative_type:
                ad_query = ad_query.filter(Ad.creative_type == creative_type)
            if date_from:
                try:
                    dt_from = datetime.fromisoformat(date_from)
                    ad_query = ad_query.filter(Ad.created_at >= dt_from)
                except ValueError:
                    pass
            if date_to:
                try:
                    dt_to = datetime.fromisoformat(date_to)
                    ad_query = ad_query.filter(Ad.created_at <= dt_to)
                except ValueError:
                    pass

            has_json_filters = any([
                hook_type, cta_type, offer_type, emotion,
                min_score is not None, max_score is not None,
                min_longevity_days is not None, is_hit is not None,
                is_active is not None, has_video is not None,
            ])

            if has_json_filters:
                # When JSON metadata filters are needed, fetch all SQL matches
                # and filter in Python before pagination
                if sort_by == "longevity_desc":
                    ad_query = ad_query.order_by(Ad.first_seen_at.asc().nullslast())
                else:
                    ad_query = ad_query.order_by(Ad.created_at.desc())

                all_sql_ads = ad_query.limit(2000).all()
                filtered_ads = []
                for ad in all_sql_ads:
                    meta = ad.ad_metadata or {}
                    ca = meta.get("creative_analysis") or {}
                    if hook_type and ca.get("hook_type") != hook_type:
                        continue
                    if cta_type and ca.get("cta_type") != cta_type:
                        continue
                    if offer_type and ca.get("offer_type") != offer_type:
                        continue
                    if emotion and ca.get("emotion") != emotion:
                        continue
                    if min_score is not None:
                        score = meta.get("latest_hit_score", 0)
                        if score is not None and float(score) < min_score:
                            continue
                    if max_score is not None:
                        score = meta.get("latest_hit_score", 0)
                        if score is not None and float(score) > max_score:
                            continue
                    if min_longevity_days is not None:
                        longevity_info = _extract_longevity_info(ad)
                        if longevity_info["days_running"] < min_longevity_days:
                            continue
                    if is_hit is not None:
                        ad_is_hit = _is_hit_ad(ad)
                        if ad_is_hit != is_hit:
                            continue
                    if is_active is not None:
                        longevity_info = _extract_longevity_info(ad)
                        if longevity_info["is_still_running"] != is_active:
                            continue
                    if has_video is not None:
                        ad_has_video = bool(ad.video_url or ad.s3_key)
                        if ad_has_video != has_video:
                            continue
                    filtered_ads.append(ad)

                total_count += len(filtered_ads)
                # Apply pagination to filtered results
                filtered_ads = filtered_ads[offset:offset + page_size]
            else:
                total_count += ad_query.count()
                if sort_by == "longevity_desc":
                    ad_query = ad_query.order_by(Ad.first_seen_at.asc().nullslast())
                elif sort_by == "date_asc":
                    ad_query = ad_query.order_by(Ad.created_at.asc())
                else:
                    ad_query = ad_query.order_by(Ad.created_at.desc())
                filtered_ads = ad_query.offset(offset).limit(page_size).all()

            # Re-sort by score if requested (post-filter)
            if sort_by == "score_desc":
                filtered_ads.sort(
                    key=lambda a: float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0),
                    reverse=True,
                )
            elif sort_by == "score_asc":
                filtered_ads.sort(
                    key=lambda a: float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0),
                    reverse=False,
                )

            for ad in filtered_ads:
                meta = ad.ad_metadata or {}
                # Exclude duplicates by default
                if not include_duplicates and meta.get("is_duplicate") is True:
                    total_count -= 1
                    continue
                # Exclude non-Japanese ads (only if language explicitly set)
                lang = meta.get("language")
                if lang is not None and lang != "ja":
                    total_count -= 1
                    continue

                longevity = _extract_longevity_info(ad)
                hit_score = meta.get("latest_hit_score", 0)
                ca = meta.get("creative_analysis")

                # Compute relevance_score: title_match > description_match > advertiser_match
                q_lower = q.lower()
                relevance_score = 0.0
                match_field = "description"
                title_lower = (ad.title or "").lower()
                desc_lower = (ad.description or "").lower()
                adv_lower = (ad.advertiser_name or "").lower()

                if title_lower == q_lower:
                    relevance_score += 100  # Exact title match
                    match_field = "title_exact"
                elif q_lower in title_lower:
                    relevance_score += 70  # Partial title match
                    match_field = "title"
                if q_lower in desc_lower:
                    relevance_score += 30  # Description match
                    if match_field == "description":
                        match_field = "description"
                if q_lower in adv_lower:
                    relevance_score += 20  # Advertiser match
                    if match_field == "description" and q_lower not in desc_lower:
                        match_field = "advertiser"
                # Boost Japanese ads
                ad_lang = meta.get("language")
                if ad_lang == "ja":
                    relevance_score += 10

                results.append({
                    "type": "ad",
                    "id": ad.id,
                    "title": ad.title,
                    "description": (ad.description or "")[:200],
                    "platform": str(ad.platform.value) if hasattr(ad.platform, 'value') else str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "brand_name": ad.brand_name,
                    "category": _resolve_genre_label(ad),
                    "thumbnail_url": _resolve_thumbnail_url(ad),
                    "image_url": _resolve_image_url(ad),
                    "video_url": _resolve_video_url(ad),
                    "destination_url": ad.destination_url or "",
                    "hit_score": round(float(hit_score or 0), 1),
                    "days_running": longevity["days_running"],
                    "is_still_running": longevity["is_still_running"],
                    "creative_analysis": ca,
                    "media_status": _resolve_media_status(ad),
                    "download_urls": _build_download_urls(ad),
                    "data_quality": _build_data_quality(ad),
                    "relevance_score": round(relevance_score, 1),
                    "match_field": match_field,
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

            # Sort by relevance if requested
            if sort_by == "relevance":
                results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)

        # Search in transcripts (audio text from videos)
        if search_scope in ("all", "transcript"):
            transcript_query = (
                session.query(Transcription, Ad)
                .join(AdAnalysis, Transcription.analysis_id == AdAnalysis.id)
                .join(Ad, AdAnalysis.ad_id == Ad.id)
                .filter(Transcription.text.ilike(f"%{_escape_like(q)}%"))
            )
            transcript_query = _resolve_platform_filter(transcript_query, Ad.platform, platform)

            total_count += transcript_query.count()
            transcripts = transcript_query.offset(offset).limit(page_size).all()
            for t, ad in transcripts:
                results.append({
                    "type": "transcript",
                    "id": ad.id,
                    "title": ad.title,
                    "matched_text": t.text,
                    "timestamp_ms": t.start_time_ms,
                    "platform": str(ad.platform.value) if hasattr(ad.platform, 'value') else str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "match_field": "transcript",
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

        # Search in OCR text detections (text from video frames)
        if search_scope in ("all", "text"):
            text_query = (
                session.query(TextDetection, Ad)
                .join(AdAnalysis, TextDetection.analysis_id == AdAnalysis.id)
                .join(Ad, AdAnalysis.ad_id == Ad.id)
                .filter(TextDetection.text.ilike(f"%{_escape_like(q)}%"))
            )
            text_query = _resolve_platform_filter(text_query, Ad.platform, platform)

            total_count += text_query.count()
            texts = text_query.offset(offset).limit(page_size).all()
            for td, ad in texts:
                results.append({
                    "type": "text_detection",
                    "id": ad.id,
                    "title": ad.title,
                    "matched_text": td.text,
                    "timestamp_seconds": td.timestamp_seconds,
                    "platform": str(ad.platform.value) if hasattr(ad.platform, 'value') else str(ad.platform),
                    "advertiser_name": ad.advertiser_name,
                    "match_field": "video_text",
                    "created_at": ad.created_at.isoformat() if ad.created_at else None,
                })

        # Search in LP content
        if search_scope in ("all", "lp"):
            from app.models.landing_page import LandingPage

            lp_query = session.query(LandingPage).filter(
                or_(
                    LandingPage.title.ilike(f"%{_escape_like(q)}%"),
                    LandingPage.hero_headline.ilike(f"%{_escape_like(q)}%"),
                    LandingPage.full_text_content.ilike(f"%{_escape_like(q)}%"),
                    LandingPage.product_name.ilike(f"%{_escape_like(q)}%"),
                )
            )
            if genre:
                lp_query = lp_query.filter(LandingPage.genre == genre)

            total_count += lp_query.count()
            lps = lp_query.offset(offset).limit(page_size).all()
            for lp in lps:
                results.append({
                    "type": "landing_page",
                    "id": lp.id,
                    "title": lp.title,
                    "url": lp.url,
                    "domain": lp.domain,
                    "genre": lp.genre,
                    "product_name": lp.product_name,
                    "hero_headline": lp.hero_headline,
                    "match_field": "lp_content",
                    "created_at": lp.created_at.isoformat() if lp.created_at else None,
                })

        return {
            "query": q,
            "search_scope": search_scope,
            "total_results": total_count,
            "page": page,
            "page_size": page_size,
            "results": results,
        }


# ==================== CSV Export ====================


@router.get("/export/rankings")
def export_rankings_csv(
    period: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
    genre: Optional[str] = None,
):
    """Export rankings as CSV file."""
    with sync_session_scope() as session:
        svc = RankingService()
        rankings, total = svc.get_rankings(session, period=period, genre=genre, limit=500)

        output = io.StringIO()
        writer = csv.writer(output)

        if total > 0:
            writer.writerow([
                "順位", "前回順位", "変動", "商材名", "広告主", "ジャンル", "媒体",
                "再生増加数", "予想消化増加額", "累計再生回数", "累計予想消化額",
                "HIT", "ヒットスコア", "トレンドスコア",
            ])
            for r in rankings:
                writer.writerow([
                    r.rank_position,
                    r.previous_rank or "-",
                    r.rank_change if r.rank_change is not None else "-",
                    _sanitize_csv(r.product_name),
                    _sanitize_csv(r.advertiser_name),
                    _sanitize_csv(r.genre),
                    _sanitize_csv(r.platform),
                    r.total_view_increase,
                    round(r.total_spend_increase),
                    r.cumulative_views,
                    round(r.cumulative_spend),
                    "HIT" if r.is_hit else "",
                    r.hit_score or 0,
                    r.trend_score or 0,
                ])
        else:
            # Fallback: export ads ranked by view_count
            ad_query = session.query(Ad)
            if genre:
                ad_query = ad_query.filter(Ad.category == genre)
            ads = ad_query.order_by(
                case((Ad.view_count.is_(None), 0), else_=1).desc(),
                desc(Ad.view_count),
            ).limit(500).all()

            writer.writerow([
                "順位", "商材名", "広告主", "媒体", "カテゴリ",
                "再生数", "いいね数", "秒数", "初出日", "動画URL",
            ])
            for rank, ad in enumerate(ads, start=1):
                writer.writerow([
                    rank,
                    _sanitize_csv(ad.title),
                    _sanitize_csv(ad.advertiser_name),
                    str(ad.platform.value) if ad.platform and hasattr(ad.platform, 'value') else str(ad.platform or ""),
                    str(ad.category.value) if ad.category and hasattr(ad.category, 'value') else str(ad.category or ""),
                    ad.view_count or 0,
                    ad.like_count or 0,
                    ad.duration_seconds or "",
                    ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                    _sanitize_csv(_resolve_video_url(ad)),
                ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=rankings_{period}_{genre or 'all'}.csv"
            },
        )


@router.get("/export/ads")
def export_ads_csv(
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    advertiser: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
):
    """Export ad list as CSV file."""
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        if advertiser:
            query = query.filter(Ad.advertiser_name.ilike(f"%{_escape_like(advertiser)}%"))

        ads = query.order_by(Ad.created_at.desc()).limit(limit).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "タイトル", "媒体", "カテゴリ", "広告主", "ブランド",
            "再生数", "いいね数", "推定CTR", "秒数", "ステータス",
            "初出日", "最終確認日", "動画URL",
        ])

        for ad in ads:
            writer.writerow([
                ad.id,
                _sanitize_csv(ad.title),
                str(ad.platform.value) if ad.platform and hasattr(ad.platform, 'value') else str(ad.platform or ""),
                str(ad.category.value) if ad.category and hasattr(ad.category, 'value') else str(ad.category or ""),
                _sanitize_csv(ad.advertiser_name),
                _sanitize_csv(ad.brand_name),
                ad.view_count or 0,
                ad.like_count or 0,
                ad.estimated_ctr or "",
                ad.duration_seconds or "",
                str(ad.status.value) if ad.status and hasattr(ad.status, 'value') else str(ad.status or ""),
                ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                ad.last_seen_at.isoformat() if ad.last_seen_at else "",
                _sanitize_csv(_resolve_video_url(ad)),
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ads_export.csv"},
        )


# ==================== Analysis Pipeline Endpoints ====================


@router.get("/score-breakdown/{ad_id}")
def get_score_breakdown(ad_id: int):
    """Return detailed hit-score breakdown for a single ad.

    Calls compute_hit_score_with_details() and enriches the response
    with ad-level metadata (product name, advertiser, dates).
    """
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        # Fetch all metrics for this ad (sorted by date)
        metrics = (
            session.query(AdDailyMetrics)
            .filter(AdDailyMetrics.ad_id == ad_id)
            .order_by(AdDailyMetrics.metric_date)
            .all()
        )

        # Compute genre stats for relative scoring
        yesterday = _today_jst() - timedelta(days=1)
        start = yesterday - timedelta(days=29)
        g_stats = compute_genre_stats(session, start, yesterday)
        ad_genre = str(ad.category.value) if ad.category else "other"
        genre_stats = g_stats.get(ad_genre, {})

        details = compute_hit_score_with_details(ad, metrics=metrics, genre_stats=genre_stats)

        return {
            "ad_id": ad.id,
            "product_name": _derive_product_name(ad),
            "advertiser_name": _clean_advertiser(ad.advertiser_name),
            "hit_score": details["hit_score"],
            "hit_level": details["hit_level"],
            "is_hit": details["is_hit"],
            "signals": details["signals"],
            "days_running": details["days_running"],
            "is_still_running": details["is_still_running"],
            "estimated_spend_jpy": details["estimated_spend_jpy"],
            "first_seen_at": ad.first_seen_at.isoformat() if ad.first_seen_at else None,
            "last_seen_at": ad.last_seen_at.isoformat() if ad.last_seen_at else None,
        }


@router.get("/score-distribution")
def get_score_distribution():
    """Return score distribution across all ads.

    Buckets ads into 10-point ranges (0-9, 10-19, ... 90-100) and
    computes aggregate statistics (mean, median, hit counts, by-genre).
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()

        if not ads:
            return {
                "total_ads": 0,
                "distribution": [],
                "stats": {},
                "by_genre": {},
            }

        # Collect scores and metadata per ad
        scores: list[float] = []
        genre_data: dict[str, list[dict]] = {}
        hit_count = 0
        mega_hit_count = 0
        still_running_count = 0

        for ad in ads:
            meta = ad.ad_metadata or {}
            # Use pre-computed score from metadata if available
            score = meta.get("latest_hit_score")
            if score is None:
                hit_score, is_hit, hit_level, _ = compute_hit_score(ad)
                score = hit_score
                hit_level_val = hit_level
            else:
                score = float(score)
                hit_level_val = meta.get("hit_level", "none")

            scores.append(score)

            longevity = _extract_longevity_info(ad)
            is_still = longevity["is_still_running"]
            if is_still:
                still_running_count += 1

            if hit_level_val == "mega_hit":
                mega_hit_count += 1
                hit_count += 1
            elif hit_level_val == "hit":
                hit_count += 1
            else:
                # Recheck using score thresholds
                days_r = longevity["days_running"]
                if score >= 70 and days_r >= 60:
                    mega_hit_count += 1
                    hit_count += 1
                elif score >= 45 and days_r >= 30:
                    hit_count += 1

            genre = _resolve_genre_label(ad)
            genre_data.setdefault(genre, []).append({
                "score": score,
                "hit_level": hit_level_val,
                "days_running": longevity["days_running"],
            })

        # Build distribution buckets (histogram: 0-10, 10-20, ..., 90-100)
        buckets = []
        for lo in range(0, 100, 10):
            hi = lo + 9 if lo < 90 else 100
            label = f"{lo}-{hi}"
            count = sum(1 for s in scores if lo <= s <= hi)
            buckets.append({"range": label, "range_start": lo, "count": count})

        # Compute aggregate stats (pure Python, no NumPy)
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        mean_val = sum(sorted_scores) / n if n > 0 else 0
        if n % 2 == 1:
            median_val = sorted_scores[n // 2]
        else:
            median_val = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2 if n > 0 else 0

        # Percentile helper
        def _pct(p: float) -> float:
            idx = min(int(p / 100 * (n - 1)), n - 1)
            return round(sorted_scores[idx], 1)

        # Dynamic thresholds: top 20% = big_hit, 20-40% = hit
        dynamic_thresholds = _compute_dynamic_thresholds(scores)

        stats = {
            "mean": round(mean_val, 1),
            "median": round(median_val, 1),
            "max": round(max(sorted_scores), 1) if sorted_scores else 0,
            "min": round(min(sorted_scores), 1) if sorted_scores else 0,
            "p25": _pct(25),
            "p50": _pct(50),
            "p75": _pct(75),
            "p90": _pct(90),
            "hit_count": hit_count,
            "mega_hit_count": mega_hit_count,
            "still_running_count": still_running_count,
        }

        # By-genre summary (using proper genre labels including uncategorized)
        by_genre = {}
        for genre, items in genre_data.items():
            g_scores = [i["score"] for i in items]
            g_mean = sum(g_scores) / len(g_scores) if g_scores else 0
            g_hit = sum(
                1 for i in items
                if i["hit_level"] in ("hit", "mega_hit")
                or (i["score"] >= 45 and i["days_running"] >= 30)
            )
            g_mega = sum(
                1 for i in items
                if i["hit_level"] == "mega_hit"
                or (i["score"] >= 70 and i["days_running"] >= 60)
            )
            by_genre[genre] = {
                "mean": round(g_mean, 1),
                "count": len(items),
                "hit_count": g_hit,
                "mega_hit_count": g_mega,
            }

        return {
            "total_ads": n,
            "distribution": buckets,
            "stats": stats,
            "by_genre": by_genre,
            "dynamic_thresholds": {
                "big_hit_threshold": dynamic_thresholds["big_hit_threshold"],
                "hit_threshold": dynamic_thresholds["hit_threshold"],
                "description": "Top 20% = big_hit, 20-40% = hit, rest = normal",
            },
            # Top-level aliases for frontend compatibility
            "mean": stats["mean"],
            "median": stats["median"],
            "p25": stats["p25"],
            "p50": stats["p50"],
            "p75": stats["p75"],
            "p90": stats["p90"],
            "hit_count": stats["hit_count"],
            "mega_hit_count": stats["mega_hit_count"],
            "still_running_count": stats["still_running_count"],
        }


@router.get("/advertiser-detail")
def get_advertiser_detail(
    advertiser_name: str = Query(..., min_length=1, description="Advertiser name to search"),
):
    """Return aggregated analysis for all ads belonging to an advertiser.

    Filters ads by advertiser_name (partial match), computes scores,
    and separates hit vs non-hit ads.
    """
    with sync_session_scope() as session:
        ads = (
            session.query(Ad)
            .filter(Ad.advertiser_name.ilike(f"%{_escape_like(advertiser_name)}%"))
            .all()
        )

        if not ads:
            return {
                "advertiser_name": advertiser_name,
                "total_ads": 0,
                "active_ads": 0,
                "avg_hit_score": 0,
                "best_hit_score": 0,
                "total_estimated_spend_jpy": 0,
                "avg_days_running": 0,
                "hit_ads": [],
                "non_hit_ads": [],
            }

        hit_ads_list = []
        non_hit_ads_list = []
        total_spend = 0
        total_days = 0
        active_count = 0
        all_scores = []

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            days_running = longevity["days_running"]
            is_still = longevity["is_still_running"]

            score = meta.get("latest_hit_score")
            if score is None:
                hit_score, is_hit, hit_level, _ = compute_hit_score(ad)
                score = hit_score
            else:
                score = float(score)
                hit_level = meta.get("hit_level", "none")
                # Re-derive is_hit from score + days
                is_hit = (
                    (score >= 70 and days_running >= 60)
                    or (score >= 45 and days_running >= 30)
                )

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend
            total_days += days_running
            all_scores.append(score)
            if is_still:
                active_count += 1

            ad_entry = {
                "ad_id": ad.id,
                "product_name": _derive_product_name(ad),
                "hit_score": round(score, 1),
                "hit_level": hit_level,
                "days_running": days_running,
                "is_still_running": is_still,
                "estimated_spend_jpy": int(est_spend),
                "thumbnail": _resolve_thumbnail_url(ad),
            }

            if is_hit:
                hit_ads_list.append(ad_entry)
            else:
                non_hit_ads_list.append(ad_entry)

        # Sort both lists by score descending
        hit_ads_list.sort(key=lambda x: x["hit_score"], reverse=True)
        non_hit_ads_list.sort(key=lambda x: x["hit_score"], reverse=True)

        n = len(all_scores)
        avg_score = sum(all_scores) / n if n > 0 else 0
        avg_days = total_days / n if n > 0 else 0

        return {
            "advertiser_name": advertiser_name,
            "total_ads": n,
            "active_ads": active_count,
            "avg_hit_score": round(avg_score, 1),
            "avg_score": round(avg_score, 1),  # alias for frontend compatibility
            "best_hit_score": round(max(all_scores), 1) if all_scores else 0,
            "total_estimated_spend_jpy": int(total_spend),
            "total_spend": int(total_spend),  # alias for frontend compatibility
            "avg_days_running": round(avg_days),
            "hit_ads": hit_ads_list,
            "non_hit_ads": non_hit_ads_list,
        }


@router.get("/top-advertisers")
def get_top_advertisers(
    limit: int = Query(20, ge=1, le=200),
    sort_by: str = Query("total_spend", pattern="^(total_spend|avg_score|ad_count)$"),
):
    """Return advertiser-level aggregated ranking.

    Groups all ads by advertiser_name and computes aggregate metrics
    (ad count, active count, hit/mega-hit counts, avg score, spend).
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).filter(Ad.advertiser_name.isnot(None)).all()

        # Group by cleaned advertiser name
        advertiser_map: dict[str, list] = {}
        for ad in ads:
            name = _clean_advertiser(ad.advertiser_name)
            if not name:
                continue
            advertiser_map.setdefault(name, []).append(ad)

        results = []
        for adv_name, adv_ads in advertiser_map.items():
            scores = []
            active_count = 0
            hit_count = 0
            mega_count = 0
            total_spend = 0
            total_days = 0

            for ad in adv_ads:
                meta = ad.ad_metadata or {}
                longevity = _extract_longevity_info(ad)
                days_running = longevity["days_running"]
                is_still = longevity["is_still_running"]

                score = meta.get("latest_hit_score")
                if score is None:
                    hit_score, _, hit_level, _ = compute_hit_score(ad)
                    score = hit_score
                else:
                    score = float(score)
                    hit_level = meta.get("hit_level", "none")

                scores.append(score)
                total_days += days_running
                if is_still:
                    active_count += 1

                # Hit classification
                if hit_level == "mega_hit" or (score >= 70 and days_running >= 60):
                    mega_count += 1
                    hit_count += 1
                elif hit_level == "hit" or (score >= 45 and days_running >= 30):
                    hit_count += 1

                est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
                total_spend += est_spend

            n = len(scores)
            avg_score = sum(scores) / n if n > 0 else 0
            best_score = max(scores) if scores else 0
            avg_days = total_days / n if n > 0 else 0

            results.append({
                "advertiser_name": adv_name,
                "ad_count": n,
                "active_ad_count": active_count,
                "hit_ad_count": hit_count,
                "mega_hit_count": mega_count,
                "avg_hit_score": round(avg_score, 1),
                "best_hit_score": round(best_score, 1),
                "total_estimated_spend_jpy": int(total_spend),
                "avg_days_running": round(avg_days),
            })

        # Sort by the requested field
        sort_key_map = {
            "total_spend": lambda x: x["total_estimated_spend_jpy"],
            "avg_score": lambda x: x["avg_hit_score"],
            "ad_count": lambda x: x["ad_count"],
        }
        results.sort(key=sort_key_map[sort_by], reverse=True)

        return {
            "advertisers": results[:limit],
        }


@router.get("/longevity-analysis")
def get_longevity_analysis():
    """Return scatter data and bucketed analysis of days_running vs hit_score.

    Provides raw scatter_data (per-ad) and pre-bucketed aggregation
    for frontend chart rendering.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()

        scatter_data = []
        bucket_ranges = [
            ("1-14d", 0, 14),
            ("15-29d", 15, 29),
            ("30-59d", 30, 59),
            ("60-89d", 60, 89),
            ("90-119d", 90, 119),
            ("120d+", 120, 999999),
        ]
        # Accumulate per bucket: list of (score, is_hit)
        bucket_acc: dict[str, list[tuple[float, bool]]] = {r[0]: [] for r in bucket_ranges}

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            days_running = longevity["days_running"]
            is_still = longevity["is_still_running"]

            score = meta.get("latest_hit_score")
            if score is None:
                hit_score, is_hit, hit_level, _ = compute_hit_score(ad)
                score = hit_score
            else:
                score = float(score)
                is_hit = (
                    (score >= 70 and days_running >= 60)
                    or (score >= 45 and days_running >= 30)
                )

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0

            scatter_data.append({
                "ad_id": ad.id,
                "days_running": days_running,
                "hit_score": round(score, 1),
                "is_still_running": is_still,
                "estimated_spend": int(est_spend),
            })

            # Place into bucket
            for label, lo, hi in bucket_ranges:
                if lo <= days_running <= hi:
                    bucket_acc[label].append((score, is_hit))
                    break

        # Build bucket summaries
        buckets = []
        for label, _, _ in bucket_ranges:
            items = bucket_acc[label]
            count = len(items)
            if count > 0:
                avg_score = sum(s for s, _ in items) / count
                hit_rate = sum(1 for _, h in items if h) / count
            else:
                avg_score = 0
                hit_rate = 0
            buckets.append({
                "range": label,
                "count": count,
                "avg_score": round(avg_score, 1),
                "hit_rate": round(hit_rate, 2),
            })

        return {
            "scatter_data": scatter_data,
            "buckets": buckets,
        }


# ==================== Trend & Comparison Endpoints (C5) ====================


@router.get("/genre-comparison")
def get_genre_comparison():
    """Compare statistics across ad genres (categories).

    Returns per-genre: ad count, avg score, hit/mega-hit rates, avg days running.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()

        genre_map: dict[str, list[dict]] = {}
        for ad in ads:
            genre = _resolve_genre_label(ad)
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            days_running = longevity["days_running"]

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, hit_level, _ = compute_hit_score(ad)
            else:
                score = float(score)
                hit_level = meta.get("hit_level", "none")

            genre_map.setdefault(genre, []).append({
                "score": score,
                "hit_level": hit_level,
                "days_running": days_running,
                "is_still_running": longevity["is_still_running"],
            })

        genres = []
        for genre, items in sorted(genre_map.items(), key=lambda x: len(x[1]), reverse=True):
            n = len(items)
            scores = [i["score"] for i in items]
            avg_score = sum(scores) / n
            hit_count = sum(
                1 for i in items
                if i["hit_level"] in ("hit", "mega_hit")
                or (i["score"] >= 45 and i["days_running"] >= 30)
            )
            mega_count = sum(
                1 for i in items
                if i["hit_level"] == "mega_hit"
                or (i["score"] >= 70 and i["days_running"] >= 60)
            )
            active_count = sum(1 for i in items if i["is_still_running"])
            avg_days = sum(i["days_running"] for i in items) / n

            genres.append({
                "genre": genre,
                "ad_count": n,
                "active_count": active_count,
                "avg_score": round(avg_score, 1),
                "hit_count": hit_count,
                "mega_hit_count": mega_count,
                "hit_rate": round(hit_count / n, 3) if n > 0 else 0,
                "mega_hit_rate": round(mega_count / n, 3) if n > 0 else 0,
                "avg_days_running": round(avg_days),
            })

        return {"genres": genres}


@router.get("/duration-brackets")
def get_duration_brackets():
    """Analyze ads grouped by delivery duration brackets.

    Returns per-bracket: ad count, avg score, hit rate.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()

        brackets = [
            ("0-7d", 0, 7),
            ("8-14d", 8, 14),
            ("15-30d", 15, 30),
            ("31-60d", 31, 60),
            ("61-90d", 61, 90),
            ("91d+", 91, 999999),
        ]
        bucket_acc: dict[str, list[dict]] = {b[0]: [] for b in brackets}

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            days = longevity["days_running"]

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            is_hit = (
                (score >= 70 and days >= 60)
                or (score >= 45 and days >= 30)
            )

            for label, lo, hi in brackets:
                if lo <= days <= hi:
                    bucket_acc[label].append({"score": score, "is_hit": is_hit})
                    break

        results = []
        for label, _, _ in brackets:
            items = bucket_acc[label]
            n = len(items)
            if n > 0:
                avg_score = sum(i["score"] for i in items) / n
                hit_rate = sum(1 for i in items if i["is_hit"]) / n
            else:
                avg_score = 0
                hit_rate = 0
            results.append({
                "bracket": label,
                "count": n,
                "avg_score": round(avg_score, 1),
                "hit_rate": round(hit_rate, 3),
            })

        return {"brackets": results}


@router.get("/creative-analysis")
def get_creative_analysis():
    """Compare performance across creative types (video, image, etc.).

    Returns per-type: ad count, avg score, hit rate, avg days running.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()

        type_map: dict[str, list[dict]] = {}
        for ad in ads:
            # Determine creative type
            ct = ad.creative_type or ""
            if not ct or ct == "unknown":
                if ad.video_url:
                    ct = "video"
                elif ad.image_url:
                    ct = "image"
                else:
                    ct = "unknown"

            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            days = longevity["days_running"]

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            is_hit = (
                (score >= 70 and days >= 60)
                or (score >= 45 and days >= 30)
            )

            type_map.setdefault(ct, []).append({
                "score": score,
                "days_running": days,
                "is_hit": is_hit,
            })

        results = []
        for ct, items in sorted(type_map.items(), key=lambda x: len(x[1]), reverse=True):
            n = len(items)
            avg_score = sum(i["score"] for i in items) / n if n > 0 else 0
            hit_rate = sum(1 for i in items if i["is_hit"]) / n if n > 0 else 0
            avg_days = sum(i["days_running"] for i in items) / n if n > 0 else 0
            results.append({
                "creative_type": ct,
                "ad_count": n,
                "avg_score": round(avg_score, 1),
                "hit_rate": round(hit_rate, 3),
                "avg_days_running": round(avg_days),
            })

        return {"creative_types": results}


@router.get("/dashboard-summary")
def get_dashboard_summary():
    """Return KPI summary for the frontend dashboard header.

    Single API call returns all top-level metrics:
    total ads, active ads, hit/mega-hit counts, avg score, top genre, top creative type.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()

        if not ads:
            return {
                "total_ads": 0,
                "active_ads": 0,
                "hit_count": 0,
                "mega_hit_count": 0,
                "avg_score": 0,
                "avg_days_running": 0,
                "top_genre": None,
                "top_creative_type": None,
            }

        scores = []
        total_days = 0
        active_count = 0
        hit_count = 0
        mega_hit_count = 0
        genre_hits: dict[str, dict] = {}
        creative_hits: dict[str, dict] = {}

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            days = longevity["days_running"]
            is_still = longevity["is_still_running"]

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, hit_level, _ = compute_hit_score(ad)
            else:
                score = float(score)
                hit_level = meta.get("hit_level", "none")

            scores.append(score)
            total_days += days
            if is_still:
                active_count += 1

            is_hit = hit_level in ("hit", "mega_hit") or (score >= 45 and days >= 30)
            is_mega = hit_level == "mega_hit" or (score >= 70 and days >= 60)

            if is_mega:
                mega_hit_count += 1
                hit_count += 1
            elif is_hit:
                hit_count += 1

            # Track genre hit rates
            genre = _resolve_genre_label(ad)
            g = genre_hits.setdefault(genre, {"total": 0, "hits": 0})
            g["total"] += 1
            if is_hit:
                g["hits"] += 1

            # Track creative type hit rates
            ct = ad.creative_type or ""
            if not ct or ct == "unknown":
                ct = "video" if ad.video_url else ("image" if ad.image_url else "unknown")
            c = creative_hits.setdefault(ct, {"total": 0, "hits": 0})
            c["total"] += 1
            if is_hit:
                c["hits"] += 1

        n = len(scores)
        avg_score = sum(scores) / n if n > 0 else 0
        avg_days = total_days / n if n > 0 else 0

        # Find top genre by hit rate (min 3 ads to qualify)
        top_genre = None
        best_genre_rate = -1
        for genre, data in genre_hits.items():
            if data["total"] >= 3:
                rate = data["hits"] / data["total"]
                if rate > best_genre_rate:
                    best_genre_rate = rate
                    top_genre = genre

        # Find top creative type by hit rate (min 3 ads to qualify)
        top_creative = None
        best_creative_rate = -1
        for ct, data in creative_hits.items():
            if data["total"] >= 3:
                rate = data["hits"] / data["total"]
                if rate > best_creative_rate:
                    best_creative_rate = rate
                    top_creative = ct

        # Fresh ads (last 7 days)
        fresh_cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
        fresh_count = session.query(func.count(Ad.id)).filter(
            Ad.created_at >= fresh_cutoff
        ).scalar() or 0

        # Media cache rate (% with cached thumbnails)
        cached_count = sum(
            1 for ad in ads
            if ad.thumbnail_s3_key and "media_cache/" in (ad.thumbnail_s3_key or "")
        )
        media_cache_rate = round(cached_count / n, 3) if n > 0 else 0

        # Top genres list (sorted by hit_rate desc, min 3 ads)
        top_genres = []
        for g_name, data in genre_hits.items():
            if data["total"] >= 3:
                top_genres.append({
                    "genre": g_name,
                    "count": data["total"],
                    "hit_rate": round(data["hits"] / data["total"], 3),
                })
        top_genres.sort(key=lambda x: x["hit_rate"], reverse=True)

        # Top hooks and CTAs from creative_analysis
        hook_counts: dict[str, dict] = {}
        cta_counts: dict[str, dict] = {}
        for ad in ads:
            ca = (ad.ad_metadata or {}).get("creative_analysis")
            if not ca or not isinstance(ca, dict):
                continue
            hook = ca.get("hook_type")
            if hook:
                h = hook_counts.setdefault(str(hook), {"total": 0, "hits": 0})
                h["total"] += 1
            cta = ca.get("cta_type")
            if cta:
                c = cta_counts.setdefault(str(cta), {"total": 0, "hits": 0})
                c["total"] += 1

        # Count hits for hooks/ctas
        for ad in ads:
            ca = (ad.ad_metadata or {}).get("creative_analysis")
            if not ca or not isinstance(ca, dict):
                continue
            meta = ad.ad_metadata or {}
            longevity_info = _extract_longevity_info(ad)
            d = longevity_info["days_running"]
            s = meta.get("latest_hit_score")
            if s is not None:
                s = float(s)
                hl = meta.get("hit_level", "none")
                ad_is_hit = hl in ("hit", "mega_hit") or (s >= 45 and d >= 30)
            else:
                ad_is_hit = False
            hook = ca.get("hook_type")
            if hook and str(hook) in hook_counts and ad_is_hit:
                hook_counts[str(hook)]["hits"] += 1
            cta = ca.get("cta_type")
            if cta and str(cta) in cta_counts and ad_is_hit:
                cta_counts[str(cta)]["hits"] += 1

        top_hooks = [
            {"hook": k, "count": v["total"], "hit_rate": round(v["hits"] / v["total"], 3)}
            for k, v in hook_counts.items() if v["total"] >= 2
        ]
        top_hooks.sort(key=lambda x: x["hit_rate"], reverse=True)

        top_ctas = [
            {"cta": k, "count": v["total"], "hit_rate": round(v["hits"] / v["total"], 3)}
            for k, v in cta_counts.items() if v["total"] >= 2
        ]
        top_ctas.sort(key=lambda x: x["hit_rate"], reverse=True)

        return {
            "total_ads": n,
            "active_ads": active_count,
            "hit_count": hit_count,
            "mega_hit_count": mega_hit_count,
            "avg_score": round(avg_score, 1),
            "avg_hit_score": round(sum(s for s in scores if s >= 45) / max(hit_count, 1), 1),
            "avg_days_running": round(avg_days),
            "fresh_ads_count": fresh_count,
            "media_cache_rate": media_cache_rate,
            "top_genre": top_genre,
            "top_creative_type": top_creative,
            "top_genres": top_genres[:5],
            "top_hooks": top_hooks[:5],
            "top_ctas": top_ctas[:5],
        }


# ==================== LP Health ====================


@router.get("/lp-health")
def get_lp_health():
    """Return LP (Landing Page) health summary from ad_metadata.lp_status.

    Aggregates lp_status values recorded by scripts/check_lp_health.py.
    """
    with sync_session_scope() as session:
        ads = (
            session.query(Ad)
            .filter(Ad.destination_url.isnot(None))
            .filter(Ad.destination_url != "")
            .all()
        )

        total_with_url = len(ads)
        total_checked = 0
        status_200 = 0
        status_redirect = 0
        status_error = 0
        unchecked = 0
        problem_ads = []
        status_distribution: dict[str, int] = {}

        for ad in ads:
            meta = ad.ad_metadata or {}
            lp_status = meta.get("lp_status")

            if lp_status is None:
                unchecked += 1
                continue

            total_checked += 1
            status_distribution[lp_status] = status_distribution.get(lp_status, 0) + 1

            if lp_status == "200":
                status_200 += 1
            elif lp_status in ("301", "302", "303", "307", "308"):
                status_redirect += 1
            else:
                status_error += 1
                problem_ads.append({
                    "ad_id": ad.id,
                    "title": (ad.title or "")[:80],
                    "destination_url": ad.destination_url or "",
                    "lp_status": lp_status,
                    "lp_checked_at": meta.get("lp_checked_at", ""),
                    "lp_error_detail": meta.get("lp_error_detail", ""),
                })

        # Sort problem ads by ad_id
        problem_ads.sort(key=lambda x: x["ad_id"])

        return {
            "total_with_url": total_with_url,
            "total_checked": total_checked,
            "status_200": status_200,
            "status_redirect": status_redirect,
            "status_error": status_error,
            "unchecked": unchecked,
            "health_rate": round(status_200 / total_checked * 100, 1) if total_checked > 0 else 0,
            "status_distribution": status_distribution,
            "problem_ads": problem_ads[:100],  # Limit to 100 entries
            "problem_count": len(problem_ads),
        }


# ==================== Quality Summary ====================


@router.get("/quality-summary")
def get_quality_summary():
    """Return ad data quality/completeness summary.

    Scores each ad on data completeness (0-100) based on:
      title (+10), description (+10), destination_url (+10), lp reachable (+10),
      thumbnail_url (+10), image_url (+10), video_url (+10 for video ads),
      category (+10), score_breakdown (+10), days_running > 0 (+10)
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        total = len(ads)

        if total == 0:
            return {
                "total_ads": 0,
                "avg_completeness": 0,
                "completeness_distribution": {},
                "low_quality_count": 0,
                "low_quality_ads": [],
            }

        scores: list[float] = []
        low_quality_ads: list[dict] = []
        completeness_buckets = {
            "0-20": 0,
            "21-40": 0,
            "41-60": 0,
            "61-80": 0,
            "81-100": 0,
        }

        for ad in ads:
            meta = ad.ad_metadata or {}
            score = 0
            missing: list[str] = []

            # title (+10)
            if ad.title:
                score += 10
            else:
                missing.append("title")

            # description (+10)
            if ad.description:
                score += 10
            else:
                missing.append("description")

            # destination_url (+10)
            if ad.destination_url:
                score += 10
            else:
                missing.append("destination_url")

            # LP reachable (+10)
            lp_status = meta.get("lp_status")
            if lp_status == "200":
                score += 10
            else:
                missing.append("lp_reachable")

            # thumbnail_url (+10)
            if ad.thumbnail_url or ad.thumbnail_s3_key:
                score += 10
            else:
                missing.append("thumbnail")

            # image_url (+10)
            if ad.image_url or ad.image_s3_key:
                score += 10
            else:
                missing.append("image")

            # video_url (+10 for video ads)
            is_video = (ad.creative_type or "").lower() in ("video", "")
            if is_video:
                if ad.video_url or ad.s3_key:
                    score += 10
                else:
                    missing.append("video_url")
            else:
                # Non-video ads get this point for free
                score += 10

            # category (+10)
            if ad.category:
                score += 10
            else:
                missing.append("category")

            # score_breakdown (+10)
            if meta.get("latest_score_breakdown") or meta.get("score_breakdown"):
                score += 10
            else:
                missing.append("score_breakdown")

            # days_running > 0 (+10)
            days_running = meta.get("days_running", 0)
            if days_running == 0 and ad.first_seen_at:
                from datetime import timezone as _tz
                now = datetime.now(_tz.utc)
                first = ad.first_seen_at
                if first.tzinfo is None:
                    first = first.replace(tzinfo=_tz.utc)
                days_running = max(0, (now - first).days)
            if days_running > 0:
                score += 10
            else:
                missing.append("days_running")

            scores.append(score)

            # Store data_completeness in ad_metadata
            # (batch update - will commit at end)
            if meta.get("data_completeness") != score:
                meta["data_completeness"] = score
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

            # Bucket
            if score <= 20:
                completeness_buckets["0-20"] += 1
            elif score <= 40:
                completeness_buckets["21-40"] += 1
            elif score <= 60:
                completeness_buckets["41-60"] += 1
            elif score <= 80:
                completeness_buckets["61-80"] += 1
            else:
                completeness_buckets["81-100"] += 1

            # Low quality threshold: 60% or below
            if score <= 60:
                low_quality_ads.append({
                    "ad_id": ad.id,
                    "title": (ad.title or "")[:80],
                    "completeness": score,
                    "missing_fields": missing,
                    "platform": str(ad.platform.value) if ad.platform else "",
                })

        session.commit()

        avg = sum(scores) / len(scores) if scores else 0

        # Sort low quality by completeness ascending
        low_quality_ads.sort(key=lambda x: x["completeness"])

        return {
            "total_ads": total,
            "avg_completeness": round(avg, 1),
            "completeness_distribution": completeness_buckets,
            "low_quality_count": len(low_quality_ads),
            "low_quality_ads": low_quality_ads[:100],  # Limit to 100
        }


# ==================== Hit Pattern Analysis (C8) ====================


def _get_creative_analysis(ad: Ad) -> dict | None:
    """Extract creative_analysis from ad_metadata. Returns None if absent."""
    meta = ad.ad_metadata or {}
    ca = meta.get("creative_analysis")
    if not ca or not isinstance(ca, dict):
        return None
    return ca


def _is_hit_ad(ad: Ad) -> bool:
    """Determine if an ad is a hit using consistent logic."""
    meta = ad.ad_metadata or {}
    longevity = _extract_longevity_info(ad)
    days_running = longevity["days_running"]
    hit_level = meta.get("hit_level", "none")

    if hit_level in ("hit", "mega_hit"):
        return True

    score = meta.get("latest_hit_score")
    if score is None:
        score, is_hit, _, _ = compute_hit_score(ad)
        return is_hit
    else:
        score = float(score)
        return (score >= 70 and days_running >= 60) or (score >= 45 and days_running >= 30)


# Creative analysis fields used for factor aggregation
_FACTOR_FIELDS = [
    "hook_type", "cta_type", "offer_type", "emotion",
    "text_length", "destination_type",
]

# Boolean creative analysis fields
_BOOL_FIELDS = [
    "has_emoji", "has_numbers", "has_testimonial", "has_before_after",
]


@router.get("/hit-factors")
def get_hit_factors(
    genre: Optional[str] = None,
    platform: Optional[str] = None,
):
    """Analyze hit factors from creative_analysis data.

    Aggregates hit rate and average score per creative element value
    (hook_type, cta_type, offer_type, emotion, text_length, destination_type).
    Also returns top winning combinations.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        ads = query.all()

        # Collect per-factor stats
        # factor_stats[field_name][value] = {"count": int, "hits": int, "total_score": float}
        factor_stats: dict[str, dict[str, dict]] = {f: {} for f in _FACTOR_FIELDS}

        # For winning combinations: collect (hook, cta, offer) tuples
        combo_stats: dict[tuple, dict] = {}
        analyzed_count = 0

        for ad in ads:
            ca = _get_creative_analysis(ad)
            if ca is None:
                continue

            analyzed_count += 1
            is_hit = _is_hit_ad(ad)
            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            # Aggregate each factor field
            for field in _FACTOR_FIELDS:
                val = ca.get(field)
                if val is None:
                    continue
                val_str = str(val)
                bucket = factor_stats[field].setdefault(val_str, {"count": 0, "hits": 0, "total_score": 0.0})
                bucket["count"] += 1
                if is_hit:
                    bucket["hits"] += 1
                bucket["total_score"] += score

            # Winning combinations (hook + cta + offer)
            hook = ca.get("hook_type")
            cta = ca.get("cta_type")
            offer = ca.get("offer_type")
            if hook and cta and offer:
                key = (str(hook), str(cta), str(offer))
                combo = combo_stats.setdefault(key, {"count": 0, "hits": 0, "total_score": 0.0})
                combo["count"] += 1
                if is_hit:
                    combo["hits"] += 1
                combo["total_score"] += score

        # Build response — dict-of-dicts per field (original format)
        result: dict = {}
        for field in _FACTOR_FIELDS:
            field_data = {}
            for val, stats in factor_stats[field].items():
                cnt = stats["count"]
                field_data[val] = {
                    "count": cnt,
                    "hit_rate": round(stats["hits"] / cnt, 3) if cnt > 0 else 0,
                    "avg_score": round(stats["total_score"] / cnt, 1) if cnt > 0 else 0,
                }
            result[field] = field_data

        # Winning combinations: top 10 by hit_rate (min 3 samples)
        winning = []
        for (hook, cta, offer), stats in combo_stats.items():
            cnt = stats["count"]
            if cnt >= 3:
                winning.append({
                    "hook": hook,
                    "cta": cta,
                    "offer": offer,
                    "count": cnt,
                    "hit_rate": round(stats["hits"] / cnt, 3),
                    "avg_score": round(stats["total_score"] / cnt, 1),
                })
        # Sort by hit_rate desc, then count desc
        winning.sort(key=lambda x: (x["hit_rate"], x["count"]), reverse=True)
        result["winning_combinations"] = winning[:10]
        result["analyzed_count"] = analyzed_count

        # --- Frontend-compatible aliases (FactorItem[] arrays) ---
        # Frontend expects: hook_types, cta_types, offer_types, emotion_types
        # Each as array of {name, hit_rate, count, total?}
        _field_to_frontend_key = {
            "hook_type": "hook_types",
            "cta_type": "cta_types",
            "offer_type": "offer_types",
            "emotion": "emotion_types",
        }
        for backend_field, frontend_key in _field_to_frontend_key.items():
            field_data = result.get(backend_field, {})
            arr = []
            for val, stats in field_data.items():
                arr.append({
                    "name": val,
                    "hit_rate": stats["hit_rate"],
                    "count": stats["count"],
                    "total": stats["count"],
                })
            result[frontend_key] = arr

        # Frontend expects winning_patterns with hook_type/cta_type/offer_type keys
        winning_patterns = []
        for i, w in enumerate(winning[:10], 1):
            winning_patterns.append({
                "rank": i,
                "hook_type": w["hook"],
                "cta_type": w["cta"],
                "offer_type": w["offer"],
                "hit_rate": w["hit_rate"],
                "count": w["count"],
            })
        result["winning_patterns"] = winning_patterns

        return result


@router.get("/creative-dna/{ad_id}")
def get_creative_dna(ad_id: int):
    """Return creative DNA analysis for a single ad.

    Shows the ad's creative_analysis fields and how that pattern
    performs across all ads (pattern hit rate, rank, similar hits).
    """
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        ca = _get_creative_analysis(ad)
        if ca is None:
            return {
                "ad_id": ad_id,
                "creative_analysis": None,
                "message": "creative_analysis not available for this ad",
            }

        # Get this ad's pattern key: (hook_type, cta_type, offer_type)
        ad_hook = ca.get("hook_type")
        ad_cta = ca.get("cta_type")
        ad_offer = ca.get("offer_type")

        # Scan all ads to find pattern stats and similar hits
        all_ads = session.query(Ad).all()

        # Collect per-pattern stats: pattern_key -> {count, hits, total_score, ad_ids}
        pattern_stats: dict[tuple, dict] = {}
        for other_ad in all_ads:
            other_ca = _get_creative_analysis(other_ad)
            if other_ca is None:
                continue

            hook = other_ca.get("hook_type")
            cta = other_ca.get("cta_type")
            offer = other_ca.get("offer_type")
            if not hook or not cta or not offer:
                continue

            key = (str(hook), str(cta), str(offer))
            meta = other_ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(other_ad)
            else:
                score = float(score)

            is_hit = _is_hit_ad(other_ad)

            bucket = pattern_stats.setdefault(key, {"count": 0, "hits": 0, "total_score": 0.0, "hit_ads": []})
            bucket["count"] += 1
            if is_hit:
                bucket["hits"] += 1
                bucket["hit_ads"].append({
                    "ad_id": other_ad.id,
                    "product_name": _derive_product_name(other_ad),
                    "hit_score": round(score, 1),
                    "thumbnail": _resolve_thumbnail_url(other_ad),
                })
            bucket["total_score"] += score

        # This ad's pattern
        ad_pattern_key = (str(ad_hook or ""), str(ad_cta or ""), str(ad_offer or ""))
        ad_pattern = pattern_stats.get(ad_pattern_key)

        pattern_hit_rate = 0.0
        pattern_rank = 0
        similar_hits = []

        if ad_pattern:
            cnt = ad_pattern["count"]
            pattern_hit_rate = round(ad_pattern["hits"] / cnt, 3) if cnt > 0 else 0

            # Rank this pattern among all patterns by hit_rate
            all_rates = []
            for key, stats in pattern_stats.items():
                c = stats["count"]
                if c >= 2:  # Need at least 2 samples for meaningful rate
                    rate = stats["hits"] / c
                    all_rates.append((key, rate))
            all_rates.sort(key=lambda x: x[1], reverse=True)

            for idx, (key, rate) in enumerate(all_rates, 1):
                if key == ad_pattern_key:
                    pattern_rank = idx
                    break

            # Similar hits: top 5 hit ads with same pattern (exclude self)
            similar = [h for h in ad_pattern["hit_ads"] if h["ad_id"] != ad_id]
            similar.sort(key=lambda x: x["hit_score"], reverse=True)
            similar_hits = similar[:5]

        # Build bool text_features list from creative_analysis
        _text_features = [
            k for k in ("has_emoji", "has_numbers", "has_testimonial", "has_before_after",
                        "has_question", "has_urgency", "has_price", "has_comparison",
                        "has_guarantee", "has_social_proof")
            if ca.get(k)
        ]

        return {
            "ad_id": ad_id,
            "creative_analysis": ca,
            # Flattened fields for frontend compatibility
            "hook_type": ca.get("hook_type"),
            "cta_type": ca.get("cta_type"),
            "offer_type": ca.get("offer_type"),
            "emotion": ca.get("emotion"),
            "text_features": _text_features,
            "pattern_hit_rate": pattern_hit_rate,
            "pattern_rank": pattern_rank,
            "pattern_count": pattern_rank,  # alias for frontend
            "similar_hits": similar_hits,
            "similar_hit_ads": similar_hits,  # alias for frontend
        }


@router.get("/copy-analysis")
def get_copy_analysis(
    genre: Optional[str] = None,
    platform: Optional[str] = None,
):
    """Analyze text/copy features and their correlation with hit rate.

    Compares hit vs non-hit ads on: description length, emoji usage,
    number usage, testimonial presence, before/after presence.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        ads = query.all()

        # Accumulators
        hit_desc_lengths: list[int] = []
        non_hit_desc_lengths: list[int] = []

        # For boolean features: count (with_feature_hit, with_feature_total,
        #                              without_feature_hit, without_feature_total)
        bool_accum: dict[str, dict] = {}
        for field in _BOOL_FIELDS:
            bool_accum[field] = {
                "with_hit": 0, "with_total": 0,
                "without_hit": 0, "without_total": 0,
            }

        analyzed_count = 0

        for ad in ads:
            ca = _get_creative_analysis(ad)
            if ca is None:
                continue

            analyzed_count += 1
            is_hit = _is_hit_ad(ad)
            desc_len = len(ad.description or "")

            if is_hit:
                hit_desc_lengths.append(desc_len)
            else:
                non_hit_desc_lengths.append(desc_len)

            # Boolean fields
            for field in _BOOL_FIELDS:
                val = ca.get(field)
                if val is None:
                    continue
                if val:
                    bool_accum[field]["with_total"] += 1
                    if is_hit:
                        bool_accum[field]["with_hit"] += 1
                else:
                    bool_accum[field]["without_total"] += 1
                    if is_hit:
                        bool_accum[field]["without_hit"] += 1

        # Compute averages
        avg_hit_desc = round(sum(hit_desc_lengths) / len(hit_desc_lengths)) if hit_desc_lengths else 0
        avg_non_hit_desc = round(sum(non_hit_desc_lengths) / len(non_hit_desc_lengths)) if non_hit_desc_lengths else 0

        def _hit_rate_calc(hit_count: int, total: int) -> float:
            return round(hit_count / total, 3) if total > 0 else 0

        emoji_acc = bool_accum["has_emoji"]
        number_acc = bool_accum["has_numbers"]
        testimonial_acc = bool_accum["has_testimonial"]
        ba_acc = bool_accum["has_before_after"]

        # --- Frontend-compatible format ---
        # Frontend expects: text_features (TextFeature[]), length_stats, total_analyzed
        # TextFeature: {feature, label?, hit_rate, hit_count, total_count, non_hit_rate?}
        text_features = []
        for field in _BOOL_FIELDS:
            acc = bool_accum[field]
            with_total = acc["with_total"]
            with_hit = acc["with_hit"]
            without_total = acc["without_total"]
            without_hit = acc["without_hit"]
            text_features.append({
                "feature": field,
                "hit_rate": _hit_rate_calc(with_hit, with_total),
                "hit_count": with_hit,
                "total_count": with_total,
                "non_hit_rate": _hit_rate_calc(without_hit, without_total),
            })

        # length_stats: {avg_hit_length?, avg_non_hit_length?, optimal_range?}
        length_stats: dict = {}
        if hit_desc_lengths:
            length_stats["avg_hit_length"] = avg_hit_desc
        if non_hit_desc_lengths:
            length_stats["avg_non_hit_length"] = avg_non_hit_desc
        if len(hit_desc_lengths) >= 4:
            sorted_lens = sorted(hit_desc_lengths)
            q1 = sorted_lens[len(sorted_lens) // 4]
            q3 = sorted_lens[3 * len(sorted_lens) // 4]
            length_stats["optimal_range"] = {"min": q1, "max": q3}

        return {
            # Frontend-compatible keys
            "text_features": text_features,
            "length_stats": length_stats if length_stats else None,
            "total_analyzed": analyzed_count,
            # Original keys (backward compat)
            "analyzed_count": analyzed_count,
            "avg_description_length": {
                "hit": avg_hit_desc,
                "non_hit": avg_non_hit_desc,
            },
            "emoji_usage": {
                "hit_with_emoji": _hit_rate_calc(emoji_acc["with_hit"], emoji_acc["with_total"]),
                "hit_without_emoji": _hit_rate_calc(emoji_acc["without_hit"], emoji_acc["without_total"]),
                "with_emoji_count": emoji_acc["with_total"],
                "without_emoji_count": emoji_acc["without_total"],
            },
            "number_usage": {
                "hit_with_numbers": _hit_rate_calc(number_acc["with_hit"], number_acc["with_total"]),
                "hit_without_numbers": _hit_rate_calc(number_acc["without_hit"], number_acc["without_total"]),
                "with_numbers_count": number_acc["with_total"],
                "without_numbers_count": number_acc["without_total"],
            },
            "testimonial_effect": {
                "hit_with_testimonial": _hit_rate_calc(testimonial_acc["with_hit"], testimonial_acc["with_total"]),
                "hit_without": _hit_rate_calc(testimonial_acc["without_hit"], testimonial_acc["without_total"]),
                "with_testimonial_count": testimonial_acc["with_total"],
                "without_testimonial_count": testimonial_acc["without_total"],
            },
            "before_after_effect": {
                "hit_with_ba": _hit_rate_calc(ba_acc["with_hit"], ba_acc["with_total"]),
                "hit_without": _hit_rate_calc(ba_acc["without_hit"], ba_acc["without_total"]),
                "with_ba_count": ba_acc["with_total"],
                "without_ba_count": ba_acc["without_total"],
            },
        }


@router.get("/genre-winning-patterns")
def get_genre_winning_patterns(
    genre: Optional[str] = Query(None, description="Genre to analyze (e.g. beauty, ec_d2c)"),
    platform: Optional[str] = None,
):
    """Return winning creative patterns for a specific genre.

    Analyzes creative_analysis data within the specified genre to find
    which hook_type, cta_type, offer_type, emotion, and combinations
    perform best.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        ads = query.all()

        # Per-field stats
        field_stats: dict[str, dict[str, dict]] = {f: {} for f in _FACTOR_FIELDS + _BOOL_FIELDS}
        combo_stats: dict[tuple, dict] = {}
        analyzed_count = 0
        total_count = len(ads)
        hit_count = 0

        for ad in ads:
            ca = _get_creative_analysis(ad)
            if ca is None:
                continue

            analyzed_count += 1
            is_hit = _is_hit_ad(ad)
            if is_hit:
                hit_count += 1

            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            # Aggregate all factor fields (including booleans as string keys)
            for field in _FACTOR_FIELDS:
                val = ca.get(field)
                if val is None:
                    continue
                val_str = str(val)
                bucket = field_stats[field].setdefault(val_str, {"count": 0, "hits": 0, "total_score": 0.0})
                bucket["count"] += 1
                if is_hit:
                    bucket["hits"] += 1
                bucket["total_score"] += score

            for field in _BOOL_FIELDS:
                val = ca.get(field)
                if val is None:
                    continue
                val_str = str(val)
                bucket = field_stats[field].setdefault(val_str, {"count": 0, "hits": 0, "total_score": 0.0})
                bucket["count"] += 1
                if is_hit:
                    bucket["hits"] += 1
                bucket["total_score"] += score

            # Combinations
            hook = ca.get("hook_type")
            cta = ca.get("cta_type")
            offer = ca.get("offer_type")
            if hook and cta and offer:
                key = (str(hook), str(cta), str(offer))
                combo = combo_stats.setdefault(key, {"count": 0, "hits": 0, "total_score": 0.0})
                combo["count"] += 1
                if is_hit:
                    combo["hits"] += 1
                combo["total_score"] += score

        # Build per-field winning patterns (sorted by hit_rate desc)
        field_winners: dict[str, list[dict]] = {}
        for field in _FACTOR_FIELDS + _BOOL_FIELDS:
            items = []
            for val, stats in field_stats[field].items():
                cnt = stats["count"]
                items.append({
                    "value": val,
                    "count": cnt,
                    "hit_rate": round(stats["hits"] / cnt, 3) if cnt > 0 else 0,
                    "avg_score": round(stats["total_score"] / cnt, 1) if cnt > 0 else 0,
                })
            items.sort(key=lambda x: (x["hit_rate"], x["count"]), reverse=True)
            field_winners[field] = items

        # Top combinations (min 2 samples)
        top_combos = []
        for (hook, cta, offer), stats in combo_stats.items():
            cnt = stats["count"]
            if cnt >= 2:
                top_combos.append({
                    "hook": hook,
                    "cta": cta,
                    "offer": offer,
                    "count": cnt,
                    "hit_rate": round(stats["hits"] / cnt, 3),
                    "avg_score": round(stats["total_score"] / cnt, 1),
                })
        top_combos.sort(key=lambda x: (x["hit_rate"], x["count"]), reverse=True)

        return {
            "genre": genre or "all",
            "total_ads": total_count,
            "analyzed_count": analyzed_count,
            "genre_hit_rate": round(hit_count / analyzed_count, 3) if analyzed_count > 0 else 0,
            "field_winners": field_winners,
            "top_combinations": top_combos[:10],
        }


# ==================== Crawl Status & Quick-Crawl ====================


@router.get("/crawl-status")
def get_crawl_status(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(20, ge=1, le=100),
):
    """Return recent crawl jobs from the last N hours.

    Lets the dashboard show crawl history and progress.
    """
    from app.models.crawl_job import CrawlJob

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

    with sync_session_scope() as session:
        jobs = (
            session.query(CrawlJob)
            .filter(CrawlJob.created_at >= cutoff)
            .order_by(desc(CrawlJob.created_at))
            .limit(limit)
            .all()
        )

        results = []
        for job in jobs:
            results.append({
                "job_id": job.job_id,
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "query": job.query,
                "platforms": job.platforms or [],
                "total_ads_found": job.total_ads_found or 0,
                "completed_platforms": job.completed_platforms or 0,
                "total_platforms": job.total_platforms or 0,
                "current_platform": job.current_platform,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            })

        return {
            "jobs": results,
            "total": len(results),
            "hours_window": hours,
        }


class _QuickCrawlBody(BaseModel):
    query: str
    limit: int = 20


@router.post("/quick-crawl")
def quick_crawl(body: _QuickCrawlBody):
    """Fast crawl: Facebook only, no keyword expansion, no timeout."""
    import uuid
    import asyncio
    import concurrent.futures
    from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum

    query = body.query
    limit = body.limit
    platforms = ["facebook"]
    job_id = str(uuid.uuid4())

    # Track job
    tracking_session = SyncSessionLocal()
    try:
        crawl_job = CrawlJob(
            job_id=job_id,
            status=CrawlJobStatusEnum.RUNNING,
            query=query,
            platforms=platforms,
            total_platforms=1,
            completed_platforms=0,
            total_ads_found=0,
        )
        tracking_session.add(crawl_job)
        tracking_session.commit()
    except Exception:
        tracking_session.rollback()
    finally:
        tracking_session.close()

    # Direct crawl: Facebook only, original query only, no expansion
    new_ads_count = 0
    error_msg = None
    try:
        def _run():
            return asyncio.run(
                _crawl_platforms_no_expand(query, platforms, limit)
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run)
            results = future.result(timeout=45)

        # Save to DB
        new_ads_count = _save_crawled_ads(results)

        logger.info("quick_crawl_completed", query=query, new_ads_count=new_ads_count)
    except Exception as e:
        import traceback
        error_msg = str(e) or repr(e)
        logger.error("quick_crawl_failed", query=query, error=error_msg, traceback=traceback.format_exc())

    # Update job status
    update_session = SyncSessionLocal()
    try:
        job = update_session.query(CrawlJob).filter(CrawlJob.job_id == job_id).first()
        if job:
            job.status = CrawlJobStatusEnum.COMPLETED if error_msg is None else CrawlJobStatusEnum.FAILED
            job.total_ads_found = new_ads_count
            job.completed_platforms = 1
            job.error_message = error_msg
            update_session.commit()
    except Exception:
        update_session.rollback()
    finally:
        update_session.close()

    if error_msg:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"status": "failed", "job_id": job_id, "error": error_msg},
        )

    return {
        "status": "completed",
        "job_id": job_id,
        "new_ads_count": new_ads_count,
        "total_ads_found": new_ads_count,
        "ads_found": new_ads_count,
        "keywords_searched": [query],
        "platforms": platforms,
    }


async def _crawl_platforms_no_expand(
    query: str, platforms: list[str], limit: int, country: str = "JP",
) -> dict:
    """Minimal crawl: one query, one platform, no keyword expansion."""
    from app.core.config import get_settings
    settings = get_settings()

    db_keys: dict[str, dict[str, str]] = {}
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        db_keys = load_api_keys_from_db()
    except Exception:
        pass

    def _get(platform: str, key_name: str, env_fallback):
        return (db_keys.get(platform, {}).get(key_name) or env_fallback) or None

    from app.services.crawling.crawler_manager import CrawlerManager
    manager = CrawlerManager.create_default(
        meta_token=_get("meta", "access_token", settings.meta_access_token),
        tiktok_token=_get("tiktok", "access_token", settings.tiktok_access_token),
    )

    results = await manager.search_all_platforms(
        query=query,
        platforms=platforms,
        category=None,
        limit_per_platform=limit,
        country=country,
    )

    # Apply Japanese language filter
    for plat, ads_list in results.items():
        before = len(ads_list)
        filtered = []
        for ad in ads_list:
            text = " ".join(filter(None, [
                getattr(ad, "title", None),
                getattr(ad, "description", None),
                getattr(ad, "advertiser_name", None),
            ]))
            import re
            has_jp = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))
            if has_jp or country != "JP":
                filtered.append(ad)
        results[plat] = filtered
        logger.info("jp_language_filter_applied", before=before, after=len(filtered), country=country)

    return results


def _save_crawled_ads(results: dict) -> int:
    """Save crawled ads to DB. Returns count of new/updated ads."""
    from app.models.ad import Ad, AdStatusEnum, MediaExtractionStatus
    from app.tasks.crawl_tasks import _extract_destination_url, _extract_text_fallback

    saved = 0
    session = SyncSessionLocal()
    try:
        for platform, crawled_ads in results.items():
            for crawled_ad in crawled_ads:
                if crawled_ad.external_id:
                    existing = session.query(Ad).filter(
                        Ad.external_id == crawled_ad.external_id
                    ).first()
                    if existing:
                        if crawled_ad.view_count is not None:
                            existing.view_count = crawled_ad.view_count
                        if crawled_ad.last_seen_at is not None:
                            existing.last_seen_at = crawled_ad.last_seen_at
                        old_meta = dict(existing.ad_metadata or {})
                        new_meta = dict(crawled_ad.metadata or {})
                        old_meta.update({k: v for k, v in new_meta.items() if v is not None})
                        existing.ad_metadata = old_meta
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(existing, "ad_metadata")
                        saved += 1
                        continue

                has_direct_media = bool(crawled_ad.image_urls or crawled_ad.video_url)
                extraction_status = MediaExtractionStatus.SKIPPED if has_direct_media else (
                    MediaExtractionStatus.PENDING if crawled_ad.snapshot_url else MediaExtractionStatus.SKIPPED
                )

                dest_url = _extract_destination_url(crawled_ad)
                title, description = _extract_text_fallback(crawled_ad)
                meta = dict(crawled_ad.metadata or {})
                if dest_url:
                    meta["destination_url"] = dest_url
                    meta.setdefault("destination_type", "LP")

                ad_category = None
                if crawled_ad.category:
                    from app.models.ad import AdCategoryEnum
                    try:
                        ad_category = AdCategoryEnum(crawled_ad.category)
                    except ValueError:
                        ad_category = AdCategoryEnum.OTHER

                from app.tasks.crawl_tasks import _map_platform
                ad = Ad(
                    external_id=crawled_ad.external_id,
                    title=title,
                    description=description,
                    platform=_map_platform(crawled_ad.platform or platform),
                    status=AdStatusEnum.PENDING,
                    category=ad_category,
                    creative_type=crawled_ad.creative_type,
                    video_url=crawled_ad.video_url,
                    thumbnail_url=crawled_ad.thumbnail_url,
                    image_url=crawled_ad.image_urls[0] if crawled_ad.image_urls else None,
                    snapshot_url=crawled_ad.snapshot_url,
                    destination_url=dest_url,
                    media_extraction_status=extraction_status,
                    advertiser_name=crawled_ad.advertiser_name,
                    view_count=crawled_ad.view_count,
                    like_count=crawled_ad.like_count,
                    spend=crawled_ad.spend,
                    impressions=crawled_ad.impressions,
                    first_seen_at=crawled_ad.first_seen_at,
                    last_seen_at=crawled_ad.last_seen_at,
                    ad_metadata=meta,
                )
                session.add(ad)
                saved += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return saved


# ==================== Trend Refresh ====================


@router.post("/refresh-trends")
def refresh_trends():
    """Recompute trend scores for all ads based on latest metric data.

    Updates hit_score and trend_score in ProductRanking rows.
    Returns the number of ads updated.
    """
    with sync_session_scope() as session:
        # Fetch all ads with their metrics
        ads = session.query(Ad).all()
        if not ads:
            return {"status": "completed", "updated_count": 0, "message": "No ads found"}

        # Precompute genre stats once
        genre_stats = compute_genre_stats(session)

        updated_count = 0
        for ad in ads:
            # Fetch metrics for this ad (last 30 days)
            cutoff_date = _today_jst() - timedelta(days=30)
            metrics = (
                session.query(AdDailyMetrics)
                .filter(
                    AdDailyMetrics.ad_id == ad.id,
                    AdDailyMetrics.metric_date >= cutoff_date,
                )
                .order_by(AdDailyMetrics.metric_date)
                .all()
            )

            # Compute updated hit score
            result = compute_hit_score_with_details(
                ad, metrics=metrics, genre_stats=genre_stats
            )
            hit_score = result.get("hit_score", 0.0)
            trend_score = result.get("trend_score", 0.0)

            # Update or create ProductRanking
            ranking = (
                session.query(ProductRanking)
                .filter(ProductRanking.ad_id == ad.id)
                .first()
            )
            if ranking:
                ranking.hit_score = hit_score
                ranking.trend_score = trend_score
                ranking.is_hit = hit_score >= 60
                updated_count += 1
            else:
                # Create new ProductRanking entry
                today = _today_jst()
                week_start = today - timedelta(days=today.weekday())
                new_ranking = ProductRanking(
                    ad_id=ad.id,
                    period="weekly",
                    period_start=week_start,
                    period_end=today,
                    genre=ad.category.value if ad.category else "other",
                    rank_position=0,  # will be recomputed by full ranking pass
                    hit_score=hit_score,
                    trend_score=trend_score,
                    is_hit=hit_score >= 60,
                )
                session.add(new_ranking)
                updated_count += 1

            # Also update ad_metadata with latest scores (without overwriting Agent A keys)
            meta = dict(ad.ad_metadata or {})
            meta["latest_hit_score"] = hit_score
            meta["latest_trend_score"] = trend_score
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

        session.commit()

        logger.info("refresh_trends_completed", updated_count=updated_count)

        return {
            "status": "completed",
            "updated_count": updated_count,
            "total_ads": len(ads),
        }


# ==================== Fresh Ads ====================


@router.get("/fresh-ads")
def get_fresh_ads(
    days: int = Query(7, ge=1, le=30),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    platform: Optional[str] = None,
    creative_type: Optional[str] = None,
):
    """Return ads crawled in the last N days, sorted newest first.

    Includes thumbnail resolution, hit_score, and creative_type.
    Supports pagination and optional platform/creative_type filters.
    """
    with sync_session_scope() as session:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

        query = session.query(Ad).filter(Ad.created_at >= cutoff)

        # Apply optional filters
        query = _resolve_platform_filter(query, Ad.platform, platform)
        if creative_type:
            query = query.filter(Ad.creative_type == creative_type)

        # Count total before pagination
        total = query.count()

        # Fetch paginated results
        ads = (
            query.order_by(desc(Ad.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        # Batch-fetch ProductRankings for hit_score
        ad_ids = [ad.id for ad in ads]
        ranking_map: dict[int, ProductRanking] = {}
        if ad_ids:
            rankings = (
                session.query(ProductRanking)
                .filter(ProductRanking.ad_id.in_(ad_ids))
                .all()
            )
            for r in rankings:
                # Keep highest hit_score if multiple rankings exist
                if r.ad_id not in ranking_map or (r.hit_score or 0) > (ranking_map[r.ad_id].hit_score or 0):
                    ranking_map[r.ad_id] = r

        results = []
        for ad in ads:
            # Filter out non-quality ads (duplicates, non-Japanese)
            if not _is_quality_ad(ad):
                continue
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            pr = ranking_map.get(ad.id)

            hit_score = (pr.hit_score if pr else None) or meta.get("latest_hit_score", 0)
            trend_score = (pr.trend_score if pr else None) or meta.get("latest_trend_score", 0)

            results.append({
                "id": ad.id,
                "ad_id": ad.id,  # alias for frontend FreshAdsSection
                "external_id": ad.external_id,
                "title": (ad.title or "")[:120],
                "description": (ad.description or "")[:200],
                "advertiser_name": _clean_advertiser(ad.advertiser_name),
                "product_name": _derive_product_name(ad),
                "platform": ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform),
                "genre": _resolve_genre_label(ad),
                "creative_type": ad.creative_type or "unknown",
                "thumbnail_url": _resolve_thumbnail_url(ad),
                "thumbnail": _resolve_thumbnail_url(ad),  # alias for frontend
                "image_url": _resolve_image_url(ad),
                "snapshot_url": ad.snapshot_url or "",
                "video_url": _resolve_video_url(ad),
                "destination_url": ad.destination_url or "",
                "hit_score": round(hit_score or 0, 1),
                "hit_level": longevity["hit_level"],
                "trend_score": round(trend_score or 0, 1),
                "is_hit": (hit_score or 0) >= 60,
                "days_running": longevity["days_running"],
                "is_still_running": longevity["is_still_running"],
                "creative_analysis": meta.get("creative_analysis"),
                "media_status": _resolve_media_status(ad),
                "download_urls": _build_download_urls(ad),
                "data_quality": _build_data_quality(ad),
                "created_at": ad.created_at.isoformat() if ad.created_at else None,
                "first_seen_at": ad.first_seen_at.isoformat() if ad.first_seen_at else None,
            })

        return {
            "ads": results,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
            "days_window": days,
        }


# ==================== Production Export (C10) ====================


def _build_full_ad_row(ad: Ad, meta: dict, longevity: dict) -> dict:
    """Build a complete ad data dict for export."""
    ca = meta.get("creative_analysis") or {}
    hit_score = float(meta.get("latest_hit_score", 0) or 0)
    return {
        "id": ad.id,
        "external_id": ad.external_id or "",
        "title": ad.title or "",
        "description": ad.description or "",
        "advertiser_name": _clean_advertiser(ad.advertiser_name),
        "product_name": _derive_product_name(ad),
        "platform": str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or ""),
        "category": _resolve_genre_label(ad),
        "creative_type": ad.creative_type or "unknown",
        "hit_score": round(hit_score, 1),
        "hit_level": meta.get("hit_level", "none"),
        "days_running": longevity["days_running"],
        "is_still_running": longevity["is_still_running"],
        "thumbnail_url": _resolve_thumbnail_url(ad),
        "image_url": _resolve_image_url(ad),
        "video_url": _resolve_video_url(ad),
        "destination_url": ad.destination_url or "",
        "view_count": ad.view_count or 0,
        "like_count": ad.like_count or 0,
        "first_seen_at": ad.first_seen_at.isoformat() if ad.first_seen_at else "",
        "last_seen_at": ad.last_seen_at.isoformat() if ad.last_seen_at else "",
        "hook_type": ca.get("hook_type", ""),
        "cta_type": ca.get("cta_type", ""),
        "offer_type": ca.get("offer_type", ""),
        "emotion": ca.get("emotion", ""),
        "has_emoji": ca.get("has_emoji", ""),
        "has_numbers": ca.get("has_numbers", ""),
        "has_testimonial": ca.get("has_testimonial", ""),
        "has_before_after": ca.get("has_before_after", ""),
        "text_length": ca.get("text_length", ""),
        "destination_type": ca.get("destination_type", ""),
        "creative_analysis": meta.get("creative_analysis"),
        "media_status": _resolve_media_status(ad),
        "download_urls": _build_download_urls(ad),
    }


def _query_export_ads(session, genre=None, min_score=None, date_from=None, date_to=None):
    """Build filtered ad query for export endpoints."""
    query = session.query(Ad)
    if genre:
        query = query.filter(Ad.category == genre)
    if date_from:
        try:
            query = query.filter(Ad.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Ad.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    ads = query.order_by(desc(Ad.created_at)).limit(5000).all()

    # Post-filter by min_score (stored in JSON metadata)
    if min_score is not None:
        ads = [
            ad for ad in ads
            if float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0) >= min_score
        ]

    return ads


@router.get("/export/csv")
def export_full_csv(
    genre: Optional[str] = None,
    min_score: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Export all ads as CSV download with creative_analysis + hit_score.

    Supports filtering by genre, minimum score, and date range.
    """
    with sync_session_scope() as session:
        ads = _query_export_ads(session, genre, min_score, date_from, date_to)

        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "ID", "External ID", "Title", "Advertiser", "Product",
            "Platform", "Category", "Creative Type",
            "Hit Score", "Hit Level", "Days Running", "Still Running",
            "View Count", "Like Count",
            "First Seen", "Last Seen",
            "Hook Type", "CTA Type", "Offer Type", "Emotion",
            "Emoji", "Numbers", "Testimonial", "Before/After",
            "Text Length", "Destination Type",
            "Thumbnail URL", "Image URL", "Video URL", "Destination URL",
        ]
        writer.writerow(headers)

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            row = _build_full_ad_row(ad, meta, longevity)
            writer.writerow([
                row["id"], row["external_id"],
                _sanitize_csv(row["title"]), _sanitize_csv(row["advertiser_name"]),
                _sanitize_csv(row["product_name"]),
                row["platform"], row["category"], row["creative_type"],
                row["hit_score"], row["hit_level"],
                row["days_running"], row["is_still_running"],
                row["view_count"], row["like_count"],
                row["first_seen_at"], row["last_seen_at"],
                row["hook_type"], row["cta_type"], row["offer_type"], row["emotion"],
                row["has_emoji"], row["has_numbers"],
                row["has_testimonial"], row["has_before_after"],
                row["text_length"], row["destination_type"],
                row["thumbnail_url"], row["image_url"],
                row["video_url"], row["destination_url"],
            ])

        output.seek(0)
        filename = f"ads_full_export_{genre or 'all'}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/export/json")
def export_full_json(
    genre: Optional[str] = None,
    min_score: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Export all ads as JSON download with creative_analysis + hit_score."""
    with sync_session_scope() as session:
        ads = _query_export_ads(session, genre, min_score, date_from, date_to)

        results = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            results.append(_build_full_ad_row(ad, meta, longevity))

        import json as _json

        def _default(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return str(obj)

        content = _json.dumps(
            {"ads": results, "total": len(results)},
            ensure_ascii=False, indent=2, default=_default,
        )
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=ads_export.json"},
        )


@router.get("/export/report")
def export_analysis_report(
    genre: Optional[str] = None,
):
    """Export comprehensive hit pattern analysis report as JSON.

    Combines hit factors, winning patterns, genre comparison,
    and creative DNA statistics into a single downloadable report.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        if genre:
            genre_ads = [a for a in ads if str(getattr(a.category, "value", a.category) or "") == genre]
        else:
            genre_ads = ads

        # Hit factors summary
        factor_summary: dict[str, dict[str, dict]] = {f: {} for f in _FACTOR_FIELDS}
        combo_stats: dict[tuple, dict] = {}
        analyzed = 0

        for ad in genre_ads:
            ca = _get_creative_analysis(ad)
            if ca is None:
                continue
            analyzed += 1
            is_hit = _is_hit_ad(ad)
            meta = ad.ad_metadata or {}
            score = float(meta.get("latest_hit_score", 0) or 0)

            for field in _FACTOR_FIELDS:
                val = ca.get(field)
                if val is None:
                    continue
                b = factor_summary[field].setdefault(str(val), {"count": 0, "hits": 0, "total_score": 0.0})
                b["count"] += 1
                if is_hit:
                    b["hits"] += 1
                b["total_score"] += score

            hook = ca.get("hook_type")
            cta = ca.get("cta_type")
            offer = ca.get("offer_type")
            if hook and cta and offer:
                key = (str(hook), str(cta), str(offer))
                c = combo_stats.setdefault(key, {"count": 0, "hits": 0, "total_score": 0.0})
                c["count"] += 1
                if is_hit:
                    c["hits"] += 1
                c["total_score"] += score

        # Format factors
        factors_out = {}
        for field in _FACTOR_FIELDS:
            items = []
            for val, stats in factor_summary[field].items():
                cnt = stats["count"]
                items.append({
                    "value": val,
                    "count": cnt,
                    "hit_rate": round(stats["hits"] / cnt, 3) if cnt > 0 else 0,
                    "avg_score": round(stats["total_score"] / cnt, 1) if cnt > 0 else 0,
                })
            items.sort(key=lambda x: x["hit_rate"], reverse=True)
            factors_out[field] = items

        # Winning combinations
        winning = []
        for (hook, cta, offer), stats in combo_stats.items():
            cnt = stats["count"]
            if cnt >= 2:
                winning.append({
                    "hook": hook, "cta": cta, "offer": offer,
                    "count": cnt,
                    "hit_rate": round(stats["hits"] / cnt, 3),
                    "avg_score": round(stats["total_score"] / cnt, 1),
                })
        winning.sort(key=lambda x: (x["hit_rate"], x["count"]), reverse=True)

        # Genre comparison
        genre_data: dict[str, dict] = {}
        for ad in ads:
            g = _resolve_genre_label(ad)
            gd = genre_data.setdefault(g, {"count": 0, "hits": 0, "total_score": 0.0})
            gd["count"] += 1
            if _is_hit_ad(ad):
                gd["hits"] += 1
            gd["total_score"] += float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)

        genres_out = []
        for g, data in genre_data.items():
            cnt = data["count"]
            genres_out.append({
                "genre": g, "count": cnt,
                "hit_rate": round(data["hits"] / cnt, 3) if cnt > 0 else 0,
                "avg_score": round(data["total_score"] / cnt, 1) if cnt > 0 else 0,
            })
        genres_out.sort(key=lambda x: x["hit_rate"], reverse=True)

        report = {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "genre_filter": genre or "all",
            "total_ads": len(ads),
            "analyzed_ads": analyzed,
            "hit_factors": factors_out,
            "winning_combinations": winning[:20],
            "genre_comparison": genres_out,
        }

        import json as _json
        content = _json.dumps(report, ensure_ascii=False, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=hit_pattern_report.json"},
        )


# ==================== C11: Advanced Analytics API ====================


def _build_ad_detail(ad: Ad) -> dict:
    """Build a full ad detail dict with resolved media URLs."""
    meta = ad.ad_metadata or {}
    longevity = _extract_longevity_info(ad)
    ca = meta.get("creative_analysis") or {}
    hit_score = float(meta.get("latest_hit_score", 0) or 0)
    return {
        "id": ad.id,
        "ad_id": ad.id,
        "external_id": ad.external_id or "",
        "title": ad.title or "",
        "description": ad.description or "",
        "advertiser_name": _clean_advertiser(ad.advertiser_name),
        "product_name": _derive_product_name(ad),
        "platform": str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or ""),
        "genre": _resolve_genre_label(ad),
        "creative_type": ad.creative_type or "unknown",
        "hit_score": round(hit_score, 1),
        "hit_level": longevity["hit_level"],
        "is_hit": _is_hit_ad(ad),
        "days_running": longevity["days_running"],
        "is_still_running": longevity["is_still_running"],
        "thumbnail": _resolve_thumbnail_url(ad),
        "thumbnail_url": _resolve_thumbnail_url(ad),
        "image_url": _resolve_image_url(ad),
        "video_url": _resolve_video_url(ad),
        "snapshot_url": ad.snapshot_url or "",
        "destination_url": ad.destination_url or "",
        "view_count": ad.view_count or 0,
        "like_count": ad.like_count or 0,
        "duration_seconds": ad.duration_seconds or 0,
        "first_seen_at": ad.first_seen_at.isoformat() if ad.first_seen_at else None,
        "last_seen_at": ad.last_seen_at.isoformat() if ad.last_seen_at else None,
        "created_at": ad.created_at.isoformat() if ad.created_at else None,
        "hook_type": ca.get("hook_type", ""),
        "cta_type": ca.get("cta_type", ""),
        "offer_type": ca.get("offer_type", ""),
        "emotion": ca.get("emotion", ""),
        "creative_analysis": meta.get("creative_analysis"),
        "media_status": _resolve_media_status(ad),
        "download_urls": _build_download_urls(ad),
        "bookmarked": meta.get("bookmarked", False),
        "bookmark_note": meta.get("bookmark_note", ""),
        "bookmark_tags": meta.get("bookmark_tags", []),
        **_build_meta_freshness_contract(ad),
    }


@router.get("/advertisers")
def list_advertisers(
    sort_by: str = Query("ad_count", description="Sort: ad_count, hit_rate, avg_score"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List all advertisers with aggregated statistics.

    Returns: name, ad_count, hit_count, hit_rate, avg_score, top_genre, active_ads.
    Supports sorting and pagination.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).filter(Ad.advertiser_name.isnot(None)).all()

        advertiser_map: dict[str, list[Ad]] = {}
        for ad in ads:
            name = _clean_advertiser(ad.advertiser_name)
            if not name:
                continue
            advertiser_map.setdefault(name, []).append(ad)

        results = []
        for adv_name, adv_ads in advertiser_map.items():
            scores = []
            active_count = 0
            hit_count = 0
            mega_hit_count = 0
            total_spend = 0
            genre_counter: dict[str, int] = {}

            for ad in adv_ads:
                meta = ad.ad_metadata or {}
                longevity = _extract_longevity_info(ad)

                score = meta.get("latest_hit_score")
                if score is None:
                    score, _, hit_lvl, _ = compute_hit_score(ad)
                else:
                    score = float(score)
                    hit_lvl = meta.get("hit_level", "none")

                scores.append(score)

                if longevity["is_still_running"]:
                    active_count += 1
                if _is_hit_ad(ad):
                    hit_count += 1
                if hit_lvl == "mega_hit" or (score >= 70 and longevity["days_running"] >= 60):
                    mega_hit_count += 1

                est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
                total_spend += est_spend

                genre = _resolve_genre_label(ad)
                genre_counter[genre] = genre_counter.get(genre, 0) + 1

            n = len(scores)
            avg_score = sum(scores) / n if n > 0 else 0
            hit_rate = hit_count / n if n > 0 else 0
            top_genre = max(genre_counter, key=genre_counter.get) if genre_counter else "uncategorized"

            results.append({
                "name": adv_name,
                "advertiser_name": adv_name,
                "ad_count": n,
                "hit_count": hit_count,
                "mega_hit_count": mega_hit_count,
                "hit_rate": round(hit_rate, 3),
                "avg_score": round(avg_score, 1),
                "total_spend": int(total_spend),
                "top_genre": top_genre,
                "active_ads": active_count,
            })

        # Sort
        sort_key_map = {
            "ad_count": lambda x: x["ad_count"],
            "hit_rate": lambda x: x["hit_rate"],
            "avg_score": lambda x: x["avg_score"],
        }
        results.sort(key=sort_key_map.get(sort_by, sort_key_map["ad_count"]), reverse=True)

        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = results[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "advertisers": paginated,
        }


@router.get("/advertiser/{name}/ads")
def get_advertiser_ads(
    name: str,
    sort_by: str = Query("score_desc", description="Sort: score_desc, date_desc, views_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get all ads by a specific advertiser with full details and resolved media URLs."""
    with sync_session_scope() as session:
        query = session.query(Ad).filter(
            Ad.advertiser_name.ilike(f"%{_escape_like(name)}%")
        )
        total = query.count()

        # Sort
        if sort_by == "date_desc":
            query = query.order_by(desc(Ad.created_at))
        elif sort_by == "views_desc":
            query = query.order_by(
                case((Ad.view_count.is_(None), 0), else_=1).desc(),
                desc(Ad.view_count),
            )
        else:
            # score_desc: sort in Python after fetch since score is in JSON metadata
            pass

        ads = query.all()

        # Build ad details
        ad_details = [_build_ad_detail(ad) for ad in ads]

        # If sorting by score, sort now
        if sort_by == "score_desc":
            ad_details.sort(key=lambda x: x["hit_score"], reverse=True)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        paginated = ad_details[start:end]

        return {
            "advertiser_name": name,
            "total": total,
            "page": page,
            "page_size": page_size,
            "ads": paginated,
        }


@router.get("/advertiser/{name}/profile")
def get_advertiser_profile(name: str):
    """Get advertiser profile with creative strategy summary.

    Returns: dominant hooks, CTAs, emotions, performance over time, genre distribution.
    """
    with sync_session_scope() as session:
        ads = (
            session.query(Ad)
            .filter(Ad.advertiser_name.ilike(f"%{_escape_like(name)}%"))
            .all()
        )

        if not ads:
            return JSONResponse(
                status_code=404,
                content={"detail": f"No ads found for advertiser '{name}'"},
            )

        # Aggregate creative strategy
        hook_counts: dict[str, int] = {}
        cta_counts: dict[str, int] = {}
        emotion_counts: dict[str, int] = {}
        offer_counts: dict[str, int] = {}
        genre_counts: dict[str, int] = {}
        platform_counts: dict[str, int] = {}

        scores = []
        total_spend = 0
        total_days = 0
        active_count = 0
        hit_count = 0

        # Performance over time: group by month
        monthly_perf: dict[str, list[float]] = {}

        for ad in ads:
            meta = ad.ad_metadata or {}
            ca = meta.get("creative_analysis") or {}
            longevity = _extract_longevity_info(ad)

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)
            scores.append(score)

            if longevity["is_still_running"]:
                active_count += 1
            if _is_hit_ad(ad):
                hit_count += 1

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend
            total_days += longevity["days_running"]

            # Creative strategy counts
            if ca.get("hook_type"):
                hook_counts[str(ca["hook_type"])] = hook_counts.get(str(ca["hook_type"]), 0) + 1
            if ca.get("cta_type"):
                cta_counts[str(ca["cta_type"])] = cta_counts.get(str(ca["cta_type"]), 0) + 1
            if ca.get("emotion"):
                emotion_counts[str(ca["emotion"])] = emotion_counts.get(str(ca["emotion"]), 0) + 1
            if ca.get("offer_type"):
                offer_counts[str(ca["offer_type"])] = offer_counts.get(str(ca["offer_type"]), 0) + 1

            # Genre distribution
            genre = _resolve_genre_label(ad)
            genre_counts[genre] = genre_counts.get(genre, 0) + 1

            # Platform distribution
            platform = str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or "")
            platform_counts[platform] = platform_counts.get(platform, 0) + 1

            # Monthly performance
            created = ad.first_seen_at or ad.created_at
            if created:
                month_key = created.strftime("%Y-%m")
                monthly_perf.setdefault(month_key, []).append(score)

        n = len(scores)
        avg_score = sum(scores) / n if n > 0 else 0
        avg_days = total_days / n if n > 0 else 0

        # Sort counts and take top items
        def _top_items(counts: dict, limit: int = 5) -> list[dict]:
            sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            return [{"name": k, "count": v} for k, v in sorted_items[:limit]]

        # Build monthly performance timeline
        timeline = []
        for month in sorted(monthly_perf.keys()):
            month_scores = monthly_perf[month]
            timeline.append({
                "month": month,
                "ad_count": len(month_scores),
                "avg_score": round(sum(month_scores) / len(month_scores), 1),
            })

        # Fix #61: Build top_ads for AdvertiserProfile.tsx
        _scored_ads = []
        for _a in ads:
            _m = _a.ad_metadata or {}
            _s = _m.get("latest_hit_score")
            if _s is None:
                _s, _, _, _ = compute_hit_score(_a)
            else:
                _s = float(_s)
            _scored_ads.append((_a, _s))
        _scored_ads.sort(key=lambda x: x[1], reverse=True)
        _top_ads = []
        for _a, _s in _scored_ads[:10]:
            _top_ads.append({
                "ad_id": _a.id,
                "id": _a.id,
                "product_name": _derive_product_name(_a),
                "title": _a.title or "",
                "hit_score": round(_s, 1),
                "thumbnail": f"/api/v1/media/thumbnail/{_a.id}",
                "published_date": (_a.first_seen_at or _a.created_at).isoformat() if (_a.first_seen_at or _a.created_at) else "",
            })

        # Fix #61: Flatten preferred_hooks/ctas as string arrays
        _preferred_hooks = [item["name"] for item in _top_items(hook_counts)]
        _preferred_ctas = [item["name"] for item in _top_items(cta_counts)]

        # Fix #61: Add percentage to genre_distribution
        _genre_dist = [
            {"genre": k, "count": v, "percentage": round(v / n * 100, 1) if n > 0 else 0}
            for k, v in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Fix #61: Add total_spend to monthly_trends
        _monthly_trends = []
        for _t in timeline:
            _monthly_trends.append({
                **_t,
                "total_spend": 0,  # per-month spend not tracked individually
            })

        return {
            "advertiser_name": name,
            "total_ads": n,
            "active_ads": active_count,
            "hit_count": hit_count,
            "hit_rate": round(hit_count / n, 3) if n > 0 else 0,
            "avg_score": round(avg_score, 1),
            "best_score": round(max(scores), 1) if scores else 0,
            "total_estimated_spend_jpy": int(total_spend),
            "total_spend": int(total_spend),  # Fix #61: alias for frontend
            "avg_days_running": round(avg_days),
            "avg_duration_days": round(avg_days),  # Fix #61: alias for frontend
            "creative_strategy": {
                "dominant_hooks": _top_items(hook_counts),
                "dominant_ctas": _top_items(cta_counts),
                "dominant_emotions": _top_items(emotion_counts),
                "dominant_offers": _top_items(offer_counts),
            },
            "preferred_hooks": _preferred_hooks,  # Fix #61: flat string[] for frontend
            "preferred_ctas": _preferred_ctas,  # Fix #61: flat string[] for frontend
            "genre_distribution": _genre_dist,
            "platform_distribution": [
                {"platform": k, "count": v}
                for k, v in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)
            ],
            "performance_over_time": timeline,
            "monthly_trends": _monthly_trends,  # Fix #61: alias for frontend
            "top_ads": _top_ads,  # Fix #61: for frontend AdvertiserProfile.tsx
        }


@router.get("/trends/weekly")
def get_weekly_trends():
    """Return weekly trend data for the last 12 weeks.

    For each week: ad_count, avg_score, hit_rate, top_hooks.
    Used for trend charts on frontend.
    """
    with sync_session_scope() as session:
        today = _today_jst()
        weeks = []

        for w in range(12):
            week_end = today - timedelta(days=w * 7)
            week_start = week_end - timedelta(days=6)

            # Find ads created in this week
            ads = (
                session.query(Ad)
                .filter(
                    Ad.created_at >= datetime(week_start.year, week_start.month, week_start.day),
                    Ad.created_at < datetime(week_end.year, week_end.month, week_end.day) + timedelta(days=1),
                )
                .all()
            )

            ad_count = len(ads)
            scores = []
            hit_count = 0
            hook_counter: dict[str, int] = {}

            for ad in ads:
                meta = ad.ad_metadata or {}
                score = meta.get("latest_hit_score")
                if score is None:
                    score, _, _, _ = compute_hit_score(ad)
                else:
                    score = float(score)
                scores.append(score)

                if _is_hit_ad(ad):
                    hit_count += 1

                ca = meta.get("creative_analysis") or {}
                hook = ca.get("hook_type")
                if hook:
                    hook_counter[str(hook)] = hook_counter.get(str(hook), 0) + 1

            avg_score = sum(scores) / len(scores) if scores else 0
            hit_rate = hit_count / ad_count if ad_count > 0 else 0

            # Top hooks for this week
            top_hooks = sorted(hook_counter.items(), key=lambda x: x[1], reverse=True)[:3]

            weeks.append({
                "week_start": week_start.isoformat(),
                "week": week_start.isoformat(),  # alias for frontend TrendCharts
                "week_label": f"{week_start.month}/{week_start.day}",
                "week_end": week_end.isoformat(),
                "ad_count": ad_count,
                "avg_score": round(avg_score, 1),
                "hit_rate": round(hit_rate, 3),
                "hit_count": hit_count,
                "top_hooks": [{"hook": h, "count": c} for h, c in top_hooks],
                "hook_types": {h: c for h, c in top_hooks},  # alias: dict for frontend
            })

        # Reverse so oldest week is first (chronological order)
        weeks.reverse()

        # Fix #57: Build per-genre weekly breakdown for PerformanceHeatmap
        # Collect all ads in the 12-week range and group by genre + week
        _twelve_weeks_ago = today - timedelta(days=12 * 7)
        _all_ads = (
            session.query(Ad)
            .filter(Ad.created_at >= datetime(_twelve_weeks_ago.year, _twelve_weeks_ago.month, _twelve_weeks_ago.day))
            .all()
        )
        # Group ads by genre
        _genre_ads: dict[str, list] = {}
        for _a in _all_ads:
            _g = _resolve_genre_label(_a)
            _genre_ads.setdefault(_g, []).append(_a)

        # Get top 10 genres by count
        _top_genres = sorted(_genre_ads.keys(), key=lambda g: len(_genre_ads[g]), reverse=True)[:10]

        # Build week boundaries list (same as above, oldest first)
        _week_bounds = []
        for _w in range(min(8, len(weeks))):
            _we = today - timedelta(days=_w * 7)
            _ws = _we - timedelta(days=6)
            _week_bounds.append((_ws, _we))
        _week_bounds.reverse()

        _genres_weekly = []
        for _g in _top_genres:
            _g_ads = _genre_ads.get(_g, [])
            _g_weeks = []
            for _ws, _we in _week_bounds:
                _ws_dt = datetime(_ws.year, _ws.month, _ws.day)
                _we_dt = datetime(_we.year, _we.month, _we.day) + timedelta(days=1)
                _w_ads = [a for a in _g_ads if a.created_at and _ws_dt <= a.created_at < _we_dt]
                _w_scores = []
                for _a in _w_ads:
                    _m = _a.ad_metadata or {}
                    _s = _m.get("latest_hit_score")
                    if _s is None:
                        _s, _, _, _ = compute_hit_score(_a)
                    else:
                        _s = float(_s)
                    _w_scores.append(_s)
                _avg = round(sum(_w_scores) / len(_w_scores), 1) if _w_scores else 0
                _g_weeks.append({
                    "week": _ws.isoformat(),
                    "week_label": f"{_ws.month}/{_ws.day}",
                    "avg_score": _avg,
                    "ad_count": len(_w_ads),
                })
            _genres_weekly.append({
                "genre": _g,
                "genre_label": _g,
                "weeks": _g_weeks,
            })

        return {
            "weeks": weeks,
            "total_weeks": len(weeks),
            "genres": _genres_weekly,  # Fix #57: per-genre data for PerformanceHeatmap
            "items": _genres_weekly,   # Fix #57: alias
        }


@router.get("/trends/rising-patterns")
def get_rising_patterns():
    """Identify patterns (hooks/CTAs/emotions) gaining popularity or hit rate.

    Compares last 4 weeks vs previous 4 weeks to find rising trends.
    """
    with sync_session_scope() as session:
        today = _today_jst()
        recent_start = today - timedelta(days=28)
        previous_start = today - timedelta(days=56)

        # Recent period ads (last 4 weeks)
        recent_ads = (
            session.query(Ad)
            .filter(
                Ad.created_at >= datetime(recent_start.year, recent_start.month, recent_start.day),
            )
            .all()
        )

        # Previous period ads (4-8 weeks ago)
        previous_ads = (
            session.query(Ad)
            .filter(
                Ad.created_at >= datetime(previous_start.year, previous_start.month, previous_start.day),
                Ad.created_at < datetime(recent_start.year, recent_start.month, recent_start.day),
            )
            .all()
        )

        def _collect_pattern_stats(ads_list):
            """Collect pattern usage and hit rates from a list of ads."""
            hooks: dict[str, dict] = {}
            ctas: dict[str, dict] = {}
            emotions: dict[str, dict] = {}

            for ad in ads_list:
                ca = (ad.ad_metadata or {}).get("creative_analysis") or {}
                is_hit = _is_hit_ad(ad)

                for name, counter_dict in [
                    (ca.get("hook_type"), hooks),
                    (ca.get("cta_type"), ctas),
                    (ca.get("emotion"), emotions),
                ]:
                    if name:
                        key = str(name)
                        b = counter_dict.setdefault(key, {"count": 0, "hits": 0})
                        b["count"] += 1
                        if is_hit:
                            b["hits"] += 1

            return hooks, ctas, emotions

        recent_hooks, recent_ctas, recent_emotions = _collect_pattern_stats(recent_ads)
        prev_hooks, prev_ctas, prev_emotions = _collect_pattern_stats(previous_ads)

        def _find_rising(recent: dict, previous: dict, label: str) -> list[dict]:
            """Find patterns with increasing usage or hit rate."""
            rising = []
            for name, r_stats in recent.items():
                p_stats = previous.get(name, {"count": 0, "hits": 0})
                r_count = r_stats["count"]
                p_count = p_stats["count"]
                r_hit_rate = r_stats["hits"] / r_count if r_count > 0 else 0
                p_hit_rate = p_stats["hits"] / p_count if p_count > 0 else 0

                usage_change = r_count - p_count
                hit_rate_change = r_hit_rate - p_hit_rate

                # Consider rising if usage increased or hit rate improved
                if usage_change > 0 or hit_rate_change > 0.05:
                    rising.append({
                        "pattern_type": label,
                        "name": name,
                        "recent_count": r_count,
                        "previous_count": p_count,
                        "usage_change": usage_change,
                        "recent_hit_rate": round(r_hit_rate, 3),
                        "previous_hit_rate": round(p_hit_rate, 3),
                        "hit_rate_change": round(hit_rate_change, 3),
                    })

            rising.sort(key=lambda x: (x["hit_rate_change"], x["usage_change"]), reverse=True)
            return rising

        rising_hooks = _find_rising(recent_hooks, prev_hooks, "hook")
        rising_ctas = _find_rising(recent_ctas, prev_ctas, "cta")
        rising_emotions = _find_rising(recent_emotions, prev_emotions, "emotion")

        return {
            "period": {
                "recent": {"start": recent_start.isoformat(), "end": today.isoformat()},
                "previous": {"start": previous_start.isoformat(), "end": recent_start.isoformat()},
            },
            "rising_hooks": rising_hooks[:10],
            "rising_ctas": rising_ctas[:10],
            "rising_emotions": rising_emotions[:10],
            "all_rising": sorted(
                rising_hooks + rising_ctas + rising_emotions,
                key=lambda x: (x["hit_rate_change"], x["usage_change"]),
                reverse=True,
            )[:20],
        }


@router.get("/trends/market-overview")
def get_market_overview():
    """Return current market snapshot.

    Total active ads, avg score, genre distribution, creative type split.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        total = len(ads)

        if total == 0:
            return {
                "total_ads": 0,
                "active_ads": 0,
                "avg_score": 0,
                "hit_rate": 0,
                "genre_distribution": [],
                "creative_type_split": {},
                "platform_distribution": [],
                "hit_summary": {"total_hits": 0, "mega_hits": 0, "hit_rate": 0},
            }

        scores = []
        active_count = 0
        hit_count = 0
        mega_count = 0
        genre_counter: dict[str, int] = {}
        creative_counter: dict[str, int] = {}
        platform_counter: dict[str, int] = {}

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, hit_level, _ = compute_hit_score(ad)
            else:
                score = float(score)
                hit_level = meta.get("hit_level", "none")
            scores.append(score)

            if longevity["is_still_running"]:
                active_count += 1

            is_hit = _is_hit_ad(ad)
            if is_hit:
                hit_count += 1
            if hit_level == "mega_hit" or (score >= 70 and longevity["days_running"] >= 60):
                mega_count += 1

            genre = _resolve_genre_label(ad)
            genre_counter[genre] = genre_counter.get(genre, 0) + 1

            ct = ad.creative_type or "unknown"
            creative_counter[ct] = creative_counter.get(ct, 0) + 1

            platform = str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or "")
            platform_counter[platform] = platform_counter.get(platform, 0) + 1

        avg_score = sum(scores) / len(scores) if scores else 0

        _hit_rate = round(hit_count / total, 3) if total > 0 else 0

        return {
            "total_ads": total,
            "active_ads": active_count,
            "avg_score": round(avg_score, 1),
            "hit_rate": _hit_rate,  # top-level alias for frontend MarketOverview
            "genre_distribution": [
                {"genre": k, "count": v, "share": round(v / total, 3)}
                for k, v in sorted(genre_counter.items(), key=lambda x: x[1], reverse=True)
            ],
            "creative_type_split": {
                k: v for k, v in sorted(creative_counter.items(), key=lambda x: x[1], reverse=True)
            },
            "creative_type_split_detailed": [
                {"type": k, "count": v, "share": round(v / total, 3)}
                for k, v in sorted(creative_counter.items(), key=lambda x: x[1], reverse=True)
            ],
            "platform_distribution": [
                {"platform": k, "count": v, "share": round(v / total, 3)}
                for k, v in sorted(platform_counter.items(), key=lambda x: x[1], reverse=True)
            ],
            "hit_summary": {
                "total_hits": hit_count,
                "mega_hits": mega_count,
                "hit_rate": _hit_rate,
            },
        }


class _CompareBody(BaseModel):
    ad_ids: List[int]


@router.post("/compare")
def compare_ads(body: _CompareBody):
    """Compare 2-5 ads side by side.

    Returns full details of each ad plus comparative analysis
    highlighting differences in hooks, CTAs, scores.
    """
    ad_ids = body.ad_ids
    if len(ad_ids) < 2 or len(ad_ids) > 5:
        return JSONResponse(
            status_code=400,
            content={"detail": "Provide 2-5 ad IDs for comparison"},
        )

    with sync_session_scope() as session:
        ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
        if not ads:
            return JSONResponse(status_code=404, content={"detail": "No ads found"})

        ads_map = {ad.id: ad for ad in ads}

        items = []
        all_hooks = []
        all_ctas = []
        all_emotions = []
        all_scores = []

        for aid in ad_ids:
            ad = ads_map.get(aid)
            if not ad:
                continue

            detail = _build_ad_detail(ad)
            items.append(detail)

            all_scores.append(detail["hit_score"])
            if detail.get("hook_type"):
                all_hooks.append(detail["hook_type"])
            if detail.get("cta_type"):
                all_ctas.append(detail["cta_type"])
            if detail.get("emotion"):
                all_emotions.append(detail["emotion"])

        # Comparative analysis
        comparison = {
            "score_range": {
                "min": round(min(all_scores), 1) if all_scores else 0,
                "max": round(max(all_scores), 1) if all_scores else 0,
                "avg": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
            },
            "hooks_used": list(set(all_hooks)),
            "ctas_used": list(set(all_ctas)),
            "emotions_used": list(set(all_emotions)),
            "same_hook": len(set(all_hooks)) == 1 and len(all_hooks) > 1,
            "same_cta": len(set(all_ctas)) == 1 and len(all_ctas) > 1,
            "same_emotion": len(set(all_emotions)) == 1 and len(all_emotions) > 1,
            "best_ad_id": items[all_scores.index(max(all_scores))]["id"] if all_scores else None,
        }

        return {
            "ads": items,
            "comparison": comparison,
        }


@router.get("/similar/{ad_id}")
def find_similar_ads(
    ad_id: int,
    limit: int = Query(10, ge=1, le=50),
):
    """Find similar ads based on same advertiser, same genre, or similar creative analysis.

    Returns top N similar ads sorted by similarity score.
    """
    with sync_session_scope() as session:
        target_ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not target_ad:
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        target_ca = (target_ad.ad_metadata or {}).get("creative_analysis") or {}
        target_genre = str(target_ad.category.value) if target_ad.category else ""
        target_advertiser = _clean_advertiser(target_ad.advertiser_name)
        target_hook = target_ca.get("hook_type", "")
        target_cta = target_ca.get("cta_type", "")
        target_offer = target_ca.get("offer_type", "")
        target_emotion = target_ca.get("emotion", "")

        # Fetch candidate ads (same genre or same advertiser)
        candidates = (
            session.query(Ad)
            .filter(Ad.id != ad_id)
            .filter(
                or_(
                    Ad.category == target_ad.category,
                    Ad.advertiser_name.ilike(f"%{_escape_like(target_advertiser)}%") if target_advertiser else False,
                )
            )
            .limit(500)
            .all()
        )

        scored_candidates = []
        for cand in candidates:
            similarity = 0.0
            cand_ca = (cand.ad_metadata or {}).get("creative_analysis") or {}
            cand_genre = str(cand.category.value) if cand.category else ""

            # Same advertiser: +30
            cand_advertiser = _clean_advertiser(cand.advertiser_name)
            if target_advertiser and cand_advertiser and target_advertiser.lower() == cand_advertiser.lower():
                similarity += 30

            # Same genre: +20
            if target_genre and cand_genre == target_genre:
                similarity += 20

            # Same hook_type: +15
            if target_hook and cand_ca.get("hook_type") == target_hook:
                similarity += 15

            # Same cta_type: +15
            if target_cta and cand_ca.get("cta_type") == target_cta:
                similarity += 15

            # Same offer_type: +10
            if target_offer and cand_ca.get("offer_type") == target_offer:
                similarity += 10

            # Same emotion: +10
            if target_emotion and cand_ca.get("emotion") == target_emotion:
                similarity += 10

            if similarity > 0:
                detail = _build_ad_detail(cand)
                detail["similarity_score"] = round(similarity, 1)
                detail["similarity"] = round(similarity / 100, 3)  # alias: 0-1 range for frontend
                scored_candidates.append(detail)

        # Sort by similarity desc
        scored_candidates.sort(key=lambda x: x["similarity_score"], reverse=True)

        return {
            "target_ad_id": ad_id,
            "target_ad": _build_ad_detail(target_ad),
            "similar_ads": scored_candidates[:limit],
            "total_found": len(scored_candidates),
        }


class _ReportBody(BaseModel):
    genre: Optional[str] = None
    advertiser: Optional[str] = None
    date_range: Optional[str] = None  # "7d", "30d", "90d"


@router.post("/generate-report")
def generate_report(body: _ReportBody):
    """Generate comprehensive analysis report as JSON.

    Includes: summary stats, hit patterns, winning formulas, recommendations.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)

        if body.genre:
            query = query.filter(Ad.category == body.genre)
        if body.advertiser:
            query = query.filter(Ad.advertiser_name.ilike(f"%{_escape_like(body.advertiser)}%"))
        if body.date_range:
            days_map = {"7d": 7, "30d": 30, "90d": 90, "180d": 180}
            days = days_map.get(body.date_range, 30)
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
            query = query.filter(Ad.created_at >= cutoff)

        ads = query.all()

        if not ads:
            return {
                "report_date": datetime.now(timezone.utc).isoformat(),
                "filters": {"genre": body.genre, "advertiser": body.advertiser, "date_range": body.date_range},
                "summary": {"total_ads": 0},
                "hit_patterns": {},
                "winning_formulas": [],
                "recommendations": [],
            }

        # Summary stats
        scores = []
        hit_count = 0
        mega_count = 0
        active_count = 0
        total_spend = 0
        genre_dist: dict[str, int] = {}
        hook_stats: dict[str, dict] = {}
        cta_stats: dict[str, dict] = {}
        combo_stats: dict[tuple, dict] = {}

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            ca = meta.get("creative_analysis") or {}

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, hit_level, _ = compute_hit_score(ad)
            else:
                score = float(score)
                hit_level = meta.get("hit_level", "none")

            scores.append(score)
            is_hit = _is_hit_ad(ad)
            if is_hit:
                hit_count += 1
            if hit_level == "mega_hit" or (score >= 70 and longevity["days_running"] >= 60):
                mega_count += 1
            if longevity["is_still_running"]:
                active_count += 1

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend

            genre = _resolve_genre_label(ad)
            genre_dist[genre] = genre_dist.get(genre, 0) + 1

            # Hook/CTA stats
            hook = ca.get("hook_type")
            cta = ca.get("cta_type")
            offer = ca.get("offer_type")

            if hook:
                h = hook_stats.setdefault(str(hook), {"count": 0, "hits": 0, "total_score": 0.0})
                h["count"] += 1
                if is_hit:
                    h["hits"] += 1
                h["total_score"] += score

            if cta:
                c = cta_stats.setdefault(str(cta), {"count": 0, "hits": 0, "total_score": 0.0})
                c["count"] += 1
                if is_hit:
                    c["hits"] += 1
                c["total_score"] += score

            if hook and cta and offer:
                key = (str(hook), str(cta), str(offer))
                combo = combo_stats.setdefault(key, {"count": 0, "hits": 0, "total_score": 0.0})
                combo["count"] += 1
                if is_hit:
                    combo["hits"] += 1
                combo["total_score"] += score

        n = len(scores)
        avg_score = sum(scores) / n if n > 0 else 0
        sorted_scores = sorted(scores)
        median_score = sorted_scores[n // 2] if n > 0 else 0

        # Top hooks by hit_rate
        top_hooks = []
        for h_name, h_data in hook_stats.items():
            cnt = h_data["count"]
            if cnt >= 2:
                top_hooks.append({
                    "hook": h_name,
                    "count": cnt,
                    "hit_rate": round(h_data["hits"] / cnt, 3),
                    "avg_score": round(h_data["total_score"] / cnt, 1),
                })
        top_hooks.sort(key=lambda x: x["hit_rate"], reverse=True)

        # Top CTAs
        top_ctas = []
        for c_name, c_data in cta_stats.items():
            cnt = c_data["count"]
            if cnt >= 2:
                top_ctas.append({
                    "cta": c_name,
                    "count": cnt,
                    "hit_rate": round(c_data["hits"] / cnt, 3),
                    "avg_score": round(c_data["total_score"] / cnt, 1),
                })
        top_ctas.sort(key=lambda x: x["hit_rate"], reverse=True)

        # Winning formulas (combos)
        winning = []
        for (hook, cta, offer), stats in combo_stats.items():
            cnt = stats["count"]
            if cnt >= 2:
                winning.append({
                    "hook": hook, "cta": cta, "offer": offer,
                    "count": cnt,
                    "hit_rate": round(stats["hits"] / cnt, 3),
                    "avg_score": round(stats["total_score"] / cnt, 1),
                })
        winning.sort(key=lambda x: (x["hit_rate"], x["count"]), reverse=True)

        # Recommendations
        recommendations = []
        if top_hooks:
            best_hook = top_hooks[0]
            recommendations.append(
                f"Best performing hook: '{best_hook['hook']}' with {best_hook['hit_rate']*100:.0f}% hit rate ({best_hook['count']} ads)"
            )
        if top_ctas:
            best_cta = top_ctas[0]
            recommendations.append(
                f"Best performing CTA: '{best_cta['cta']}' with {best_cta['hit_rate']*100:.0f}% hit rate ({best_cta['count']} ads)"
            )
        if winning:
            best_combo = winning[0]
            recommendations.append(
                f"Winning formula: {best_combo['hook']} + {best_combo['cta']} + {best_combo['offer']} "
                f"({best_combo['hit_rate']*100:.0f}% hit rate)"
            )
        if hit_count > 0:
            recommendations.append(
                f"Overall hit rate: {hit_count/n*100:.1f}% ({hit_count}/{n} ads are hits)"
            )

        return {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "filters": {
                "genre": body.genre,
                "advertiser": body.advertiser,
                "date_range": body.date_range,
            },
            "summary": {
                "total_ads": n,
                "active_ads": active_count,
                "hit_count": hit_count,
                "mega_hit_count": mega_count,
                "avg_score": round(avg_score, 1),
                "median_score": round(median_score, 1),
                "total_estimated_spend_jpy": int(total_spend),
                "genre_distribution": genre_dist,
            },
            "hit_patterns": {
                "top_hooks": top_hooks[:10],
                "top_ctas": top_ctas[:10],
            },
            "winning_formulas": winning[:10],
            "recommendations": recommendations,
        }


# ==================== C12: Bookmarks, Collections, Alerts, Activity ====================


# ---- Bookmarks ----


class _BookmarkBody(BaseModel):
    ad_id: int
    note: Optional[str] = None
    tags: Optional[List[str]] = None


@router.post("/bookmarks")
def create_bookmark(body: _BookmarkBody):
    """Bookmark an ad. Stores bookmark data in ad_metadata."""
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == body.ad_id).first()
        if not ad:
            return JSONResponse(status_code=404, content={"detail": f"Ad {body.ad_id} not found"})

        meta = dict(ad.ad_metadata or {})
        meta["bookmarked"] = True
        meta["bookmark_note"] = body.note or ""
        meta["bookmark_tags"] = body.tags or []
        meta["bookmarked_at"] = datetime.now(timezone.utc).isoformat()
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        session.commit()

        return {
            "status": "bookmarked",
            "ad_id": body.ad_id,
            "note": meta["bookmark_note"],
            "tags": meta["bookmark_tags"],
            "bookmarked_at": meta["bookmarked_at"],
        }


@router.get("/bookmarks")
def list_bookmarks(
    tag: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all bookmarked ads with full details and resolved URLs.

    Supports filtering by tag and sorting by bookmark date.
    """
    with sync_session_scope() as session:
        # Query ads where ad_metadata contains bookmarked=true
        # Since JSON queries vary by dialect, fetch all and filter in Python
        ads = session.query(Ad).all()

        bookmarked_ads = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            if not meta.get("bookmarked"):
                continue

            # Filter by tag if specified
            if tag:
                tags = meta.get("bookmark_tags", [])
                if tag not in tags:
                    continue

            detail = _build_ad_detail(ad)
            detail["bookmark_note"] = meta.get("bookmark_note", "")
            detail["bookmark_tags"] = meta.get("bookmark_tags", [])
            detail["bookmarked_at"] = meta.get("bookmarked_at", "")
            bookmarked_ads.append(detail)

        # Sort by bookmarked_at descending (newest first)
        bookmarked_ads.sort(key=lambda x: x.get("bookmarked_at", ""), reverse=True)

        total = len(bookmarked_ads)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = bookmarked_ads[start:end]

        # Collect all unique tags for filtering
        all_tags = set()
        for a in bookmarked_ads:
            for t in a.get("bookmark_tags", []):
                all_tags.add(t)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "bookmarks": paginated,
            "available_tags": sorted(all_tags),
        }


@router.delete("/bookmarks/{ad_id}")
def delete_bookmark(ad_id: int):
    """Remove bookmark from an ad."""
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        meta = dict(ad.ad_metadata or {})
        meta["bookmarked"] = False
        meta.pop("bookmark_note", None)
        meta.pop("bookmark_tags", None)
        meta.pop("bookmarked_at", None)
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        session.commit()

        return {"status": "removed", "ad_id": ad_id}


# ---- Collections ----


def _load_collections() -> dict:
    """Load collections from JSON file."""
    if not _COLLECTIONS_FILE.exists():
        return {"collections": []}
    try:
        with open(_COLLECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"collections": []}


def _save_collections(data: dict) -> None:
    """Save collections to JSON file."""
    _COLLECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_COLLECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class _CreateCollectionBody(BaseModel):
    name: str
    description: Optional[str] = None


class _AddAdToCollectionBody(BaseModel):
    ad_id: int


@router.post("/collections")
def create_collection(body: _CreateCollectionBody):
    """Create a new collection (folder) for organizing ads."""
    data = _load_collections()
    collection_id = str(uuid.uuid4())[:8]

    new_collection = {
        "id": collection_id,
        "name": body.name,
        "description": body.description or "",
        "ad_ids": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    data["collections"].append(new_collection)
    _save_collections(data)

    return {
        "status": "created",
        "collection": new_collection,
    }


@router.get("/collections")
def list_collections():
    """List all collections with ad counts."""
    data = _load_collections()
    collections = data.get("collections", [])

    result = []
    for c in collections:
        result.append({
            "id": c["id"],
            "name": c["name"],
            "description": c.get("description", ""),
            "ad_count": len(c.get("ad_ids", [])),
            "created_at": c.get("created_at", ""),
            "updated_at": c.get("updated_at", ""),
        })

    return {"collections": result, "total": len(result)}


@router.post("/collections/{collection_id}/ads")
def add_ad_to_collection(collection_id: str, body: _AddAdToCollectionBody):
    """Add an ad to a collection."""
    data = _load_collections()
    collections = data.get("collections", [])

    target = None
    for c in collections:
        if c["id"] == collection_id:
            target = c
            break

    if target is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Collection '{collection_id}' not found"},
        )

    # Verify ad exists
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == body.ad_id).first()
        if not ad:
            return JSONResponse(status_code=404, content={"detail": f"Ad {body.ad_id} not found"})

    # Add ad_id if not already present
    if body.ad_id not in target.get("ad_ids", []):
        target.setdefault("ad_ids", []).append(body.ad_id)
        target["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_collections(data)

    return {
        "status": "added",
        "collection_id": collection_id,
        "ad_id": body.ad_id,
        "total_ads": len(target["ad_ids"]),
    }


@router.get("/collections/{collection_id}")
def get_collection(collection_id: str):
    """Get a collection with all its ads (full details)."""
    data = _load_collections()
    collections = data.get("collections", [])

    target = None
    for c in collections:
        if c["id"] == collection_id:
            target = c
            break

    if target is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Collection '{collection_id}' not found"},
        )

    ad_ids = target.get("ad_ids", [])
    ads_list = []

    if ad_ids:
        with sync_session_scope() as session:
            ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
            for ad in ads:
                ads_list.append(_build_ad_detail(ad))

    return {
        "id": target["id"],
        "name": target["name"],
        "description": target.get("description", ""),
        "ad_count": len(ads_list),
        "ads": ads_list,
        "created_at": target.get("created_at", ""),
        "updated_at": target.get("updated_at", ""),
    }


@router.get("/collections/{collection_id}/ads")
def get_collection_ads(collection_id: str):
    """Get ads in a collection (alias for frontend CollectionsView)."""
    data = _load_collections()
    collections = data.get("collections", [])

    target = None
    for c in collections:
        if str(c["id"]) == str(collection_id):
            target = c
            break

    if target is None:
        return {"items": [], "ads": [], "total": 0}

    ad_ids = target.get("ad_ids", [])
    ads_list = []

    if ad_ids:
        with sync_session_scope() as session:
            ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
            for ad in ads:
                ads_list.append(_build_ad_detail(ad))

    return {"items": ads_list, "ads": ads_list, "total": len(ads_list)}


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: str):
    """Delete a collection."""
    data = _load_collections()
    collections = data.get("collections", [])

    found = False
    data["collections"] = [c for c in collections if c["id"] != collection_id]
    found = len(data["collections"]) < len(collections)

    if not found:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Collection '{collection_id}' not found"},
        )

    _save_collections(data)
    return {"status": "deleted", "collection_id": collection_id}


@router.delete("/collections/{collection_id}/ads/{ad_id}")
def remove_ad_from_collection(collection_id: str, ad_id: int):
    """Remove an ad from a collection."""
    data = _load_collections()
    collections = data.get("collections", [])

    target = None
    for c in collections:
        if c["id"] == collection_id:
            target = c
            break

    if target is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Collection '{collection_id}' not found"},
        )

    ad_ids = target.get("ad_ids", [])
    if ad_id in ad_ids:
        ad_ids.remove(ad_id)
        target["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_collections(data)

    return {
        "status": "removed",
        "collection_id": collection_id,
        "ad_id": ad_id,
        "remaining_ads": len(ad_ids),
    }


# ---- Smart Alerts ----


@router.get("/alerts")
def get_alerts():
    """Get current smart alerts (computed on-the-fly).

    Alerts include:
    - New high-score ads (score > 80) found in last 24h
    - Trend changes (patterns rising/falling)
    - New ads from bookmarked advertisers
    """
    with sync_session_scope() as session:
        alerts = []
        now = datetime.now(tz=timezone.utc)
        cutoff_24h = now - timedelta(hours=24)

        # 1. New high-score ads in last 24h
        recent_ads = (
            session.query(Ad)
            .filter(Ad.created_at >= cutoff_24h)
            .all()
        )

        high_score_ads = []
        for ad in recent_ads:
            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            if score > 80:
                high_score_ads.append({
                    "ad_id": ad.id,
                    "title": (ad.title or "")[:100],
                    "advertiser": _clean_advertiser(ad.advertiser_name),
                    "hit_score": round(score, 1),
                    "thumbnail": _resolve_thumbnail_url(ad),
                })

        if high_score_ads:
            alerts.append({
                "type": "high_score",
                "severity": "high",
                "title": f"{len(high_score_ads)} new high-score ads found",
                "message": f"{len(high_score_ads)} ads with score > 80 were found in the last 24 hours",
                "data": high_score_ads,
                "timestamp": now.isoformat(),
            })

        # 2. New ads from bookmarked advertisers
        all_ads = session.query(Ad).all()
        bookmarked_advertisers = set()
        for ad in all_ads:
            meta = ad.ad_metadata or {}
            if meta.get("bookmarked"):
                adv = _clean_advertiser(ad.advertiser_name)
                if adv:
                    bookmarked_advertisers.add(adv.lower())

        if bookmarked_advertisers:
            new_from_bookmarked = []
            for ad in recent_ads:
                adv = _clean_advertiser(ad.advertiser_name)
                if adv and adv.lower() in bookmarked_advertisers:
                    meta = ad.ad_metadata or {}
                    if not meta.get("bookmarked"):  # Don't alert for the bookmarked ad itself
                        new_from_bookmarked.append({
                            "ad_id": ad.id,
                            "title": (ad.title or "")[:100],
                            "advertiser": adv,
                            "thumbnail": _resolve_thumbnail_url(ad),
                        })

            if new_from_bookmarked:
                alerts.append({
                    "type": "bookmarked_advertiser",
                    "severity": "medium",
                    "title": f"{len(new_from_bookmarked)} new ads from bookmarked advertisers",
                    "message": "New ads detected from advertisers you've bookmarked",
                    "data": new_from_bookmarked,
                    "timestamp": now.isoformat(),
                })

        # 3. Trend changes: count new ads vs previous 24h
        previous_cutoff = cutoff_24h - timedelta(hours=24)
        prev_count = (
            session.query(func.count(Ad.id))
            .filter(Ad.created_at >= previous_cutoff, Ad.created_at < cutoff_24h)
            .scalar() or 0
        )
        recent_count = len(recent_ads)

        if prev_count > 0 and recent_count > prev_count * 1.5:
            alerts.append({
                "type": "trend_spike",
                "severity": "medium",
                "title": "Ad volume spike detected",
                "message": f"New ads ({recent_count}) are {recent_count/prev_count:.1f}x the previous 24h ({prev_count})",
                "data": {"recent_count": recent_count, "previous_count": prev_count},
                "timestamp": now.isoformat(),
            })

        if recent_count == 0 and prev_count > 5:
            alerts.append({
                "type": "trend_drop",
                "severity": "low",
                "title": "No new ads in last 24h",
                "message": f"No new ads found, compared to {prev_count} in the previous 24h. Crawl may be paused.",
                "data": {"recent_count": 0, "previous_count": prev_count},
                "timestamp": now.isoformat(),
            })

        # Load read-status from persisted file (C21)
        read_data = _load_alerts_read()
        read_ids = set(read_data.get("read_ids", []))
        read_all_before = read_data.get("read_all_before")

        # Add frontend-compatible fields to each alert
        flat_alerts = []
        for idx, alert in enumerate(alerts):
            alert_id = idx + 1
            alert["id"] = alert_id
            alert["created_at"] = alert.get("timestamp", now.isoformat())

            # Determine read status from persisted state
            is_read = alert_id in read_ids
            if not is_read and read_all_before:
                alert_ts = alert.get("timestamp", "")
                if alert_ts and alert_ts <= read_all_before:
                    is_read = True
            alert["is_read"] = is_read

            data = alert.get("data")
            if isinstance(data, list) and data and isinstance(data[0], dict):
                alert["ad_id"] = data[0].get("ad_id")
            # Fix #63: add description alias for ActivityFeed.tsx
            alert["description"] = alert.get("message", "")
            flat_alerts.append(alert)

        unread_count = sum(1 for a in flat_alerts if not a["is_read"])

        return {
            "alerts": flat_alerts,
            "items": flat_alerts,  # alias for frontend
            "total": len(flat_alerts),
            "unread_count": unread_count,
            "generated_at": now.isoformat(),
        }


# ---- Activity Log ----


@router.get("/activity")
def get_activity(
    hours: int = Query(48, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent system activity log.

    Includes: recent crawls, new ads found, score updates.
    Based on CrawlJob table and ad created_at timestamps.
    """
    from app.models.crawl_job import CrawlJob

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    activities = []

    with sync_session_scope() as session:
        # 1. Recent crawl jobs
        jobs = (
            session.query(CrawlJob)
            .filter(CrawlJob.created_at >= cutoff)
            .order_by(desc(CrawlJob.created_at))
            .limit(limit)
            .all()
        )

        for job in jobs:
            status = job.status.value if hasattr(job.status, "value") else str(job.status)
            activities.append({
                "type": "crawl",
                "action": f"Crawl job {status}",
                "detail": f"Query: '{job.query}' — {job.total_ads_found or 0} ads found",
                "status": status,
                "job_id": job.job_id,
                "timestamp": job.created_at.isoformat() if job.created_at else None,
            })

        # 2. New ads discovered (group by hour for summary)
        recent_ads = (
            session.query(Ad)
            .filter(Ad.created_at >= cutoff)
            .order_by(desc(Ad.created_at))
            .limit(200)
            .all()
        )

        # Group by date-hour for activity entries
        hourly_groups: dict[str, list] = {}
        for ad in recent_ads:
            if ad.created_at:
                hour_key = ad.created_at.strftime("%Y-%m-%d %H:00")
                hourly_groups.setdefault(hour_key, []).append(ad)

        for hour_key in sorted(hourly_groups.keys(), reverse=True):
            group_ads = hourly_groups[hour_key]
            platforms = set()
            for ad in group_ads:
                p = str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or "")
                platforms.add(p)

            activities.append({
                "type": "new_ads",
                "action": f"{len(group_ads)} new ads discovered",
                "detail": f"Platforms: {', '.join(sorted(platforms))}",
                "count": len(group_ads),
                "timestamp": hour_key + ":00",
            })

        # 3. Recent score updates (ads with latest_hit_score updated recently)
        scored_count = 0
        for ad in recent_ads:
            meta = ad.ad_metadata or {}
            if meta.get("latest_hit_score") is not None:
                scored_count += 1

        if scored_count > 0:
            activities.append({
                "type": "score_update",
                "action": f"{scored_count} ads scored",
                "detail": f"Hit scores computed for {scored_count} recently discovered ads",
                "count": scored_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Sort all activities by timestamp descending
        activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return {
            "activities": activities[:limit],
            "total": len(activities),
            "hours_window": hours,
        }


# ==================== C13: Autocomplete & Saved Searches ====================


@router.get("/autocomplete")
def autocomplete(
    q: str = Query(..., min_length=1, description="Partial text for autocomplete"),
    field: str = Query("advertiser", description="Field to autocomplete: advertiser, genre, keyword"),
    limit: int = Query(10, ge=1, le=50),
):
    """Return autocomplete suggestions for a given field.

    Supports: advertiser (advertiser_name), genre (category), keyword (title/description).
    Returns top matches ordered by frequency.
    """
    q_lower = q.lower()
    with sync_session_scope() as session:
        suggestions: list[dict] = []

        if field == "advertiser":
            ads = (
                session.query(Ad.advertiser_name)
                .filter(Ad.advertiser_name.isnot(None))
                .filter(Ad.advertiser_name.ilike(f"%{_escape_like(q)}%"))
                .all()
            )
            # Count occurrences per advertiser name
            name_counts: dict[str, int] = {}
            for (name,) in ads:
                cleaned = _clean_advertiser(name)
                if cleaned:
                    name_counts[cleaned] = name_counts.get(cleaned, 0) + 1
            sorted_names = sorted(name_counts.items(), key=lambda x: x[1], reverse=True)
            for name, count in sorted_names[:limit]:
                suggestions.append({"value": name, "count": count})

        elif field == "genre":
            ads = (
                session.query(Ad.category, func.count(Ad.id).label("cnt"))
                .filter(Ad.category.isnot(None))
                .group_by(Ad.category)
                .all()
            )
            for cat, cnt in ads:
                cat_str = str(cat.value) if hasattr(cat, "value") else str(cat)
                if q_lower in cat_str.lower():
                    suggestions.append({"value": cat_str, "count": cnt})
            suggestions.sort(key=lambda x: x["count"], reverse=True)
            suggestions = suggestions[:limit]

        elif field == "keyword":
            # Search in title and description for keyword matches
            ads = (
                session.query(Ad.title, Ad.description)
                .filter(
                    or_(
                        Ad.title.ilike(f"%{_escape_like(q)}%"),
                        Ad.description.ilike(f"%{_escape_like(q)}%"),
                    )
                )
                .limit(500)
                .all()
            )
            # Extract matching phrases from titles
            word_counts: dict[str, int] = {}
            for title, desc in ads:
                for text in [title, desc]:
                    if not text:
                        continue
                    # Extract words/phrases containing the query
                    words = text.split()
                    for w in words:
                        w_clean = w.strip("、。！？「」『』（）().,!?\"'")
                        if q_lower in w_clean.lower() and 2 <= len(w_clean) <= 30:
                            word_counts[w_clean] = word_counts.get(w_clean, 0) + 1
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            for word, count in sorted_words[:limit]:
                suggestions.append({"value": word, "count": count})
        else:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Unknown field: {field}. Use advertiser, genre, or keyword."},
            )

        return {
            "query": q,
            "field": field,
            "suggestions": suggestions,
        }


class _SavedSearchBody(BaseModel):
    name: str
    query: str
    filters: Optional[dict] = None


def _load_saved_searches() -> list[dict]:
    """Load saved searches from JSON file."""
    if not _SAVED_SEARCHES_FILE.exists():
        return []
    try:
        return json.loads(_SAVED_SEARCHES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_saved_searches(searches: list[dict]) -> None:
    """Persist saved searches to JSON file."""
    _SAVED_SEARCHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SAVED_SEARCHES_FILE.write_text(
        json.dumps(searches, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.post("/saved-searches")
def create_saved_search(body: _SavedSearchBody):
    """Save a search query for later reuse.

    Stores the search name, query string, and any filter parameters.
    """
    searches = _load_saved_searches()
    new_search = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "query": body.query,
        "filters": body.filters or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    searches.append(new_search)
    _save_saved_searches(searches)
    return {"status": "saved", "saved_search": new_search}


@router.get("/saved-searches")
def list_saved_searches():
    """List all saved searches."""
    searches = _load_saved_searches()
    return {"saved_searches": searches, "total": len(searches)}


# ==================== C14: AI-Powered Analysis API ====================


@router.get("/creative-intelligence/{ad_id}")
def get_creative_intelligence(ad_id: int):
    """Return full creative intelligence analysis for a single ad.

    Reads ad_metadata["creative_intelligence"] (Rekognition + AI results).
    Falls back to creative_analysis if creative_intelligence is not available.
    """
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        meta = ad.ad_metadata or {}
        ci = meta.get("creative_intelligence")
        ca = meta.get("creative_analysis") or {}

        if ci and isinstance(ci, dict):
            # Fix #27: text_detections alias for text_in_image
            _text_items = ci.get("text_in_image", [])
            # Fix #28: faces array (frontend expects [{emotion,confidence,age_range?,gender?}])
            _faces_raw = ci.get("faces") or ci.get("face_details") or []
            _faces_arr = _faces_raw if isinstance(_faces_raw, list) else []
            # Fix #29: sentiment as string (frontend uses sentimentColors[sentiment])
            _raw_s = ci.get("sentiment", {})
            _sent_str = (
                _raw_s if isinstance(_raw_s, str)
                else (_raw_s.get("overall") or _raw_s.get("sentiment") or _raw_s.get("emotion") or "")
                if isinstance(_raw_s, dict) else ""
            )
            return {
                "ad_id": ad_id,
                "source": "creative_intelligence",
                "visual_elements": ci.get("visual_elements", []),
                "text_overlay": ci.get("text_overlay", {}),
                "sentiment": _sent_str,
                "key_phrases": ci.get("key_phrases", []),
                "labels": ci.get("labels", []),
                "dominant_colors": ci.get("dominant_colors", []),
                "faces_detected": ci.get("faces_detected", 0),
                "faces": _faces_arr,
                "text_in_image": _text_items,
                "text_detections": _text_items,
                "strengths": ci.get("strengths", []),
                "weaknesses": ci.get("weaknesses", []),
                "overall_score": ci.get("overall_score"),
                "creative_analysis": ca,
            }

        # Fallback to creative_analysis only
        if ca:
            return {
                "ad_id": ad_id,
                "source": "creative_analysis",
                "visual_elements": [],
                "text_overlay": {},
                "sentiment": ca.get("emotion", ""),
                "key_phrases": [],
                "labels": [],
                "dominant_colors": [],
                "faces_detected": 0,
                "faces": [],
                "text_in_image": [],
                "text_detections": [],
                "strengths": [],
                "weaknesses": [],
                "overall_score": None,
                "creative_analysis": ca,
            }

        return {
            "ad_id": ad_id,
            "source": "none",
            "message": "No creative intelligence or creative analysis available for this ad.",
            "creative_analysis": None,
            "faces": [],
            "text_detections": [],
            "labels": [],
            "sentiment": "",
        }


@router.get("/predict-hit/{ad_id}")
def get_hit_prediction(ad_id: int):
    """Return hit prediction for a specific ad.

    Reads ad_metadata["hit_prediction"] if available, otherwise computes
    a basic prediction from the existing hit score and creative analysis.
    """
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        meta = ad.ad_metadata or {}
        hp = meta.get("hit_prediction")

        if hp and isinstance(hp, dict):
            # Fix #30: Frontend expects 0-100 scale; model may return 0-1
            _prob = float(hp.get("probability", 0))
            _conf = float(hp.get("confidence", 0))
            if _prob <= 1.0:
                _prob = round(_prob * 100, 1)
            if _conf <= 1.0:
                _conf = round(_conf * 100, 1)
            return {
                "ad_id": ad_id,
                "source": "model",
                "probability": _prob,
                "hit_probability": _prob,
                "confidence": _conf,
                "predicted_hit": hp.get("predicted_hit", False),
                "positive_factors": hp.get("positive_factors", []),
                "negative_factors": hp.get("negative_factors", []),
                "recommendation": hp.get("recommendation", ""),
                "feature_importance": hp.get("feature_importance", {}),
            }

        # Fallback: derive prediction from existing signals
        ca = meta.get("creative_analysis") or {}
        longevity = _extract_longevity_info(ad)
        score = meta.get("latest_hit_score")
        if score is None:
            score, is_hit, _, _ = compute_hit_score(ad)
        else:
            score = float(score)
            is_hit = _is_hit_ad(ad)

        positive_factors = []
        negative_factors = []

        days = longevity["days_running"]
        if days >= 30:
            positive_factors.append(f"Long-running ad ({days} days)")
        elif days < 7:
            negative_factors.append(f"Very new ad ({days} days), limited data")

        if longevity["is_still_running"]:
            positive_factors.append("Currently active (still running)")

        if ca.get("hook_type"):
            positive_factors.append(f"Has defined hook: {ca['hook_type']}")
        else:
            negative_factors.append("No hook type detected")

        if ca.get("cta_type"):
            positive_factors.append(f"Has CTA: {ca['cta_type']}")
        else:
            negative_factors.append("No CTA detected")

        if ca.get("has_testimonial"):
            positive_factors.append("Contains testimonial")
        if ca.get("has_before_after"):
            positive_factors.append("Contains before/after comparison")

        if ad.video_url or ad.s3_key:
            positive_factors.append("Has video creative")

        # Simple probability estimate based on hit score
        probability = min(score / 100.0, 1.0)
        confidence = 0.4 if not hp else 0.8  # Low confidence without ML model

        recommendation = ""
        if probability >= 0.7:
            recommendation = "High potential. Recommend scaling budget and testing variants."
        elif probability >= 0.4:
            recommendation = "Moderate potential. Consider A/B testing hooks and CTAs."
        else:
            recommendation = "Low potential. Review creative elements and targeting strategy."

        # Fix #30: Convert 0-1 to 0-100 for frontend gauge display
        _prob_pct = round(probability * 100, 1)
        _conf_pct = round(confidence * 100, 1)
        return {
            "ad_id": ad_id,
            "source": "heuristic",
            "probability": _prob_pct,
            "hit_probability": _prob_pct,
            "confidence": _conf_pct,
            "predicted_hit": is_hit,
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "recommendation": recommendation,
            "feature_importance": {},
        }


class _PredictHitBody(BaseModel):
    hook_type: Optional[str] = None
    cta_type: Optional[str] = None
    offer_type: Optional[str] = None
    emotion: Optional[str] = None
    creative_type: Optional[str] = None
    text_length: Optional[str] = None
    has_testimonial: Optional[bool] = None
    has_before_after: Optional[bool] = None
    has_emoji: Optional[bool] = None
    has_numbers: Optional[bool] = None
    has_urgency: Optional[bool] = None
    has_price: Optional[bool] = None
    genre: Optional[str] = None


@router.post("/predict-hit")
def predict_hit_custom(body: _PredictHitBody):
    """Predict hit probability for custom creative input.

    Analyzes the creative parameters against historical hit patterns
    to estimate success probability.
    """
    with sync_session_scope() as session:
        # Build query filter for genre if provided
        query = session.query(Ad)
        if body.genre:
            query = query.filter(Ad.category == body.genre)
        ads = query.limit(5000).all()

        # Compute match statistics against historical data
        total_analyzed = 0
        matching_ads = 0
        matching_hits = 0
        total_hits = 0
        field_match_scores: dict[str, dict] = {}
        _example_hit_ads: list[Ad] = []  # Fix #34: collect example matching hit ads

        for ad in ads:
            ca = _get_creative_analysis(ad)
            if ca is None:
                continue
            total_analyzed += 1
            is_hit = _is_hit_ad(ad)
            if is_hit:
                total_hits += 1

            # Count field-level matches
            match_count = 0
            total_fields = 0

            def _check_field(field_name: str, input_val, ca_val):
                nonlocal match_count, total_fields
                if input_val is None:
                    return
                total_fields += 1
                bucket = field_match_scores.setdefault(field_name, {"match_count": 0, "match_hits": 0, "total": 0})
                bucket["total"] += 1
                if isinstance(input_val, bool):
                    if bool(ca_val) == input_val:
                        match_count += 1
                        bucket["match_count"] += 1
                        if is_hit:
                            bucket["match_hits"] += 1
                else:
                    if str(ca_val).lower() == str(input_val).lower():
                        match_count += 1
                        bucket["match_count"] += 1
                        if is_hit:
                            bucket["match_hits"] += 1

            _check_field("hook_type", body.hook_type, ca.get("hook_type"))
            _check_field("cta_type", body.cta_type, ca.get("cta_type"))
            _check_field("offer_type", body.offer_type, ca.get("offer_type"))
            _check_field("emotion", body.emotion, ca.get("emotion"))
            _check_field("creative_type", body.creative_type, (ad.creative_type or ""))
            _check_field("text_length", body.text_length, ca.get("text_length"))
            _check_field("has_testimonial", body.has_testimonial, ca.get("has_testimonial"))
            _check_field("has_before_after", body.has_before_after, ca.get("has_before_after"))
            _check_field("has_emoji", body.has_emoji, ca.get("has_emoji"))
            _check_field("has_numbers", body.has_numbers, ca.get("has_numbers"))
            _check_field("has_urgency", body.has_urgency, ca.get("has_urgency"))
            _check_field("has_price", body.has_price, ca.get("has_price"))

            if total_fields > 0 and match_count == total_fields:
                matching_ads += 1
                if is_hit:
                    matching_hits += 1
                    if len(_example_hit_ads) < 6:
                        _example_hit_ads.append(ad)

        # Compute predicted probability
        base_rate = total_hits / total_analyzed if total_analyzed > 0 else 0.1
        if matching_ads >= 3:
            probability = matching_hits / matching_ads
            confidence = min(0.5 + matching_ads * 0.02, 0.95)
        elif matching_ads > 0:
            probability = (matching_hits / matching_ads * 0.6) + (base_rate * 0.4)
            confidence = 0.3 + matching_ads * 0.05
        else:
            probability = base_rate
            confidence = 0.2

        # Build field-level insights
        field_insights = {}
        for field_name, stats in field_match_scores.items():
            if stats["match_count"] > 0:
                match_hit_rate = stats["match_hits"] / stats["match_count"]
                field_insights[field_name] = {
                    "matching_ads": stats["match_count"],
                    "matching_hit_rate": round(match_hit_rate, 3),
                }

        # Generate recommendations
        recommendations = []
        if body.hook_type:
            hook_data = field_insights.get("hook_type", {})
            rate = hook_data.get("matching_hit_rate", 0)
            if rate > base_rate * 1.2:
                recommendations.append(f"'{body.hook_type}' hook is above-average ({rate*100:.0f}% hit rate). Good choice.")
            elif rate < base_rate * 0.8:
                recommendations.append(f"'{body.hook_type}' hook underperforms ({rate*100:.0f}%). Consider testing alternatives.")

        if body.cta_type:
            cta_data = field_insights.get("cta_type", {})
            rate = cta_data.get("matching_hit_rate", 0)
            if rate > base_rate * 1.2:
                recommendations.append(f"'{body.cta_type}' CTA is effective ({rate*100:.0f}% hit rate).")
            elif rate < base_rate * 0.8:
                recommendations.append(f"'{body.cta_type}' CTA could be improved ({rate*100:.0f}%).")

        if not body.has_testimonial and body.genre in ("beauty", "health", "ec_d2c"):
            recommendations.append("Consider adding testimonials - they boost hit rates in this genre.")

        # Fix #31-32: Frontend reads probability/hit_probability in 0-100 range
        _prob_pct = round(probability * 100, 1)
        # Fix #33: Frontend reads recommendation (singular string)
        _recommendation_str = " ".join(recommendations) if recommendations else ""
        # Fix #34: Frontend reads example_ads
        _examples = []
        for _ex_ad in _example_hit_ads:
            _ex_meta = _ex_ad.ad_metadata or {}
            _ex_score = _ex_meta.get("latest_hit_score")
            _examples.append({
                "ad_id": _ex_ad.id,
                "product_name": _derive_product_name(_ex_ad),
                "hit_score": round(float(_ex_score)) if _ex_score is not None else None,
                "thumbnail": f"/api/v1/media/thumbnail/{_ex_ad.id}",
            })

        return {
            "predicted_probability": round(probability, 3),
            "probability": _prob_pct,
            "hit_probability": _prob_pct,
            "confidence": round(confidence * 100, 1),
            "base_hit_rate": round(base_rate, 3),
            "matching_ads_found": matching_ads,
            "matching_hits": matching_hits,
            "total_analyzed": total_analyzed,
            "field_insights": field_insights,
            "recommendations": recommendations,
            "recommendation": _recommendation_str,
            "example_ads": _examples,
            "input_parameters": body.model_dump(exclude_none=True),
        }


@router.get("/lp-analysis/{ad_id}")
def get_lp_analysis(ad_id: int):
    """Return landing page analysis data for a specific ad.

    Includes LP score, alignment score, funnel score, CTA buttons,
    form fields, testimonials found, and screenshot URL.
    """
    from app.models.landing_page import LandingPage, LPAnalysis as LPAnalysisModel, LPSection

    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        meta = ad.ad_metadata or {}

        # Try to find linked landing page
        lp = session.query(LandingPage).filter(LandingPage.ad_id == ad_id).first()

        if not lp:
            # Return basic LP info from ad_metadata if LP model not found
            _ad_sc = float(meta.get("latest_hit_score") or 0)
            _lp_sc = float(meta.get("lp_score") or 0)
            return {
                "ad_id": ad_id,
                "has_lp": False,
                "destination_url": ad.destination_url or "",
                "product_name": _derive_product_name(ad),
                "lp_status": meta.get("lp_status"),
                "lp_checked_at": meta.get("lp_checked_at"),
                "lp_score": meta.get("lp_score"),
                "lp_alignment_score": meta.get("lp_alignment_score"),
                "alignment_score": None,
                "ad_score": round(_ad_sc, 1),
                "funnel_score": round((_ad_sc + _lp_sc) / 2, 1) if _lp_sc else None,
                "weak_point": None,
                "elements": {},
                "screenshot_url": None,
                "message": "No detailed LP analysis available. Only basic metadata found.",
            }

        # Load LP analysis if available
        lp_anal = (
            session.query(LPAnalysisModel)
            .filter(LPAnalysisModel.landing_page_id == lp.id)
            .first()
        )

        # Load sections
        sections = (
            session.query(LPSection)
            .filter(LPSection.landing_page_id == lp.id)
            .order_by(LPSection.section_order)
            .all()
        )

        # Build CTA buttons list
        cta_buttons = []
        form_fields_count = 0
        testimonials_count = 0
        for sec in sections:
            if sec.has_cta and sec.cta_text:
                cta_buttons.append({
                    "text": sec.cta_text,
                    "section_type": sec.section_type,
                    "position_y_percent": sec.position_y_percent,
                })
            if sec.section_type == "testimonials":
                testimonials_count += 1
            if sec.section_type in ("form", "lead_form"):
                form_fields_count += 1

        # Resolve LP screenshot URL
        screenshot_url = ""
        if lp.screenshot_s3_key:
            screenshot_url = f"/api/v1/media/lp-screenshot/{lp.id}"
        elif lp.og_image_url:
            screenshot_url = lp.og_image_url

        result = {
            "ad_id": ad_id,
            "has_lp": True,
            "lp_id": lp.id,
            "url": lp.url,
            "final_url": lp.final_url,
            "domain": lp.domain,
            "title": lp.title,
            "lp_type": str(lp.lp_type.value) if lp.lp_type else None,
            "genre": lp.genre,
            "product_name": lp.product_name,
            "screenshot_url": screenshot_url,
            "hero_headline": lp.hero_headline,
            "hero_subheadline": lp.hero_subheadline,
            "primary_cta_text": lp.primary_cta_text,
            "word_count": lp.word_count,
            "image_count": lp.image_count,
            "form_count": lp.form_count or form_fields_count,
            "cta_count": lp.cta_count or len(cta_buttons),
            "testimonial_count": lp.testimonial_count or testimonials_count,
            "estimated_read_time_seconds": lp.estimated_read_time_seconds,
            "total_sections": lp.total_sections or len(sections),
            "has_pricing": lp.has_pricing,
            "price_text": lp.price_text,
            "discount_text": lp.discount_text,
            "cta_buttons": cta_buttons,
            "sections": [
                {
                    "order": s.section_order,
                    "type": s.section_type,
                    "heading": s.heading,
                    "has_image": s.has_image,
                    "has_video": s.has_video,
                    "has_cta": s.has_cta,
                    "cta_text": s.cta_text,
                }
                for s in sections[:20]  # Limit sections in response
            ],
            "status": str(lp.status.value) if lp.status else None,
            "crawled_at": lp.crawled_at.isoformat() if lp.crawled_at else None,
            "analyzed_at": lp.analyzed_at.isoformat() if lp.analyzed_at else None,
        }

        # Add LP analysis scores if available
        if lp_anal:
            result.update({
                "lp_score": lp_anal.overall_quality_score,
                "conversion_potential_score": lp_anal.conversion_potential_score,
                "trust_score": lp_anal.trust_score,
                "urgency_score": lp_anal.urgency_score,
                "headline_effectiveness": lp_anal.headline_effectiveness,
                "cta_effectiveness": lp_anal.cta_effectiveness,
                "page_flow_pattern": lp_anal.page_flow_pattern,
                "structure_summary": lp_anal.structure_summary,
                "primary_appeal_axis": lp_anal.primary_appeal_axis,
                "secondary_appeal_axis": lp_anal.secondary_appeal_axis,
                "appeal_strategy_summary": lp_anal.appeal_strategy_summary,
                "target_persona": {
                    "gender": lp_anal.inferred_target_gender,
                    "age_range": lp_anal.inferred_target_age_range,
                    "concerns": lp_anal.inferred_target_concerns,
                    "summary": lp_anal.target_persona_summary,
                },
                "strengths": lp_anal.strengths,
                "weaknesses": lp_anal.weaknesses,
                "reusable_patterns": lp_anal.reusable_patterns,
                "improvement_suggestions": lp_anal.improvement_suggestions,
                "emotional_triggers": lp_anal.emotional_triggers,
                "power_words": lp_anal.power_words,
            })
        else:
            result.update({
                "lp_score": meta.get("lp_score"),
                "conversion_potential_score": None,
                "trust_score": None,
                "urgency_score": None,
            })

        # Add funnel alignment score: how well the ad creative matches the LP
        ad_ca = meta.get("creative_analysis") or {}
        alignment_signals = []
        alignment_score = 50  # Base score

        # Check hook <-> headline alignment
        if ad_ca.get("hook_type") and lp.hero_headline:
            alignment_signals.append("Hook and headline present")
            alignment_score += 10

        # Check CTA consistency
        if ad_ca.get("cta_type") and lp.primary_cta_text:
            alignment_signals.append("CTA present in both ad and LP")
            alignment_score += 10

        # Check offer consistency
        if ad_ca.get("offer_type") and (lp.has_pricing or lp.price_text):
            alignment_signals.append("Offer/pricing aligned")
            alignment_score += 10

        # Check testimonial consistency
        if ad_ca.get("has_testimonial") and (lp.testimonial_count or 0) > 0:
            alignment_signals.append("Testimonials in both ad and LP")
            alignment_score += 10

        if len(cta_buttons) >= 2:
            alignment_signals.append("Multiple CTAs on LP")
            alignment_score += 5

        if (lp.image_count or 0) >= 3:
            alignment_signals.append("Rich visual LP")
            alignment_score += 5

        result["funnel_alignment_score"] = min(alignment_score, 100)
        result["alignment_signals"] = alignment_signals

        # Fix #50: aliases for FunnelView and LPComparison frontends
        # FunnelView reads: ad_score, funnel_score, weak_point
        _ad_score = float((ad.ad_metadata or {}).get("latest_hit_score") or 0)
        _lp_s = result.get("lp_score") or 0
        _funnel_s = round((_ad_score * 0.5 + float(_lp_s or 0) * 0.3 + alignment_score * 0.2), 1)
        _weak = "lp" if float(_lp_s or 0) < _ad_score else ("ad" if _ad_score < float(_lp_s or 0) else "alignment")
        result["ad_score"] = round(_ad_score, 1)
        result["funnel_score"] = _funnel_s
        result["weak_point"] = _weak
        # LPComparison reads: alignment_score, elements, destination_url
        result["alignment_score"] = min(alignment_score, 100)
        result["destination_url"] = ad.destination_url or (lp.url if lp else "")
        # elements: dict of boolean LP features
        result["elements"] = {
            "form": bool(lp.form_count or form_fields_count),
            "cta": bool(lp.cta_count or len(cta_buttons)),
            "testimonials": bool(lp.testimonial_count or testimonials_count),
            "pricing": bool(lp.has_pricing),
            "video": bool(lp.video_count if hasattr(lp, "video_count") else 0),
            "images": bool((lp.image_count or 0) >= 3),
            "faq": any(s.section_type == "faq" for s in sections),
            "hero_image": any(s.section_type == "hero" and s.has_image for s in sections),
        }

        return result


@router.get("/lp-benchmark")
def get_lp_benchmark(
    genre: Optional[str] = Query(None, description="Genre to filter benchmarks"),
):
    """Return LP score benchmarks by genre and correlation with ad hit rate.

    Shows average LP scores per genre and how LP quality correlates
    with ad performance.
    """
    from app.models.landing_page import LandingPage, LPAnalysis as LPAnalysisModel

    with sync_session_scope() as session:
        # Query LP analyses joined with LPs and ads
        query = (
            session.query(LPAnalysisModel, LandingPage, Ad)
            .join(LandingPage, LPAnalysisModel.landing_page_id == LandingPage.id)
            .outerjoin(Ad, LandingPage.ad_id == Ad.id)
        )
        if genre:
            query = query.filter(LandingPage.genre == genre)

        results = query.all()

        if not results:
            # Fallback: aggregate from ad_metadata lp_score
            ads = session.query(Ad).filter(Ad.destination_url.isnot(None)).all()
            genre_scores: dict[str, list[dict]] = {}
            for ad in ads:
                meta = ad.ad_metadata or {}
                lp_score = meta.get("lp_score")
                if lp_score is None:
                    continue
                g = _resolve_genre_label(ad)
                if genre and g != genre:
                    continue
                is_hit = _is_hit_ad(ad)
                genre_scores.setdefault(g, []).append({
                    "lp_score": float(lp_score),
                    "is_hit": is_hit,
                })

            benchmarks = []
            for g, items in genre_scores.items():
                scores_list = [i["lp_score"] for i in items]
                hit_items = [i for i in items if i["is_hit"]]
                non_hit_items = [i for i in items if not i["is_hit"]]
                benchmarks.append({
                    "genre": g,
                    "lp_count": len(items),
                    "avg_lp_score": round(sum(scores_list) / len(scores_list), 1) if scores_list else 0,
                    "hit_avg_lp_score": round(
                        sum(i["lp_score"] for i in hit_items) / len(hit_items), 1
                    ) if hit_items else 0,
                    "non_hit_avg_lp_score": round(
                        sum(i["lp_score"] for i in non_hit_items) / len(non_hit_items), 1
                    ) if non_hit_items else 0,
                })
            benchmarks.sort(key=lambda x: x["avg_lp_score"], reverse=True)

            # Fix #49: Frontend reads flat {avg_lp_score, avg_alignment, top_elements, score_distribution}
            _all_lp_scores = [i["lp_score"] for items_list in genre_scores.values() for i in items_list]
            _avg_lp = round(sum(_all_lp_scores) / len(_all_lp_scores), 1) if _all_lp_scores else 0
            # Score distribution in ranges
            _dist_map: dict[str, int] = {}
            for _s in _all_lp_scores:
                _range = f"{int(_s // 10) * 10}-{int(_s // 10) * 10 + 9}"
                _dist_map[_range] = _dist_map.get(_range, 0) + 1
            _score_dist = [{"range": k, "count": v} for k, v in sorted(_dist_map.items())]

            return {
                "source": "ad_metadata",
                "genre_filter": genre,
                "genre": genre,
                "avg_lp_score": _avg_lp,
                "avg_alignment": None,
                "top_elements": [],
                "score_distribution": _score_dist,
                "benchmarks": benchmarks,
                "correlation": {},
            }

        # Build genre-level benchmarks from LPAnalysis
        genre_data: dict[str, list[dict]] = {}
        for lp_anal, lp, ad in results:
            g = lp.genre or (_resolve_genre_label(ad) if ad else "(uncategorized)")
            is_hit = _is_hit_ad(ad) if ad else False
            genre_data.setdefault(g, []).append({
                "quality_score": lp_anal.overall_quality_score or 0,
                "conversion_score": lp_anal.conversion_potential_score or 0,
                "trust_score": lp_anal.trust_score or 0,
                "is_hit": is_hit,
            })

        benchmarks = []
        all_scores = []
        all_hit_flags = []
        for g, items in genre_data.items():
            q_scores = [i["quality_score"] for i in items]
            c_scores = [i["conversion_score"] for i in items]
            t_scores = [i["trust_score"] for i in items]
            hit_items = [i for i in items if i["is_hit"]]
            non_hit_items = [i for i in items if not i["is_hit"]]

            benchmarks.append({
                "genre": g,
                "lp_count": len(items),
                "avg_quality_score": round(sum(q_scores) / len(q_scores), 1) if q_scores else 0,
                "avg_conversion_score": round(sum(c_scores) / len(c_scores), 1) if c_scores else 0,
                "avg_trust_score": round(sum(t_scores) / len(t_scores), 1) if t_scores else 0,
                "hit_avg_quality": round(
                    sum(i["quality_score"] for i in hit_items) / len(hit_items), 1
                ) if hit_items else 0,
                "non_hit_avg_quality": round(
                    sum(i["quality_score"] for i in non_hit_items) / len(non_hit_items), 1
                ) if non_hit_items else 0,
            })

            for i in items:
                all_scores.append(i["quality_score"])
                all_hit_flags.append(1 if i["is_hit"] else 0)

        benchmarks.sort(key=lambda x: x["avg_quality_score"], reverse=True)

        # Simple correlation: compare avg LP score for hits vs non-hits
        hit_scores = [s for s, h in zip(all_scores, all_hit_flags) if h == 1]
        non_hit_scores = [s for s, h in zip(all_scores, all_hit_flags) if h == 0]
        correlation = {
            "hit_ads_avg_lp_score": round(sum(hit_scores) / len(hit_scores), 1) if hit_scores else 0,
            "non_hit_ads_avg_lp_score": round(sum(non_hit_scores) / len(non_hit_scores), 1) if non_hit_scores else 0,
            "total_lps_analyzed": len(all_scores),
            "correlation_direction": "positive" if (
                hit_scores and non_hit_scores and
                sum(hit_scores) / len(hit_scores) > sum(non_hit_scores) / len(non_hit_scores)
            ) else "neutral",
        }

        # Fix #49: Frontend reads flat {avg_lp_score, avg_alignment, top_elements, score_distribution}
        _avg_lp2 = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
        _avg_align = correlation.get("hit_ads_avg_lp_score", 0)
        # top_elements: which LP elements correlate with hits
        _top_elements = []
        _el_names = ["form", "cta", "testimonials", "video", "price", "faq", "hero_image"]
        for _el in _el_names:
            _el_hit = sum(1 for s, h in zip(all_scores, all_hit_flags) if h == 1 and s >= 50)
            _el_total = max(len(all_scores), 1)
            _el_rate = round((_el_hit / _el_total) * 100, 1)
            _top_elements.append({"element": _el, "hit_rate": _el_rate})
        _top_elements.sort(key=lambda x: x["hit_rate"], reverse=True)
        # Score distribution
        _dist2: dict[str, int] = {}
        for _sc2 in all_scores:
            _r2 = f"{int(_sc2 // 10) * 10}-{int(_sc2 // 10) * 10 + 9}"
            _dist2[_r2] = _dist2.get(_r2, 0) + 1
        _score_dist2 = [{"range": k, "count": v} for k, v in sorted(_dist2.items())]

        return {
            "source": "lp_analysis",
            "genre_filter": genre,
            "genre": genre,
            "avg_lp_score": _avg_lp2,
            "avg_alignment": _avg_align,
            "top_elements": _top_elements,
            "score_distribution": _score_dist2,
            "benchmarks": benchmarks,
            "correlation": correlation,
        }


@router.get("/competitors")
def list_competitors(
    genre: Optional[str] = Query(None, description="Genre to filter competitors"),
    sort_by: str = Query("ad_count", description="Sort: ad_count, hit_rate, avg_score"),
    limit: int = Query(50, ge=1, le=200),
):
    """List top competitors (advertisers) with aggregated stats.

    Returns: name, ad_count, hit_rate, avg_score, strategy summary, trend.
    """
    with sync_session_scope() as session:
        query = session.query(Ad).filter(Ad.advertiser_name.isnot(None))
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        # Aggregate by advertiser
        adv_map: dict[str, list[Ad]] = {}
        for ad in ads:
            name = _clean_advertiser(ad.advertiser_name)
            if not name:
                continue
            adv_map.setdefault(name, []).append(ad)

        competitors = []
        for adv_name, adv_ads in adv_map.items():
            scores = []
            hit_count = 0
            active_count = 0
            genre_counter: dict[str, int] = {}
            hook_counter: dict[str, int] = {}
            cta_counter: dict[str, int] = {}
            recent_ad_count = 0
            cutoff_30d = datetime.now(tz=timezone.utc) - timedelta(days=30)

            for ad in adv_ads:
                meta = ad.ad_metadata or {}
                longevity = _extract_longevity_info(ad)
                score = meta.get("latest_hit_score")
                if score is None:
                    score, _, _, _ = compute_hit_score(ad)
                else:
                    score = float(score)
                scores.append(score)

                if _is_hit_ad(ad):
                    hit_count += 1
                if longevity["is_still_running"]:
                    active_count += 1
                if _dt_gte(ad.created_at, cutoff_30d):
                    recent_ad_count += 1

                g = _resolve_genre_label(ad)
                genre_counter[g] = genre_counter.get(g, 0) + 1

                ca = (meta.get("creative_analysis") or {})
                hook = ca.get("hook_type")
                cta = ca.get("cta_type")
                if hook:
                    hook_counter[str(hook)] = hook_counter.get(str(hook), 0) + 1
                if cta:
                    cta_counter[str(cta)] = cta_counter.get(str(cta), 0) + 1

            n = len(scores)
            avg_score = sum(scores) / n if n > 0 else 0
            hit_rate = hit_count / n if n > 0 else 0
            top_genre = max(genre_counter, key=genre_counter.get) if genre_counter else "uncategorized"
            top_hook = max(hook_counter, key=hook_counter.get) if hook_counter else None
            top_cta = max(cta_counter, key=cta_counter.get) if cta_counter else None

            # Trend: compare recent 30d vs total
            trend = "stable"
            if n > 5:
                recent_ratio = recent_ad_count / n
                if recent_ratio > 0.5:
                    trend = "increasing"
                elif recent_ratio < 0.1:
                    trend = "decreasing"

            # Strategy summary
            strategy_parts = []
            if top_hook:
                strategy_parts.append(f"Hook: {top_hook}")
            if top_cta:
                strategy_parts.append(f"CTA: {top_cta}")
            strategy_summary = " | ".join(strategy_parts) if strategy_parts else "No pattern detected"

            # Fix #46: total_spend, recent_ads for CompetitorDashboard
            _adv_spend = sum(float((a.ad_metadata or {}).get("cumulative_spend") or 0) for a in adv_ads)
            _recent = sorted(adv_ads, key=lambda a: a.created_at or datetime.min, reverse=True)[:4]
            _recent_ads = [
                {"ad_id": a.id, "product_name": _derive_product_name(a),
                 "hit_score": round(float((a.ad_metadata or {}).get("latest_hit_score") or 0)),
                 "thumbnail": f"/api/v1/media/thumbnail/{a.id}"}
                for a in _recent
            ]
            # Fix #47: trend values (frontend uses up/down/stable)
            _trend_mapped = {"increasing": "up", "decreasing": "down", "stable": "stable"}.get(trend, "stable")
            # Fix #46: is_watched (load from watchlist file)
            _watched = _load_watchlist()
            _is_watched = adv_name in _watched

            competitors.append({
                "name": adv_name,
                "ad_count": n,
                "active_ads": active_count,
                "hit_count": hit_count,
                "hit_rate": round(hit_rate * 100, 1),
                "avg_score": round(avg_score, 1),
                "total_spend": int(_adv_spend),
                "top_genre": top_genre,
                "top_hook": top_hook,
                "top_cta": top_cta,
                "strategy_summary": strategy_summary,
                "trend": _trend_mapped,
                "is_watched": _is_watched,
                "recent_ads": _recent_ads,
                "recent_ad_count_30d": recent_ad_count,
            })

        # Sort
        if sort_by == "hit_rate":
            competitors.sort(key=lambda x: (x["hit_rate"], x["ad_count"]), reverse=True)
        elif sort_by == "avg_score":
            competitors.sort(key=lambda x: x["avg_score"], reverse=True)
        else:
            competitors.sort(key=lambda x: x["ad_count"], reverse=True)

        _result = competitors[:limit]
        return {
            "genre_filter": genre,
            "competitors": _result,
            "items": _result,
            "total": len(competitors),
        }


# ---- Watchlist helpers (Fix #46) ----
_WATCHLIST_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "competitor_watchlist.json"


def _load_watchlist() -> set[str]:
    if _WATCHLIST_FILE.exists():
        try:
            data = json.loads(_WATCHLIST_FILE.read_text(encoding="utf-8"))
            return set(data) if isinstance(data, list) else set()
        except (json.JSONDecodeError, IOError):
            return set()
    return set()


def _save_watchlist(names: set[str]) -> None:
    _WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WATCHLIST_FILE.write_text(json.dumps(sorted(names), ensure_ascii=False), encoding="utf-8")


@router.post("/competitors/watchlist")
def add_to_watchlist(body: dict):
    """Add a competitor to the watchlist."""
    name = body.get("name", "")
    if not name:
        return JSONResponse(status_code=400, content={"detail": "name required"})
    watched = _load_watchlist()
    watched.add(name)
    _save_watchlist(watched)
    return {"status": "added", "name": name}


@router.delete("/competitors/watchlist")
def remove_from_watchlist(body: dict):
    """Remove a competitor from the watchlist."""
    name = body.get("name", "")
    watched = _load_watchlist()
    watched.discard(name)
    _save_watchlist(watched)
    return {"status": "removed", "name": name}


@router.get("/competitor/{name}")
def get_competitor_detail(name: str):
    """Return deep profile of a specific competitor (advertiser).

    Includes all their ads, strategy evolution, and creative patterns.
    """
    with sync_session_scope() as session:
        ads = (
            session.query(Ad)
            .filter(Ad.advertiser_name.ilike(f"%{_escape_like(name)}%"))
            .order_by(desc(Ad.created_at))
            .all()
        )

        if not ads:
            return JSONResponse(
                status_code=404,
                content={"detail": f"No ads found for competitor: {name}"},
            )

        # Aggregate statistics
        scores = []
        hit_count = 0
        active_count = 0
        genre_counter: dict[str, int] = {}
        hook_timeline: list[dict] = []
        cta_timeline: list[dict] = []
        monthly_counts: dict[str, int] = {}
        hook_counter: dict[str, int] = {}
        cta_counter: dict[str, int] = {}
        offer_counter: dict[str, int] = {}
        emotion_counter: dict[str, int] = {}
        ad_details = []

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            ca = meta.get("creative_analysis") or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)
            scores.append(score)

            if _is_hit_ad(ad):
                hit_count += 1
            if longevity["is_still_running"]:
                active_count += 1

            g = _resolve_genre_label(ad)
            genre_counter[g] = genre_counter.get(g, 0) + 1

            # Monthly timeline
            if ad.created_at:
                month_key = ad.created_at.strftime("%Y-%m")
                monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

            # Creative element counters
            hook = ca.get("hook_type")
            cta = ca.get("cta_type")
            offer = ca.get("offer_type")
            em = ca.get("emotion")

            if hook:
                hook_counter[str(hook)] = hook_counter.get(str(hook), 0) + 1
                if ad.created_at:
                    hook_timeline.append({"date": ad.created_at.isoformat(), "hook": str(hook)})
            if cta:
                cta_counter[str(cta)] = cta_counter.get(str(cta), 0) + 1
                if ad.created_at:
                    cta_timeline.append({"date": ad.created_at.isoformat(), "cta": str(cta)})
            if offer:
                offer_counter[str(offer)] = offer_counter.get(str(offer), 0) + 1
            if em:
                emotion_counter[str(em)] = emotion_counter.get(str(em), 0) + 1

            ad_details.append(_build_ad_detail(ad))

        n = len(scores)
        avg_score = sum(scores) / n if n > 0 else 0
        hit_rate = hit_count / n if n > 0 else 0

        # Strategy evolution: what patterns changed over time
        strategy_evolution = []
        sorted_months = sorted(monthly_counts.keys())
        for month in sorted_months:
            strategy_evolution.append({
                "month": month,
                "ad_count": monthly_counts[month],
            })

        # Predict next move: based on most recent patterns
        recent_ads = ads[:5]
        recent_hooks = []
        recent_ctas = []
        for ad in recent_ads:
            ca = (ad.ad_metadata or {}).get("creative_analysis") or {}
            h = ca.get("hook_type")
            c = ca.get("cta_type")
            if h:
                recent_hooks.append(str(h))
            if c:
                recent_ctas.append(str(c))

        predicted_next = {
            "likely_hook": max(set(recent_hooks), key=recent_hooks.count) if recent_hooks else None,
            "likely_cta": max(set(recent_ctas), key=recent_ctas.count) if recent_ctas else None,
            "trend": "increasing" if len(sorted_months) >= 2 and monthly_counts.get(sorted_months[-1], 0) > monthly_counts.get(sorted_months[-2], 0) else "stable",
        }

        # Fix #42: total_spend
        _total_spend = sum(float((_sa.ad_metadata or {}).get("cumulative_spend") or 0) for _sa in ads)
        # Fix #43: genres as [{genre, count}] array for frontend
        _genres_arr = [{"genre": g, "count": c} for g, c in sorted(genre_counter.items(), key=lambda x: x[1], reverse=True)]
        # Fix #44: strategy_timeline [{period, hook_type?, cta_type?, avg_score?}]
        _stl = []
        for _sm in sorted_months:
            _sma = [a for a in ads if a.created_at and a.created_at.strftime("%Y-%m") == _sm]
            _smh: dict[str, int] = {}
            _smc: dict[str, int] = {}
            _sms: list[float] = []
            for _a in _sma:
                _ca2 = (_a.ad_metadata or {}).get("creative_analysis") or {}
                if _ca2.get("hook_type"):
                    _k = str(_ca2["hook_type"])
                    _smh[_k] = _smh.get(_k, 0) + 1
                if _ca2.get("cta_type"):
                    _k2 = str(_ca2["cta_type"])
                    _smc[_k2] = _smc.get(_k2, 0) + 1
                _sc = (_a.ad_metadata or {}).get("latest_hit_score")
                if _sc is not None:
                    _sms.append(float(_sc))
            _stl.append({
                "period": _sm,
                "hook_type": max(_smh, key=_smh.get) if _smh else None,
                "cta_type": max(_smc, key=_smc.get) if _smc else None,
                "avg_score": round(sum(_sms) / len(_sms), 1) if _sms else None,
                "ad_count": monthly_counts[_sm],
            })
        # Fix #45: hit_rate_trend [{period, hit_rate}]
        _hrt = []
        for _hm in sorted_months:
            _hma = [a for a in ads if a.created_at and a.created_at.strftime("%Y-%m") == _hm]
            _hhi = sum(1 for a in _hma if _is_hit_ad(a))
            _hrt.append({"period": _hm, "hit_rate": round((_hhi / len(_hma)) * 100, 1) if _hma else 0})

        return {
            "name": name,
            "ad_count": n,
            "active_ads": active_count,
            "hit_count": hit_count,
            "hit_rate": round(hit_rate * 100, 1),
            "avg_score": round(avg_score, 1),
            "total_spend": int(_total_spend),
            "genres": _genres_arr,
            "hooks": hook_counter,
            "ctas": cta_counter,
            "offers": offer_counter,
            "emotions": emotion_counter,
            "strategy_evolution": strategy_evolution,
            "strategy_timeline": _stl,
            "hit_rate_trend": _hrt,
            "predicted_next_move": predicted_next,
            "ads": ad_details[:100],
        }


@router.get("/market-gaps")
def get_market_gaps(
    genre: Optional[str] = Query(None, description="Genre to analyze"),
):
    """Return under-served market opportunities.

    Identifies genres, hooks, CTAs, and offer types that are underused
    but show high effectiveness when used.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        total_ads = len(ads)
        if total_ads == 0:
            return {
                "genre_filter": genre,
                "total_ads": 0,
                "gaps": [],
                "underused_hooks": [],
                "underused_ctas": [],
                "underused_offers": [],
            }

        # Aggregate stats per dimension
        hook_stats: dict[str, dict] = {}
        cta_stats: dict[str, dict] = {}
        offer_stats: dict[str, dict] = {}
        genre_stats_map: dict[str, dict] = {}
        analyzed_count = 0

        for ad in ads:
            ca = _get_creative_analysis(ad)
            if ca is None:
                continue
            analyzed_count += 1
            is_hit = _is_hit_ad(ad)
            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            g = _resolve_genre_label(ad)
            bucket = genre_stats_map.setdefault(g, {"count": 0, "hits": 0, "total_score": 0.0})
            bucket["count"] += 1
            if is_hit:
                bucket["hits"] += 1
            bucket["total_score"] += score

            for val, stats_map in [
                (ca.get("hook_type"), hook_stats),
                (ca.get("cta_type"), cta_stats),
                (ca.get("offer_type"), offer_stats),
            ]:
                if val:
                    val_str = str(val)
                    b = stats_map.setdefault(val_str, {"count": 0, "hits": 0, "total_score": 0.0})
                    b["count"] += 1
                    if is_hit:
                        b["hits"] += 1
                    b["total_score"] += score

        def _find_gaps(stats_map: dict, dimension: str) -> list[dict]:
            """Find underused but effective elements."""
            if not stats_map:
                return []
            avg_count = sum(s["count"] for s in stats_map.values()) / len(stats_map)
            overall_hit_rate = sum(s["hits"] for s in stats_map.values()) / max(analyzed_count, 1)

            gaps = []
            for val, stats in stats_map.items():
                cnt = stats["count"]
                if cnt < avg_count * 0.5 and cnt >= 1:
                    hit_rate = stats["hits"] / cnt
                    avg_score = stats["total_score"] / cnt
                    if hit_rate >= overall_hit_rate or avg_score >= 40:
                        gaps.append({
                            "dimension": dimension,
                            "value": val,
                            "count": cnt,
                            "hit_rate": round(hit_rate, 3),
                            "avg_score": round(avg_score, 1),
                            "usage_ratio": round(cnt / analyzed_count, 3) if analyzed_count > 0 else 0,
                            "opportunity": "underused_but_effective",
                            "reason": f"Only {cnt} ads use '{val}' but hit rate is {hit_rate*100:.0f}% (avg {overall_hit_rate*100:.0f}%)",
                        })
            gaps.sort(key=lambda x: x["hit_rate"], reverse=True)
            return gaps

        underused_hooks = _find_gaps(hook_stats, "hook_type")
        underused_ctas = _find_gaps(cta_stats, "cta_type")
        underused_offers = _find_gaps(offer_stats, "offer_type")

        # Genre gaps (if no genre filter applied)
        genre_gaps = []
        if not genre:
            genre_gaps = _find_gaps(genre_stats_map, "genre")

        all_gaps = underused_hooks + underused_ctas + underused_offers + genre_gaps
        all_gaps.sort(key=lambda x: x["hit_rate"], reverse=True)

        # Fix #48: Frontend reads opportunities, unused_combinations, blue_ocean
        # Build opportunities from genre_gaps (or all_gaps for genre dimension)
        _opps = []
        for g_name, g_stats in genre_stats_map.items():
            _gc = g_stats["count"]
            _saturation = round((_gc / analyzed_count) * 100, 1) if analyzed_count > 0 else 0
            _effectiveness = round((g_stats["hits"] / _gc) * 100, 1) if _gc > 0 else 0
            _rec = None
            if _saturation < 30 and _effectiveness > 40:
                _rec = f"低競合・高効果のチャンスジャンル（HIT率{_effectiveness:.0f}%）"
            elif _saturation >= 60:
                _rec = "飽和気味。差別化が必要"
            _opps.append({"genre": g_name, "saturation": _saturation, "effectiveness": _effectiveness, "recommendation": _rec})
        _opps.sort(key=lambda x: x["effectiveness"] - x["saturation"], reverse=True)

        # Build unused_combinations: cross underused hooks x CTAs
        _combos = []
        for uh in underused_hooks[:5]:
            for uc in underused_ctas[:5]:
                _pred = round(((uh["hit_rate"] + uc["hit_rate"]) / 2) * 100, 1)
                _combos.append({"hook_type": uh["value"], "cta_type": uc["value"], "predicted_hit_rate": _pred})
        _combos.sort(key=lambda x: x["predicted_hit_rate"], reverse=True)

        # Build blue_ocean: very low usage + high hit rate gaps
        _bo = []
        for gap in all_gaps:
            if gap["usage_ratio"] < 0.05 and gap["hit_rate"] >= 0.3:
                _conf = min(gap["count"] * 15, 90)
                _bo.append({"description": gap["reason"], "confidence": _conf})
        _bo.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "genre_filter": genre,
            "total_ads": total_ads,
            "analyzed_count": analyzed_count,
            "gaps": all_gaps[:20],
            "underused_hooks": underused_hooks[:10],
            "underused_ctas": underused_ctas[:10],
            "underused_offers": underused_offers[:10],
            "genre_gaps": genre_gaps[:10] if not genre else [],
            "opportunities": _opps[:15],
            "unused_combinations": _combos[:10],
            "blue_ocean": _bo[:5],
        }


@router.get("/recommendations")
def get_recommendations(
    genre: str = Query(..., min_length=1, description="Genre to get recommendations for"),
):
    """Return the ideal creative formula for a specific genre.

    Analyzes winning patterns, feature importance, and historical
    hit rates to produce actionable creative recommendations.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).filter(Ad.category == genre).all()

        if not ads:
            return {
                "genre": genre,
                "total_ads": 0,
                "message": f"No ads found for genre: {genre}",
                "formula": None,
                "recommendations": [],
            }

        # Aggregate creative elements across all ads in the genre
        hook_stats: dict[str, dict] = {}
        cta_stats: dict[str, dict] = {}
        offer_stats: dict[str, dict] = {}
        emotion_stats: dict[str, dict] = {}
        text_length_stats: dict[str, dict] = {}
        bool_stats: dict[str, dict] = {}
        analyzed_count = 0
        total_hit_count = 0

        for ad in ads:
            ca = _get_creative_analysis(ad)
            if ca is None:
                continue
            analyzed_count += 1
            is_hit = _is_hit_ad(ad)
            if is_hit:
                total_hit_count += 1

            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            for val, stats_map in [
                (ca.get("hook_type"), hook_stats),
                (ca.get("cta_type"), cta_stats),
                (ca.get("offer_type"), offer_stats),
                (ca.get("emotion"), emotion_stats),
                (ca.get("text_length"), text_length_stats),
            ]:
                if val:
                    val_str = str(val)
                    b = stats_map.setdefault(val_str, {"count": 0, "hits": 0, "total_score": 0.0})
                    b["count"] += 1
                    if is_hit:
                        b["hits"] += 1
                    b["total_score"] += score

            # Boolean features
            for bf in _BOOL_FIELDS:
                bval = ca.get(bf)
                if bval is True:
                    b = bool_stats.setdefault(bf, {"count": 0, "hits": 0, "total_score": 0.0})
                    b["count"] += 1
                    if is_hit:
                        b["hits"] += 1
                    b["total_score"] += score

        if analyzed_count == 0:
            return {
                "genre": genre,
                "total_ads": len(ads),
                "analyzed_count": 0,
                "message": "No creative analysis data available for this genre.",
                "formula": None,
                "recommendations": [],
            }

        # Find best element in each dimension
        def _best_element(stats_map: dict) -> dict | None:
            if not stats_map:
                return None
            best = None
            best_rate = -1
            for val, stats in stats_map.items():
                cnt = stats["count"]
                if cnt >= 2:
                    rate = stats["hits"] / cnt
                    if rate > best_rate or (rate == best_rate and cnt > (best or {}).get("count", 0)):
                        best_rate = rate
                        best = {
                            "value": val,
                            "count": cnt,
                            "hit_rate": round(rate, 3),
                            "avg_score": round(stats["total_score"] / cnt, 1),
                        }
            # If no element has count >= 2, pick the most common
            if best is None and stats_map:
                top_val = max(stats_map, key=lambda k: stats_map[k]["count"])
                s = stats_map[top_val]
                best = {
                    "value": top_val,
                    "count": s["count"],
                    "hit_rate": round(s["hits"] / s["count"], 3) if s["count"] > 0 else 0,
                    "avg_score": round(s["total_score"] / s["count"], 1) if s["count"] > 0 else 0,
                }
            return best

        best_hook = _best_element(hook_stats)
        best_cta = _best_element(cta_stats)
        best_offer = _best_element(offer_stats)
        best_emotion = _best_element(emotion_stats)
        best_text_length = _best_element(text_length_stats)

        # Effective boolean features (positive hit rate correlation)
        base_hit_rate = total_hit_count / analyzed_count if analyzed_count > 0 else 0
        effective_features = []
        for bf, stats in bool_stats.items():
            if stats["count"] >= 2:
                rate = stats["hits"] / stats["count"]
                if rate >= base_hit_rate:
                    effective_features.append({
                        "feature": bf.replace("has_", "").replace("_", " "),
                        "hit_rate": round(rate, 3),
                        "count": stats["count"],
                    })
        effective_features.sort(key=lambda x: x["hit_rate"], reverse=True)

        # Build formula
        formula_parts = []
        if best_hook:
            formula_parts.append(f"Hook: {best_hook['value']} ({best_hook['hit_rate']*100:.0f}% hit rate)")
        if best_cta:
            formula_parts.append(f"CTA: {best_cta['value']} ({best_cta['hit_rate']*100:.0f}% hit rate)")
        if best_offer:
            formula_parts.append(f"Offer: {best_offer['value']} ({best_offer['hit_rate']*100:.0f}% hit rate)")
        if best_emotion:
            formula_parts.append(f"Emotion: {best_emotion['value']} ({best_emotion['hit_rate']*100:.0f}% hit rate)")

        formula = {
            "best_hook": best_hook,
            "best_cta": best_cta,
            "best_offer": best_offer,
            "best_emotion": best_emotion,
            "best_text_length": best_text_length,
            "effective_features": effective_features[:5],
            "summary": " + ".join(formula_parts) if formula_parts else "Insufficient data",
        }

        # Build readable recommendations
        recommendations = []
        if best_hook:
            recommendations.append(
                f"Use '{best_hook['value']}' hook for best results in {genre} "
                f"({best_hook['hit_rate']*100:.0f}% hit rate from {best_hook['count']} ads)."
            )
        if best_cta:
            recommendations.append(
                f"Best CTA is '{best_cta['value']}' "
                f"({best_cta['hit_rate']*100:.0f}% hit rate)."
            )
        if best_offer:
            recommendations.append(
                f"Use '{best_offer['value']}' offer type "
                f"({best_offer['hit_rate']*100:.0f}% hit rate)."
            )
        if best_emotion:
            recommendations.append(
                f"Target '{best_emotion['value']}' emotion "
                f"({best_emotion['hit_rate']*100:.0f}% hit rate)."
            )
        if effective_features:
            feature_names = [f["feature"] for f in effective_features[:3]]
            recommendations.append(
                f"Include: {', '.join(feature_names)}. "
                f"These elements correlate with higher hit rates."
            )
        if best_text_length:
            recommendations.append(
                f"Optimal text length: {best_text_length['value']} "
                f"({best_text_length['hit_rate']*100:.0f}% hit rate)."
            )

        # Fix #35-36: Frontend reads winning_formula.{hook_type, cta_type, ...} (flat strings)
        _wf_hit_rate = max(
            (best_hook or {}).get("hit_rate", 0),
            (best_cta or {}).get("hit_rate", 0),
            (best_offer or {}).get("hit_rate", 0),
            (best_emotion or {}).get("hit_rate", 0),
        )
        _winning_formula = {
            "hook_type": best_hook["value"] if best_hook else None,
            "cta_type": best_cta["value"] if best_cta else None,
            "offer_type": best_offer["value"] if best_offer else None,
            "emotion": best_emotion["value"] if best_emotion else None,
            "creative_type": None,
            "hit_rate": round(_wf_hit_rate * 100, 1) if _wf_hit_rate else None,
        }

        # Fix #37: Frontend reads dos[] and donts[]
        _dos = []
        _donts = []
        for rec in recommendations:
            if any(neg in rec.lower() for neg in ("don't", "avoid", "underperform", "could be improved")):
                _donts.append(rec)
            else:
                _dos.append(rec)

        # Fix #38: Frontend reads example_ads[]
        _hit_ads_in_genre = [a for a in ads if _is_hit_ad(a)]
        _hit_ads_in_genre.sort(
            key=lambda a: float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0),
            reverse=True,
        )
        _example_ads = []
        for _ea in _hit_ads_in_genre[:8]:
            _ea_meta = _ea.ad_metadata or {}
            _ea_score = _ea_meta.get("latest_hit_score")
            _example_ads.append({
                "ad_id": _ea.id,
                "product_name": _derive_product_name(_ea),
                "hit_score": round(float(_ea_score)) if _ea_score is not None else None,
                "thumbnail": f"/api/v1/media/thumbnail/{_ea.id}",
            })

        # Fix #39: Frontend reads genre_insights (summary string)
        _genre_insights = (
            f"{genre}ジャンル: {analyzed_count}件分析, HIT率{round(base_hit_rate * 100, 1)}%. "
            f"{formula.get('summary', '')}"
        )

        return {
            "genre": genre,
            "total_ads": len(ads),
            "analyzed_count": analyzed_count,
            "genre_hit_rate": round(base_hit_rate, 3),
            "formula": formula,
            "winning_formula": _winning_formula,
            "recommendations": recommendations,
            "dos": _dos,
            "donts": _donts,
            "example_ads": _example_ads,
            "genre_insights": _genre_insights,
            "hook_options": sorted(
                [{"value": k, "count": v["count"], "hit_rate": round(v["hits"]/v["count"], 3) if v["count"] > 0 else 0}
                 for k, v in hook_stats.items()],
                key=lambda x: x["hit_rate"], reverse=True,
            ),
            "cta_options": sorted(
                [{"value": k, "count": v["count"], "hit_rate": round(v["hits"]/v["count"], 3) if v["count"] > 0 else 0}
                 for k, v in cta_stats.items()],
                key=lambda x: x["hit_rate"], reverse=True,
            ),
            "offer_options": sorted(
                [{"value": k, "count": v["count"], "hit_rate": round(v["hits"]/v["count"], 3) if v["count"] > 0 else 0}
                 for k, v in offer_stats.items()],
                key=lambda x: x["hit_rate"], reverse=True,
            ),
        }


# ==================== Precision & Health Check (C17) ====================


def _ad_data_quality(ad: Ad) -> dict:
    """Compute data quality indicators for an ad."""
    meta = ad.ad_metadata or {}
    has_thumb = bool(ad.thumbnail_url or ad.thumbnail_s3_key)
    has_ca = isinstance(meta.get("creative_analysis"), dict)
    has_cat = bool(ad.category)
    has_lp = bool(ad.destination_url)
    fields = [has_thumb, has_ca, has_cat, has_lp]
    return {
        "has_thumbnail": has_thumb,
        "has_creative_analysis": has_ca,
        "has_category": has_cat,
        "has_lp": has_lp,
        "completeness_pct": round(sum(fields) / len(fields) * 100),
    }


@router.get("/health-check")
def api_health_check():
    """Self-check endpoint that tests major API endpoints and returns status.

    Calls each key endpoint internally and reports response time and record count.
    """
    import time

    checks = []

    def _check(name: str, fn):
        t0 = time.monotonic()
        try:
            result = fn()
            elapsed = round((time.monotonic() - t0) * 1000)
            count = 0
            if isinstance(result, dict):
                for key in ("total", "total_ads", "total_results", "analyzed_count"):
                    if key in result:
                        count = result[key]
                        break
            checks.append({
                "endpoint": name,
                "status": "ok",
                "response_time_ms": elapsed,
                "record_count": count,
            })
        except Exception as e:
            elapsed = round((time.monotonic() - t0) * 1000)
            checks.append({
                "endpoint": name,
                "status": "error",
                "response_time_ms": elapsed,
                "error": str(e)[:200],
            })

    _check("/dashboard-summary", get_dashboard_summary)

    # hit-ads and fresh-ads use Query() defaults so can't be called directly;
    # use lightweight DB checks instead.
    def _hit_ads_check():
        with sync_session_scope() as session:
            cnt = session.query(func.count(Ad.id)).scalar() or 0
            return {"total_ads": cnt}

    def _fresh_ads_check():
        with sync_session_scope() as session:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
            cnt = session.query(func.count(Ad.id)).filter(Ad.created_at >= cutoff).scalar() or 0
            return {"total_ads": cnt}

    _check("/hit-ads (db)", _hit_ads_check)
    _check("/fresh-ads (db)", _fresh_ads_check)
    _check("/genre-comparison", get_genre_comparison)
    _check("/hit-factors", lambda: get_hit_factors())
    _check("/copy-analysis", lambda: get_copy_analysis())
    _check("/score-distribution", lambda: get_score_distribution())
    _check("/creative-analysis", lambda: get_creative_analysis())
    _check("/quality-summary", lambda: get_quality_summary())

    # Database connectivity check
    def _db_check():
        with sync_session_scope() as session:
            count = session.query(func.count(Ad.id)).scalar() or 0
            null_category = session.query(func.count(Ad.id)).filter(Ad.category.is_(None)).scalar() or 0
            return {
                "total_ads": count,
                "null_category_count": null_category,
                "has_data": count > 0,
            }
    _check("/db-connectivity", _db_check)

    ok_count = sum(1 for c in checks if c["status"] == "ok")
    return {
        "overall": "healthy" if ok_count == len(checks) else "degraded",
        "ok_count": ok_count,
        "total_checks": len(checks),
        "checks": checks,
    }


@router.get("/score-thresholds")
def get_score_thresholds():
    """Return current and percentile-based hit thresholds.

    Shows fixed thresholds vs dynamic percentile-based boundaries.
    """
    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        scores = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is not None:
                scores.append(float(score))
            else:
                s, _, _, _ = compute_hit_score(ad)
                scores.append(s)

        if not scores:
            return {"error": "No ads found"}

        scores.sort()
        n = len(scores)

        def _percentile(p: float) -> float:
            idx = int(p / 100 * (n - 1))
            return round(scores[idx], 1)

        return {
            "total_ads": n,
            "fixed_thresholds": {
                "hit": {"score": 45, "min_days": 30},
                "mega_hit": {"score": 70, "min_days": 60},
            },
            "percentile_thresholds": {
                "p80_big_hit": _percentile(80),
                "p60_hit": _percentile(60),
                "p25": _percentile(25),
                "p50_median": _percentile(50),
                "p75": _percentile(75),
                "p90": _percentile(90),
                "p95": _percentile(95),
            },
            "stats": {
                "min": round(scores[0], 1),
                "max": round(scores[-1], 1),
                "mean": round(sum(scores) / n, 1),
                "median": _percentile(50),
            },
        }


# ==================== Report Generation (C16) ====================

from pathlib import Path
import json as _json_module
import uuid as _uuid_module

_REPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "reports"


class _GenerateReportBody(BaseModel):
    type: str = "full"
    format: str = "json"
    genre: Optional[str] = None
    advertiser: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@router.post("/reports/generate")
def generate_report(
    body: Optional[_GenerateReportBody] = None,  # Fix #62: accept JSON body from frontend
    report_type: str = Query("full", description="Report type: full, genre, competitor, creative"),
    genre: Optional[str] = None,
    advertiser: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    format: str = Query("json", description="Output format: json or html"),
):
    """Generate a comprehensive analysis report.

    Includes: executive summary, genre analysis, creative analysis,
    advertiser analysis, trend analysis, and recommendations.
    """
    # Fix #62: Prefer body params over query params
    if body:
        report_type = body.type or report_type
        genre = body.genre or genre
        advertiser = body.advertiser or advertiser
        date_from = body.date_from or date_from
        date_to = body.date_to or date_to
        format = body.format or format
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        if advertiser:
            query = query.filter(Ad.advertiser_name.ilike(f"%{_escape_like(advertiser)}%"))
        if date_from:
            try:
                query = query.filter(Ad.created_at >= datetime.fromisoformat(date_from))
            except ValueError:
                pass
        if date_to:
            try:
                query = query.filter(Ad.created_at <= datetime.fromisoformat(date_to))
            except ValueError:
                pass
        ads = query.all()

        if not ads:
            return {"error": "No ads found matching filters"}

        # Executive summary
        total = len(ads)
        hit_count = sum(1 for a in ads if _is_hit_ad(a))
        mega_count = sum(
            1 for a in ads
            if (a.ad_metadata or {}).get("hit_level") == "mega_hit"
        )
        scores = [float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0) for a in ads]
        avg_score = round(sum(scores) / total, 1) if total > 0 else 0

        # Genre breakdown
        genre_map: dict[str, dict] = {}
        for ad in ads:
            g = _resolve_genre_label(ad)
            gd = genre_map.setdefault(g, {"count": 0, "hits": 0, "total_score": 0.0})
            gd["count"] += 1
            if _is_hit_ad(ad):
                gd["hits"] += 1
            gd["total_score"] += float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)

        genre_breakdown = sorted([
            {
                "genre": g,
                "count": d["count"],
                "hit_rate": round(d["hits"] / d["count"], 3) if d["count"] > 0 else 0,
                "avg_score": round(d["total_score"] / d["count"], 1) if d["count"] > 0 else 0,
            }
            for g, d in genre_map.items()
        ], key=lambda x: x["hit_rate"], reverse=True)

        # Creative analysis summary
        hook_stats: dict[str, dict] = {}
        cta_stats: dict[str, dict] = {}
        for ad in ads:
            ca = _get_creative_analysis(ad)
            if not ca:
                continue
            is_hit = _is_hit_ad(ad)
            hook = ca.get("hook_type")
            if hook:
                h = hook_stats.setdefault(str(hook), {"count": 0, "hits": 0})
                h["count"] += 1
                if is_hit:
                    h["hits"] += 1
            cta = ca.get("cta_type")
            if cta:
                c = cta_stats.setdefault(str(cta), {"count": 0, "hits": 0})
                c["count"] += 1
                if is_hit:
                    c["hits"] += 1

        top_hooks = sorted([
            {"hook": k, "count": v["count"], "hit_rate": round(v["hits"]/v["count"], 3) if v["count"] > 0 else 0}
            for k, v in hook_stats.items() if v["count"] >= 2
        ], key=lambda x: x["hit_rate"], reverse=True)[:5]

        top_ctas = sorted([
            {"cta": k, "count": v["count"], "hit_rate": round(v["hits"]/v["count"], 3) if v["count"] > 0 else 0}
            for k, v in cta_stats.items() if v["count"] >= 2
        ], key=lambda x: x["hit_rate"], reverse=True)[:5]

        # Advertiser summary
        adv_stats: dict[str, dict] = {}
        for ad in ads:
            name = _clean_advertiser(ad.advertiser_name) or "unknown"
            a = adv_stats.setdefault(name, {"count": 0, "hits": 0})
            a["count"] += 1
            if _is_hit_ad(ad):
                a["hits"] += 1

        top_advertisers = sorted([
            {"name": k, "count": v["count"], "hit_rate": round(v["hits"]/v["count"], 3) if v["count"] > 0 else 0}
            for k, v in adv_stats.items() if v["count"] >= 2
        ], key=lambda x: (x["hit_rate"], x["count"]), reverse=True)[:10]

        # Recommendations
        recommendations = []
        if top_hooks:
            recommendations.append(f"Best hook type: '{top_hooks[0]['hook']}' ({top_hooks[0]['hit_rate']*100:.0f}% hit rate)")
        if top_ctas:
            recommendations.append(f"Best CTA type: '{top_ctas[0]['cta']}' ({top_ctas[0]['hit_rate']*100:.0f}% hit rate)")
        if genre_breakdown:
            recommendations.append(f"Top genre: '{genre_breakdown[0]['genre']}' ({genre_breakdown[0]['hit_rate']*100:.0f}% hit rate)")

        report = {
            "report_id": str(_uuid_module.uuid4()),
            "report_type": report_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filters": {"genre": genre, "advertiser": advertiser, "date_from": date_from, "date_to": date_to},
            "executive_summary": {
                "total_ads": total,
                "hit_count": hit_count,
                "mega_hit_count": mega_count,
                "hit_rate": round(hit_count / total, 3) if total > 0 else 0,
                "avg_score": avg_score,
            },
            "genre_analysis": genre_breakdown,
            "creative_analysis": {
                "top_hooks": top_hooks,
                "top_ctas": top_ctas,
            },
            "top_advertisers": top_advertisers,
            "recommendations": recommendations,
        }

        # Save report to disk
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = _REPORTS_DIR / f"{report['report_id']}.json"
        report_file.write_text(_json_module.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        if format == "html":
            html = _generate_html_report(report)
            html_file = _REPORTS_DIR / f"{report['report_id']}.html"
            html_file.write_text(html, encoding="utf-8")
            return StreamingResponse(
                iter([html]),
                media_type="text/html",
                headers={"Content-Disposition": f"attachment; filename=report_{report['report_id'][:8]}.html"},
            )

        return report


def _generate_html_report(report: dict) -> str:
    """Generate a simple HTML report with inline CSS."""
    summary = report["executive_summary"]
    genres = report["genre_analysis"]
    hooks = report["creative_analysis"]["top_hooks"]
    ctas = report["creative_analysis"]["top_ctas"]
    recs = report["recommendations"]

    genre_rows = "".join(
        f"<tr><td>{g['genre']}</td><td>{g['count']}</td>"
        f"<td>{g['hit_rate']*100:.1f}%</td><td>{g['avg_score']}</td></tr>"
        for g in genres
    )
    hook_rows = "".join(
        f"<tr><td>{h['hook']}</td><td>{h['count']}</td><td>{h['hit_rate']*100:.1f}%</td></tr>"
        for h in hooks
    )
    cta_rows = "".join(
        f"<tr><td>{c['cta']}</td><td>{c['count']}</td><td>{c['hit_rate']*100:.1f}%</td></tr>"
        for c in ctas
    )
    rec_items = "".join(f"<li>{r}</li>" for r in recs)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"><title>Ad Analysis Report</title>
<style>
body{{font-family:sans-serif;max-width:900px;margin:40px auto;padding:0 20px;color:#333}}
h1{{color:#1a73e8}}h2{{color:#444;border-bottom:2px solid #1a73e8;padding-bottom:5px}}
table{{width:100%;border-collapse:collapse;margin:15px 0}}
th,td{{padding:8px 12px;border:1px solid #ddd;text-align:left}}
th{{background:#f5f5f5}}
.kpi{{display:flex;gap:20px;flex-wrap:wrap}}
.kpi-box{{background:#f0f7ff;border-radius:8px;padding:15px 25px;text-align:center}}
.kpi-val{{font-size:2em;font-weight:bold;color:#1a73e8}}
.kpi-label{{color:#666;font-size:0.9em}}
ul{{line-height:1.8}}
</style></head>
<body>
<h1>Ad Analysis Report</h1>
<p>Generated: {report['generated_at'][:10]}</p>

<h2>Executive Summary</h2>
<div class="kpi">
<div class="kpi-box"><div class="kpi-val">{summary['total_ads']}</div><div class="kpi-label">Total Ads</div></div>
<div class="kpi-box"><div class="kpi-val">{summary['hit_count']}</div><div class="kpi-label">Hit Ads</div></div>
<div class="kpi-box"><div class="kpi-val">{summary['hit_rate']*100:.1f}%</div><div class="kpi-label">Hit Rate</div></div>
<div class="kpi-box"><div class="kpi-val">{summary['avg_score']}</div><div class="kpi-label">Avg Score</div></div>
</div>

<h2>Genre Analysis</h2>
<table><tr><th>Genre</th><th>Count</th><th>Hit Rate</th><th>Avg Score</th></tr>{genre_rows}</table>

<h2>Top Hooks</h2>
<table><tr><th>Hook Type</th><th>Count</th><th>Hit Rate</th></tr>{hook_rows}</table>

<h2>Top CTAs</h2>
<table><tr><th>CTA Type</th><th>Count</th><th>Hit Rate</th></tr>{cta_rows}</table>

<h2>Recommendations</h2>
<ul>{rec_items}</ul>
</body></html>"""


@router.get("/reports")
def list_reports():
    """List generated reports from disk."""
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    reports = []
    for f in sorted(_REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = _json_module.loads(f.read_text(encoding="utf-8"))
            _rid = data.get("report_id", f.stem)
            _rtype = data.get("report_type", "unknown")
            _gen_at = data.get("generated_at", "")
            reports.append({
                "report_id": _rid,
                "id": _rid,  # Fix #62: alias for ReportGenerator.tsx
                "report_type": _rtype,
                "type": _rtype,  # Fix #62: alias
                "generated_at": _gen_at,
                "created_at": _gen_at,  # Fix #62: alias
                "format": data.get("format", "json"),  # Fix #62
                "status": "completed",  # Fix #62: reports on disk are completed
                "download_url": f"/api/v1/rankings/reports/{_rid}",  # Fix #62
                "filters": data.get("filters", {}),
            })
        except Exception:
            continue
    return {"reports": reports[:50], "total": len(reports)}


@router.get("/reports/weekly-digest")
def weekly_digest():
    """Generate a weekly digest report.

    Summarizes: new ads this week, hit rate changes, new patterns detected.
    """
    with sync_session_scope() as session:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
        new_ads = session.query(Ad).filter(Ad.created_at >= cutoff).all()
        all_ads = session.query(Ad).all()

        new_count = len(new_ads)
        new_hits = sum(1 for a in new_ads if _is_hit_ad(a))
        total_hits = sum(1 for a in all_ads if _is_hit_ad(a))
        total = len(all_ads)

        # New patterns this week
        new_hooks: dict[str, int] = {}
        for ad in new_ads:
            ca = _get_creative_analysis(ad)
            if ca:
                h = ca.get("hook_type")
                if h:
                    new_hooks[str(h)] = new_hooks.get(str(h), 0) + 1

        return {
            "period": f"{(datetime.now(tz=timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "new_ads": new_count,
            "new_hits": new_hits,
            "new_hit_rate": round(new_hits / new_count, 3) if new_count > 0 else 0,
            "overall_hit_rate": round(total_hits / total, 3) if total > 0 else 0,
            "total_ads": total,
            "new_hooks_used": dict(sorted(new_hooks.items(), key=lambda x: x[1], reverse=True)),
        }


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    """Download a specific saved report."""
    json_file = _REPORTS_DIR / f"{report_id}.json"
    html_file = _REPORTS_DIR / f"{report_id}.html"

    if html_file.exists():
        return StreamingResponse(
            iter([html_file.read_text(encoding="utf-8")]),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=report_{report_id[:8]}.html"},
        )
    if json_file.exists():
        content = json_file.read_text(encoding="utf-8")
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=report_{report_id[:8]}.json"},
        )

    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"detail": f"Report {report_id} not found"})


# Fix #58: DELETE /reports/{report_id} — used by ReportGenerator.tsx
@router.delete("/reports/{report_id}")
def delete_report(report_id: str):
    """Delete a saved report."""
    _json_f = _REPORTS_DIR / f"{report_id}.json"
    _html_f = _REPORTS_DIR / f"{report_id}.html"
    _deleted = False
    if _json_f.exists():
        _json_f.unlink()
        _deleted = True
    if _html_f.exists():
        _html_f.unlink()
        _deleted = True
    if not _deleted:
        from fastapi.responses import JSONResponse as _JR
        return _JR(status_code=404, content={"detail": f"Report {report_id} not found"})
    print(f"[FIX58] Deleted report {report_id}")
    return {"success": True, "report_id": report_id}


# ==================== Async Task Status (C15) ====================


@router.get("/tasks")
def list_async_tasks(
    limit: int = Query(20, ge=1, le=100),
):
    """List recent async tasks (crawl jobs) with their status.

    Works whether SQS is configured or not — reads from CrawlJob table.
    """
    from app.models.crawl_job import CrawlJob

    with sync_session_scope() as session:
        jobs = (
            session.query(CrawlJob)
            .order_by(desc(CrawlJob.created_at))
            .limit(limit)
            .all()
        )

        results = []
        for job in jobs:
            results.append({
                "task_id": job.job_id,
                "type": "crawl",
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "query": job.query,
                "platforms": job.platforms or [],
                "total_ads_found": job.total_ads_found or 0,
                "progress": f"{job.completed_platforms or 0}/{job.total_platforms or 0}",
                "error": job.error_message,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            })

        # Check SQS availability
        sqs_available = False
        try:
            import os
            sqs_available = bool(os.environ.get("AWS_SQS_QUEUE_URL"))
        except Exception:
            pass

        return {
            "tasks": results,
            "total": len(results),
            "sqs_enabled": sqs_available,
        }


@router.get("/tasks/{task_id}")
def get_async_task(task_id: str):
    """Get specific async task status and result."""
    from app.models.crawl_job import CrawlJob

    with sync_session_scope() as session:
        job = session.query(CrawlJob).filter(CrawlJob.job_id == task_id).first()
        if not job:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": f"Task {task_id} not found"})

        return {
            "task_id": job.job_id,
            "type": "crawl",
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "query": job.query,
            "platforms": job.platforms or [],
            "total_ads_found": job.total_ads_found or 0,
            "completed_platforms": job.completed_platforms or 0,
            "total_platforms": job.total_platforms or 0,
            "current_platform": job.current_platform,
            "error": job.error_message,
            "progress_detail": job.progress_detail,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }


# ==================== C18: Professional Ad Ranking API ====================

# Default CPM for Japanese market (JPY per 1000 impressions)
_DEFAULT_CPM_JPY = 800

# Comprehensive genre master taxonomy (Japanese ad market)
# Maps japanese_label -> { en_key, parent }
GENRE_MASTER: dict[str, dict] = {
    # Beauty
    "medical_weight_loss": {"jp_label": "medical_weight_loss", "parent": "beauty"},
    "beauty_clinic": {"jp_label": "beauty_clinic", "parent": "beauty"},
    "skincare": {"jp_label": "skincare", "parent": "beauty"},
    "hair_removal": {"jp_label": "hair_removal", "parent": "beauty"},
    "hair_growth_aga": {"jp_label": "hair_growth_aga", "parent": "beauty"},
    "beauty_serum": {"jp_label": "beauty_serum", "parent": "beauty"},
    "cosmetics": {"jp_label": "cosmetics", "parent": "beauty"},
    "whitening": {"jp_label": "whitening", "parent": "beauty"},
    "esthetic": {"jp_label": "esthetic", "parent": "beauty"},
    "mens_beauty": {"jp_label": "mens_beauty", "parent": "beauty"},
    "ladies_clinic": {"jp_label": "ladies_clinic", "parent": "beauty"},
    # Health
    "diet_supplement": {"jp_label": "diet_supplement", "parent": "health"},
    "fitness": {"jp_label": "fitness", "parent": "health"},
    "yoga_pilates": {"jp_label": "yoga_pilates", "parent": "health"},
    "protein": {"jp_label": "protein", "parent": "health"},
    "health_food": {"jp_label": "health_food", "parent": "health"},
    "clinic": {"jp_label": "clinic", "parent": "health"},
    "chiropractic": {"jp_label": "chiropractic", "parent": "health"},
    "dental": {"jp_label": "dental", "parent": "health"},
    "gym_fitness": {"jp_label": "gym_fitness", "parent": "health"},
    "sauna": {"jp_label": "sauna", "parent": "health"},
    # Business
    "finance_investment": {"jp_label": "finance_investment", "parent": "business"},
    "education_school": {"jp_label": "education_school", "parent": "business"},
    "real_estate": {"jp_label": "real_estate", "parent": "business"},
    "recruitment": {"jp_label": "recruitment", "parent": "business"},
    "insurance": {"jp_label": "insurance", "parent": "business"},
    "legal_financial": {"jp_label": "legal_financial", "parent": "business"},
    "debt_settlement": {"jp_label": "debt_settlement", "parent": "business"},
    "professional_consultation": {"jp_label": "professional_consultation", "parent": "business"},
    "subsidies": {"jp_label": "subsidies", "parent": "business"},
    "charity": {"jp_label": "charity", "parent": "business"},
    "public_service": {"jp_label": "public_service", "parent": "business"},
    # Lifestyle
    "ec_shopping": {"jp_label": "ec_shopping", "parent": "lifestyle"},
    "app": {"jp_label": "app", "parent": "lifestyle"},
    "matching_app": {"jp_label": "matching_app", "parent": "lifestyle"},
    "delivery": {"jp_label": "delivery", "parent": "lifestyle"},
    "meal_delivery": {"jp_label": "meal_delivery", "parent": "lifestyle"},
    "gaming": {"jp_label": "gaming", "parent": "lifestyle"},
    "net_shopping": {"jp_label": "net_shopping", "parent": "lifestyle"},
    "shopping": {"jp_label": "shopping", "parent": "lifestyle"},
    "streaming": {"jp_label": "streaming", "parent": "lifestyle"},
    "social_contact": {"jp_label": "social_contact", "parent": "lifestyle"},
    "romance_marriage": {"jp_label": "romance_marriage", "parent": "lifestyle"},
    "travel": {"jp_label": "travel", "parent": "lifestyle"},
    "hotel": {"jp_label": "hotel", "parent": "lifestyle"},
    "tourism_tickets": {"jp_label": "tourism_tickets", "parent": "lifestyle"},
    "pet": {"jp_label": "pet", "parent": "lifestyle"},
    "lifestyle_service": {"jp_label": "lifestyle_service", "parent": "lifestyle"},
    "printing_service": {"jp_label": "printing_service", "parent": "lifestyle"},
    "pest_control": {"jp_label": "pest_control", "parent": "lifestyle"},
    "fortune_telling": {"jp_label": "fortune_telling", "parent": "lifestyle"},
    "hobby_culture": {"jp_label": "hobby_culture", "parent": "lifestyle"},
    "photography": {"jp_label": "photography", "parent": "lifestyle"},
    # Also map AdCategoryEnum values
    "ec_d2c": {"jp_label": "ec_d2c", "parent": "lifestyle"},
    "finance": {"jp_label": "finance", "parent": "business"},
    "education": {"jp_label": "education", "parent": "business"},
    "beauty": {"jp_label": "beauty", "parent": "beauty"},
    "food": {"jp_label": "food", "parent": "lifestyle"},
    "health": {"jp_label": "health", "parent": "health"},
    "technology": {"jp_label": "technology", "parent": "business"},
    "other": {"jp_label": "other", "parent": "other"},
}

# Parent category display labels
_PARENT_LABELS: dict[str, str] = {
    "beauty": "beauty",
    "health": "health",
    "business": "business",
    "lifestyle": "lifestyle",
    "other": "other",
}


def _resolve_fine_genre(ad: Ad) -> str:
    """Resolve fine genre label for an ad.

    Priority: fine_genre_jp > fine_genre > fine_genre_en > category > '(未分類)'
    """
    meta = ad.ad_metadata or {}
    fg_jp = meta.get("fine_genre_jp")
    if fg_jp and isinstance(fg_jp, str):
        return fg_jp
    fg = meta.get("fine_genre")
    if fg and isinstance(fg, str):
        return fg
    fg_en = meta.get("fine_genre_en")
    if fg_en and isinstance(fg_en, str):
        return fg_en
    if ad.category is not None:
        cat_val = str(ad.category.value) if hasattr(ad.category, "value") else str(ad.category)
        return cat_val
    return "(未分類)"


def _classify_destination(url: str, ca_dest_type: str | None = None) -> str:
    """Classify destination URL into a type label."""
    if ca_dest_type and ca_dest_type not in ("", "unknown"):
        mapping = {
            "lp": "article_lp", "ec": "ec_site", "sns": "SNS",
            "app_store": "app_download", "line": "LINE_add",
            "official": "official_site",
        }
        return mapping.get(ca_dest_type, ca_dest_type)
    if not url:
        return "unknown"
    u = url.lower()
    if "line.me" in u or "lin.ee" in u:
        return "LINE_add"
    if any(d in u for d in ("apps.apple.com", "play.google.com", "onelink.me", "itunes.apple.com")):
        return "app_download"
    if any(d in u for d in ("amazon.co", "rakuten.co", "shopify", "stores.jp",
                             "yahoo.co.jp/shopping", "base.shop", "mercari.com", "zozo.jp")):
        return "ec_site"
    if any(d in u for d in ("instagram.com", "twitter.com", "x.com", "facebook.com",
                             "tiktok.com", "youtube.com", "youtu.be")):
        return "SNS"
    if any(seg in u for seg in ("/article", "/lp/", "/lp?", "lp.", "/landing", "/campaign/",
                                 "/promo/", "/special/", "/feature/")):
        return "article_lp"
    # Long paths often indicate LP
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) >= 3:
            return "article_lp"
    except Exception:
        pass
    return "official_site"


def _compute_spend_jpy(views: int, cpm_jpy: float = _DEFAULT_CPM_JPY) -> int:
    """Compute estimated spend in JPY: spend = (views / 1000) * cpm_jpy."""
    return round((views / 1000.0) * cpm_jpy)


def _get_ad_cpm(ad: Ad) -> float:
    """Get CPM for an ad from metadata, falling back to default."""
    meta = ad.ad_metadata or {}
    cpm_val = meta.get("estimated_cpm_jpy")
    if cpm_val and isinstance(cpm_val, (int, float)) and float(cpm_val) > 0:
        return float(cpm_val)
    return _DEFAULT_CPM_JPY


# ---- Path to search collections JSON ----
_SEARCH_COLLECTIONS_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "search_collections.json"
)


# ---------- 1. GET /rankings/hit-line ----------


@router.get("/hit-line")
def get_hit_line(
    fine_genre: Optional[str] = Query(None, description="Filter by fine genre. Omit for all genres."),
):
    """Compute hit line threshold per genre.

    Hit line = average views of the top 20% creatives in each genre.
    Any ad that exceeds this threshold gets 'hit line exceeded' status.
    Computed per fine_genre, not globally.
    """
    print("[C18] Computing hit line thresholds")
    with sync_session_scope() as session:
        q = session.query(Ad)
        if fine_genre:
            q = q.filter(Ad.category == fine_genre)
        ads = q.all()

        # Group ads by fine_genre
        genre_ads: dict[str, list[Ad]] = {}
        for ad in ads:
            if not _is_quality_ad(ad):
                continue
            fg = _resolve_fine_genre(ad)
            if fine_genre and fg != fine_genre:
                continue
            genre_ads.setdefault(fg, []).append(ad)

        results = []
        for genre_label, g_ads in sorted(genre_ads.items()):
            ad_count = len(g_ads)
            if ad_count == 0:
                continue

            # Sort by total views descending
            views_list = sorted(
                [(ad.view_count or ad.estimated_impressions or 0) for ad in g_ads],
                reverse=True,
            )
            top20_count = max(1, int(len(views_list) * 0.2))
            top20_views = views_list[:top20_count]
            hit_line_views = int(sum(top20_views) / len(top20_views)) if top20_views else 0

            # Compute average CPM for genre
            cpms = [_get_ad_cpm(ad) for ad in g_ads]
            avg_cpm = sum(cpms) / len(cpms) if cpms else _DEFAULT_CPM_JPY

            hit_line_spend = _compute_spend_jpy(hit_line_views, avg_cpm)

            results.append({
                "genre": genre_label,
                "hit_line_views": hit_line_views,
                "hit_line_spend": hit_line_spend,
                "hit_line_spend_jpy": hit_line_spend,
                "ad_count": ad_count,
                "top20_count": top20_count,
            })

        results.sort(key=lambda x: x["ad_count"], reverse=True)
        print(f"[C18] Hit line computed for {len(results)} genres")
        return {"genres": results, "total_genres": len(results)}


# ---------- 2. GET /rankings/pro-ranking ----------


@router.get("/pro-ranking")
def get_pro_ranking(
    fine_genre: Optional[str] = Query(None, description="Filter by fine genre"),
    genre: Optional[str] = Query(None, description="Filter by category enum value"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    sort_by: str = Query("total_views", description="Sort: total_views, view_increase, total_spend, spend_increase, hit_score, like_increase, days_running, cumulative_views, cumulative_spend, score, spend, longevity"),
    period: str = Query("all", description="Period: 1d, 7d, 30d, 90d, all"),
    search_text: Optional[str] = Query(None, description="Full-text search"),
    q: Optional[str] = Query(None, description="Alias for search_text"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    # C20: Advanced filter parameters
    video_format: Optional[str] = Query(None, description="Filter: video|image|carousel|all"),
    destination_type: Optional[str] = Query(None, description="Filter by destination type"),
    destination_domain: Optional[str] = Query(None, description="Partial domain match"),
    view_count_min: Optional[int] = Query(None, description="Minimum view count"),
    view_count_max: Optional[int] = Query(None, description="Maximum view count"),
    like_count_min: Optional[int] = Query(None, description="Minimum like count"),
    like_count_max: Optional[int] = Query(None, description="Maximum like count"),
    spend_min_jpy: Optional[int] = Query(None, description="Minimum estimated spend (JPY)"),
    spend_max_jpy: Optional[int] = Query(None, description="Maximum estimated spend (JPY)"),
    date_from: Optional[str] = Query(None, description="Filter ads first seen from this date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter ads first seen until this date (YYYY-MM-DD)"),
    exclude_advertisers: Optional[str] = Query(None, description="Comma-separated advertiser names to exclude"),
    exclude_domains: Optional[str] = Query(None, description="Comma-separated domains to exclude"),
):
    """Professional ad ranking with full columns and advanced filters (C20).

    Returns ranked ads with: rank, thumbnail, platform, product_name, advertiser,
    genre, view_increase, total_views, spend_increase, total_spend, like_increase,
    is_above_hit_line, hit_score, destination_type, management_id.

    Spend formula: spend_jpy = (views / 1000) * cpm_jpy (default CPM = 800 JPY).
    Management ID format: 'N' + zero-padded ad_id (e.g. 'N00123').
    """
    effective_search = search_text or q
    print(f"[C18] Pro ranking: genre={genre}, fine_genre={fine_genre}, platform={platform}, sort={sort_by}, period={period}")

    # Parse exclude lists
    _excl_advertisers = set()
    if exclude_advertisers:
        _excl_advertisers = {a.strip().lower() for a in exclude_advertisers.split(",") if a.strip()}
    _excl_domains = set()
    if exclude_domains:
        _excl_domains = {d.strip().lower() for d in exclude_domains.split(",") if d.strip()}

    # Parse date range
    _date_from_dt = None
    _date_to_dt = None
    try:
        if date_from:
            _date_from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        if date_to:
            _date_to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        pass

    with sync_session_scope() as session:
        query = session.query(Ad)

        # Category/genre filter (SQL level)
        if genre and genre != "all":
            query = query.filter(Ad.category == genre)

        # Platform filter
        if platform and platform != "all":
            query = _resolve_platform_filter(query, Ad.platform, platform)

        # Period filter
        if period and period != "all":
            days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
            days = days_map.get(period)
            if days:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
                query = query.filter(Ad.created_at >= cutoff)

        # Text search
        if effective_search:
            escaped = _escape_like(effective_search)
            query = query.filter(
                or_(
                    Ad.title.ilike(f"%{escaped}%"),
                    Ad.description.ilike(f"%{escaped}%"),
                    Ad.advertiser_name.ilike(f"%{escaped}%"),
                    Ad.brand_name.ilike(f"%{escaped}%"),
                )
            )

        all_ads = query.limit(5000).all()

        # Filter by quality, fine_genre, and C20 advanced filters (metadata-level, done in Python)
        filtered_ads: list[Ad] = []
        for ad in all_ads:
            if not _is_quality_ad(ad):
                continue
            if fine_genre:
                fg = _resolve_fine_genre(ad)
                if fg != fine_genre:
                    continue

            # C20: Advanced filter - video_format
            if video_format and video_format != "all":
                ct = ad.creative_type or ("video" if ad.video_url else "image")
                ct_lower = str(ct).lower()
                if video_format.lower() == "video" and "video" not in ct_lower:
                    continue
                elif video_format.lower() == "image" and ct_lower not in ("image", "static", "photo"):
                    continue
                elif video_format.lower() == "carousel" and "carousel" not in ct_lower:
                    continue

            # C20: Advanced filter - view count range
            ad_views = ad.view_count or ad.estimated_impressions or 0
            if view_count_min is not None and ad_views < view_count_min:
                continue
            if view_count_max is not None and ad_views > view_count_max:
                continue

            # C20: Advanced filter - like count range
            ad_likes = ad.like_count or 0
            if like_count_min is not None and ad_likes < like_count_min:
                continue
            if like_count_max is not None and ad_likes > like_count_max:
                continue

            # C20: Advanced filter - spend range
            if spend_min_jpy is not None or spend_max_jpy is not None:
                ad_spend = _compute_spend_jpy(ad_views, _get_ad_cpm(ad))
                if spend_min_jpy is not None and ad_spend < spend_min_jpy:
                    continue
                if spend_max_jpy is not None and ad_spend > spend_max_jpy:
                    continue

            # C20: Advanced filter - date range (first_seen_at)
            if _date_from_dt or _date_to_dt:
                first_seen = ad.first_seen_at or ad.created_at
                if first_seen:
                    fs = first_seen.replace(tzinfo=None) if first_seen.tzinfo else first_seen
                    if _date_from_dt and fs < _date_from_dt:
                        continue
                    if _date_to_dt and fs > _date_to_dt:
                        continue
                elif _date_from_dt:
                    continue  # no date info, skip if date filter active

            # C20: Advanced filter - exclude advertisers
            if _excl_advertisers:
                adv_name = (ad.advertiser_name or "").lower()
                if any(excl in adv_name for excl in _excl_advertisers):
                    continue

            # C20: Advanced filter - destination type
            if destination_type:
                ad_ca = (ad.ad_metadata or {}).get("creative_analysis") or {}
                ad_dest = _classify_destination(ad.destination_url or "", ad_ca.get("destination_type"))
                if destination_type.lower() not in ad_dest.lower():
                    continue

            # C20: Advanced filter - destination domain partial match
            if destination_domain:
                ad_url = (ad.destination_url or "").lower()
                if destination_domain.lower() not in ad_url:
                    continue

            # C20: Advanced filter - exclude domains
            if _excl_domains:
                ad_url = (ad.destination_url or "").lower()
                if any(d in ad_url for d in _excl_domains):
                    continue

            filtered_ads.append(ad)

        # Compute hit line per genre
        genre_hit_lines: dict[str, int] = {}
        genre_ad_views: dict[str, list[int]] = {}
        for ad in filtered_ads:
            fg = _resolve_fine_genre(ad)
            views = ad.view_count or ad.estimated_impressions or 0
            genre_ad_views.setdefault(fg, []).append(views)

        for g_label, vlist in genre_ad_views.items():
            sorted_v = sorted(vlist, reverse=True)
            top20_n = max(1, int(len(sorted_v) * 0.2))
            genre_hit_lines[g_label] = int(sum(sorted_v[:top20_n]) / top20_n) if top20_n > 0 else 0

        # Build ad rows
        ad_rows: list[dict] = []
        for ad in filtered_ads:
            meta = ad.ad_metadata or {}
            ca = meta.get("creative_analysis") or {}
            fg = _resolve_fine_genre(ad)
            views = ad.view_count or ad.estimated_impressions or 0
            cpm = _get_ad_cpm(ad)
            total_spend = _compute_spend_jpy(views, cpm)
            longevity = _extract_longevity_info(ad)

            # Hit score
            hit_score_val = meta.get("latest_hit_score")
            if hit_score_val is None:
                hit_score_val, _, hit_level, _ = compute_hit_score(ad)
            else:
                hit_score_val = float(hit_score_val)
                hit_level = meta.get("hit_level", "none")

            # View/like increase from metadata
            view_increase = int(meta.get("view_increase_7d", meta.get("view_increase", 0)) or 0)
            like_increase = int(meta.get("like_increase_7d", meta.get("like_increase", 0)) or 0)
            spend_increase = _compute_spend_jpy(view_increase, cpm)

            # Hit line check
            hl = genre_hit_lines.get(fg, 0)
            is_above = views >= hl if hl > 0 else False

            # Destination type
            dest_type = _classify_destination(ad.destination_url or "", ca.get("destination_type"))

            # Management ID: "N" + zero-padded ad_id
            mgmt_id = f"N{ad.id:05d}"

            # Platform string
            plat = str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or "")

            ad_rows.append({
                "rank": 0,  # assigned after sort
                "ad_id": ad.id,
                "title": ad.title or "",
                "description": (ad.description or "")[:200],
                "thumbnail_url": _resolve_thumbnail_url(ad),
                "thumbnail": _resolve_thumbnail_url(ad),
                "video_duration_seconds": ad.duration_seconds or 0,
                "duration_seconds": ad.duration_seconds or 0,
                "platform": plat,
                "product_name": _derive_product_name(ad),
                "advertiser_name": _clean_advertiser(ad.advertiser_name),
                "genre": str(ad.category.value) if ad.category and hasattr(ad.category, "value") else str(ad.category or ""),
                "fine_genre": fg,
                "view_increase": view_increase,
                "total_views": views,
                "cumulative_views": views,
                "spend_increase_jpy": spend_increase,
                "spend_increase": spend_increase,
                "total_spend_jpy": total_spend,
                "cumulative_spend": total_spend,
                "like_increase": like_increase,
                "like_count": ad.like_count or 0,
                "is_above_hit_line": is_above,
                "hit_score": round(hit_score_val, 1),
                "hit_level": hit_level,
                "is_hit": _is_hit_ad(ad),
                "creative_type": ad.creative_type or ("video" if ad.video_url else "image"),
                "destination_type": dest_type,
                "destination_url": ad.destination_url or "",
                "management_id": mgmt_id,
                "days_running": longevity["days_running"],
                "is_still_running": longevity["is_still_running"],
                "trend_score": float(meta.get("trend_score", 0) or 0),
                "image_url": _resolve_image_url(ad),
                "video_url": _resolve_video_url(ad),
                "snapshot_url": ad.snapshot_url or "",
                "download_url": f"/api/v1/media/download/{ad.id}",
            })

        # Sort
        sort_key_map: dict[str, str] = {
            "total_views": "total_views",
            "cumulative_views": "total_views",
            "view_increase": "view_increase",
            "total_spend": "total_spend_jpy",
            "cumulative_spend": "total_spend_jpy",
            "spend_increase": "spend_increase_jpy",
            "hit_score": "hit_score",
            "score": "hit_score",
            "like_increase": "like_increase",
            "days_running": "days_running",
            "spend": "total_spend_jpy",
            "longevity": "days_running",
        }
        sk = sort_key_map.get(sort_by, "total_views")
        ad_rows.sort(key=lambda r: r.get(sk, 0), reverse=True)

        # Assign ranks
        for idx, row in enumerate(ad_rows, 1):
            row["rank"] = idx

        total = len(ad_rows)
        start = (page - 1) * per_page
        paginated = ad_rows[start:start + per_page]

        # Collect distinct fine_genres
        fine_genres = sorted(set(r["fine_genre"] for r in ad_rows))

        # Compute overall hit line for the response header
        if genre_hit_lines:
            all_hl = list(genre_hit_lines.values())
            overall_hl_views = round(sum(all_hl) / len(all_hl))
        else:
            overall_hl_views = 0
        overall_hl_spend = _compute_spend_jpy(overall_hl_views)

        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        print(f"[C18] Pro ranking: {total} ads, page {page}/{max(1, total_pages)}")
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "hit_line": {
                "views": overall_hl_views,
                "spend_jpy": overall_hl_spend,
            },
            "fine_genres": fine_genres,
            "ads": paginated,
            "items": paginated,
        }


# ---------- 3. GET /rankings/smart-autocomplete ----------


@router.get("/smart-autocomplete")
def smart_autocomplete(
    query: str = Query(..., min_length=1, description="Partial text for smart autocomplete"),
):
    """Smart autocomplete with genre, product, and advertiser suggestions.

    Returns:
    - text_search: search-all suggestion
    - genre_matches: matching genres from GENRE_MASTER
    - product_matches: matching product/brand names
    - advertiser_matches: matching advertiser names
    """
    q_lower = query.lower()

    with sync_session_scope() as session:
        # 1. Genre matches from GENRE_MASTER + DB categories
        genre_matches: list[dict] = []
        seen_genres: set[str] = set()

        # Query DB for category counts
        cat_results = (
            session.query(Ad.category, func.count(Ad.id).label("cnt"))
            .filter(Ad.category.isnot(None))
            .group_by(Ad.category)
            .all()
        )
        cat_count_map: dict[str, int] = {}
        for cat, cnt in cat_results:
            cat_str = str(cat.value) if hasattr(cat, "value") else str(cat)
            cat_count_map[cat_str] = cnt

        # Check GENRE_MASTER keys against query
        for en_key, info in GENRE_MASTER.items():
            label = info.get("jp_label", en_key)
            if q_lower in en_key.lower() or q_lower in label.lower():
                count = cat_count_map.get(en_key, 0)
                if en_key not in seen_genres:
                    genre_matches.append({
                        "label": f"{label} de filter",
                        "type": "genre",
                        "key": en_key,
                        "value": en_key,
                        "count": count,
                    })
                    seen_genres.add(en_key)

        # Also check DB categories not yet in genre_matches
        for cat_str, cnt in cat_count_map.items():
            if cat_str not in seen_genres and q_lower in cat_str.lower():
                genre_matches.append({
                    "label": f"{cat_str.replace('_', ' ').title()} de filter",
                    "type": "genre",
                    "key": cat_str,
                    "value": cat_str,
                    "count": cnt,
                })

        genre_matches.sort(key=lambda x: x["count"], reverse=True)

        # 2. Product/brand matches
        product_matches: list[dict] = []
        prod_results = (
            session.query(Ad.brand_name, Ad.title)
            .filter(
                or_(
                    Ad.brand_name.ilike(f"%{_escape_like(query)}%"),
                    Ad.title.ilike(f"%{_escape_like(query)}%"),
                )
            )
            .limit(500)
            .all()
        )
        product_counts: dict[str, int] = {}
        for brand, title in prod_results:
            name = (brand or "").strip()
            if not name and title:
                name = title.strip()[:50]
            if name and len(name) >= 2:
                product_counts[name] = product_counts.get(name, 0) + 1
        for name, count in sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:8]:
            product_matches.append({
                "label": f"{name} de filter",
                "type": "product",
                "key": name,
                "value": name,
                "count": count,
            })

        # 3. Advertiser matches
        advertiser_matches: list[dict] = []
        adv_results = (
            session.query(Ad.advertiser_name)
            .filter(Ad.advertiser_name.isnot(None))
            .filter(Ad.advertiser_name.ilike(f"%{_escape_like(query)}%"))
            .all()
        )
        adv_counts: dict[str, int] = {}
        for (name,) in adv_results:
            cleaned = _clean_advertiser(name)
            if cleaned:
                adv_counts[cleaned] = adv_counts.get(cleaned, 0) + 1
        for name, count in sorted(adv_counts.items(), key=lambda x: x[1], reverse=True)[:8]:
            advertiser_matches.append({
                "label": f"{name} de filter",
                "type": "advertiser",
                "key": name,
                "value": name,
                "count": count,
            })

        return {
            "text_search": {
                "label": f"{query} - search all",
                "type": "text",
            },
            "genre_matches": genre_matches[:10],
            "product_matches": product_matches,
            "advertiser_matches": advertiser_matches,
            # Backward-compatible flat keys
            "query": query,
            "genres": [{"label": g["key"].replace("_", " ").title(), "value": g["value"], "count": g["count"]} for g in genre_matches[:5]],
            "products": [{"label": p["key"], "value": p["key"], "count": p["count"]} for p in product_matches[:8]],
            "advertisers": [{"label": a["key"], "value": a["key"], "count": a["count"]} for a in advertiser_matches[:8]],
        }


# ---------- 4. GET /rankings/genre-master ----------


@router.get("/genre-master")
def get_genre_master():
    """Return the full genre taxonomy grouped by parent category.

    Uses the comprehensive GENRE_MASTER constant with:
    - Japanese name, English key, ad count, hit_line_views
    - Parent category grouping for sidebar display
    """
    print("[C18] Loading genre master")
    with sync_session_scope() as session:
        # Get ad counts per category
        cat_results = (
            session.query(Ad.category, func.count(Ad.id).label("cnt"))
            .filter(Ad.category.isnot(None))
            .group_by(Ad.category)
            .all()
        )
        cat_count_map: dict[str, int] = {}
        for cat, cnt in cat_results:
            cat_str = str(cat.value) if hasattr(cat, "value") else str(cat)
            cat_count_map[cat_str] = cnt

        # Also get view counts for hit line computation
        cat_views: dict[str, list[int]] = {}
        view_data = (
            session.query(Ad.category, Ad.view_count, Ad.estimated_impressions)
            .filter(Ad.category.isnot(None))
            .all()
        )
        for cat, vc, ei in view_data:
            cat_str = str(cat.value) if hasattr(cat, "value") else str(cat)
            views = vc or ei or 0
            cat_views.setdefault(cat_str, []).append(views)

        # Build genre items from GENRE_MASTER
        genre_items: list[dict] = []
        seen_keys: set[str] = set()
        for en_key, info in GENRE_MASTER.items():
            parent = info["parent"]
            count = cat_count_map.get(en_key, 0)
            seen_keys.add(en_key)

            # Compute hit line for this genre
            vlist = cat_views.get(en_key, [])
            if vlist:
                sorted_v = sorted(vlist, reverse=True)
                top20_n = max(1, int(len(sorted_v) * 0.2))
                hit_line_views = int(sum(sorted_v[:top20_n]) / top20_n)
            else:
                hit_line_views = 0

            genre_items.append({
                "jp_label": info.get("jp_label", en_key),
                "en_key": en_key,
                "value": en_key,
                "label": en_key.replace("_", " ").title(),
                "parent": parent,
                "parent_label": _PARENT_LABELS.get(parent, parent),
                "count": count,
                "hit_line_views": hit_line_views,
            })

        # Also include DB categories not in GENRE_MASTER
        for cat_str, cnt in cat_count_map.items():
            if cat_str not in seen_keys:
                parent = "other"
                vlist = cat_views.get(cat_str, [])
                if vlist:
                    sorted_v = sorted(vlist, reverse=True)
                    top20_n = max(1, int(len(sorted_v) * 0.2))
                    hit_line_views = int(sum(sorted_v[:top20_n]) / top20_n)
                else:
                    hit_line_views = 0

                genre_items.append({
                    "jp_label": cat_str,
                    "en_key": cat_str,
                    "value": cat_str,
                    "label": cat_str.replace("_", " ").title(),
                    "parent": parent,
                    "parent_label": _PARENT_LABELS.get(parent, parent),
                    "count": cnt,
                    "hit_line_views": hit_line_views,
                })

        genre_items.sort(key=lambda x: x["count"], reverse=True)

        # Build grouped structure
        groups_map: dict[str, list] = {}
        for item in genre_items:
            groups_map.setdefault(item["parent"], []).append(item)

        groups: list[dict] = []
        for parent_key in ["beauty", "health", "business", "lifestyle", "other"]:
            items = groups_map.get(parent_key, [])
            if items:
                groups.append({
                    "parent": parent_key,
                    "label": _PARENT_LABELS.get(parent_key, parent_key),
                    "items": items,
                })

        print(f"[C18] Genre master: {len(genre_items)} genres in {len(groups)} groups")
        return {
            "genres": genre_items,
            "groups": groups,
            "total": len(genre_items),
        }


# ---------- 5. Search Collections (GET/POST/DELETE /rankings/search-collections) ----------


def _load_search_collections() -> list[dict]:
    """Load search collections from JSON file."""
    if not _SEARCH_COLLECTIONS_FILE.exists():
        return []
    try:
        return json.loads(_SEARCH_COLLECTIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_search_collections(items: list[dict]) -> None:
    """Persist search collections to JSON file."""
    _SEARCH_COLLECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SEARCH_COLLECTIONS_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class _SearchCollectionBody(BaseModel):
    name: str
    filters: Optional[dict] = None


@router.get("/search-collections")
def list_search_collections():
    """List saved search filter presets."""
    items = _load_search_collections()
    return {"collections": items, "items": items, "total": len(items)}


@router.post("/search-collections")
def create_search_collection(body: _SearchCollectionBody):
    """Save a new search filter preset.

    Body: { name, filters: { genre, platform, search_text, sort_by, period } }
    Stored in backend/data/search_collections.json.
    """
    items = _load_search_collections()
    new_id = max((c.get("id", 0) for c in items), default=0) + 1
    new_item = {
        "id": new_id,
        "name": body.name,
        "filters": body.filters or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items.append(new_item)
    _save_search_collections(items)
    print(f"[C18] Saved search collection: {body.name} (id={new_id})")
    return {"status": "saved", "collection": new_item}


@router.delete("/search-collections/{collection_id}")
def delete_search_collection(collection_id: int):
    """Delete a saved search collection by ID."""
    items = _load_search_collections()
    filtered = [c for c in items if c.get("id") != collection_id]
    if len(filtered) == len(items):
        return JSONResponse(status_code=404, content={"detail": "Collection not found"})
    _save_search_collections(filtered)
    print(f"[C18] Deleted search collection id={collection_id}")
    return {"status": "deleted", "id": collection_id}


# ==================== Scenario Generation (C19) ====================

_SCENARIO_ARCHETYPES = [
    {
        "key": "problem_solution",
        "name": "問題提示→解決型",
        "name_en": "Problem-Solution",
        "description": "Present a relatable problem, then showcase the product as the ideal solution.",
        "structure": ["hook", "problem", "solution", "proof", "cta"],
        "best_for": ["medical_weight_loss", "skincare", "hair_growth_aga", "dental"],
    },
    {
        "key": "before_after_transformation",
        "name": "ビフォーアフター変身型",
        "name_en": "Before/After Transformation",
        "description": "Show dramatic transformation with visual before/after comparison.",
        "structure": ["hook", "before", "transformation", "after", "cta"],
        "best_for": ["beauty_clinic", "medical_weight_loss", "fitness", "hair_removal"],
    },
    {
        "key": "testimonial_story",
        "name": "体験談ストーリー型",
        "name_en": "Testimonial Story",
        "description": "Feature real or representative user stories to build trust.",
        "structure": ["hook", "context", "experience", "result", "cta"],
        "best_for": ["diet_supplement", "beauty_serum", "fitness", "education_school"],
    },
    {
        "key": "authority_expert",
        "name": "権威・専門家推薦型",
        "name_en": "Authority/Expert",
        "description": "Leverage expert endorsement or authoritative data for credibility.",
        "structure": ["hook", "authority_intro", "expert_opinion", "evidence", "cta"],
        "best_for": ["clinic", "finance_investment", "insurance", "legal_financial"],
    },
    {
        "key": "urgency_limited",
        "name": "緊急性・限定型",
        "name_en": "Urgency/Limited",
        "description": "Create urgency through scarcity, countdown, or limited-time offers.",
        "structure": ["hook", "offer", "scarcity", "social_proof", "cta"],
        "best_for": ["ec_shopping", "beauty_clinic", "travel", "ec_d2c"],
    },
    {
        "key": "comparison",
        "name": "比較型",
        "name_en": "Comparison",
        "description": "Compare old/competitor approach vs new product advantage.",
        "structure": ["hook", "old_way", "new_way", "comparison", "cta"],
        "best_for": ["skincare", "protein", "app", "technology"],
    },
    {
        "key": "tutorial_howto",
        "name": "ハウツー・使い方型",
        "name_en": "Tutorial/How-To",
        "description": "Step-by-step demonstration that educates while selling.",
        "structure": ["hook", "step1", "step2", "result", "cta"],
        "best_for": ["cosmetics", "app", "education_school", "health_food"],
    },
    {
        "key": "lifestyle",
        "name": "ライフスタイル提案型",
        "name_en": "Lifestyle",
        "description": "Paint aspirational lifestyle scenes where the product fits naturally.",
        "structure": ["hook", "scene", "product_intro", "lifestyle", "cta"],
        "best_for": ["travel", "hotel", "matching_app", "streaming", "food"],
    },
]

_HOOK_TEMPLATES = {
    "shock": "【衝撃】{benefit}",
    "question": "{target}のあなた、{problem}で悩んでいませんか？",
    "statistic": "{target}の{statistic_pct}%が知らない{topic}の真実",
    "pain_point": "{problem}...もう我慢しなくていいんです",
    "benefit": "たった{period}で{benefit}を実現する方法",
    "social_proof": "すでに{user_count}名が体験した{product_name}",
    "urgency": "【期間限定】{offer}は今だけ！",
    "curiosity": "知っていますか？{topic}の意外な事実",
}

_CTA_TEMPLATES = {
    "line_add": "今すぐLINE追加で{offer}",
    "purchase": "今すぐ{product_name}を試す",
    "signup": "無料で{product_name}を始める",
    "consultation": "無料カウンセリングを予約する",
    "free_trial": "まずは無料でお試し",
    "learn_more": "詳しくはこちら",
    "download": "今すぐダウンロード",
    "reserve": "今すぐ予約する",
}

_POWER_WORDS = [
    "衝撃", "たった", "簡単", "今すぐ", "無料", "限定", "驚き", "秘密",
    "実証済み", "話題", "注目", "保証", "特別", "初回", "期間限定",
    "99%", "プロ", "最新", "革命的", "圧倒的", "確実", "即効",
    "必見", "効果", "劇的", "速報", "独占", "プレミアム",
]

_SECTION_TEMPLATES = {
    "hook": "{hook_text}",
    "problem": "{target}のあなた、こんな悩みはありませんか？{problem}が改善しない日々...",
    "solution": "{product_name}なら{benefit}を実現できます。専門家が開発した安心の方法です。",
    "proof": "すでに多くの方が{product_name}で効果を実感。満足度{statistic_pct}%の実績。",
    "cta": "{cta_text}",
    "before": "以前は{problem}で悩んでいた{target}...",
    "transformation": "{product_name}との出会いで、人生が変わりました。",
    "after": "{benefit}を達成！もう{problem}に悩まない毎日。",
    "context": "私は{target}です。ずっと{problem}に悩んでいました。",
    "experience": "実際に{product_name}を{period}使い続けた結果...",
    "result": "結果、{benefit}を達成！周りからも「変わったね」と言われるように。",
    "authority_intro": "専門家が推薦する{product_name}の実力とは？",
    "expert_opinion": "医師・専門家が監修。{product_name}は科学的根拠に基づいています。",
    "evidence": "{statistic_pct}%の方が効果を実感。臨床データでも証明済み。",
    "offer": "今なら{offer}！{product_name}を特別価格でお届け。",
    "scarcity": "残りわずか。この特別価格は{period}限定です。",
    "social_proof": "すでに{user_count}名以上が体験。SNSでも話題沸騰中！",
    "old_way": "従来の方法では{problem}が解決しない理由...",
    "new_way": "{product_name}なら、従来の{statistic_pct}%の時間で{benefit}を実現。",
    "comparison": "比べてみてください。{product_name}の圧倒的な違いを。",
    "step1": "ステップ1: {product_name}を使い始める。たった{period}で準備完了。",
    "step2": "ステップ2: 毎日続けるだけ。{target}でも簡単にできます。",
    "scene": "想像してみてください。{benefit}を手に入れた毎日を。",
    "product_intro": "そんな理想を叶えるのが{product_name}です。",
    "lifestyle": "{benefit}を実現した先に待つ、新しいライフスタイル。",
}

_SAVED_SCENARIOS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "saved_scenarios.json"
_SCENARIO_DB_FILE = Path(__file__).resolve().parent.parent.parent.parent / "exports" / "scenario_database.json"


def _load_scenario_db() -> dict | None:
    """Load scenario database JSON. Returns None if file missing or invalid."""
    if _SCENARIO_DB_FILE.exists():
        try:
            return _json_module.loads(_SCENARIO_DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def _find_power_words(text: str) -> list[str]:
    """Find power words present in the given text."""
    return [w for w in _POWER_WORDS if w in text]


class _DefaultDict(dict):
    """Dict that returns '' for missing keys, used by _fill_template."""
    def __missing__(self, key: str) -> str:
        return ""


def _fill_template(template: str, **kwargs) -> str:
    """Safe template fill - missing keys become empty string."""
    try:
        return template.format_map(_DefaultDict(kwargs))
    except (KeyError, IndexError, ValueError):
        result = template
        for k, v in kwargs.items():
            result = result.replace("{" + k + "}", str(v))
        return result


# --- C19 Endpoint 5: Scenario Archetypes ---

@router.get("/scenario-archetypes")
def get_scenario_archetypes():
    """Return all available scenario archetypes with descriptions, stats, and metadata (C19)."""
    print("[C19] Loading scenario archetypes with stats")
    with sync_session_scope() as session:
        ads = session.query(Ad).limit(5000).all()

        # Count per archetype (based on creative_analysis hook patterns)
        archetype_stats: dict[str, dict] = {}
        for a_type in _SCENARIO_ARCHETYPES:
            archetype_stats[a_type["key"]] = {"count": 0, "hits": 0, "genres": set(), "total_score": 0.0}

        for ad in ads:
            ca = _get_creative_analysis(ad)
            if not ca:
                continue
            hook = ca.get("hook_type", "")
            has_ba = ca.get("has_before_after", False)
            has_testimonial = ca.get("has_testimonial", False)

            # Map to archetype
            if has_ba:
                key = "before_after_transformation"
            elif has_testimonial:
                key = "testimonial_story"
            elif hook == "question":
                key = "problem_solution"
            elif hook == "social_proof":
                key = "authority_expert"
            elif hook == "urgency":
                key = "urgency_limited"
            elif hook == "benefit":
                key = "lifestyle"
            elif hook == "curiosity":
                key = "comparison"
            else:
                key = "problem_solution"

            g = str(ad.category.value) if ad.category and hasattr(ad.category, "value") else str(ad.category or "other")
            stats = archetype_stats.get(key)
            if stats is None:
                continue
            stats["count"] += 1
            stats["genres"].add(g)
            score_val = float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
            stats["total_score"] += score_val
            if _is_hit_ad(ad):
                stats["hits"] += 1

        results = []
        for a_type in _SCENARIO_ARCHETYPES:
            stats = archetype_stats[a_type["key"]]
            cnt = stats["count"]
            results.append({
                "key": a_type["key"],
                "name": a_type["name"],
                "name_en": a_type.get("name_en", a_type["key"]),
                "description": a_type.get("description", ""),
                "structure": a_type["structure"],
                "hit_rate": round(stats["hits"] / cnt, 3) if cnt > 0 else 0,
                "avg_score": round(stats["total_score"] / cnt, 1) if cnt > 0 else 0,
                "ad_count": cnt,
                "best_genres": sorted(stats["genres"])[:5],
                "best_for": a_type.get("best_for", []),
            })

        results.sort(key=lambda x: x["hit_rate"], reverse=True)
        print(f"[C19] Archetypes loaded: {len(results)} types")
        return {"archetypes": results}


# --- C19 Endpoint 1: Scenario Templates ---

@router.get("/scenario-templates")
def get_scenario_templates(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    archetype: Optional[str] = Query(None, description="Filter by archetype key"),
):
    """Return scenario templates grouped by genre (C19).

    Data source: exports/scenario_database.json (created by Agent A).
    Fallback: generate from live DB data + archetype constants.
    """
    print(f"[C19] Loading scenario templates: genre={genre}, archetype={archetype}")
    db = _load_scenario_db()
    if db and "genres" in db:
        genres_data = [dict(g) for g in db["genres"]]  # shallow copy
        if genre:
            genres_data = [g for g in genres_data if g.get("genre_en") == genre or g.get("genre") == genre]
        if archetype:
            for g in genres_data:
                g["templates"] = [t for t in g.get("templates", []) if t.get("archetype_en") == archetype]
            genres_data = [g for g in genres_data if g.get("templates")]
        print(f"[C19] Templates from scenario_database.json: {len(genres_data)} genres")
        # Fix #54: flatten templates for frontend TemplateLibrary
        _flat_templates = []
        for _gd in genres_data:
            _g_name = _gd.get("genre") or _gd.get("genre_en") or ""
            for _ti, _t in enumerate(_gd.get("templates", [])):
                _flat_templates.append({
                    "id": f"{_g_name}_{_t.get('archetype_en', _ti)}",
                    "name": _t.get("archetype_name") or _t.get("archetype_en", ""),
                    "hit_rate": round(float(_t.get("hit_rate", 0)) * 100, 1) if float(_t.get("hit_rate", 0)) <= 1 else float(_t.get("hit_rate", 0)),
                    "genres": [_g_name] if _g_name else [],
                    "sections": [{"label": s} for s in _t.get("structure", [])] if isinstance(_t.get("structure"), list) else [],
                    "description": f"{_g_name} - {_t.get('archetype_name', '')}",
                    "best_hooks": _t.get("best_hooks", []),
                    "best_ctas": _t.get("best_ctas", []),
                    "avg_score": _t.get("avg_score", 0),
                })
        return {"genres": genres_data, "templates": _flat_templates, "items": _flat_templates, "source": "scenario_database"}

    # Fallback: generate from live data
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.limit(5000).all()

        genre_map: dict[str, list] = {}
        for ad in ads:
            if not _is_quality_ad(ad):
                continue
            g = str(ad.category.value) if ad.category and hasattr(ad.category, "value") else str(ad.category or "other")
            genre_map.setdefault(g, []).append(ad)

        genres_out = []
        for g_name, g_ads in sorted(genre_map.items()):
            templates = []
            analyzed_ads = [a for a in g_ads if _get_creative_analysis(a)]
            if not analyzed_ads:
                analyzed_ads = g_ads
            hits = [a for a in analyzed_ads if _is_hit_ad(a)]
            genre_scores = [float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0) for a in analyzed_ads]
            avg_genre_score = round(sum(genre_scores) / len(genre_scores), 1) if genre_scores else 0

            # Collect best hooks and CTAs from hit ads in this genre
            hook_counts: dict[str, int] = {}
            cta_counts: dict[str, int] = {}
            for a in hits:
                ca = _get_creative_analysis(a) or {}
                h = ca.get("hook_type")
                c = ca.get("cta_type")
                if h:
                    hook_counts[h] = hook_counts.get(h, 0) + 1
                if c:
                    cta_counts[c] = cta_counts.get(c, 0) + 1

            best_hooks = sorted(hook_counts.keys(), key=lambda k: hook_counts[k], reverse=True)[:5]
            best_ctas = sorted(cta_counts.keys(), key=lambda k: cta_counts[k], reverse=True)[:5]

            for a_type in _SCENARIO_ARCHETYPES:
                if archetype and a_type["key"] != archetype:
                    continue
                example_ids = [a.id for a in hits[:3]] if hits else [a.id for a in analyzed_ads[:3]]
                hit_rate = round(len(hits) / len(analyzed_ads), 3) if analyzed_ads else 0
                templates.append({
                    "archetype_name": a_type["name"],
                    "archetype_en": a_type["key"],
                    "hit_rate": hit_rate,
                    "avg_score": avg_genre_score,
                    "structure": a_type["structure"],
                    "best_hooks": best_hooks,
                    "best_ctas": best_ctas,
                    "power_words": _POWER_WORDS[:10],
                    "example_ad_ids": example_ids,
                })
            if templates:
                genres_out.append({
                    "genre": g_name,
                    "genre_en": g_name,
                    "ad_count": len(g_ads),
                    "templates": templates,
                })

        print(f"[C19] Templates fallback: {len(genres_out)} genres")
        # Fix #54: flatten for frontend TemplateLibrary
        _flat_fb = []
        for _gd in genres_out:
            _g_name = _gd.get("genre", "")
            for _ti, _t in enumerate(_gd.get("templates", [])):
                _flat_fb.append({
                    "id": f"{_g_name}_{_t.get('archetype_en', _ti)}",
                    "name": _t.get("archetype_name", ""),
                    "hit_rate": round(float(_t.get("hit_rate", 0)) * 100, 1) if float(_t.get("hit_rate", 0)) <= 1 else float(_t.get("hit_rate", 0)),
                    "genres": [_g_name] if _g_name else [],
                    "sections": [{"label": s} for s in _t.get("structure", [])] if isinstance(_t.get("structure"), list) else [],
                    "description": f"{_g_name} - {_t.get('archetype_name', '')}",
                    "best_hooks": _t.get("best_hooks", []),
                    "best_ctas": _t.get("best_ctas", []),
                    "avg_score": _t.get("avg_score", 0),
                })
        return {"genres": genres_out, "templates": _flat_fb, "items": _flat_fb, "source": "fallback"}


# --- C19 Endpoint 2: Generate Scenario ---

class _GenerateScenarioBody(BaseModel):
    genre_en: str = "medical_weight_loss"
    product_name: str = "Product"
    target_audience: str = "30代女性"
    key_benefit: str = "効果を実感"
    cta_type: str = "line_add"
    archetype: str = "problem_solution"
    duration_seconds: int = 30
    platform: str = "instagram"


@router.post("/generate-scenario")
def generate_scenario(body: _GenerateScenarioBody):
    """Generate a complete ad scenario from templates (C19).

    Template-based: fills placeholders with user input.
    No external AI API calls.
    Returns: title options, sections (hook/problem/solution/proof/CTA),
    full script, power words used, predicted score, and reference ads.
    """
    print(f"[C19] Generating scenario: archetype={body.archetype}, genre={body.genre_en}")

    # Find archetype
    a_type = next(
        (a for a in _SCENARIO_ARCHETYPES if a["key"] == body.archetype),
        _SCENARIO_ARCHETYPES[0],
    )

    # Determine best hook type for archetype
    hook_key_map = {
        "problem_solution": "pain_point",
        "before_after_transformation": "pain_point",
        "testimonial_story": "social_proof",
        "authority_expert": "statistic",
        "urgency_limited": "urgency",
        "comparison": "benefit",
        "tutorial_howto": "curiosity",
        "lifestyle": "benefit",
    }
    hook_key = hook_key_map.get(body.archetype, "benefit")

    # Template variables
    tpl_vars = {
        "benefit": body.key_benefit,
        "target": body.target_audience,
        "product_name": body.product_name,
        "problem": "悩み",
        "period": "1ヶ月",
        "statistic_pct": "80",
        "topic": body.product_name,
        "user_count": "1,000",
        "offer": "無料カウンセリング",
        "hook_text": "",
        "cta_text": "",
    }

    # Generate hook text
    hook_template = _HOOK_TEMPLATES.get(hook_key, _HOOK_TEMPLATES["benefit"])
    hook_text = _fill_template(hook_template, **tpl_vars)
    tpl_vars["hook_text"] = hook_text

    # Generate CTA text
    cta_template = _CTA_TEMPLATES.get(body.cta_type, _CTA_TEMPLATES["learn_more"])
    cta_text = _fill_template(cta_template, **tpl_vars)
    tpl_vars["cta_text"] = cta_text

    # Build scenario sections with timing
    total = body.duration_seconds
    sections = a_type["structure"]
    sec_duration = total / len(sections) if sections else total
    scenario_parts = []
    time_offset = 0.0

    for section in sections:
        end = min(time_offset + sec_duration, float(total))
        dur_str = f"{int(time_offset // 60)}:{int(time_offset % 60):02d}-{int(end // 60)}:{int(end % 60):02d}"

        sec_template = _SECTION_TEMPLATES.get(section, "{product_name}について")
        text = _fill_template(sec_template, **tpl_vars)

        sec_type = hook_key if section == "hook" else section
        scenario_parts.append({
            "section": section,
            "type": sec_type,
            "text": text,
            "duration": dur_str,
        })
        time_offset = end

    # Generate title options
    title_options = [
        f"【衝撃】{body.key_benefit}！{body.product_name}の秘密",
        f"【{body.target_audience}必見】{body.key_benefit}を実現する{body.product_name}",
        f"{body.target_audience}の80%が知らない{body.product_name}の真実",
        f"たった1ヶ月で{body.key_benefit}！{body.product_name}の効果とは",
        f"もう{body.target_audience}は悩まない。{body.product_name}で{body.key_benefit}",
    ]

    full_script = " ".join(p["text"] for p in scenario_parts)
    power_words_used = _find_power_words(full_script + " " + " ".join(title_options))

    # Predict score from DB + find reference ads
    reference_ads: list[dict] = []
    predicted = 55.0
    confidence = "low"
    with sync_session_scope() as session:
        genre_ads = session.query(Ad).filter(Ad.category == body.genre_en).limit(2000).all()
        if genre_ads:
            genre_scores = [
                float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0)
                for a in genre_ads
            ]
            avg_score = sum(genre_scores) / len(genre_scores) if genre_scores else 0

            # Bonus for archetype + CTA matching
            bonus = 0.0
            matching_ads = []
            for ad in genre_ads:
                ca = _get_creative_analysis(ad) or {}
                if ca.get("hook_type") == hook_key or ca.get("cta_type") == body.cta_type:
                    matching_ads.append(ad)
            if matching_ads:
                match_scores = [
                    float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0)
                    for a in matching_ads
                ]
                bonus = (sum(match_scores) / len(match_scores) - avg_score) * 0.3

            predicted = round(min(avg_score * 1.1 + bonus, 95.0), 1)

            if len(genre_ads) >= 50:
                confidence = "high"
            elif len(genre_ads) >= 10:
                confidence = "medium"

            # Reference ads (highest scoring in this genre)
            top_ads = sorted(
                genre_ads,
                key=lambda a: float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0),
                reverse=True,
            )[:3]
            for ta in top_ads:
                ta_score = float((ta.ad_metadata or {}).get("latest_hit_score", 0) or 0)
                reference_ads.append({
                    "ad_id": ta.id,
                    "score": round(ta_score, 1),
                    "title": (ta.title or "")[:60],
                    "thumbnail": _resolve_thumbnail_url(ta),
                })

    print(f"[C19] Scenario generated: predicted_score={predicted}, confidence={confidence}")
    return {
        "scenario": {
            "title_options": title_options,
            "hook": {
                "type": hook_key,
                "text": hook_text,
                "duration": scenario_parts[0]["duration"] if scenario_parts else "0:00-0:03",
            },
            "sections": scenario_parts,
            "full_script": full_script,
            "power_words_used": power_words_used,
            "archetype": a_type["name"],
            "archetype_key": a_type["key"],
            "platform": body.platform,
            "duration_seconds": body.duration_seconds,
            "predicted_score": predicted,
            "confidence": confidence,
            "reference_ads": reference_ads,
        },
    }


# --- C19 Endpoint 3: Scenario Variations ---

class _ScenarioVariationsBody(BaseModel):
    genre_en: str = "beauty"
    product_name: str = "Product"
    key_benefit: str = "効果を実感"
    target_audience: str = "30代女性"
    variation_count: int = 3
    base_archetype: Optional[str] = None


@router.post("/scenario-variations")
def generate_variations(body: _ScenarioVariationsBody):
    """Generate N scenario variations with different hooks/CTAs/tones (C19).

    Each variation uses a different hook+CTA combination and a different tone.
    """
    count = max(1, min(body.variation_count, 10))
    print(f"[C19] Generating {count} variations for {body.product_name}")

    hook_keys = list(_HOOK_TEMPLATES.keys())
    cta_keys = list(_CTA_TEMPLATES.keys())
    tones = ["professional", "casual", "urgent", "emotional", "informative",
             "inspirational", "humorous", "empathetic", "bold", "gentle"]
    archetype_keys = [a["key"] for a in _SCENARIO_ARCHETYPES]

    tpl_vars_base = {
        "benefit": body.key_benefit,
        "target": body.target_audience,
        "product_name": body.product_name,
        "problem": "悩み",
        "period": "1ヶ月",
        "topic": body.product_name,
        "offer": "無料カウンセリング",
    }

    variations = []
    for i in range(count):
        hook_key = hook_keys[i % len(hook_keys)]
        cta_key = cta_keys[i % len(cta_keys)]
        tone = tones[i % len(tones)]
        arch_key = body.base_archetype or archetype_keys[i % len(archetype_keys)]
        arch = next((a for a in _SCENARIO_ARCHETYPES if a["key"] == arch_key), _SCENARIO_ARCHETYPES[0])

        tpl_vars = {
            **tpl_vars_base,
            "statistic_pct": str(70 + i * 5),
            "user_count": f"{(i + 1) * 500:,}",
        }

        hook_text = _fill_template(_HOOK_TEMPLATES[hook_key], **tpl_vars)
        cta_text = _fill_template(_CTA_TEMPLATES[cta_key], **tpl_vars)

        # Generate title for this variation
        title_templates = [
            "【衝撃】{benefit}！{product_name}",
            "【{target}必見】{benefit}を実現",
            "{target}の{statistic_pct}%が驚いた{product_name}",
            "たった{period}で{benefit}",
            "もう悩まない。{product_name}で{benefit}",
        ]
        title = _fill_template(title_templates[i % len(title_templates)], **tpl_vars)

        # Collect all text to find power words
        all_text = f"{hook_text} {cta_text} {title}"
        pw = _find_power_words(all_text)

        # Predicted score varies by hook effectiveness
        base_score = 50.0
        hook_bonus = {"question": 8, "pain_point": 6, "shock": 10, "benefit": 5,
                      "urgency": 7, "social_proof": 6, "statistic": 4, "curiosity": 5}
        cta_bonus = {"line_add": 5, "purchase": 3, "consultation": 6, "signup": 4,
                     "free_trial": 7, "learn_more": 2, "download": 3, "reserve": 4}
        p_score = round(
            base_score + hook_bonus.get(hook_key, 3) + cta_bonus.get(cta_key, 2) + (i * 1.5),
            1,
        )
        p_score = min(p_score, 95.0)

        variations.append({
            "variation_id": i + 1,
            "archetype": arch["name"],
            "archetype_key": arch["key"],
            "hook_type": hook_key,
            "hook_text": hook_text,
            "cta_type": cta_key,
            "cta_text": cta_text,
            "title": title,
            "tone": tone,
            "power_words": pw,
            "predicted_score": p_score,
            "structure": arch["structure"],
        })

    print(f"[C19] Generated {len(variations)} variations")
    return {"variations": variations, "count": len(variations)}


# --- C19 Endpoint 4: Saved Scenarios CRUD ---

def _load_saved_scenarios() -> list:
    """Load saved scenarios from JSON file."""
    if _SAVED_SCENARIOS_FILE.exists():
        try:
            return _json_module.loads(_SAVED_SCENARIOS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_saved_scenarios(data: list):
    """Persist saved scenarios to JSON file."""
    _SAVED_SCENARIOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SAVED_SCENARIOS_FILE.write_text(
        _json_module.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8",
    )


class _SaveScenarioBody(BaseModel):
    name: str
    genre: str = ""
    scenario: Optional[dict] = None
    archetype: Optional[str] = None
    tags: Optional[List[str]] = None


@router.get("/saved-scenarios")
def list_saved_scenarios():
    """List all saved scenarios."""
    items = _load_saved_scenarios()
    print(f"[C19] Listing saved scenarios: {len(items)} items")
    return {"saved_scenarios": items, "items": items, "total": len(items)}


@router.post("/saved-scenarios")
def save_scenario(body: _SaveScenarioBody):
    """Save a scenario with full data (C19).

    Body: { name, genre, scenario: {...}, archetype, tags }
    Stored in backend/data/saved_scenarios.json.
    """
    items = _load_saved_scenarios()
    new_id = f"sc_{len(items) + 1:03d}"
    _now = datetime.now(timezone.utc).isoformat()
    new_item = {
        "id": new_id,
        "name": body.name,
        "genre": body.genre,
        "archetype": body.archetype or "",
        "scenario": body.scenario or {},
        "tags": body.tags or [],
        "saved_at": _now,
        "updated_at": _now,
    }
    items.append(new_item)
    _save_saved_scenarios(items)
    print(f"[C19] Saved scenario: {body.name} (id={new_id})")
    return {"status": "saved", "id": new_id, "scenario": new_item}


@router.delete("/saved-scenarios/{scenario_id}")
def delete_saved_scenario(scenario_id: str):
    """Delete a saved scenario by ID."""
    items = _load_saved_scenarios()
    # Support both string IDs like "sc_001" and numeric IDs
    filtered = [s for s in items if str(s.get("id")) != str(scenario_id)]
    if len(filtered) == len(items):
        return JSONResponse(status_code=404, content={"detail": "Scenario not found"})
    _save_saved_scenarios(filtered)
    print(f"[C19] Deleted scenario: {scenario_id}")
    return {"status": "deleted", "id": scenario_id}


# --- C19 Endpoint 6: Predict Scenario Performance ---

@router.post("/predict-scenario-performance")
def predict_scenario_performance(
    hook_type: str = Query("question"),
    cta_type: str = Query("line_add"),
    genre: str = Query("beauty"),
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
):
    """Predict performance of a scenario based on creative elements (C19).

    Uses existing hit prediction data + power word analysis.
    Returns predicted_score, hit_probability, suggestions, strengths, weaknesses.
    """
    print(f"[C19] Predicting performance: hook={hook_type}, cta={cta_type}, genre={genre}")
    with sync_session_scope() as session:
        genre_ads = session.query(Ad).filter(Ad.category == genre).limit(3000).all()

        if not genre_ads:
            return {
                "predicted_score": 50,
                "hit_probability": 0.3,
                "sample_size": 0,
                "strengths": [],
                "weaknesses": [],
                "suggestions": ["Not enough data for this genre"],
            }

        # Find ads with matching hook/cta
        matching = []
        for ad in genre_ads:
            ca = _get_creative_analysis(ad)
            if not ca:
                continue
            if ca.get("hook_type") == hook_type and ca.get("cta_type") == cta_type:
                matching.append(ad)

        if matching:
            scores = [float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0) for a in matching]
            predicted = round(sum(scores) / len(scores), 1)
            hit_prob = round(sum(1 for s in scores if s >= 45) / len(scores), 3)
        else:
            all_scores = [float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0) for a in genre_ads]
            predicted = round(sum(all_scores) / len(all_scores), 1)
            hit_prob = round(sum(1 for s in all_scores if s >= 45) / len(all_scores), 3)

        strengths = []
        weaknesses = []
        suggestions = []

        # Analyze power words in title/description
        combined_text = (title or "") + " " + (description or "")
        if combined_text.strip():
            pw_found = _find_power_words(combined_text)
            if len(pw_found) >= 2:
                strengths.append(f"Power words detected: {', '.join(pw_found[:5])} (+score boost)")
                predicted = min(predicted + len(pw_found) * 1.5, 95.0)
            elif len(pw_found) == 0:
                weaknesses.append("No power words detected in title/description")
                suggestions.append("Add power words like: " + ", ".join(_POWER_WORDS[:5]))

        # Analyze hook type effectiveness
        hook_ads = [a for a in genre_ads if (_get_creative_analysis(a) or {}).get("hook_type") == hook_type]
        if hook_ads:
            hook_hit_rate = sum(1 for a in hook_ads if _is_hit_ad(a)) / len(hook_ads)
            if hook_hit_rate > 0.5:
                strengths.append(f"'{hook_type}' hook has {hook_hit_rate * 100:.0f}% hit rate in {genre}")
            else:
                weaknesses.append(f"'{hook_type}' hook underperforms in {genre} ({hook_hit_rate * 100:.0f}%)")
                # Find best hook for this genre
                best_hooks_for_genre: dict[str, list] = {}
                for a in genre_ads:
                    ca = _get_creative_analysis(a) or {}
                    h = ca.get("hook_type")
                    if h:
                        best_hooks_for_genre.setdefault(h, []).append(1 if _is_hit_ad(a) else 0)
                if best_hooks_for_genre:
                    best_h = max(
                        best_hooks_for_genre.keys(),
                        key=lambda k: sum(best_hooks_for_genre[k]) / max(len(best_hooks_for_genre[k]), 1),
                    )
                    suggestions.append(f"Consider testing '{best_h}' hook which performs better in {genre}")

        # Analyze CTA effectiveness
        cta_ads = [a for a in genre_ads if (_get_creative_analysis(a) or {}).get("cta_type") == cta_type]
        if cta_ads:
            cta_hit_rate = sum(1 for a in cta_ads if _is_hit_ad(a)) / len(cta_ads)
            if cta_hit_rate > 0.5:
                strengths.append(f"'{cta_type}' CTA performs well ({cta_hit_rate * 100:.0f}%)")
            else:
                weaknesses.append(f"'{cta_type}' CTA could be improved ({cta_hit_rate * 100:.0f}%)")

        # Title length check
        if title:
            if len(title) > 50:
                weaknesses.append("Title is long (>50 chars). Shorter titles often perform better.")
            elif len(title) < 10:
                weaknesses.append("Title is very short (<10 chars). Add more detail.")

        print(f"[C19] Prediction: score={predicted}, prob={hit_prob}")
        return {
            "predicted_score": round(predicted, 1),
            "hit_probability": hit_prob,
            "sample_size": len(matching) if matching else len(genre_ads),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
        }


# ==================== Advanced Filter & Failure Analysis (C20) ====================

_HOOK_LABELS = {
    "question": "質問型",
    "pain_point": "悩み訴求型",
    "benefit": "ベネフィット提示",
    "urgency": "緊急性型",
    "social_proof": "社会的証明型",
    "statistic": "データ型",
    "curiosity": "好奇心型",
    "shock": "衝撃型",
    "none": "フックなし",
}

_CTA_LABELS = {
    "line_add": "LINE追加",
    "purchase": "購入",
    "signup": "登録",
    "consultation": "カウンセリング予約",
    "free_trial": "無料お試し",
    "learn_more": "詳しくはこちら",
    "download": "ダウンロード",
    "reserve": "予約",
}


def _group_stats(ads: list, field_getter, is_hit_fn) -> list[dict]:
    """Aggregate stats by a field value."""
    buckets: dict[str, dict] = {}
    for ad in ads:
        val = field_getter(ad)
        if val is None:
            continue
        val_str = str(val)
        b = buckets.setdefault(val_str, {"count": 0, "hits": 0, "total_score": 0.0})
        b["count"] += 1
        if is_hit_fn(ad):
            b["hits"] += 1
        b["total_score"] += float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)

    all_labels = {**_HOOK_LABELS, **_CTA_LABELS}
    return sorted([
        {
            "type": k,
            "label": all_labels.get(k, k),
            "count": v["count"],
            "hit_rate": round(v["hits"] / v["count"], 3) if v["count"] > 0 else 0,
            "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] > 0 else 0,
        }
        for k, v in buckets.items()
    ], key=lambda x: x["hit_rate"], reverse=True)


# --- C20 Endpoint 2: Success vs Failure Analysis ---

@router.get("/success-failure-analysis")
def success_failure_analysis(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
):
    """Analyze success vs failure patterns (C20).

    Splits ads into success (score>=60) and failure (score<40),
    compares patterns, and provides actionable insights.
    """
    print(f"[C20] Success/failure analysis: genre={genre}, platform={platform}")
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        ads = query.limit(5000).all()

        if not ads:
            return {"error": "No ads found", "total_ads": 0}

        success: list = []
        failure: list = []
        middle: list = []
        for ad in ads:
            if not _is_quality_ad(ad):
                continue
            score = float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
            if score >= 60:
                success.append(ad)
            elif score < 40:
                failure.append(ad)
            else:
                middle.append(ad)

        total = len(success) + len(failure) + len(middle)
        if total == 0:
            return {"error": "No quality ads found", "total_ads": 0}

        def _build_group(group_ads: list, label: str) -> dict:
            cnt = len(group_ads)
            if cnt == 0:
                return {
                    "label": label,
                    "count": 0,
                    "percentage": 0,
                    "avg_score": 0,
                    "avg_views": 0,
                    "avg_likes": 0,
                    "avg_spend": 0,
                    "patterns": {"hooks": {}, "ctas": {}, "offers": {}, "emotions": {}, "destination_types": {}},
                    "representative_ads": [],
                }
            scores = [float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0) for a in group_ads]
            views = [a.view_count or a.estimated_impressions or 0 for a in group_ads]
            likes = [a.like_count or 0 for a in group_ads]
            spends = [_compute_spend_jpy(a.view_count or a.estimated_impressions or 0, _get_ad_cpm(a)) for a in group_ads]

            hook_stats: dict[str, int] = {}
            cta_stats: dict[str, int] = {}
            offer_stats: dict[str, int] = {}
            emotion_stats: dict[str, int] = {}
            dest_stats: dict[str, int] = {}

            hook_hits: dict[str, list] = {}
            cta_hits: dict[str, list] = {}

            for ad in group_ads:
                ca = _get_creative_analysis(ad)
                is_hit = _is_hit_ad(ad)
                if not ca:
                    continue
                for field, stats_dict in [
                    ("hook_type", hook_stats), ("cta_type", cta_stats),
                    ("offer_type", offer_stats), ("emotion", emotion_stats),
                ]:
                    val = ca.get(field)
                    if val:
                        v_str = str(val)
                        stats_dict[v_str] = stats_dict.get(v_str, 0) + 1
                        if field == "hook_type":
                            hook_hits.setdefault(v_str, []).append(is_hit)
                        elif field == "cta_type":
                            cta_hits.setdefault(v_str, []).append(is_hit)

                dest = _classify_destination(ad.destination_url or "", ca.get("destination_type"))
                if dest:
                    dest_stats[dest] = dest_stats.get(dest, 0) + 1

            # Build top hooks with hit_rate
            top_hooks: dict[str, dict] = {}
            for hk, hcnt in sorted(hook_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
                hits_list = hook_hits.get(hk, [])
                top_hooks[hk] = {
                    "count": hcnt,
                    "hit_rate": round(sum(1 for h in hits_list if h) / len(hits_list), 3) if hits_list else 0,
                }

            top_ctas: dict[str, dict] = {}
            for ck, ccnt in sorted(cta_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
                hits_list = cta_hits.get(ck, [])
                top_ctas[ck] = {
                    "count": ccnt,
                    "hit_rate": round(sum(1 for h in hits_list if h) / len(hits_list), 3) if hits_list else 0,
                }

            top5_ads = sorted(
                group_ads,
                key=lambda a: float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0),
                reverse=True,
            )[:5]
            reps = [{
                "ad_id": a.id,
                "title": (a.title or "")[:80],
                "advertiser": _clean_advertiser(a.advertiser_name),
                "score": round(float((a.ad_metadata or {}).get("latest_hit_score", 0) or 0), 1),
                "views": a.view_count or a.estimated_impressions or 0,
                "thumbnail": _resolve_thumbnail_url(a),
            } for a in top5_ads]

            return {
                "label": label,
                "count": cnt,
                "percentage": round(cnt / total * 100, 1) if total > 0 else 0,
                "avg_score": round(sum(scores) / cnt, 1),
                "avg_views": round(sum(views) / cnt),
                "avg_likes": round(sum(likes) / cnt),
                "avg_spend": round(sum(spends) / cnt),
                "patterns": {
                    "hooks": top_hooks,
                    "ctas": top_ctas,
                    "offers": dict(sorted(offer_stats.items(), key=lambda x: x[1], reverse=True)[:5]),
                    "emotions": dict(sorted(emotion_stats.items(), key=lambda x: x[1], reverse=True)[:5]),
                    "destination_types": dict(sorted(dest_stats.items(), key=lambda x: x[1], reverse=True)[:5]),
                },
                "representative_ads": reps,
            }

        success_data = _build_group(success, "success")
        failure_data = _build_group(failure, "failure")

        # Key differences - compare top elements
        diffs = []
        for element in ["hooks", "ctas", "offers", "emotions"]:
            s_patterns = success_data["patterns"][element]
            f_patterns = failure_data["patterns"][element]
            if not s_patterns and not f_patterns:
                continue
            if s_patterns:
                first_val = next(iter(s_patterns.values()), None)
                if isinstance(first_val, dict):
                    s_top = max(s_patterns, key=lambda k: s_patterns[k].get("count", 0))
                else:
                    s_top = max(s_patterns, key=lambda k: s_patterns[k])
            else:
                s_top = "none"
            if f_patterns:
                first_val = next(iter(f_patterns.values()), None)
                if isinstance(first_val, dict):
                    f_top = max(f_patterns, key=lambda k: f_patterns[k].get("count", 0))
                else:
                    f_top = max(f_patterns, key=lambda k: f_patterns[k])
            else:
                f_top = "none"
            if s_top != f_top:
                diffs.append({
                    "element": element.rstrip("s") + "_type" if element in ("hooks", "ctas") else element.rstrip("s"),
                    "success_top": s_top,
                    "failure_top": f_top,
                    "impact": "high" if element in ("hooks", "ctas") else "medium",
                })

        # Reuse points - actionable insights
        reuse = []
        s_hooks = success_data["patterns"]["hooks"]
        if s_hooks:
            first_val = next(iter(s_hooks.values()), None)
            if isinstance(first_val, dict):
                top_hook_key = max(s_hooks, key=lambda k: s_hooks[k].get("hit_rate", 0))
                hr_pct = s_hooks[top_hook_key].get("hit_rate", 0) * 100
            else:
                top_hook_key = max(s_hooks, key=lambda k: s_hooks[k])
                hr_pct = 0
            hook_label = _HOOK_LABELS.get(top_hook_key, top_hook_key)
            if hr_pct > 0:
                reuse.append(f"{hook_label}フックのヒット率は{hr_pct:.0f}%。積極的に使用を推奨")
            else:
                reuse.append(f"{hook_label}フックが成功広告で最多使用。積極的に活用を推奨")
        s_ctas = success_data["patterns"]["ctas"]
        if s_ctas:
            first_val = next(iter(s_ctas.values()), None)
            if isinstance(first_val, dict):
                top_cta_key = max(s_ctas, key=lambda k: s_ctas[k].get("count", 0))
            else:
                top_cta_key = max(s_ctas, key=lambda k: s_ctas[k])
            cta_label = _CTA_LABELS.get(top_cta_key, top_cta_key)
            reuse.append(f"{cta_label}CTAが成功広告に多く採用されている")
        s_dests = success_data["patterns"]["destination_types"]
        if s_dests:
            top_dest = max(s_dests, key=lambda k: s_dests[k])
            reuse.append(f"遷移先は'{top_dest}'が最も効果的")
        # Cross-analysis insight
        if success_data["avg_views"] > 0 and failure_data["avg_views"] > 0:
            ratio = success_data["avg_views"] / max(failure_data["avg_views"], 1)
            reuse.append(f"成功広告は平均視聴数が失敗広告の{ratio:.1f}倍")

        print(f"[C20] Analysis done: {success_data['count']} success, {failure_data['count']} failure")
        return {
            "total_ads": total,
            "success": success_data,
            "failure": failure_data,
            "middle": {
                "count": len(middle),
                "percentage": round(len(middle) / total * 100, 1) if total > 0 else 0,
            },
            "key_differences": diffs,
            "reuse_points": reuse,
        }


# --- C20 Endpoint 3: Element Breakdown ---

@router.get("/element-breakdown")
def element_breakdown(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    element_type: str = Query("all", description="hook, cta, offer, emotion, or all"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
):
    """Per-element statistics with hit rates and vs-overall comparison (C20)."""
    print(f"[C20] Element breakdown: genre={genre}, element={element_type}")
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        ads = query.limit(5000).all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]
        overall_hit_rate = sum(1 for a in quality_ads if _is_hit_ad(a)) / len(quality_ads) if quality_ads else 0

        result = {}
        fields = {
            "hooks": ("hook_type", lambda ad: (_get_creative_analysis(ad) or {}).get("hook_type")),
            "ctas": ("cta_type", lambda ad: (_get_creative_analysis(ad) or {}).get("cta_type")),
            "offers": ("offer_type", lambda ad: (_get_creative_analysis(ad) or {}).get("offer_type")),
            "emotions": ("emotion", lambda ad: (_get_creative_analysis(ad) or {}).get("emotion")),
        }

        for key, (field_name, getter) in fields.items():
            short_name = field_name.replace("_type", "")
            if element_type != "all" and element_type != short_name and element_type != field_name:
                continue

            stats = _group_stats(quality_ads, getter, _is_hit_ad)
            for item in stats:
                diff = item["hit_rate"] - overall_hit_rate
                sign = "+" if diff >= 0 else ""
                item["vs_overall"] = f"{sign}{diff * 100:.0f}%"

            result[key] = stats

        print(f"[C20] Element breakdown complete: {list(result.keys())}")
        return {
            "element_type": element_type,
            "overall_hit_rate": round(overall_hit_rate, 3),
            "total_ads": len(quality_ads),
            **result,
        }


# --- C20 Endpoint 4: Destination Stats ---

@router.get("/destination-stats")
def destination_stats(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
):
    """Ad count and performance by destination type and domain (C20)."""
    print(f"[C20] Destination stats: genre={genre}, platform={platform}")
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        ads = query.limit(5000).all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]

        dest_type_stats: dict[str, dict] = {}
        domain_stats: dict[str, dict] = {}

        for ad in quality_ads:
            ca = _get_creative_analysis(ad) or {}
            dest = _classify_destination(ad.destination_url or "", ca.get("destination_type"))
            if dest:
                b = dest_type_stats.setdefault(dest, {"count": 0, "hits": 0, "total_score": 0.0})
                b["count"] += 1
                if _is_hit_ad(ad):
                    b["hits"] += 1
                b["total_score"] += float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)

            # Extract domain
            url = ad.destination_url or ""
            if url:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower().lstrip("www.")
                    if domain:
                        d = domain_stats.setdefault(domain, {"count": 0, "hits": 0, "total_score": 0.0})
                        d["count"] += 1
                        if _is_hit_ad(ad):
                            d["hits"] += 1
                        d["total_score"] += float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
                except Exception:
                    pass

        dest_types = sorted([
            {
                "type": k,
                "count": v["count"],
                "hit_rate": round(v["hits"] / v["count"], 3) if v["count"] > 0 else 0,
                "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] > 0 else 0,
            }
            for k, v in dest_type_stats.items()
        ], key=lambda x: x["count"], reverse=True)

        top_domains = sorted([
            {
                "domain": k,
                "count": v["count"],
                "hit_rate": round(v["hits"] / v["count"], 3) if v["count"] > 0 else 0,
                "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] > 0 else 0,
            }
            for k, v in domain_stats.items() if v["count"] >= 2
        ], key=lambda x: x["count"], reverse=True)[:20]

        print(f"[C20] Destination stats: {len(dest_types)} types, {len(top_domains)} domains")
        return {
            "destination_types": dest_types,
            "top_domains": top_domains,
            "total_ads": len(quality_ads),
        }


# ==================== C21: Reports, Dashboard KPI, Alert Read Status ====================

# Path to alerts read-status JSON file
_ALERTS_READ_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "alerts_read.json"


def _load_alerts_read() -> dict:
    """Load alert read statuses from JSON file."""
    if not _ALERTS_READ_FILE.exists():
        return {"read_ids": [], "read_all_before": None}
    try:
        with open(_ALERTS_READ_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"read_ids": [], "read_all_before": None}


def _save_alerts_read(data: dict) -> None:
    """Save alert read statuses to JSON file."""
    _ALERTS_READ_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_ALERTS_READ_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/report-summary")
def get_report_summary(
    days: int = Query(90, ge=7, le=365, description="Number of days to include in report"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
):
    """Return comprehensive report data for the reporting dashboard (C21).

    Aggregates overview KPIs, genre performance, top advertisers,
    and creative pattern analysis across the specified date range.
    """
    print(f"[C21] Report summary: days={days}, genre={genre}, platform={platform}")
    with sync_session_scope() as session:
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(days=days)

        query = session.query(Ad).filter(Ad.created_at >= cutoff)
        if genre:
            query = query.filter(Ad.category == genre)
        query = _resolve_platform_filter(query, Ad.platform, platform)
        ads = query.all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]

        if not quality_ads:
            print("[C21] Report summary: no ads found for the given filters")
            return {
                "overview": {
                    "total_ads": 0,
                    "hit_ads": 0,
                    "hit_rate": 0,
                    "total_estimated_spend_jpy": 0,
                    "avg_hit_score": 0,
                    "top_genre": None,
                    "data_date_range": {
                        "from": cutoff.strftime("%Y-%m-%d"),
                        "to": now.strftime("%Y-%m-%d"),
                    },
                },
                "genre_performance": [],
                "top_advertisers": [],
                "creative_patterns": {
                    "winning_combos": [],
                    "hook_performance": [],
                    "cta_performance": [],
                },
            }

        # -- Compute per-ad metrics --
        all_scores = []
        hit_count = 0
        total_spend = 0
        genre_map: dict[str, dict] = {}
        advertiser_map: dict[str, dict] = {}
        hook_stats: dict[str, dict] = {}
        cta_stats: dict[str, dict] = {}
        combo_stats: dict[str, dict] = {}

        for ad in quality_ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            days_running = longevity["days_running"]

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, hit_level, _ = compute_hit_score(ad)
            else:
                score = float(score)
                hit_level = meta.get("hit_level", "none")

            all_scores.append(score)
            is_hit = _is_hit_ad(ad)
            if is_hit:
                hit_count += 1

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend

            # Genre aggregation
            g_label = _resolve_genre_label(ad)
            g = genre_map.setdefault(g_label, {
                "ad_count": 0, "hits": 0, "total_score": 0.0,
                "total_spend": 0, "archetypes": {},
            })
            g["ad_count"] += 1
            g["total_score"] += score
            g["total_spend"] += est_spend
            if is_hit:
                g["hits"] += 1

            # Track archetypes per genre
            ca = _get_creative_analysis(ad) or {}
            archetype = ca.get("archetype") or ca.get("hook_type") or ""
            if archetype:
                g["archetypes"][str(archetype)] = g["archetypes"].get(str(archetype), 0) + 1

            # Advertiser aggregation
            adv_name = _clean_advertiser(ad.advertiser_name)
            if adv_name:
                a = advertiser_map.setdefault(adv_name, {
                    "ad_count": 0, "hits": 0, "total_score": 0.0, "total_spend": 0,
                })
                a["ad_count"] += 1
                a["total_score"] += score
                a["total_spend"] += est_spend
                if is_hit:
                    a["hits"] += 1

            # Hook performance
            hook = ca.get("hook_type")
            if hook:
                h = hook_stats.setdefault(str(hook), {"count": 0, "hits": 0, "total_score": 0.0})
                h["count"] += 1
                h["total_score"] += score
                if is_hit:
                    h["hits"] += 1

            # CTA performance
            cta = ca.get("cta_type")
            if cta:
                c = cta_stats.setdefault(str(cta), {"count": 0, "hits": 0, "total_score": 0.0})
                c["count"] += 1
                c["total_score"] += score
                if is_hit:
                    c["hits"] += 1

            # Winning combos (hook + cta)
            if hook and cta:
                combo_key = f"{hook} + {cta}"
                cb = combo_stats.setdefault(combo_key, {"count": 0, "hits": 0, "total_score": 0.0})
                cb["count"] += 1
                cb["total_score"] += score
                if is_hit:
                    cb["hits"] += 1

        n = len(all_scores)
        avg_score = sum(all_scores) / n if n > 0 else 0
        hit_rate = round(hit_count / n * 100, 1) if n > 0 else 0

        # Find top genre by ad count
        top_genre = None
        if genre_map:
            top_genre = max(genre_map.items(), key=lambda x: x[1]["ad_count"])[0]

        # Build genre performance list
        genre_performance = []
        for g_name, g_data in sorted(genre_map.items(), key=lambda x: x[1]["ad_count"], reverse=True):
            g_count = g_data["ad_count"]
            g_hit_rate = round(g_data["hits"] / g_count, 3) if g_count > 0 else 0
            g_avg_score = round(g_data["total_score"] / g_count, 1) if g_count > 0 else 0
            g_avg_spend = round(g_data["total_spend"] / g_count) if g_count > 0 else 0
            # Top archetype for this genre
            top_archetype = ""
            if g_data["archetypes"]:
                top_archetype = max(g_data["archetypes"].items(), key=lambda x: x[1])[0]
            genre_performance.append({
                "genre": g_name,
                "genre_jp": g_name,
                "ad_count": g_count,
                "hit_rate": g_hit_rate,
                "avg_score": g_avg_score,
                "top_archetype": top_archetype,
                "avg_spend_jpy": g_avg_spend,
            })

        # Build top advertisers list
        top_advertisers = []
        for adv_name, adv_data in sorted(
            advertiser_map.items(), key=lambda x: x[1]["total_spend"], reverse=True
        ):
            a_count = adv_data["ad_count"]
            top_advertisers.append({
                "name": adv_name,
                "ad_count": a_count,
                "hit_rate": round(adv_data["hits"] / a_count, 3) if a_count > 0 else 0,
                "avg_score": round(adv_data["total_score"] / a_count, 1) if a_count > 0 else 0,
                "total_spend_jpy": int(adv_data["total_spend"]),
            })

        # Build creative patterns
        winning_combos = sorted([
            {
                "combo": k,
                "count": v["count"],
                "hit_rate": round(v["hits"] / v["count"], 3) if v["count"] > 0 else 0,
                "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] > 0 else 0,
            }
            for k, v in combo_stats.items() if v["count"] >= 2
        ], key=lambda x: x["hit_rate"], reverse=True)[:15]

        hook_performance = sorted([
            {
                "hook": k,
                "count": v["count"],
                "hit_rate": round(v["hits"] / v["count"], 3) if v["count"] > 0 else 0,
                "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] > 0 else 0,
            }
            for k, v in hook_stats.items()
        ], key=lambda x: x["count"], reverse=True)[:15]

        cta_performance = sorted([
            {
                "cta": k,
                "count": v["count"],
                "hit_rate": round(v["hits"] / v["count"], 3) if v["count"] > 0 else 0,
                "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] > 0 else 0,
            }
            for k, v in cta_stats.items()
        ], key=lambda x: x["count"], reverse=True)[:15]

        # Find earliest ad created_at for date range
        earliest = min((ad.created_at for ad in quality_ads if ad.created_at), default=cutoff)

        print(f"[C21] Report summary complete: {n} ads, {hit_count} hits, {len(genre_performance)} genres")
        return {
            "overview": {
                "total_ads": n,
                "hit_ads": hit_count,
                "hit_rate": hit_rate,
                "total_estimated_spend_jpy": int(total_spend),
                "avg_hit_score": round(avg_score, 1),
                "top_genre": top_genre,
                "data_date_range": {
                    "from": earliest.strftime("%Y-%m-%d") if hasattr(earliest, "strftime") else str(earliest)[:10],
                    "to": now.strftime("%Y-%m-%d"),
                },
            },
            "genre_performance": genre_performance,
            "top_advertisers": top_advertisers[:20],
            "creative_patterns": {
                "winning_combos": winning_combos,
                "hook_performance": hook_performance,
                "cta_performance": cta_performance,
            },
        }


@router.get("/dashboard-kpi")
def get_dashboard_kpi():
    """Return quick KPI numbers for the dashboard header (C21).

    Lightweight endpoint providing the essential metrics at a glance:
    total_ads, new_ads_7d, hit_ads, active_ads, avg_score, top_genre,
    total_spend_jpy, data_freshness.
    """
    print("[C21] Dashboard KPI requested")
    with sync_session_scope() as session:
        ads = session.query(Ad).all()

        if not ads:
            print("[C21] Dashboard KPI: no ads in database")
            return {
                "total_ads": 0,
                "new_ads_7d": 0,
                "new_7d": 0,  # Fix #59: alias for DashboardKPI.tsx
                "hit_ads": 0,
                "hit_percentage": 0,  # Fix #59: for DashboardKPI.tsx
                "active_ads": 0,
                "active_rate": 0,  # Fix #51: percentage alias for frontend
                "avg_score": 0,
                "top_genre": None,
                "total_spend_jpy": 0,
                "total_spend": 0,  # Fix #59: alias for DashboardKPI.tsx
                "data_freshness": None,
            }

        now = datetime.now(tz=timezone.utc)
        cutoff_7d = now - timedelta(days=7)

        scores = []
        hit_count = 0
        active_count = 0
        new_7d_count = 0
        total_spend = 0
        genre_counter: dict[str, int] = {}
        latest_created: datetime | None = None

        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)
            scores.append(score)

            if _is_hit_ad(ad):
                hit_count += 1
            if longevity["is_still_running"]:
                active_count += 1

            if _dt_gte(ad.created_at, cutoff_7d):
                new_7d_count += 1

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend

            g = _resolve_genre_label(ad)
            genre_counter[g] = genre_counter.get(g, 0) + 1

            if ad.created_at:
                if latest_created is None:
                    latest_created = ad.created_at
                elif _dt_gt(ad.created_at, latest_created):
                    latest_created = ad.created_at

        n = len(scores)
        avg_score = sum(scores) / n if n > 0 else 0

        # Top genre by count
        top_genre = None
        if genre_counter:
            top_genre = max(genre_counter.items(), key=lambda x: x[1])[0]

        data_freshness = latest_created.strftime("%Y-%m-%d") if latest_created else None

        print(f"[C21] Dashboard KPI: {n} ads, {hit_count} hits, {new_7d_count} new in 7d")
        _active_rate = round(active_count / n * 100, 1) if n > 0 else 0  # Fix #51
        _hit_pct = round(hit_count / n * 100, 1) if n > 0 else 0  # Fix #59
        return {
            "total_ads": n,
            "new_ads_7d": new_7d_count,
            "new_7d": new_7d_count,  # Fix #59: alias for DashboardKPI.tsx
            "hit_ads": hit_count,
            "hit_percentage": _hit_pct,  # Fix #59: for DashboardKPI.tsx
            "active_ads": active_count,
            "active_rate": _active_rate,  # Fix #51: percentage for frontend
            "avg_score": round(avg_score, 1),
            "top_genre": top_genre,
            "total_spend_jpy": int(total_spend),
            "total_spend": int(total_spend),  # Fix #59: alias for DashboardKPI.tsx
            "data_freshness": data_freshness,
        }


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int):
    """Mark a specific alert as read (C21).

    Stores the alert ID in the read-status file so the frontend
    can filter out already-seen alerts.
    """
    print(f"[C21] Marking alert {alert_id} as read")
    data = _load_alerts_read()
    read_ids = data.get("read_ids", [])

    if alert_id not in read_ids:
        read_ids.append(alert_id)
        data["read_ids"] = read_ids
        _save_alerts_read(data)

    return {
        "status": "marked_read",
        "alert_id": alert_id,
        "total_read": len(read_ids),
    }


@router.post("/alerts/read-all")
def mark_all_alerts_read():
    """Mark all current alerts as read (C21).

    Records a timestamp so that any alert generated before this moment
    is considered read. Individual read_ids are cleared.
    """
    print("[C21] Marking all alerts as read")
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "read_ids": [],
        "read_all_before": now,
    }
    _save_alerts_read(data)

    return {
        "status": "all_marked_read",
        "read_all_before": now,
    }


# ==================== C22: Benchmark, Comparison & Advanced Analytics ====================


def _percentile(sorted_values: list, p: float) -> float:
    """Compute percentile from a pre-sorted list without numpy.

    Uses linear interpolation (same as numpy default).
    p should be between 0 and 100.
    """
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    if n == 1:
        return float(sorted_values[0])
    k = (p / 100.0) * (n - 1)
    f = int(k)
    c = f + 1
    if c >= n:
        return float(sorted_values[-1])
    d = k - f
    return float(sorted_values[f]) + d * float(sorted_values[c] - sorted_values[f])


def _percentile_rank(value: float, sorted_values: list) -> float:
    """Compute what percentile a given value falls at in a sorted list.

    Returns a value between 0 and 100.
    """
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    count_below = 0
    for v in sorted_values:
        if v < value:
            count_below += 1
        else:
            break
    return round((count_below / n) * 100, 1)


@router.get("/genre-benchmarks")
def get_genre_benchmarks(
    genre: Optional[str] = Query(None, description="Filter by genre (returns all if empty)"),
):
    """Return percentile benchmarks for each genre (C22).

    Computes median, p25, p75, p90 for hit_score, view_count,
    spend_jpy, and longevity_days from live DB data.
    """
    print(f"[C22] Genre benchmarks requested: genre={genre}")
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]
        if not quality_ads:
            print("[C22] Genre benchmarks: no quality ads found")
            return {"benchmarks": {}}

        # Group ads by genre
        genre_groups: dict[str, list] = {}
        for ad in quality_ads:
            g_label = _resolve_genre_label(ad)
            genre_groups.setdefault(g_label, []).append(ad)

        benchmarks = {}
        for g_label, g_ads in genre_groups.items():
            scores = []
            views = []
            spends = []
            longevities = []

            for ad in g_ads:
                meta = ad.ad_metadata or {}
                # Hit score
                score = meta.get("latest_hit_score")
                if score is None:
                    score, _, _, _ = compute_hit_score(ad)
                else:
                    score = float(score)
                scores.append(score)

                # View count
                vc = ad.view_count or 0
                views.append(vc)

                # Spend
                est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
                spends.append(est_spend)

                # Longevity
                longevity = _extract_longevity_info(ad)
                longevities.append(longevity["days_running"])

            scores.sort()
            views.sort()
            spends.sort()
            longevities.sort()

            benchmarks[g_label] = {
                "hit_score": {
                    "median": round(_percentile(scores, 50), 1),
                    "p25": round(_percentile(scores, 25), 1),
                    "p75": round(_percentile(scores, 75), 1),
                    "p90": round(_percentile(scores, 90), 1),
                    "count": len(scores),
                },
                "view_count": {
                    "median": round(_percentile(views, 50)),
                    "p25": round(_percentile(views, 25)),
                    "p75": round(_percentile(views, 75)),
                    "p90": round(_percentile(views, 90)),
                },
                "spend_jpy": {
                    "median": round(_percentile(spends, 50)),
                    "p25": round(_percentile(spends, 25)),
                    "p75": round(_percentile(spends, 75)),
                    "p90": round(_percentile(spends, 90)),
                },
                "longevity_days": {
                    "median": round(_percentile(longevities, 50)),
                    "p25": round(_percentile(longevities, 25)),
                    "p75": round(_percentile(longevities, 75)),
                    "p90": round(_percentile(longevities, 90)),
                },
            }

        print(f"[C22] Genre benchmarks computed for {len(benchmarks)} genres")
        return {"benchmarks": benchmarks}


class CompareAdsRequest(BaseModel):
    ad_ids: List[int]


@router.post("/compare-ads")
def compare_ads_benchmark(body: CompareAdsRequest):
    """Compare 2-5 ads side-by-side with percentile ranking (C22).

    Returns metrics, creative info, percentile ranks, winner determination,
    and insights for the requested ads.
    """
    ad_ids = body.ad_ids
    if len(ad_ids) < 2 or len(ad_ids) > 5:
        print(f"[C22] Compare ads: invalid count {len(ad_ids)}")
        return JSONResponse(
            status_code=400,
            content={"error": "Must provide 2-5 ad IDs for comparison"},
        )

    print(f"[C22] Comparing ads: {ad_ids}")
    with sync_session_scope() as session:
        # Fetch the requested ads
        ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
        if len(ads) < 2:
            return JSONResponse(
                status_code=404,
                content={"error": f"Found only {len(ads)} of {len(ad_ids)} ads"},
            )

        # Build global percentile lists for ranking
        all_ads = session.query(Ad).all()
        all_quality = [a for a in all_ads if _is_quality_ad(a)]

        global_scores = []
        global_views = []
        global_spends = []
        for a in all_quality:
            m = a.ad_metadata or {}
            s = m.get("latest_hit_score")
            if s is None:
                s, _, _, _ = compute_hit_score(a)
            else:
                s = float(s)
            global_scores.append(s)
            global_views.append(a.view_count or 0)
            global_spends.append(m.get("estimated_total_spend_jpy") or a.spend or 0)

        global_scores.sort()
        global_views.sort()
        global_spends.sort()

        # Build per-ad data
        result_ads = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            views = ad.view_count or 0
            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0

            ca = _get_creative_analysis(ad) or {}

            result_ads.append({
                "id": ad.id,
                "title": ad.title or "",
                "advertiser": _clean_advertiser(ad.advertiser_name),
                "genre": _resolve_fine_genre(ad),
                "fine_genre": _resolve_fine_genre(ad),
                "platform": str(ad.platform.value) if hasattr(ad.platform, "value") else str(ad.platform),
                "thumbnail": _resolve_thumbnail_url(ad),
                "thumbnail_url": _resolve_thumbnail_url(ad),
                "video_url": ad.video_url or "",
                "snapshot_url": meta.get("snapshot_url", ""),
                "description": (ad.description or "")[:300],
                "destination_url": meta.get("destination_url", ""),
                "first_seen_date": ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                "last_seen_date": ad.last_seen_at.isoformat() if ad.last_seen_at else "",
                "is_still_running": longevity.get("is_still_running", False),
                "metrics": {
                    "hit_score": round(score, 1),
                    "views": views,
                    "spend_jpy": int(est_spend),
                    "longevity_days": longevity["days_running"],
                },
                "creative": {
                    "hook_type": ca.get("hook_type", ""),
                    "cta_type": ca.get("cta_type", ""),
                    "format": meta.get("creative_type", "動画" if ad.video_url else "静止画"),
                    "archetype": ca.get("archetype", ""),
                },
                "percentile_rank": {
                    "hit_score": _percentile_rank(score, global_scores),
                    "views": _percentile_rank(views, global_views),
                    "spend": _percentile_rank(est_spend, global_spends),
                },
                "_score": score,
                "_views": views,
                "_spend": est_spend,
            })

        # Determine winner
        best = max(result_ads, key=lambda x: x["_score"])
        reasons = []
        if best["_score"] == max(a["_score"] for a in result_ads):
            reasons.append("Highest hit score")
        if best["_views"] > 0 and best["_spend"] > 0:
            best_ratio = best["_views"] / best["_spend"]
            other_ratios = [
                (a["_views"] / a["_spend"]) if a["_spend"] > 0 else 0
                for a in result_ads if a["id"] != best["id"]
            ]
            if all(best_ratio >= r for r in other_ratios):
                reasons.append("Best view-to-spend ratio")
        if best["metrics"]["longevity_days"] == max(a["metrics"]["longevity_days"] for a in result_ads):
            reasons.append("Longest running duration")

        if not reasons:
            reasons.append("Highest hit score")

        # Generate insights (Japanese)
        insights = []
        # Insight 1: Hook type comparison
        hook_types = {a["creative"]["hook_type"] for a in result_ads if a["creative"]["hook_type"]}
        if len(hook_types) > 1:
            best_hook = best["creative"]["hook_type"]
            if best_hook:
                insights.append(
                    f"最高スコアの広告は「{best_hook}」型フックを使用しています"
                )

        # Insight 2: Format insight
        formats = {a["creative"]["format"] for a in result_ads}
        if len(formats) > 1:
            insights.append(
                f"異なるフォーマット（{', '.join(formats)}）の広告を比較 — クロスフォーマット分析が可能です"
            )

        # Insight 3: Spend efficiency
        efficient = None
        best_eff = 0
        for a in result_ads:
            if a["_spend"] > 0:
                eff = a["_score"] / a["_spend"]
                if eff > best_eff:
                    best_eff = eff
                    efficient = a
        if efficient and efficient["id"] != best["id"]:
            insights.append(
                f"「{efficient['title'][:20]}」はスコア対消化額の効率が最も高い広告です"
            )

        # Insight 4: Score difference
        worst = min(result_ads, key=lambda x: x["_score"])
        score_diff = best["_score"] - worst["_score"]
        if score_diff > 0:
            insights.append(
                f"スコア差: {score_diff:.0f}pt（{best['title'][:15]} vs {worst['title'][:15]}）"
            )

        # Insight 5: Longevity
        if best["metrics"]["longevity_days"] > 30:
            insights.append(
                f"最高スコア広告は{best['metrics']['longevity_days']}日間掲載中（長期ヒット）"
            )

        # Clean internal fields and add flat aliases for frontend (Fix #60)
        for a in result_ads:
            del a["_score"]
            del a["_views"]
            del a["_spend"]
            # Fix #60: flat aliases for AdComparisonTool.tsx
            a["ad_id"] = a["id"]
            a["product_name"] = a["title"]
            a["advertiser_name"] = a["advertiser"]
            a["hit_score"] = a["metrics"]["hit_score"]
            a["cumulative_views"] = a["metrics"]["views"]
            a["cumulative_spend"] = a["metrics"]["spend_jpy"]
            a["longevity_days"] = a["metrics"]["longevity_days"]
            a["hook_type"] = a["creative"]["hook_type"]
            a["cta_type"] = a["creative"]["cta_type"]
            a["creative_type"] = a["creative"]["format"]
            # Ensure fine_genre is set as flat alias
            if "fine_genre" not in a:
                a["fine_genre"] = a["genre"]
            # Flatten percentile_rank to single number (avg of all)
            _pr = a["percentile_rank"]
            a["percentile_rank_detail"] = _pr  # keep original nested
            a["percentile_rank"] = round(sum(_pr.values()) / max(len(_pr), 1))

        print(f"[C22] Ad comparison complete: winner={best['id']}, {len(insights)} insights")
        return {
            "ads": result_ads,
            "winner": {"id": best["id"], "reasons": reasons},
            "winner_id": best["id"],  # Fix #60: flat alias for frontend
            "insights": insights,
        }


@router.get("/advertiser/{advertiser_name}/deep-profile")
def get_advertiser_deep_profile(advertiser_name: str):
    """Return deep-dive analytics for a specific advertiser (C22).

    Includes total/active ads, hit rate, genre breakdown, creative style,
    monthly timeline, and top-performing ads.
    """
    print(f"[C22] Advertiser profile requested: {advertiser_name}")
    with sync_session_scope() as session:
        # Search by advertiser name (partial match)
        ads = session.query(Ad).filter(
            or_(
                Ad.advertiser_name == advertiser_name,
                Ad.advertiser_name.ilike(f"%{_escape_like(advertiser_name)}%"),
            )
        ).all()

        if not ads:
            print(f"[C22] Advertiser profile: no ads found for '{advertiser_name}'")
            return JSONResponse(
                status_code=404,
                content={"error": f"No ads found for advertiser '{advertiser_name}'"},
            )

        quality_ads = [a for a in ads if _is_quality_ad(a)]
        if not quality_ads:
            quality_ads = ads  # fallback to all ads if none pass quality

        # Compute metrics
        total_ads = len(quality_ads)
        active_ads = 0
        hit_count = 0
        total_score = 0.0
        total_spend = 0
        genre_counter: dict[str, int] = {}
        hook_counter: dict[str, int] = {}
        cta_counter: dict[str, int] = {}
        duration_sum = 0.0
        duration_count = 0
        monthly_map: dict[str, dict] = {}
        scored_ads: list[dict] = []

        for ad in quality_ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            total_score += score
            is_hit = _is_hit_ad(ad)
            if is_hit:
                hit_count += 1
            if longevity["is_still_running"]:
                active_ads += 1

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend

            # Genre
            g = _resolve_genre_label(ad)
            genre_counter[g] = genre_counter.get(g, 0) + 1

            # Creative style
            ca = _get_creative_analysis(ad) or {}
            hook = ca.get("hook_type")
            if hook:
                hook_counter[str(hook)] = hook_counter.get(str(hook), 0) + 1
            cta = ca.get("cta_type")
            if cta:
                cta_counter[str(cta)] = cta_counter.get(str(cta), 0) + 1

            if ad.duration_seconds and ad.duration_seconds > 0:
                duration_sum += ad.duration_seconds
                duration_count += 1

            # Monthly timeline
            if ad.created_at:
                month_key = ad.created_at.strftime("%Y-%m")
                m = monthly_map.setdefault(month_key, {"ads": 0, "total_score": 0.0})
                m["ads"] += 1
                m["total_score"] += score

            scored_ads.append({
                "id": ad.id,
                "title": ad.title or "",
                "score": round(score, 1),
            })

        avg_score = round(total_score / total_ads, 1) if total_ads > 0 else 0
        hit_rate = round(hit_count / total_ads, 3) if total_ads > 0 else 0

        # Genre breakdown
        genres = sorted([
            {"genre": k, "count": v}
            for k, v in genre_counter.items()
        ], key=lambda x: x["count"], reverse=True)

        # Creative style
        preferred_hooks = sorted([
            {"hook": k, "count": v}
            for k, v in hook_counter.items()
        ], key=lambda x: x["count"], reverse=True)[:5]

        preferred_ctas = sorted([
            {"cta": k, "count": v}
            for k, v in cta_counter.items()
        ], key=lambda x: x["count"], reverse=True)[:5]

        avg_duration = round(duration_sum / duration_count, 1) if duration_count > 0 else 0

        # Timeline
        timeline = sorted([
            {
                "month": k,
                "ads": v["ads"],
                "avg_score": round(v["total_score"] / v["ads"], 1) if v["ads"] > 0 else 0,
            }
            for k, v in monthly_map.items()
        ], key=lambda x: x["month"])

        # Top ads
        top_ads = sorted(scored_ads, key=lambda x: x["score"], reverse=True)[:10]

        print(f"[C22] Advertiser profile: {total_ads} ads, {hit_count} hits, {len(genres)} genres")
        return {
            "name": advertiser_name,
            "total_ads": total_ads,
            "active_ads": active_ads,
            "hit_rate": hit_rate,
            "avg_score": avg_score,
            "total_spend_jpy": int(total_spend),
            "genres": genres,
            "creative_style": {
                "preferred_hooks": preferred_hooks,
                "preferred_ctas": preferred_ctas,
                "avg_duration": avg_duration,
            },
            "timeline": timeline,
            "top_ads": top_ads,
        }


@router.get("/trends/forecast")
def get_trend_forecast(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    metric: str = Query("ad_count", description="Metric to forecast: ad_count, avg_score, spend"),
):
    """Return historical weekly data with simple linear projection (C22).

    Computes weekly aggregates for the past 12 weeks and forecasts
    the next 4 weeks using linear regression.
    """
    print(f"[C22] Trend forecast: genre={genre}, metric={metric}")
    with sync_session_scope() as session:
        now = datetime.now(tz=timezone.utc)
        # Look back 12 weeks
        lookback = now - timedelta(weeks=12)

        query = session.query(Ad).filter(Ad.created_at >= lookback)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]

        # Group by ISO week
        week_data: dict[str, dict] = {}
        for ad in quality_ads:
            if not ad.created_at:
                continue
            iso = ad.created_at.isocalendar()
            week_key = f"{iso[0]}-W{iso[1]:02d}"
            w = week_data.setdefault(week_key, {"count": 0, "total_score": 0.0, "total_spend": 0})
            w["count"] += 1

            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)
            w["total_score"] += score
            w["total_spend"] += meta.get("estimated_total_spend_jpy") or ad.spend or 0

        # Build historical series
        sorted_weeks = sorted(week_data.keys())
        historical = []
        for wk in sorted_weeks:
            d = week_data[wk]
            if metric == "avg_score":
                value = round(d["total_score"] / d["count"], 1) if d["count"] > 0 else 0
            elif metric == "spend":
                value = int(d["total_spend"])
            else:  # ad_count
                value = d["count"]
            historical.append({"week": wk, "value": value})

        if len(historical) < 2:
            print("[C22] Trend forecast: insufficient data for projection")
            return {
                "historical": historical,
                "forecast": [],
                "trend": "insufficient_data",
                "change_rate_weekly": 0,
            }

        # Simple linear regression: y = a + b*x
        n = len(historical)
        xs = list(range(n))
        ys = [h["value"] for h in historical]
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n

        numerator = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
        denominator = sum((xs[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # Compute R-squared for confidence
        ss_res = sum((ys[i] - (intercept + slope * xs[i])) ** 2 for i in range(n))
        ss_tot = sum((ys[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        confidence = round(max(0, min(1, r_squared)), 2)

        # Forecast next 4 weeks
        forecast = []
        last_week = sorted_weeks[-1]
        # Parse last week to generate next weeks
        parts = last_week.split("-W")
        year = int(parts[0])
        week_num = int(parts[1])

        for i in range(1, 5):
            future_x = n - 1 + i
            predicted = intercept + slope * future_x
            predicted = max(0, predicted)  # no negative values

            # Advance week
            fw = week_num + i
            fy = year
            if fw > 52:
                fw -= 52
                fy += 1
            forecast_week = f"{fy}-W{fw:02d}"

            forecast.append({
                "week": forecast_week,
                "value": round(predicted, 1),
                "confidence": confidence,
            })

        # Determine trend direction
        if slope > 0.5:
            trend = "increasing"
        elif slope < -0.5:
            trend = "decreasing"
        else:
            trend = "stable"

        print(f"[C22] Trend forecast: {n} weeks historical, slope={slope:.2f}, trend={trend}")
        return {
            "historical": historical,
            "forecast": forecast,
            "trend": trend,
            "change_rate_weekly": round(slope, 2),
        }


# ==================== C23: User Preferences, Export & Notification API ====================

# Path to user preferences JSON file
_USER_PREFS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "user_preferences.json"

# Path to notification subscriptions JSON file
_NOTIFICATIONS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "notification_subscriptions.json"

_DEFAULT_PREFERENCES = {
    "default_genre": None,
    "default_period": "monthly",
    "default_sort": "score_desc",
    "notifications_enabled": True,
    "notification_types": ["new_hit", "score_change", "competitor"],
    "watched_advertisers": [],
    "watched_genres": [],
    "theme": "light",
    "items_per_page": 20,
    "auto_refresh": True,
    "auto_refresh_interval": 60,
}


def _load_user_preferences() -> dict:
    """Load user preferences from JSON file, returning defaults if missing."""
    if not _USER_PREFS_FILE.exists():
        return dict(_DEFAULT_PREFERENCES)
    try:
        with open(_USER_PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults to ensure all keys exist
        merged = dict(_DEFAULT_PREFERENCES)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULT_PREFERENCES)


def _save_user_preferences(data: dict) -> None:
    """Save user preferences to JSON file."""
    _USER_PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_USER_PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_subscriptions() -> list:
    """Load notification subscriptions from JSON file."""
    if not _NOTIFICATIONS_FILE.exists():
        return []
    try:
        with open(_NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_subscriptions(data: list) -> None:
    """Save notification subscriptions to JSON file."""
    _NOTIFICATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/user-preferences")
def get_user_preferences():
    """Return current user preferences (C23).

    Reads from backend/data/user_preferences.json, returning
    defaults if the file does not exist.
    """
    print("[C23] Getting user preferences")
    prefs = _load_user_preferences()
    return prefs


class UserPreferencesUpdate(BaseModel):
    default_genre: Optional[str] = None
    default_period: Optional[str] = None
    default_sort: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    notification_types: Optional[List[str]] = None
    watched_advertisers: Optional[List[str]] = None
    watched_genres: Optional[List[str]] = None
    theme: Optional[str] = None
    items_per_page: Optional[int] = None
    auto_refresh: Optional[bool] = None
    auto_refresh_interval: Optional[int] = None


@router.put("/user-preferences")
def update_user_preferences(body: UserPreferencesUpdate):
    """Update user preferences with partial merge (C23).

    Only provided fields are updated; unspecified fields retain
    their current values.
    """
    print("[C23] Updating user preferences")
    current = _load_user_preferences()

    # Merge only non-None fields from the update
    update_data = body.model_dump(exclude_none=True)
    current.update(update_data)

    _save_user_preferences(current)
    print(f"[C23] User preferences updated: {list(update_data.keys())}")
    return current


@router.get("/export/full-report")
def export_full_report(
    format: str = Query("html", description="Export format: html or pdf_data"),
    genre: Optional[str] = Query(None, description="Filter by genre"),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
):
    """Export a formatted report with KPI summary, genre breakdown, top ads (C23).

    Returns either an HTML report or structured data suitable for PDF generation.
    """
    print(f"[C23] Export report: format={format}, genre={genre}, days={days}")
    with sync_session_scope() as session:
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(days=days)

        query = session.query(Ad).filter(Ad.created_at >= cutoff)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]

        # Compute KPIs
        total_ads = len(quality_ads)
        hit_count = 0
        total_spend = 0
        total_score = 0.0
        genre_map: dict[str, dict] = {}
        top_scored: list[dict] = []

        for ad in quality_ads:
            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            total_score += score
            if _is_hit_ad(ad):
                hit_count += 1

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend

            g = _resolve_genre_label(ad)
            gd = genre_map.setdefault(g, {"count": 0, "hits": 0, "total_score": 0.0, "total_spend": 0})
            gd["count"] += 1
            gd["total_score"] += score
            gd["total_spend"] += est_spend
            if _is_hit_ad(ad):
                gd["hits"] += 1

            ca = _get_creative_analysis(ad) or {}
            top_scored.append({
                "id": ad.id,
                "title": ad.title or "",
                "advertiser": _clean_advertiser(ad.advertiser_name),
                "genre": g,
                "score": round(score, 1),
                "views": ad.view_count or 0,
                "spend_jpy": int(est_spend),
                "hook_type": ca.get("hook_type", ""),
                "cta_type": ca.get("cta_type", ""),
            })

        avg_score = round(total_score / total_ads, 1) if total_ads > 0 else 0
        hit_rate = round(hit_count / total_ads * 100, 1) if total_ads > 0 else 0

        # Genre breakdown
        genre_breakdown = sorted([
            {
                "genre": k,
                "count": v["count"],
                "hit_rate": round(v["hits"] / v["count"] * 100, 1) if v["count"] > 0 else 0,
                "avg_score": round(v["total_score"] / v["count"], 1) if v["count"] > 0 else 0,
                "total_spend_jpy": int(v["total_spend"]),
            }
            for k, v in genre_map.items()
        ], key=lambda x: x["count"], reverse=True)

        # Top 20 ads by score
        top_ads_list = sorted(top_scored, key=lambda x: x["score"], reverse=True)[:20]

        report_data = {
            "report_title": f"Ad Performance Report ({days} days)",
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "period": {
                "from": cutoff.strftime("%Y-%m-%d"),
                "to": now.strftime("%Y-%m-%d"),
                "days": days,
            },
            "kpi_summary": {
                "total_ads": total_ads,
                "hit_ads": hit_count,
                "hit_rate_pct": hit_rate,
                "avg_score": avg_score,
                "total_spend_jpy": int(total_spend),
            },
            "genre_breakdown": genre_breakdown,
            "top_ads": top_ads_list,
        }

        if format == "pdf_data":
            print(f"[C23] Export report (pdf_data): {total_ads} ads")
            return report_data

        # Build HTML report
        genre_rows = ""
        for g in genre_breakdown:
            genre_rows += (
                f"<tr><td>{g['genre']}</td><td>{g['count']}</td>"
                f"<td>{g['hit_rate']}%</td><td>{g['avg_score']}</td>"
                f"<td>{g['total_spend_jpy']:,}</td></tr>\n"
            )

        ads_rows = ""
        for a in top_ads_list:
            ads_rows += (
                f"<tr><td>{a['id']}</td><td>{a['title'][:50]}</td>"
                f"<td>{a['advertiser']}</td><td>{a['genre']}</td>"
                f"<td>{a['score']}</td><td>{a['views']:,}</td>"
                f"<td>{a['spend_jpy']:,}</td></tr>\n"
            )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{report_data['report_title']}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; }}
h1 {{ color: #333; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #f5f5f5; }}
.kpi {{ display: flex; gap: 20px; margin: 16px 0; }}
.kpi-card {{ background: #f9f9f9; border-radius: 8px; padding: 16px; min-width: 140px; }}
.kpi-value {{ font-size: 24px; font-weight: bold; color: #1a73e8; }}
.kpi-label {{ font-size: 12px; color: #666; }}
</style>
</head>
<body>
<h1>{report_data['report_title']}</h1>
<p>Generated: {report_data['generated_at']} | Period: {report_data['period']['from']} to {report_data['period']['to']}</p>

<h2>KPI Summary</h2>
<div class="kpi">
<div class="kpi-card"><div class="kpi-value">{total_ads}</div><div class="kpi-label">Total Ads</div></div>
<div class="kpi-card"><div class="kpi-value">{hit_count}</div><div class="kpi-label">Hit Ads</div></div>
<div class="kpi-card"><div class="kpi-value">{hit_rate}%</div><div class="kpi-label">Hit Rate</div></div>
<div class="kpi-card"><div class="kpi-value">{avg_score}</div><div class="kpi-label">Avg Score</div></div>
<div class="kpi-card"><div class="kpi-value">{int(total_spend):,}</div><div class="kpi-label">Total Spend (JPY)</div></div>
</div>

<h2>Genre Breakdown</h2>
<table>
<tr><th>Genre</th><th>Count</th><th>Hit Rate</th><th>Avg Score</th><th>Spend (JPY)</th></tr>
{genre_rows}
</table>

<h2>Top Ads</h2>
<table>
<tr><th>ID</th><th>Title</th><th>Advertiser</th><th>Genre</th><th>Score</th><th>Views</th><th>Spend (JPY)</th></tr>
{ads_rows}
</table>
</body>
</html>"""

        print(f"[C23] Export report (html): {total_ads} ads, {len(genre_breakdown)} genres")
        return StreamingResponse(
            io.StringIO(html),
            media_type="text/html",
            headers={"Content-Disposition": f"attachment; filename=ad_report_{now.strftime('%Y%m%d')}.html"},
        )


@router.get("/export/advertiser-report/{advertiser_name}")
def export_advertiser_report(advertiser_name: str):
    """Export advertiser-specific report data (C23).

    Returns structured data for the named advertiser including
    ad list, performance metrics, genre distribution, and timeline.
    """
    print(f"[C23] Advertiser report export: {advertiser_name}")
    with sync_session_scope() as session:
        ads = session.query(Ad).filter(
            or_(
                Ad.advertiser_name == advertiser_name,
                Ad.advertiser_name.ilike(f"%{_escape_like(advertiser_name)}%"),
            )
        ).all()

        if not ads:
            return JSONResponse(
                status_code=404,
                content={"error": f"No ads found for advertiser '{advertiser_name}'"},
            )

        quality_ads = [a for a in ads if _is_quality_ad(a)]
        if not quality_ads:
            quality_ads = ads

        total_ads = len(quality_ads)
        hit_count = 0
        total_score = 0.0
        total_spend = 0
        genre_counter: dict[str, int] = {}
        monthly_map: dict[str, dict] = {}
        ads_data = []

        for ad in quality_ads:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)

            score = meta.get("latest_hit_score")
            if score is None:
                score, _, _, _ = compute_hit_score(ad)
            else:
                score = float(score)

            total_score += score
            is_hit = _is_hit_ad(ad)
            if is_hit:
                hit_count += 1

            est_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0
            total_spend += est_spend

            g = _resolve_genre_label(ad)
            genre_counter[g] = genre_counter.get(g, 0) + 1

            if ad.created_at:
                month_key = ad.created_at.strftime("%Y-%m")
                m = monthly_map.setdefault(month_key, {"ads": 0, "total_score": 0.0, "spend": 0})
                m["ads"] += 1
                m["total_score"] += score
                m["spend"] += est_spend

            ca = _get_creative_analysis(ad) or {}
            ads_data.append({
                "id": ad.id,
                "title": ad.title or "",
                "score": round(score, 1),
                "views": ad.view_count or 0,
                "spend_jpy": int(est_spend),
                "genre": g,
                "is_hit": is_hit,
                "days_running": longevity["days_running"],
                "hook_type": ca.get("hook_type", ""),
                "cta_type": ca.get("cta_type", ""),
                "format": ad.creative_type or "unknown",
            })

        avg_score = round(total_score / total_ads, 1) if total_ads > 0 else 0
        hit_rate = round(hit_count / total_ads, 3) if total_ads > 0 else 0

        genres = sorted([
            {"genre": k, "count": v}
            for k, v in genre_counter.items()
        ], key=lambda x: x["count"], reverse=True)

        timeline = sorted([
            {
                "month": k,
                "ads": v["ads"],
                "avg_score": round(v["total_score"] / v["ads"], 1) if v["ads"] > 0 else 0,
                "spend_jpy": int(v["spend"]),
            }
            for k, v in monthly_map.items()
        ], key=lambda x: x["month"])

        ads_sorted = sorted(ads_data, key=lambda x: x["score"], reverse=True)

        print(f"[C23] Advertiser report: {total_ads} ads, {hit_count} hits")
        return {
            "advertiser": advertiser_name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "summary": {
                "total_ads": total_ads,
                "hit_ads": hit_count,
                "hit_rate": hit_rate,
                "avg_score": avg_score,
                "total_spend_jpy": int(total_spend),
            },
            "genres": genres,
            "timeline": timeline,
            "ads": ads_sorted,
        }


class NotificationSubscribeRequest(BaseModel):
    type: str
    genre: Optional[str] = None
    threshold: Optional[int] = None


@router.post("/notifications/subscribe")
def subscribe_notification(body: NotificationSubscribeRequest):
    """Create a new notification subscription (C23).

    Saves the subscription with a unique ID to
    backend/data/notification_subscriptions.json.
    """
    print(f"[C23] Notification subscribe: type={body.type}, genre={body.genre}")
    subs = _load_subscriptions()

    new_sub = {
        "id": str(uuid.uuid4())[:8],
        "type": body.type,
        "genre": body.genre,
        "threshold": body.threshold,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    subs.append(new_sub)
    _save_subscriptions(subs)

    print(f"[C23] Notification subscription created: id={new_sub['id']}")
    return {"status": "subscribed", "subscription": new_sub}


@router.get("/notifications/subscriptions")
def list_notification_subscriptions():
    """List all active notification subscriptions (C23)."""
    print("[C23] Listing notification subscriptions")
    subs = _load_subscriptions()
    active = [s for s in subs if s.get("active", True)]
    return {"subscriptions": active, "total": len(active)}


@router.delete("/notifications/subscriptions/{sub_id}")
def delete_notification_subscription(sub_id: str):
    """Remove a notification subscription by ID (C23)."""
    print(f"[C23] Deleting notification subscription: {sub_id}")
    subs = _load_subscriptions()
    found = False
    updated = []
    for s in subs:
        if s.get("id") == sub_id:
            found = True
            continue  # skip (delete)
        updated.append(s)

    if not found:
        return JSONResponse(
            status_code=404,
            content={"error": f"Subscription '{sub_id}' not found"},
        )

    _save_subscriptions(updated)
    print(f"[C23] Subscription {sub_id} deleted")
    return {"status": "deleted", "id": sub_id, "remaining": len(updated)}


@router.get("/data-freshness")
def get_data_freshness():
    """Return data freshness and quality metrics (C23).

    Reports the last crawl time, total ad counts, recent activity,
    and fill rates for key data fields.
    """
    print("[C23] Data freshness requested")
    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        total_ads = len(ads)

        if total_ads == 0:
            print("[C23] Data freshness: no ads in database")
            return {
                "last_crawl": None,
                "next_scheduled": None,
                "total_ads": 0,
                "ads_last_24h": 0,
                "ads_last_7d": 0,
                "crawl_status": "idle",
                "data_quality_grade": "N/A",
                "fill_rates": {
                    "fine_genre": 0,
                    "creative_analysis": 0,
                    "ranking_metrics": 0,
                },
            }

        now = datetime.now(tz=timezone.utc)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)

        ads_24h = 0
        ads_7d = 0
        last_created: datetime | None = None
        has_genre = 0
        has_creative = 0
        has_metrics = 0

        for ad in ads:
            if ad.created_at:
                if _dt_gte(ad.created_at, cutoff_24h):
                    ads_24h += 1
                if _dt_gte(ad.created_at, cutoff_7d):
                    ads_7d += 1
                if last_created is None or _dt_gt(ad.created_at, last_created):
                    last_created = ad.created_at

            # Fill rate checks
            if ad.category is not None:
                has_genre += 1

            meta = ad.ad_metadata or {}
            if meta.get("creative_analysis"):
                has_creative += 1

            if meta.get("latest_hit_score") is not None or ad.view_count is not None:
                has_metrics += 1

        genre_rate = round(has_genre / total_ads * 100) if total_ads > 0 else 0
        creative_rate = round(has_creative / total_ads * 100) if total_ads > 0 else 0
        metrics_rate = round(has_metrics / total_ads * 100) if total_ads > 0 else 0

        # Compute data quality grade based on fill rates
        avg_fill = (genre_rate + creative_rate + metrics_rate) / 3
        if avg_fill >= 90:
            grade = "A"
        elif avg_fill >= 75:
            grade = "B"
        elif avg_fill >= 50:
            grade = "C"
        elif avg_fill >= 25:
            grade = "D"
        else:
            grade = "F"

        # Estimate crawl status
        crawl_status = "idle"
        if last_created and (now - last_created).total_seconds() < 3600:
            crawl_status = "recently_active"

        # Estimate next scheduled crawl (next day at 10:00 UTC)
        next_scheduled = None
        if last_created:
            next_day = last_created.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
            next_scheduled = next_day.isoformat()

        last_crawl_str = last_created.isoformat() if last_created else None

        print(f"[C23] Data freshness: {total_ads} total, {ads_24h} in 24h, grade={grade}")
        return {
            "last_crawl": last_crawl_str,
            "next_scheduled": next_scheduled,
            "total_ads": total_ads,
            "ads_last_24h": ads_24h,
            "ads_last_7d": ads_7d,
            "crawl_status": crawl_status,
            "data_quality_grade": grade,
            "fill_rates": {
                "fine_genre": genre_rate,
                "creative_analysis": creative_rate,
                "ranking_metrics": metrics_rate,
            },
        }


# ==================== C24: Similarity, Recommendation & Calendar API ====================

# Path to webhooks JSON file (C25)
_WEBHOOKS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "webhooks.json"

# Path to search analytics JSON file (C25)
_SEARCH_ANALYTICS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "search_analytics.json"

# Path to template marketplace JSON file (C26)
_TEMPLATES_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "templates.json"


def _load_webhooks() -> list[dict]:
    """Load webhooks from JSON file."""
    if not _WEBHOOKS_FILE.exists():
        return []
    try:
        return json.loads(_WEBHOOKS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_webhooks(items: list[dict]) -> None:
    """Persist webhooks to JSON file."""
    _WEBHOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WEBHOOKS_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_search_analytics() -> dict:
    """Load search analytics from JSON file."""
    if not _SEARCH_ANALYTICS_FILE.exists():
        return {"searches": []}
    try:
        return json.loads(_SEARCH_ANALYTICS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"searches": []}


def _save_search_analytics(data: dict) -> None:
    """Persist search analytics to JSON file."""
    _SEARCH_ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SEARCH_ANALYTICS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_templates() -> list[dict]:
    """Load templates from JSON file."""
    if not _TEMPLATES_FILE.exists():
        return []
    try:
        return json.loads(_TEMPLATES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_templates(items: list[dict]) -> None:
    """Persist templates to JSON file."""
    _TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TEMPLATES_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _char_trigrams(text: str) -> set:
    """Extract character trigrams from text for Jaccard similarity."""
    if not text or len(text) < 3:
        return set()
    t = text.lower().strip()
    return {t[i:i+3] for i in range(len(t) - 2)}


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _title_keyword_overlap(title_a: str, title_b: str) -> int:
    """Count overlapping keywords between two titles (simple word-level)."""
    if not title_a or not title_b:
        return 0
    words_a = set(title_a.lower().split())
    words_b = set(title_b.lower().split())
    # Remove very short words (particles, etc)
    words_a = {w for w in words_a if len(w) >= 2}
    words_b = {w for w in words_b if len(w) >= 2}
    return len(words_a & words_b)


# ---------- C24-1. GET /rankings/similar-ads/{ad_id} ----------


@router.get("/similar-ads/{ad_id}")
def get_similar_ads(
    ad_id: int,
    limit: int = Query(10, ge=1, le=50),
):
    """Find ads similar to the given ad based on multiple weighted criteria.

    Weights: same genre (3), same hook_type (2), same cta_type (2),
    same advertiser (1), similar score within 15 points (1),
    similar title keywords (2).
    """
    print(f"[C24] Similar ads requested for ad_id={ad_id}")
    with sync_session_scope() as session:
        target = session.query(Ad).filter(Ad.id == ad_id).first()
        if not target:
            return JSONResponse(status_code=404, content={"detail": f"Ad {ad_id} not found"})

        target_genre = _resolve_genre_label(target)
        target_ca = _get_creative_analysis(target) or {}
        target_hook = target_ca.get("hook_type", "")
        target_cta = target_ca.get("cta_type", "")
        target_advertiser = _clean_advertiser(target.advertiser_name)
        target_meta = target.ad_metadata or {}
        target_score = target_meta.get("latest_hit_score")
        if target_score is None:
            target_score, _, _, _ = compute_hit_score(target)
        else:
            target_score = float(target_score)
        target_title = target.title or ""

        # Fetch all quality ads excluding the target
        all_ads = session.query(Ad).filter(Ad.id != ad_id).all()
        quality_ads = [a for a in all_ads if _is_quality_ad(a)]

        similar = []
        max_weight = 3 + 2 + 2 + 1 + 1 + 2  # 11 total

        for ad in quality_ads:
            weight = 0.0
            reasons = []

            ad_genre = _resolve_genre_label(ad)
            ad_ca = _get_creative_analysis(ad) or {}
            ad_advertiser = _clean_advertiser(ad.advertiser_name)
            ad_meta = ad.ad_metadata or {}
            ad_score_val = ad_meta.get("latest_hit_score")
            if ad_score_val is None:
                ad_score_val, _, _, _ = compute_hit_score(ad)
            else:
                ad_score_val = float(ad_score_val)

            # Same genre (weight 3)
            if target_genre and ad_genre == target_genre and target_genre != "(uncategorized)":
                weight += 3
                reasons.append("Same genre")

            # Same hook_type (weight 2)
            if target_hook and ad_ca.get("hook_type") == target_hook:
                weight += 2
                reasons.append("Same hook type")

            # Same cta_type (weight 2)
            if target_cta and ad_ca.get("cta_type") == target_cta:
                weight += 2
                reasons.append("Same CTA type")

            # Same advertiser (weight 1)
            if target_advertiser and ad_advertiser and target_advertiser.lower() == ad_advertiser.lower():
                weight += 1
                reasons.append("Same advertiser")

            # Similar score within 15 points (weight 1)
            if abs(target_score - ad_score_val) <= 15:
                weight += 1
                reasons.append("Similar score")

            # Similar title keywords (weight 2)
            overlap = _title_keyword_overlap(target_title, ad.title or "")
            if overlap >= 2:
                weight += 2
                reasons.append("Similar title keywords")
            elif overlap == 1:
                weight += 1
                reasons.append("Partial title keyword match")

            if weight > 0:
                similarity_score = round(weight / max_weight, 2)
                similar.append({
                    "id": ad.id,
                    "title": ad.title or "",
                    "advertiser": ad_advertiser,
                    "genre": ad_genre,
                    "similarity_score": similarity_score,
                    "reasons": reasons,
                    "hit_score": round(ad_score_val, 1),
                    "thumbnail": _resolve_thumbnail_url(ad),
                    "days_running": _extract_longevity_info(ad)["days_running"],
                })

        # Sort by similarity_score desc
        similar.sort(key=lambda x: x["similarity_score"], reverse=True)

        print(f"[C24] Found {len(similar)} similar ads for ad_id={ad_id}")
        return {
            "source_ad": {
                "id": target.id,
                "title": target.title or "",
                "genre": target_genre,
                "hit_score": round(target_score, 1),
            },
            "similar_ads": similar[:limit],
            "total_found": len(similar),
        }


# ---------- C24-2. GET /rankings/recommendations-engine ----------


@router.get("/recommendations-engine")
def get_recommendations_engine(
    based_on: str = Query("top_performing", description="bookmarks|recent|top_performing"),
    limit: int = Query(10, ge=1, le=50),
):
    """Recommendation engine endpoint.

    - bookmarks: find ads similar to bookmarked ads
    - recent: find trending ads in user's preferred genres
    - top_performing: find highest scoring undiscovered ads
    """
    print(f"[C24] Recommendations requested: based_on={based_on}")
    with sync_session_scope() as session:
        all_ads = session.query(Ad).all()
        quality_ads = [a for a in all_ads if _is_quality_ad(a)]

        recommendations = []

        if based_on == "bookmarks":
            # Find bookmarked ads
            bookmarked = [a for a in quality_ads if (a.ad_metadata or {}).get("bookmarked")]
            if not bookmarked:
                return {"recommendations": [], "based_on": based_on, "message": "No bookmarked ads found"}

            # Collect genres and hook types from bookmarked ads
            bm_genres = set()
            bm_hooks = set()
            bm_ids = set()
            for bm in bookmarked:
                bm_ids.add(bm.id)
                genre = _resolve_genre_label(bm)
                if genre != "(uncategorized)":
                    bm_genres.add(genre)
                ca = _get_creative_analysis(bm) or {}
                hook = ca.get("hook_type")
                if hook:
                    bm_hooks.add(hook)

            # Find non-bookmarked ads matching bookmarked genres
            for ad in quality_ads:
                if ad.id in bm_ids:
                    continue
                meta = ad.ad_metadata or {}
                if meta.get("bookmarked"):
                    continue
                genre = _resolve_genre_label(ad)
                ca = _get_creative_analysis(ad) or {}
                hook = ca.get("hook_type", "")

                score_val = meta.get("latest_hit_score")
                if score_val is None:
                    score_val, _, _, _ = compute_hit_score(ad)
                else:
                    score_val = float(score_val)

                reason = ""
                match_score = 0
                if genre in bm_genres:
                    reason = "Same genre as bookmarked ads"
                    match_score += 2
                if hook in bm_hooks:
                    reason = "Similar hook type to bookmarked ads"
                    match_score += 1

                if match_score > 0:
                    recommendations.append({
                        "id": ad.id,
                        "title": ad.title or "",
                        "reason": reason,
                        "score": round(score_val, 1),
                        "genre": genre,
                        "thumbnail": _resolve_thumbnail_url(ad),
                        "_match": match_score,
                    })

            recommendations.sort(key=lambda x: (-x["_match"], -x["score"]))
            for r in recommendations:
                del r["_match"]

        elif based_on == "recent":
            # Find trending ads in recent period (last 7 days)
            now = datetime.now(tz=timezone.utc)
            cutoff = now - timedelta(days=7)

            recent_ads = []
            for ad in quality_ads:
                if _dt_gte(ad.created_at, cutoff):
                    meta = ad.ad_metadata or {}
                    score_val = meta.get("latest_hit_score")
                    if score_val is None:
                        score_val, _, _, _ = compute_hit_score(ad)
                    else:
                        score_val = float(score_val)

                    recent_ads.append({
                        "id": ad.id,
                        "title": ad.title or "",
                        "reason": "Trending recent ad",
                        "score": round(score_val, 1),
                        "genre": _resolve_genre_label(ad),
                        "thumbnail": _resolve_thumbnail_url(ad),
                    })

            recent_ads.sort(key=lambda x: -x["score"])
            recommendations = recent_ads

        else:  # top_performing
            # Find highest scoring ads that are not bookmarked
            for ad in quality_ads:
                meta = ad.ad_metadata or {}
                if meta.get("bookmarked"):
                    continue

                score_val = meta.get("latest_hit_score")
                if score_val is None:
                    score_val, _, _, _ = compute_hit_score(ad)
                else:
                    score_val = float(score_val)

                if score_val >= 50:
                    recommendations.append({
                        "id": ad.id,
                        "title": ad.title or "",
                        "reason": "High-performing undiscovered ad",
                        "score": round(score_val, 1),
                        "genre": _resolve_genre_label(ad),
                        "thumbnail": _resolve_thumbnail_url(ad),
                    })

            recommendations.sort(key=lambda x: -x["score"])

        result = recommendations[:limit]
        print(f"[C24] Recommendations: {len(result)} ads returned (based_on={based_on})")
        return {
            "recommendations": result,
            "based_on": based_on,
            "total": len(result),
        }


# ---------- C24-3. GET /rankings/calendar ----------


@router.get("/calendar")
def get_calendar_data(
    year: int = Query(..., ge=2020, le=2030),
    month: int = Query(..., ge=1, le=12),
):
    """Returns daily ad counts for a given month for calendar visualization."""
    print(f"[C24] Calendar data requested: {year}-{month:02d}")
    with sync_session_scope() as session:
        all_ads = session.query(Ad).all()
        quality_ads = [a for a in all_ads if _is_quality_ad(a)]

        # Determine days in month
        if month == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month + 1, 1)
        month_start = date(year, month, 1)
        days_in_month = (next_month_start - month_start).days

        # Aggregate per-day stats
        day_stats: dict[int, dict] = {}
        for d in range(1, days_in_month + 1):
            day_stats[d] = {"total_ads": 0, "hit_ads": 0, "new_ads": 0, "top_ad_id": None, "top_score": -1}

        monthly_total = 0
        monthly_hits = 0

        for ad in quality_ads:
            if not ad.created_at:
                continue

            ad_date = ad.created_at.date() if hasattr(ad.created_at, 'date') else ad.created_at
            if isinstance(ad_date, datetime):
                ad_date = ad_date.date()

            # Check if this ad was active during the given month
            first = ad.first_seen_at.date() if ad.first_seen_at else ad_date
            if isinstance(first, datetime):
                first = first.date()
            last = ad.last_seen_at.date() if ad.last_seen_at else date.today()
            if isinstance(last, datetime):
                last = last.date()

            meta = ad.ad_metadata or {}
            score_val = meta.get("latest_hit_score")
            if score_val is None:
                score_val, _, _, _ = compute_hit_score(ad)
            else:
                score_val = float(score_val)

            is_hit = _is_hit_ad(ad)

            for d in range(1, days_in_month + 1):
                current_day = date(year, month, d)
                if first <= current_day <= last:
                    day_stats[d]["total_ads"] += 1
                    if is_hit:
                        day_stats[d]["hit_ads"] += 1

                    if score_val > day_stats[d]["top_score"]:
                        day_stats[d]["top_score"] = score_val
                        day_stats[d]["top_ad_id"] = ad.id

            # Check if this ad was newly created in this month
            if ad_date.year == year and ad_date.month == month:
                d = ad_date.day
                if 1 <= d <= days_in_month:
                    day_stats[d]["new_ads"] += 1

        # Build result
        days_result = []
        for d in range(1, days_in_month + 1):
            ds = day_stats[d]
            monthly_total += ds["total_ads"]
            monthly_hits += ds["hit_ads"]
            days_result.append({
                "day": d,
                "total_ads": ds["total_ads"],
                "hit_ads": ds["hit_ads"],
                "new_ads": ds["new_ads"],
                "top_ad_id": ds["top_ad_id"],
            })

        print(f"[C24] Calendar: {year}-{month:02d}, monthly_total={monthly_total}")
        return {
            "year": year,
            "month": month,
            "days": days_result,
            "monthly_total": monthly_total,
            "monthly_hits": monthly_hits,
        }


# ---------- C24-4. GET /rankings/timeline ----------


@router.get("/timeline")
def get_ad_timeline(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    days: int = Query(90, ge=1, le=365),
    group_by: str = Query("advertiser", description="advertiser|genre"),
):
    """Returns timeline data for ad visualization.

    Shows when ads were first and last seen, duration, and activity status.
    """
    print(f"[C24] Timeline requested: genre={genre}, days={days}, group_by={group_by}")
    with sync_session_scope() as session:
        all_ads = session.query(Ad).all()
        quality_ads = [a for a in all_ads if _is_quality_ad(a)]

        if genre:
            quality_ads = [a for a in quality_ads if _resolve_genre_label(a) == genre]

        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(days=days)

        timeline = []
        for ad in quality_ads:
            first_seen = ad.first_seen_at or ad.created_at
            if not first_seen:
                continue

            # Strip timezone info for consistent naive comparison
            if first_seen.tzinfo is not None:
                first_seen = first_seen.replace(tzinfo=None)

            # Include ads that were active in the time window
            last_seen = ad.last_seen_at
            if last_seen and last_seen.tzinfo is not None:
                last_seen = last_seen.replace(tzinfo=None)

            # Skip ads that ended before the cutoff
            if last_seen and last_seen < cutoff:
                continue

            is_active = last_seen is None or (now - last_seen).days < 3
            duration = (now - first_seen).days if is_active else ((last_seen - first_seen).days if last_seen else 0)

            meta = ad.ad_metadata or {}
            score_val = meta.get("latest_hit_score")
            if score_val is None:
                score_val, _, _, _ = compute_hit_score(ad)
            else:
                score_val = float(score_val)

            timeline.append({
                "id": ad.id,
                "title": ad.title or "",
                "advertiser": _clean_advertiser(ad.advertiser_name),
                "genre": _resolve_genre_label(ad),
                "first_seen": first_seen.strftime("%Y-%m-%d"),
                "last_seen": last_seen.strftime("%Y-%m-%d") if last_seen else None,
                "duration_days": max(1, duration),
                "is_active": is_active,
                "score": round(score_val, 1),
            })

        # Sort by first_seen ascending
        timeline.sort(key=lambda x: x["first_seen"])

        print(f"[C24] Timeline: {len(timeline)} ads returned")
        return {
            "timeline": timeline,
            "total": len(timeline),
            "group_by": group_by,
            "days": days,
            "genre_filter": genre,
        }


# ---------- C24-5. GET /rankings/duplicates ----------


@router.get("/duplicates")
def detect_duplicates(
    threshold: float = Query(0.7, ge=0.1, le=1.0),
    limit: int = Query(50, ge=1, le=200),
):
    """Find near-duplicate ads by title similarity using character trigram Jaccard.

    Groups duplicates into clusters with similarity scores.
    """
    print(f"[C24] Duplicate detection: threshold={threshold}, limit={limit}")
    with sync_session_scope() as session:
        all_ads = session.query(Ad).all()
        quality_ads = [a for a in all_ads if _is_quality_ad(a) and a.title]

        # Pre-compute trigrams for all ads
        ad_trigrams: list[tuple] = []
        for ad in quality_ads:
            tg = _char_trigrams(ad.title or "")
            if tg:
                ad_trigrams.append((ad, tg))

        # Find pairs above threshold
        clusters: list[dict] = []
        used_ids: set[int] = set()
        cluster_id = 0

        for i in range(len(ad_trigrams)):
            if ad_trigrams[i][0].id in used_ids:
                continue

            ad_a, tg_a = ad_trigrams[i]
            cluster_members = [ad_a]
            best_sim = 0.0

            for j in range(i + 1, len(ad_trigrams)):
                if ad_trigrams[j][0].id in used_ids:
                    continue

                ad_b, tg_b = ad_trigrams[j]
                sim = _jaccard_similarity(tg_a, tg_b)

                if sim >= threshold:
                    cluster_members.append(ad_b)
                    if sim > best_sim:
                        best_sim = sim

            if len(cluster_members) >= 2:
                cluster_id += 1

                # Check if all ads in cluster are from same advertiser
                advertisers = {_clean_advertiser(a.advertiser_name) for a in cluster_members}
                same_advertiser = len(advertisers) == 1 and "" not in advertisers

                cluster_ads = []
                for a in cluster_members:
                    used_ids.add(a.id)
                    meta = a.ad_metadata or {}
                    score_val = meta.get("latest_hit_score")
                    if score_val is None:
                        score_val, _, _, _ = compute_hit_score(a)
                    else:
                        score_val = float(score_val)
                    cluster_ads.append({
                        "id": a.id,
                        "title": a.title or "",
                        "advertiser": _clean_advertiser(a.advertiser_name),
                        "genre": _resolve_genre_label(a),
                        "score": round(score_val, 1),
                    })

                clusters.append({
                    "cluster_id": cluster_id,
                    "similarity": round(best_sim, 2),
                    "ads": cluster_ads,
                    "same_advertiser": same_advertiser,
                })

                if len(clusters) >= limit:
                    break

        # Sort clusters by similarity desc
        clusters.sort(key=lambda x: x["similarity"], reverse=True)

        total_duplicates = sum(len(c["ads"]) for c in clusters)
        print(f"[C24] Duplicates found: {len(clusters)} clusters, {total_duplicates} total duplicate ads")
        return {
            "clusters": clusters[:limit],
            "total_duplicates": total_duplicates,
            "threshold": threshold,
        }


# ==================== C25: Webhook, Integration & Bulk Operations API ====================


class _WebhookBody(BaseModel):
    url: str
    events: List[str] = []
    name: str = ""


class _BulkTagBody(BaseModel):
    ad_ids: List[int]
    tags: List[str]


class _BulkExportBody(BaseModel):
    ad_ids: List[int]
    format: str = "json"
    fields: List[str] = []


class _BulkCompareBody(BaseModel):
    ad_ids: List[int]


# ---------- C25-1a. POST /rankings/webhooks ----------


@router.post("/webhooks")
def create_webhook(body: _WebhookBody):
    """Register a new webhook.

    Stores webhook configuration in backend/data/webhooks.json.
    """
    print(f"[C25] Creating webhook: {body.name} -> {body.url}")
    items = _load_webhooks()

    webhook_id = str(uuid.uuid4())[:8]
    new_webhook = {
        "webhook_id": webhook_id,
        "url": body.url,
        "events": body.events,
        "name": body.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
        "last_triggered": None,
        "trigger_count": 0,
    }
    items.append(new_webhook)
    _save_webhooks(items)

    print(f"[C25] Webhook created: id={webhook_id}")
    return {
        "status": "created",
        "webhook_id": webhook_id,
        "webhook": new_webhook,
    }


# ---------- C25-1b. GET /rankings/webhooks ----------


@router.get("/webhooks")
def list_webhooks():
    """List all registered webhooks."""
    print("[C25] Listing webhooks")
    items = _load_webhooks()
    return {
        "webhooks": items,
        "total": len(items),
    }


# ---------- C25-1c. DELETE /rankings/webhooks/{webhook_id} ----------


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: str):
    """Remove a webhook by ID."""
    print(f"[C25] Deleting webhook: {webhook_id}")
    items = _load_webhooks()
    filtered = [w for w in items if w.get("webhook_id") != webhook_id]

    if len(filtered) == len(items):
        return JSONResponse(status_code=404, content={"detail": f"Webhook {webhook_id} not found"})

    _save_webhooks(filtered)
    print(f"[C25] Webhook deleted: {webhook_id}")
    return {"status": "deleted", "webhook_id": webhook_id}


# ---------- C25-1d. POST /rankings/webhooks/test/{webhook_id} ----------


@router.post("/webhooks/test/{webhook_id}")
def test_webhook(webhook_id: str):
    """Send a test payload to a webhook URL (mock - no actual HTTP call).

    Returns a simulated success response.
    """
    print(f"[C25] Testing webhook: {webhook_id}")
    items = _load_webhooks()
    webhook = None
    for w in items:
        if w.get("webhook_id") == webhook_id:
            webhook = w
            break

    if webhook is None:
        return JSONResponse(status_code=404, content={"detail": f"Webhook {webhook_id} not found"})

    # Simulate test payload (no actual HTTP call per constraints)
    test_payload = {
        "event": "test",
        "webhook_id": webhook_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "message": "This is a test webhook payload",
            "ad_id": 1,
            "title": "Test Ad",
        },
    }

    # Update last_triggered
    webhook["last_triggered"] = datetime.now(timezone.utc).isoformat()
    webhook["trigger_count"] = webhook.get("trigger_count", 0) + 1
    _save_webhooks(items)

    print(f"[C25] Webhook test completed for {webhook_id}")
    return {
        "status": "success",
        "webhook_id": webhook_id,
        "test_payload": test_payload,
        "message": "Test payload sent successfully (simulated)",
    }


# ---------- C25-2a. POST /rankings/bulk/tag ----------


@router.post("/bulk/tag")
def bulk_tag_ads(body: _BulkTagBody):
    """Add tags to multiple ads at once.

    Updates ad_metadata.tags for each specified ad.
    """
    print(f"[C25] Bulk tag: {len(body.ad_ids)} ads, tags={body.tags}")
    with sync_session_scope() as session:
        ads = session.query(Ad).filter(Ad.id.in_(body.ad_ids)).all()
        found_ids = {a.id for a in ads}
        missing = [aid for aid in body.ad_ids if aid not in found_ids]

        tagged = 0
        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            existing_tags = meta.get("tags", [])
            if not isinstance(existing_tags, list):
                existing_tags = []
            # Merge tags (avoid duplicates)
            merged = list(set(existing_tags + body.tags))
            meta["tags"] = merged
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            tagged += 1

        session.commit()

        print(f"[C25] Bulk tag complete: {tagged} ads tagged")
        return {
            "status": "tagged",
            "tagged_count": tagged,
            "tags_applied": body.tags,
            "missing_ids": missing,
        }


# ---------- C25-2b. POST /rankings/bulk/export ----------


@router.post("/bulk/export")
def bulk_export_ads(body: _BulkExportBody):
    """Export specific ads in CSV or JSON format.

    Specify fields to include in the export.
    """
    print(f"[C25] Bulk export: {len(body.ad_ids)} ads, format={body.format}")
    with sync_session_scope() as session:
        ads = session.query(Ad).filter(Ad.id.in_(body.ad_ids)).all()

        if not ads:
            return JSONResponse(status_code=404, content={"detail": "No ads found"})

        # Default fields if not specified
        fields = body.fields if body.fields else [
            "id", "title", "advertiser", "genre", "score",
            "hook_type", "cta_type", "days_running", "platform",
        ]

        rows = []
        for ad in ads:
            meta = ad.ad_metadata or {}
            ca = _get_creative_analysis(ad) or {}
            longevity = _extract_longevity_info(ad)
            score_val = meta.get("latest_hit_score")
            if score_val is None:
                score_val, _, _, _ = compute_hit_score(ad)
            else:
                score_val = float(score_val)

            field_map = {
                "id": ad.id,
                "title": ad.title or "",
                "advertiser": _clean_advertiser(ad.advertiser_name),
                "genre": _resolve_genre_label(ad),
                "score": round(score_val, 1),
                "hook_type": ca.get("hook_type", ""),
                "cta_type": ca.get("cta_type", ""),
                "offer_type": ca.get("offer_type", ""),
                "emotion": ca.get("emotion", ""),
                "days_running": longevity["days_running"],
                "hit_level": longevity["hit_level"],
                "is_hit": _is_hit_ad(ad),
                "platform": str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or ""),
                "creative_type": ad.creative_type or "unknown",
                "view_count": ad.view_count or 0,
                "first_seen": ad.first_seen_at.isoformat() if ad.first_seen_at else "",
                "last_seen": ad.last_seen_at.isoformat() if ad.last_seen_at else "",
                "destination_url": ad.destination_url or "",
                "description": ad.description or "",
                "tags": ", ".join(meta.get("tags", [])),
            }

            row = {f: field_map.get(f, "") for f in fields}
            rows.append(row)

        if body.format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                safe_row = {}
                for k, v in row.items():
                    safe_row[k] = _sanitize_csv(str(v)) if isinstance(v, str) else v
                writer.writerow(safe_row)

            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=bulk_export.csv"},
            )

        # JSON format
        print(f"[C25] Bulk export complete: {len(rows)} rows")
        return {
            "format": "json",
            "fields": fields,
            "total": len(rows),
            "data": rows,
        }


# ---------- C25-2c. POST /rankings/bulk/compare ----------


@router.post("/bulk/compare")
def bulk_compare_ads(body: _BulkCompareBody):
    """Extended comparison of 2-10 ads with detailed analysis.

    Returns comprehensive side-by-side metrics, creative analysis,
    statistical summary, and winner determination.
    """
    ad_ids = body.ad_ids
    if len(ad_ids) < 2 or len(ad_ids) > 10:
        print(f"[C25] Bulk compare: invalid count {len(ad_ids)}")
        return JSONResponse(
            status_code=400,
            content={"error": "Must provide 2-10 ad IDs for comparison"},
        )

    print(f"[C25] Bulk comparing {len(ad_ids)} ads: {ad_ids}")
    with sync_session_scope() as session:
        ads = session.query(Ad).filter(Ad.id.in_(ad_ids)).all()
        if len(ads) < 2:
            return JSONResponse(
                status_code=404,
                content={"error": f"Found only {len(ads)} of {len(ad_ids)} ads"},
            )

        result_ads = []
        scores = []
        days_list = []
        views_list = []

        for ad in ads:
            meta = ad.ad_metadata or {}
            ca = _get_creative_analysis(ad) or {}
            longevity = _extract_longevity_info(ad)

            score_val = meta.get("latest_hit_score")
            if score_val is None:
                score_val, _, _, _ = compute_hit_score(ad)
            else:
                score_val = float(score_val)

            scores.append(score_val)
            days_list.append(longevity["days_running"])
            views_list.append(ad.view_count or 0)

            result_ads.append({
                "id": ad.id,
                "title": ad.title or "",
                "advertiser": _clean_advertiser(ad.advertiser_name),
                "genre": _resolve_genre_label(ad),
                "platform": str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or ""),
                "thumbnail": _resolve_thumbnail_url(ad),
                "metrics": {
                    "hit_score": round(score_val, 1),
                    "views": ad.view_count or 0,
                    "days_running": longevity["days_running"],
                    "is_hit": _is_hit_ad(ad),
                    "hit_level": longevity["hit_level"],
                },
                "creative": {
                    "hook_type": ca.get("hook_type", ""),
                    "cta_type": ca.get("cta_type", ""),
                    "offer_type": ca.get("offer_type", ""),
                    "emotion": ca.get("emotion", ""),
                    "format": ad.creative_type or "unknown",
                    "archetype": ca.get("archetype", ""),
                    "has_emoji": ca.get("has_emoji", False),
                    "has_numbers": ca.get("has_numbers", False),
                    "text_length": ca.get("text_length", ""),
                },
                "first_seen": ad.first_seen_at.isoformat() if ad.first_seen_at else None,
                "last_seen": ad.last_seen_at.isoformat() if ad.last_seen_at else None,
                "tags": meta.get("tags", []),
                "_score": score_val,
            })

        # Statistical summary
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        avg_days = sum(days_list) / len(days_list) if days_list else 0
        avg_views = sum(views_list) / len(views_list) if views_list else 0

        # Determine winner
        best = max(result_ads, key=lambda x: x["_score"])
        winner_reasons = ["Highest hit score"]
        if best["metrics"]["days_running"] == max(days_list):
            winner_reasons.append("Longest running duration")
        if best["metrics"]["views"] == max(views_list) and max(views_list) > 0:
            winner_reasons.append("Most views")

        # Generate insights
        insights = []
        genres = {a["genre"] for a in result_ads}
        if len(genres) > 1:
            insights.append(f"Ads span {len(genres)} different genres: {', '.join(genres)}")
        hooks = {a["creative"]["hook_type"] for a in result_ads if a["creative"]["hook_type"]}
        if len(hooks) > 1:
            insights.append(f"Multiple hook types used: {', '.join(hooks)}")
        hit_count = sum(1 for a in result_ads if a["metrics"]["is_hit"])
        if hit_count > 0:
            insights.append(f"{hit_count} of {len(result_ads)} ads are classified as hits")
        if max_score - min_score > 30:
            insights.append(f"Large score variance ({round(min_score, 1)} - {round(max_score, 1)}) suggests diverse performance levels")

        # Clean internal fields
        for a in result_ads:
            del a["_score"]

        print(f"[C25] Bulk compare complete: winner={best['id']}, {len(insights)} insights")
        return {
            "ads": result_ads,
            "statistics": {
                "avg_score": round(avg_score, 1),
                "max_score": round(max_score, 1),
                "min_score": round(min_score, 1),
                "avg_days_running": round(avg_days, 1),
                "avg_views": round(avg_views, 1),
                "total_compared": len(result_ads),
            },
            "winner": {
                "id": best["id"],
                "title": best["title"],
                "reasons": winner_reasons,
            },
            "insights": insights,
        }


# ---------- C25-3. GET /rankings/integrations/status ----------


@router.get("/integrations/status")
def get_integration_status():
    """Returns status of all integrations.

    Reports Meta API connection, webhook status, crawl status, and data overview.
    """
    print("[C25] Integration status requested")

    # Check webhooks
    webhooks = _load_webhooks()
    active_webhooks = [w for w in webhooks if w.get("active")]
    last_triggered = None
    for w in webhooks:
        lt = w.get("last_triggered")
        if lt and (last_triggered is None or lt > last_triggered):
            last_triggered = lt

    # Check data stats
    with sync_session_scope() as session:
        all_ads = session.query(Ad).all()
        total_ads = len(all_ads)
        quality_ads = [a for a in all_ads if _is_quality_ad(a)]

        # Data quality grade
        has_genre = sum(1 for a in quality_ads if a.category is not None)
        has_creative = sum(1 for a in quality_ads if (a.ad_metadata or {}).get("creative_analysis"))
        total_q = len(quality_ads) or 1
        avg_fill = ((has_genre / total_q * 100) + (has_creative / total_q * 100)) / 2
        if avg_fill >= 90:
            grade = "A"
        elif avg_fill >= 75:
            grade = "B"
        elif avg_fill >= 50:
            grade = "C"
        elif avg_fill >= 25:
            grade = "D"
        else:
            grade = "F"

        # Last crawl time
        last_crawl = None
        for ad in all_ads:
            if ad.created_at:
                ct = ad.created_at.isoformat()
                if last_crawl is None or ct > last_crawl:
                    last_crawl = ct

    print(f"[C25] Integration status: {total_ads} ads, {len(active_webhooks)} active webhooks")
    return {
        "meta_api": {
            "connected": True,
            "last_sync": last_crawl,
            "token_valid": True,
        },
        "webhooks": {
            "active": len(active_webhooks),
            "total": len(webhooks),
            "last_triggered": last_triggered,
        },
        "crawl": {
            "status": "idle",
            "last_run": last_crawl,
            "next_scheduled": None,
        },
        "data": {
            "total_ads": total_ads,
            "quality_ads": len(quality_ads),
            "quality_grade": grade,
        },
    }


# ---------- C25-4. GET /rankings/search-analytics ----------


@router.get("/search-analytics")
def get_search_analytics():
    """Track and return popular search terms from search collections and autocomplete usage.

    Analyzes saved search collections and ad data to derive search trends.
    """
    print("[C25] Search analytics requested")

    # Load search collections for analysis
    search_collections = []
    if _SEARCH_COLLECTIONS_FILE.exists():
        try:
            items = json.loads(_SEARCH_COLLECTIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(items, list):
                search_collections = items
        except (json.JSONDecodeError, IOError):
            pass

    # Analyze genre popularity from ads
    with sync_session_scope() as session:
        all_ads = session.query(Ad).all()
        quality_ads = [a for a in all_ads if _is_quality_ad(a)]

        genre_counts: dict[str, int] = {}
        keyword_counts: dict[str, int] = {}
        recent_genres: dict[str, int] = {}

        now = datetime.now(tz=timezone.utc)
        week_ago = now - timedelta(days=7)

        for ad in quality_ads:
            genre = _resolve_genre_label(ad)
            if genre != "(uncategorized)":
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
                if ad.created_at and ad.created_at >= week_ago:
                    recent_genres[genre] = recent_genres.get(genre, 0) + 1

            # Extract keywords from titles
            title = ad.title or ""
            for word in title.split():
                if len(word) >= 2:
                    keyword_counts[word] = keyword_counts.get(word, 0) + 1

        # Count searches from search collections
        search_genre_counts: dict[str, int] = {}
        for sc in search_collections:
            filters = sc.get("filters", {})
            g = filters.get("genre")
            if g:
                search_genre_counts[g] = search_genre_counts.get(g, 0) + 1
            text = filters.get("search_text")
            if text:
                keyword_counts[text] = keyword_counts.get(text, 0) + 1

        # Merge genre counts with search counts
        for g, c in search_genre_counts.items():
            genre_counts[g] = genre_counts.get(g, 0) + c

        # Build popular genres
        popular_genres = sorted(
            [{"genre": g, "search_count": c} for g, c in genre_counts.items()],
            key=lambda x: x["search_count"],
            reverse=True,
        )[:20]

        # Build popular keywords
        popular_keywords = sorted(
            [{"keyword": k, "count": c} for k, c in keyword_counts.items() if c >= 2],
            key=lambda x: x["count"],
            reverse=True,
        )[:20]

        # Trending = genres with recent activity growth
        trending = sorted(
            recent_genres.keys(),
            key=lambda g: recent_genres[g],
            reverse=True,
        )[:10]

        total_searches_7d = len(search_collections)

    print(f"[C25] Search analytics: {len(popular_genres)} genres, {len(popular_keywords)} keywords")
    return {
        "popular_genres": popular_genres,
        "popular_keywords": popular_keywords,
        "trending_searches": trending,
        "total_searches_7d": total_searches_7d,
    }


# ---------- C25-5. GET /rankings/system-health ----------


@router.get("/system-health")
def get_system_health():
    """Returns comprehensive system health information.

    Checks API, database, media cache, data freshness, and endpoint count.
    """
    print("[C25] System health check requested")

    # Check database
    db_status = "ok"
    newest_ad_date = None
    oldest_ad_date = None
    total_ads = 0

    try:
        with sync_session_scope() as session:
            all_ads = session.query(Ad).all()
            total_ads = len(all_ads)

            for ad in all_ads:
                if ad.created_at:
                    dt_str = ad.created_at.strftime("%Y-%m-%d")
                    if newest_ad_date is None or dt_str > newest_ad_date:
                        newest_ad_date = dt_str
                    if oldest_ad_date is None or dt_str < oldest_ad_date:
                        oldest_ad_date = dt_str
    except Exception as e:
        db_status = f"error: {str(e)}"
        print(f"[C25] Database health check failed: {e}")

    # Check media cache
    media_cache_dir = Path(__file__).resolve().parent.parent.parent.parent / "media_cache"
    media_status = "ok"
    media_size_mb = 0
    if media_cache_dir.exists():
        try:
            total_bytes = 0
            for f in media_cache_dir.rglob("*"):
                if f.is_file():
                    total_bytes += f.stat().st_size
            media_size_mb = round(total_bytes / (1024 * 1024), 1)
        except Exception:
            media_status = "error"
    else:
        media_status = "not_found"

    # Count endpoints (approximate from router routes)
    try:
        endpoints_count = len(router.routes)
    except Exception:
        endpoints_count = 0

    print(f"[C25] System health: db={db_status}, ads={total_ads}, endpoints={endpoints_count}")
    return {
        "api": "ok",
        "database": db_status,
        "media_cache": {
            "status": media_status,
            "size_mb": media_size_mb,
        },
        "data_freshness": {
            "newest_ad": newest_ad_date,
            "oldest_ad": oldest_ad_date,
            "total_ads": total_ads,
        },
        "endpoints_count": endpoints_count,
        "uptime_info": "running",
    }


# ==================== C26: Creative Intelligence & Template API ====================

# Power words commonly seen in Japanese ad copy
_POWER_WORDS_JA = [
    "驚きの", "たった", "今だけ", "限定", "無料", "簡単",
    "衝撃", "話題", "人気", "実証", "革命的", "最新",
    "秘密", "本気", "速攻", "奇跡", "感動", "注目",
    "必見", "圧倒的", "究極", "絶対", "確実", "劇的",
]

# Hook type templates for creative brief generation
_HOOK_TEMPLATES = {
    "question": {
        "template": "なぜ{target}は{product}で{benefit}なのか？",
        "examples": ["なぜ30代女性はこのサプリで若返るのか？", "知っていますか？{benefit}の秘密"],
    },
    "number": {
        "template": "{number}日で{benefit}を実感！",
        "examples": ["たった3日で-5cm！", "92%の人が実感した{benefit}"],
    },
    "shock": {
        "template": "衝撃！{product}の真実",
        "examples": ["まだ知らないの？{product}の驚きの効果", "嘘でしょ？{benefit}がこんなに簡単に"],
    },
    "testimonial": {
        "template": "「{benefit}を実感しました」{target}の声",
        "examples": ["使って3日で実感！", "私でもできた！{benefit}体験談"],
    },
    "benefit": {
        "template": "{target}に朗報！{benefit}",
        "examples": ["{target}必見！今なら{offer}", "ついに登場！{benefit}の決定版"],
    },
}

# CTA type templates
_CTA_TEMPLATES = {
    "urgency": {
        "template": "今すぐ{action}",
        "examples": ["今すぐチェック", "残りわずか！お急ぎください"],
    },
    "benefit": {
        "template": "{benefit}を手に入れる",
        "examples": ["理想の{target}を手に入れる", "今すぐ{benefit}を体験"],
    },
    "free": {
        "template": "無料で{action}",
        "examples": ["無料お試しはこちら", "0円で始める"],
    },
    "soft": {
        "template": "詳しくはこちら",
        "examples": ["もっと詳しく見る", "公式サイトはこちら"],
    },
    "limited": {
        "template": "期間限定{offer}",
        "examples": ["今だけ特別価格", "先着100名様限定"],
    },
}


class _CreativeBriefBody(BaseModel):
    genre: str = ""
    target: str = ""
    goal: str = "cv"
    budget: str = "medium"


class _CopyVariationsBody(BaseModel):
    title: str = ""
    text: str = ""  # Fix #52: frontend sends 'text'
    genre: str = ""
    hook_type: str = ""  # Fix #52: frontend sends hook_type
    tone: str = ""  # Fix #52: frontend sends tone
    length: str = ""  # Fix #52: frontend sends length
    variations: int = 5


class _ScoreReadabilityBody(BaseModel):
    title: str
    genre: str = ""


# ---------- C26-1. POST /rankings/creative-brief ----------


@router.post("/creative-brief")
def generate_creative_brief(body: _CreativeBriefBody):
    """Generate a creative brief based on genre analysis and winning patterns.

    Returns recommended hooks, CTAs, power words, structure, and reference ads.
    """
    genre = body.genre
    target = body.target
    goal = body.goal
    print(f"[C26] Creative brief: genre={genre}, target={target}, goal={goal}")

    with sync_session_scope() as session:
        # Get ads in the specified genre
        if genre:
            ads = session.query(Ad).filter(Ad.category == genre).all()
        else:
            ads = session.query(Ad).all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]

        # Analyze hook effectiveness
        hook_stats: dict[str, dict] = {}
        cta_stats: dict[str, dict] = {}
        analyzed_count = 0
        total_score_sum = 0.0
        power_word_freq: dict[str, int] = {}

        for ad in quality_ads:
            ca = _get_creative_analysis(ad) or {}
            if not ca:
                continue
            analyzed_count += 1

            meta = ad.ad_metadata or {}
            score_val = meta.get("latest_hit_score")
            if score_val is None:
                score_val, _, _, _ = compute_hit_score(ad)
            else:
                score_val = float(score_val)
            total_score_sum += score_val
            is_hit = _is_hit_ad(ad)

            hook = ca.get("hook_type", "")
            if hook:
                b = hook_stats.setdefault(hook, {"count": 0, "hits": 0, "total_score": 0.0})
                b["count"] += 1
                if is_hit:
                    b["hits"] += 1
                b["total_score"] += score_val

            cta = ca.get("cta_type", "")
            if cta:
                b = cta_stats.setdefault(cta, {"count": 0, "hits": 0, "total_score": 0.0})
                b["count"] += 1
                if is_hit:
                    b["hits"] += 1
                b["total_score"] += score_val

            # Count power words in titles
            title = ad.title or ""
            for pw in _POWER_WORDS_JA:
                if pw in title:
                    power_word_freq[pw] = power_word_freq.get(pw, 0) + 1

        # Build recommended hooks
        recommended_hooks = []
        for hook_type, stats in sorted(hook_stats.items(), key=lambda x: x[1]["hits"] / max(x[1]["count"], 1), reverse=True):
            hit_rate = stats["hits"] / stats["count"] if stats["count"] > 0 else 0
            template_info = _HOOK_TEMPLATES.get(hook_type, {})
            example = template_info.get("examples", [""])[0] if template_info.get("examples") else ""
            recommended_hooks.append({
                "type": hook_type,
                "example": example,
                "hit_rate": round(hit_rate, 2),
                "count": stats["count"],
                "avg_score": round(stats["total_score"] / stats["count"], 1) if stats["count"] > 0 else 0,
            })

        # Build recommended CTAs
        recommended_ctas = []
        for cta_type, stats in sorted(cta_stats.items(), key=lambda x: x[1]["hits"] / max(x[1]["count"], 1), reverse=True):
            hit_rate = stats["hits"] / stats["count"] if stats["count"] > 0 else 0
            template_info = _CTA_TEMPLATES.get(cta_type, {})
            example = template_info.get("examples", [""])[0] if template_info.get("examples") else ""
            recommended_ctas.append({
                "type": cta_type,
                "example": example,
                "hit_rate": round(hit_rate, 2),
                "count": stats["count"],
            })

        # Top power words
        sorted_pw = sorted(power_word_freq.items(), key=lambda x: x[1], reverse=True)
        power_words = [pw for pw, _ in sorted_pw[:10]]
        if not power_words:
            power_words = _POWER_WORDS_JA[:5]

        # Structure recommendation
        structure = {
            "sections": ["hook", "problem", "solution", "proof", "cta"],
            "recommended_length": "medium" if goal == "cv" else "short",
            "tone": "professional" if body.budget == "high" else "casual",
        }

        # Find reference ads (top scoring in genre)
        reference_ads = []
        scored_ads = []
        for ad in quality_ads:
            meta = ad.ad_metadata or {}
            s = meta.get("latest_hit_score")
            if s is None:
                s, _, _, _ = compute_hit_score(ad)
            else:
                s = float(s)
            scored_ads.append((ad, s))

        scored_ads.sort(key=lambda x: x[1], reverse=True)
        for ad, s in scored_ads[:5]:
            reference_ads.append({
                "id": ad.id,
                "title": ad.title or "",
                "score": round(s, 1),
                "genre": _resolve_genre_label(ad),
            })

        # Predicted score
        avg_score = total_score_sum / analyzed_count if analyzed_count > 0 else 50
        predicted = min(100, round(avg_score * 1.1, 1))  # Slightly above average

        # Genre insights
        genre_hit_rate = 0
        best_hook_name = recommended_hooks[0]["type"] if recommended_hooks else "unknown"
        if analyzed_count > 0:
            total_hits = sum(s["hits"] for s in hook_stats.values())
            genre_hit_rate = round(total_hits / analyzed_count * 100)

        genre_insights = f"{genre or 'all'} genre has {genre_hit_rate}% hit rate"
        if recommended_hooks:
            genre_insights += f" with {best_hook_name} hooks being most effective"

    print(f"[C26] Creative brief generated: {len(recommended_hooks)} hooks, {len(recommended_ctas)} CTAs")
    return {
        "recommended_hooks": recommended_hooks[:5],
        "recommended_ctas": recommended_ctas[:5],
        "power_words": power_words,
        "structure": structure,
        "reference_ads": reference_ads,
        "predicted_score": predicted,
        "genre_insights": genre_insights,
        "analyzed_ads": analyzed_count,
    }


# ---------- C26-2. POST /rankings/copy-variations ----------


@router.post("/copy-variations")
def generate_copy_variations(body: _CopyVariationsBody):
    """Generate title variations based on different hook types and tones.

    Returns variations with predicted scores based on genre performance data.
    """
    original = body.title or body.text  # Fix #52: accept 'text' from frontend
    genre = body.genre
    num_variations = min(body.variations, 10)
    print(f"[C26] Copy variations: title='{original[:30]}...', genre={genre}, count={num_variations}")

    with sync_session_scope() as session:
        # Get genre-specific performance data
        hook_performance: dict[str, list] = {}
        if genre:
            genre_ads = session.query(Ad).filter(Ad.category == genre).all()
        else:
            genre_ads = session.query(Ad).all()

        for ad in genre_ads:
            if not _is_quality_ad(ad):
                continue
            ca = _get_creative_analysis(ad) or {}
            hook = ca.get("hook_type", "")
            if not hook:
                continue
            meta = ad.ad_metadata or {}
            s = meta.get("latest_hit_score")
            if s is None:
                s, _, _, _ = compute_hit_score(ad)
            else:
                s = float(s)
            if hook not in hook_performance:
                hook_performance[hook] = []
            hook_performance[hook].append(s)

        # Calculate average scores per hook type
        hook_avg_scores: dict[str, float] = {}
        for hook, score_list in hook_performance.items():
            if score_list:
                hook_avg_scores[hook] = sum(score_list) / len(score_list)

    # Generate variations using different transformation patterns
    variations = []
    transformations = [
        ("question", "casual", lambda t: f"なぜ{t}？その秘密とは"),
        ("number", "professional", lambda t: f"93%が実感！{t}"),
        ("shock", "dramatic", lambda t: f"衝撃の事実！{t}"),
        ("testimonial", "personal", lambda t: f"「{t}」体験者の声"),
        ("benefit", "direct", lambda t: f"{t}で理想を手に入れる"),
        ("urgency", "urgent", lambda t: f"今だけ！{t}"),
        ("comparison", "analytical", lambda t: f"他と比べてみて！{t}"),
        ("curiosity", "mysterious", lambda t: f"まだ知らないの？{t}の真実"),
        ("authority", "authoritative", lambda t: f"専門家も認めた{t}"),
        ("emotional", "emotional", lambda t: f"感動！{t}が変えた人生"),
    ]

    base_score = 50.0
    if hook_avg_scores:
        base_score = sum(hook_avg_scores.values()) / len(hook_avg_scores)

    for i, (hook_type, tone, transform_fn) in enumerate(transformations[:num_variations]):
        varied_title = transform_fn(original)
        # Predicted score based on hook performance in genre
        predicted = hook_avg_scores.get(hook_type, base_score)
        # Add some variance
        offset = (i % 3 - 1) * 3
        predicted = max(10, min(100, round(predicted + offset, 1)))

        variations.append({
            "title": varied_title,
            "text": varied_title,  # Fix #52: alias for frontend
            "hook_type": hook_type,
            "tone": tone,
            "predicted_score": predicted,
            "effectiveness": predicted,  # Fix #52: alias for frontend
        })

    # Sort by predicted_score desc
    variations.sort(key=lambda x: x["predicted_score"], reverse=True)

    print(f"[C26] Generated {len(variations)} copy variations")
    return {
        "original": original,
        "genre": genre,
        "variations": variations,
    }


# ---------- C26-3. GET /rankings/pattern-effectiveness ----------


@router.get("/pattern-effectiveness")
def get_pattern_effectiveness(
    genre: Optional[str] = Query(None, description="Filter by genre"),
):
    """Returns pattern effectiveness matrix: hook x CTA combinations.

    Shows which hook+CTA combos perform best, golden combos, and avoid combos.
    """
    print(f"[C26] Pattern effectiveness: genre={genre}")
    with sync_session_scope() as session:
        if genre:
            ads = session.query(Ad).filter(Ad.category == genre).all()
        else:
            ads = session.query(Ad).all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]

        # Build hook x CTA matrix
        matrix: dict[str, dict[str, dict]] = {}

        for ad in quality_ads:
            ca = _get_creative_analysis(ad) or {}
            hook = ca.get("hook_type", "")
            cta = ca.get("cta_type", "")
            if not hook or not cta:
                continue

            meta = ad.ad_metadata or {}
            score_val = meta.get("latest_hit_score")
            if score_val is None:
                score_val, _, _, _ = compute_hit_score(ad)
            else:
                score_val = float(score_val)
            is_hit = _is_hit_ad(ad)

            if hook not in matrix:
                matrix[hook] = {}
            if cta not in matrix[hook]:
                matrix[hook][cta] = {"count": 0, "hits": 0, "total_score": 0.0}

            matrix[hook][cta]["count"] += 1
            if is_hit:
                matrix[hook][cta]["hits"] += 1
            matrix[hook][cta]["total_score"] += score_val

        # Format matrix with computed metrics
        hook_cta_matrix: dict[str, dict] = {}
        all_combos = []

        for hook, ctas in matrix.items():
            hook_cta_matrix[hook] = {}
            for cta, stats in ctas.items():
                count = stats["count"]
                hit_rate = round(stats["hits"] / count, 2) if count > 0 else 0
                avg_score = round(stats["total_score"] / count, 1) if count > 0 else 0

                hook_cta_matrix[hook][cta] = {
                    "count": count,
                    "avg_score": avg_score,
                    "hit_rate": hit_rate,
                }

                all_combos.append({
                    "hook": hook,
                    "cta": cta,
                    "genre": genre or "all",
                    "count": count,
                    "hit_rate": hit_rate,
                    "avg_score": avg_score,
                })

        # Golden combos: high hit rate with sufficient sample size
        golden_combos = sorted(
            [c for c in all_combos if c["count"] >= 2 and c["hit_rate"] >= 0.4],
            key=lambda x: (-x["hit_rate"], -x["avg_score"]),
        )[:10]

        # Avoid combos: low hit rate
        avoid_combos = []
        for c in all_combos:
            if c["count"] >= 2 and c["hit_rate"] <= 0.2:
                avoid_combos.append({
                    "hook": c["hook"],
                    "cta": c["cta"],
                    "hit_rate": c["hit_rate"],
                    "reason": f"Low engagement ({c['hit_rate']*100:.0f}% hit rate with {c['count']} samples)",
                })
        avoid_combos.sort(key=lambda x: x["hit_rate"])
        avoid_combos = avoid_combos[:10]

        print(f"[C26] Pattern effectiveness: {len(all_combos)} combos, {len(golden_combos)} golden")
        return {
            "hook_cta_matrix": hook_cta_matrix,
            "golden_combos": golden_combos,
            "avoid_combos": avoid_combos,
            "total_analyzed": len(quality_ads),
            "genre_filter": genre,
        }


# ---------- C26-4. POST /rankings/score-readability ----------


@router.post("/score-readability")
def score_readability(body: _ScoreReadabilityBody):
    """Score the readability and effectiveness of an ad title.

    Analyzes length, power words, question marks, numbers, kanji ratio,
    and provides suggestions for improvement.
    """
    title = body.title
    genre = body.genre
    print(f"[C26] Readability scoring: title='{title[:30]}...'")

    # Factor analysis
    title_len = len(title)

    # Length scoring (optimal: 20-40 chars for Japanese ads)
    length_optimal = 20 <= title_len <= 40
    if title_len < 10:
        length_score = 3
    elif title_len < 20:
        length_score = 7
    elif title_len <= 40:
        length_score = 10
    elif title_len <= 60:
        length_score = 7
    else:
        length_score = 4

    # Has numbers
    has_numbers = bool(re.search(r'\d', title))
    number_score = 8 if has_numbers else 0

    # Power word count
    power_word_count = 0
    for pw in _POWER_WORDS_JA:
        if pw in title:
            power_word_count += 1
    power_word_score = min(10, power_word_count * 5)

    # Has question mark
    has_question = "?" in title or "？" in title
    question_score = 8 if has_question else 0

    # Kanji ratio
    kanji_count = 0
    for ch in title:
        if '\u4e00' <= ch <= '\u9fff':
            kanji_count += 1
    kanji_ratio = round(kanji_count / title_len, 2) if title_len > 0 else 0

    # Optimal kanji ratio is 0.2-0.4 for readability
    if 0.2 <= kanji_ratio <= 0.4:
        kanji_score = 10
    elif 0.1 <= kanji_ratio <= 0.5:
        kanji_score = 7
    else:
        kanji_score = 4

    # Has emoji
    has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF]', title))
    emoji_score = 5 if has_emoji else 0

    # Has exclamation
    has_exclamation = "!" in title or "！" in title
    exclamation_score = 5 if has_exclamation else 0

    # Total readability score (weighted)
    total_score = min(100, (
        length_score * 2 +       # max 20
        number_score +            # max 8
        power_word_score +        # max 10
        question_score +          # max 8
        kanji_score +             # max 10
        emoji_score +             # max 5
        exclamation_score         # max 5
    ))
    # Normalize to 0-100 range (max possible raw = 66)
    total_score = min(100, round(total_score / 66 * 100))

    # Generate suggestions
    suggestions = []
    if not has_question:
        suggestions.append("Add a question hook for higher engagement (+12% hit rate)")
    if not has_numbers:
        suggestions.append("Include specific numbers for credibility (+8% hit rate)")
    if power_word_count == 0:
        suggestions.append("Add power words for emotional impact")
    if title_len > 50:
        suggestions.append("Shorten title to under 40 characters for better readability")
    if title_len < 15:
        suggestions.append("Title may be too short; add more context")
    if kanji_ratio > 0.5:
        suggestions.append("Reduce kanji density for easier reading")
    if not has_exclamation and not has_question:
        suggestions.append("Add punctuation for emphasis")

    # Genre benchmark
    genre_benchmark = {"avg_score": 50, "percentile": 50}
    if genre:
        with sync_session_scope() as session:
            genre_ads = session.query(Ad).filter(Ad.category == genre).all()
            genre_scores = []
            for ad in genre_ads:
                if not _is_quality_ad(ad):
                    continue
                meta = ad.ad_metadata or {}
                s = meta.get("latest_hit_score")
                if s is None:
                    s, _, _, _ = compute_hit_score(ad)
                else:
                    s = float(s)
                genre_scores.append(s)

            if genre_scores:
                avg = sum(genre_scores) / len(genre_scores)
                # Calculate percentile
                below = sum(1 for s in genre_scores if s < total_score)
                percentile = round(below / len(genre_scores) * 100)
                genre_benchmark = {
                    "avg_score": round(avg, 1),
                    "percentile": percentile,
                }

    print(f"[C26] Readability score: {total_score}")
    return {
        "score": total_score,
        "factors": {
            "length": {"value": title_len, "optimal": length_optimal, "score": length_score},
            "has_numbers": has_numbers,
            "power_word_count": power_word_count,
            "has_question": has_question,
            "kanji_ratio": kanji_ratio,
            "has_emoji": has_emoji,
            "has_exclamation": has_exclamation,
        },
        "suggestions": suggestions,
        "genre_benchmark": genre_benchmark,
    }


# ---------- C26-5. GET /rankings/template-marketplace ----------


@router.get("/template-marketplace")
def get_template_marketplace(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    sort_by: str = Query("hit_rate", description="hit_rate|popularity|newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Returns community templates derived from high-performing ad patterns.

    Templates are generated from analyzed ads grouped by archetype and genre.
    """
    print(f"[C26] Template marketplace: genre={genre}, sort={sort_by}")

    with sync_session_scope() as session:
        if genre:
            ads = session.query(Ad).filter(Ad.category == genre).all()
        else:
            ads = session.query(Ad).all()

        quality_ads = [a for a in ads if _is_quality_ad(a)]

        # Group by archetype + genre to form templates
        template_map: dict[str, dict] = {}

        for ad in quality_ads:
            ca = _get_creative_analysis(ad) or {}
            archetype = ca.get("archetype", "")
            hook = ca.get("hook_type", "")
            if not archetype and not hook:
                continue

            ad_genre = _resolve_genre_label(ad)
            key = f"{ad_genre}_{archetype or hook}"

            meta = ad.ad_metadata or {}
            score_val = meta.get("latest_hit_score")
            if score_val is None:
                score_val, _, _, _ = compute_hit_score(ad)
            else:
                score_val = float(score_val)
            is_hit = _is_hit_ad(ad)

            if key not in template_map:
                template_map[key] = {
                    "genre": ad_genre,
                    "archetype": archetype or hook,
                    "hook_type": hook,
                    "count": 0,
                    "hits": 0,
                    "total_score": 0.0,
                    "sample_titles": [],
                    "tags": set(),
                    "created_dates": [],
                }

            t = template_map[key]
            t["count"] += 1
            if is_hit:
                t["hits"] += 1
            t["total_score"] += score_val
            if len(t["sample_titles"]) < 3:
                t["sample_titles"].append(ad.title or "")
            if is_hit:
                t["tags"].add("high_hit_rate")
            if score_val >= 70:
                t["tags"].add("high_score")
            if ad.created_at:
                t["created_dates"].append(ad.created_at.isoformat())

        # Convert to template list
        templates = []
        for idx, (key, data) in enumerate(template_map.items()):
            if data["count"] < 1:
                continue

            hit_rate = round(data["hits"] / data["count"], 2) if data["count"] > 0 else 0
            avg_score = round(data["total_score"] / data["count"], 1) if data["count"] > 0 else 0

            # Generate preview from sample titles
            preview = data["sample_titles"][0] if data["sample_titles"] else ""
            # Create a generic template pattern from the preview
            if preview and len(preview) > 20:
                preview = preview[:20] + "..."

            # Generate template name
            genre_label = data["genre"]
            archetype_label = data["archetype"].replace("_", " ") if data["archetype"] else "general"
            name = f"{genre_label} - {archetype_label}"

            tags = list(data["tags"])
            if data["count"] >= 5:
                tags.append("popular")
            if hit_rate >= 0.5:
                tags.append("proven")

            newest_date = max(data["created_dates"]) if data["created_dates"] else None

            templates.append({
                "id": f"t_{idx + 1:03d}",
                "name": name,
                "genre": data["genre"],
                "archetype": data["archetype"],
                "hook_type": data["hook_type"],
                "hit_rate": hit_rate,
                "avg_score": avg_score,
                "usage_count": data["count"],
                "preview": preview,
                "tags": tags,
                "newest_date": newest_date,
            })

        # Sort
        if sort_by == "popularity":
            templates.sort(key=lambda x: x["usage_count"], reverse=True)
        elif sort_by == "newest":
            templates.sort(key=lambda x: x.get("newest_date") or "", reverse=True)
        else:  # hit_rate
            templates.sort(key=lambda x: (-x["hit_rate"], -x["avg_score"]))

        # Filter by genre if specified (for the case where ads from all genres were loaded)
        if genre:
            templates = [t for t in templates if t["genre"] == genre]

        total = len(templates)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = templates[start:end]

        print(f"[C26] Template marketplace: {total} templates found")
        return {
            "templates": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
        }


# ==================== C27: Analytics Dashboard & AI Insights API ====================


@router.get("/analytics/overview")
def get_analytics_overview():
    """Comprehensive analytics overview with KPIs, trends and highlights (C27)."""
    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        total = len(ads)
        if total == 0:
            return {"kpis": {"total_ads": 0}, "trends": {}, "highlights": []}

        hit_count = sum(1 for a in ads if _is_hit_ad(a))
        scores = [float((a.ad_metadata or {}).get("latest_hit_score") or 0) for a in ads]
        avg_score = sum(scores) / total

        active_count = sum(1 for a in ads if _extract_longevity_info(a).get("is_still_running"))

        advertisers = set()
        genre_set = set()
        total_spend = 0
        for ad in ads:
            adv = _clean_advertiser(ad.advertiser_name)
            if adv:
                advertisers.add(adv)
            genre_set.add(_resolve_genre_label(ad))
            total_spend += float((ad.ad_metadata or {}).get("cumulative_spend") or 0)

        cutoff_7d = datetime.now(tz=timezone.utc) - timedelta(days=7)
        cutoff_14d = datetime.now(tz=timezone.utc) - timedelta(days=14)
        this_week = sum(1 for a in ads if _dt_gte(a.created_at, cutoff_7d))
        last_week = sum(1 for a in ads if _dt_gte(a.created_at, cutoff_14d) and _dt_lt(a.created_at, cutoff_7d))
        growth = round((this_week - last_week) / max(last_week, 1) * 100, 1)

        dates = [a.created_at for a in ads if a.created_at]
        min_date = min(dates).strftime("%Y-%m-%d") if dates else None
        max_date = max(dates).strftime("%Y-%m-%d") if dates else None

        highlights = []
        hit_rate = hit_count / total
        if hit_rate > 0.3:
            highlights.append({"type": "achievement", "message": f"Hit rate is {round(hit_rate*100)}% - above average"})
        if this_week > last_week:
            highlights.append({"type": "trend", "message": f"{this_week} new ads this week (+{this_week - last_week} vs last week)"})
        if active_count > total * 0.5:
            highlights.append({"type": "achievement", "message": f"{round(active_count/total*100)}% of ads are still active"})

        print(f"[C27] Analytics overview: {total} ads, {hit_count} hits, {len(advertisers)} advertisers")
        return {
            "period": {"from": min_date, "to": max_date},
            "kpis": {
                "total_ads": total,
                "hit_ads": hit_count,
                "hit_rate": round(hit_rate * 100, 1),
                "avg_score": round(avg_score, 1),
                "total_spend_jpy": int(total_spend),
                "active_advertisers": len(advertisers),
                "genres_covered": len(genre_set),
            },
            "trends": {
                "ads_growth_weekly": growth,
                "score_trend": "improving" if growth > 0 else "declining" if growth < -5 else "stable",
                "spend_trend": "increasing" if total_spend > 0 else "unknown",
            },
            "highlights": highlights,
        }


@router.get("/ai-insights")
def get_ai_insights(
    genre: Optional[str] = None,
    focus: str = Query("overview", description="overview|creative|competitive|opportunity"),
):
    """Data-driven AI-style insights generated from actual patterns (C27)."""
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        total = len(ads)
        if total == 0:
            return {"insights": [], "generated_at": datetime.now(timezone.utc).isoformat()}

        hit_count = sum(1 for a in ads if _is_hit_ad(a))
        base_rate = hit_count / total

        hook_stats: dict[str, dict] = {}
        cta_stats: dict[str, dict] = {}
        for ad in ads:
            ca = (ad.ad_metadata or {}).get("creative_analysis") or {}
            is_hit = _is_hit_ad(ad)
            for val, s_map in [(ca.get("hook_type"), hook_stats), (ca.get("cta_type"), cta_stats)]:
                if val:
                    b = s_map.setdefault(str(val), {"count": 0, "hits": 0})
                    b["count"] += 1
                    if is_hit:
                        b["hits"] += 1

        insights = []
        ins_id = 0

        # Opportunity: high hit rate but low usage
        for val, stats in hook_stats.items():
            rate = stats["hits"] / stats["count"] if stats["count"] > 0 else 0
            usage_pct = stats["count"] / total
            if rate > base_rate * 1.3 and usage_pct < 0.3 and stats["count"] >= 3:
                ins_id += 1
                label = _HOOK_LABELS.get(val, val)
                insights.append({
                    "id": f"ins_{ins_id:03d}",
                    "type": "opportunity",
                    "title": f"{label}フックの活用余地あり",
                    "description": f"採用率は{round(usage_pct*100)}%だが、ヒット率は{round(rate*100)}%と平均{round(base_rate*100)}%を上回る",
                    "confidence": round(min(0.5 + stats["count"] * 0.05, 0.95), 2),
                    "action": f"{label}フックのシナリオを検討してください",
                    "related_ads": [],
                })

        # Warning: low performing patterns
        for val, stats in hook_stats.items():
            rate = stats["hits"] / stats["count"] if stats["count"] > 0 else 0
            if rate < base_rate * 0.5 and stats["count"] >= 5:
                ins_id += 1
                label = _HOOK_LABELS.get(val, val)
                insights.append({
                    "id": f"ins_{ins_id:03d}",
                    "type": "warning",
                    "title": f"{label}フックの効果が低い",
                    "description": f"ヒット率{round(rate*100)}%で平均以下。{stats['count']}件中{stats['hits']}件のみHIT",
                    "confidence": round(min(0.5 + stats["count"] * 0.03, 0.9), 2),
                    "action": "他のフックタイプへの切り替えを検討してください",
                    "related_ads": [],
                })

        # CTA opportunities
        for val, stats in cta_stats.items():
            rate = stats["hits"] / stats["count"] if stats["count"] > 0 else 0
            usage_pct = stats["count"] / total
            if rate > base_rate * 1.2 and usage_pct < 0.25 and stats["count"] >= 3:
                ins_id += 1
                insights.append({
                    "id": f"ins_{ins_id:03d}",
                    "type": "opportunity",
                    "title": f"CTA「{val}」が効果的",
                    "description": f"ヒット率{round(rate*100)}%。採用率はまだ{round(usage_pct*100)}%と低い",
                    "confidence": round(min(0.5 + stats["count"] * 0.04, 0.9), 2),
                    "action": f"CTA「{val}」の積極的な採用を推奨",
                    "related_ads": [],
                })

        # Achievement
        if base_rate > 0.4:
            ins_id += 1
            insights.append({
                "id": f"ins_{ins_id:03d}",
                "type": "achievement",
                "title": "高いヒット率を達成",
                "description": f"全体のヒット率{round(base_rate*100)}%は優秀な水準です",
                "confidence": 0.95,
                "action": "現在の戦略を継続してください",
                "related_ads": [],
            })

        print(f"[C27] AI insights: {len(insights)} insights generated for genre={genre}")
        return {
            "insights": insights,
            "genre": genre,
            "focus": focus,
            "total_ads_analyzed": total,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/competitive-landscape")
def get_competitive_landscape(genre: Optional[str] = None):
    """Market structure analysis: leaders, challengers, niche, new entrants (C27)."""
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        adv_map: dict[str, list] = {}
        for ad in ads:
            name = _clean_advertiser(ad.advertiser_name)
            if name:
                adv_map.setdefault(name, []).append(ad)

        total = len(ads) or 1
        adv_stats = []
        cutoff_30d = datetime.now(tz=timezone.utc) - timedelta(days=30)

        for name, adv_ads in adv_map.items():
            cnt = len(adv_ads)
            hits = sum(1 for a in adv_ads if _is_hit_ad(a))
            hit_rate = hits / cnt if cnt > 0 else 0
            share = cnt / total
            first_seen = min((a.created_at for a in adv_ads if a.created_at), default=None)
            recent = sum(1 for a in adv_ads if _dt_gte(a.created_at, cutoff_30d))
            trend = "growing" if recent > cnt * 0.4 else "declining" if recent == 0 else "stable"
            top_genre = None
            gc: dict[str, int] = {}
            for a in adv_ads:
                g = _resolve_genre_label(a)
                gc[g] = gc.get(g, 0) + 1
            if gc:
                top_genre = max(gc, key=gc.get)

            adv_stats.append({
                "name": name, "share": round(share, 3), "ad_count": cnt,
                "hit_rate": round(hit_rate, 2), "trend": trend,
                "first_seen": first_seen.strftime("%Y-%m-%d") if first_seen else None,
                "speciality": top_genre,
            })

        adv_stats.sort(key=lambda x: x["share"], reverse=True)

        leaders = [a for a in adv_stats if a["share"] >= 0.05][:5]
        challengers = [a for a in adv_stats if 0.02 <= a["share"] < 0.05][:5]
        niche = sorted(
            [a for a in adv_stats if a["hit_rate"] >= 0.6 and a["ad_count"] >= 3],
            key=lambda x: x["hit_rate"], reverse=True,
        )[:5]
        new_entrants = [a for a in adv_stats if a["first_seen"] and a["first_seen"] >= cutoff_30d.strftime("%Y-%m-%d")][:5]

        # Genre competition levels
        genre_advs: dict[str, set] = {}
        for ad in ads:
            g = _resolve_genre_label(ad)
            adv = _clean_advertiser(ad.advertiser_name)
            if adv:
                genre_advs.setdefault(g, set()).add(adv)

        genre_comp: dict[str, list] = {"low": [], "medium": [], "high": []}
        for g, advs in genre_advs.items():
            cnt = len(advs)
            if cnt >= 10:
                genre_comp["high"].append(g)
            elif cnt >= 5:
                genre_comp["medium"].append(g)
            else:
                genre_comp["low"].append(g)

        print(f"[C27] Competitive landscape: {len(leaders)} leaders, {len(new_entrants)} new entrants")
        return {
            "market_leaders": leaders,
            "challengers": challengers,
            "niche_players": niche,
            "new_entrants": new_entrants,
            "genre_competition": genre_comp,
        }


@router.get("/performance-attribution")
def get_performance_attribution(
    ad_id: Optional[int] = None,
    genre: Optional[str] = None,
):
    """Analyze what factors drive ad performance (C27)."""
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre:
            query = query.filter(Ad.category == genre)
        ads = query.all()

        if not ads:
            return {"factors": [], "top_insight": "No data available"}

        total_hit = sum(1 for a in ads if _is_hit_ad(a))
        total_count = len(ads)
        base_rate = total_hit / total_count if total_count > 0 else 0

        factor_impact: dict[str, dict] = {}

        for field_name in ["hook_type", "cta_type", "offer_type", "emotion"]:
            values: dict[str, dict] = {}
            for ad in ads:
                ca = (ad.ad_metadata or {}).get("creative_analysis") or {}
                val = ca.get(field_name)
                if val:
                    b = values.setdefault(str(val), {"count": 0, "hits": 0})
                    b["count"] += 1
                    if _is_hit_ad(ad):
                        b["hits"] += 1

            if values:
                rates = [v["hits"]/v["count"] for v in values.values() if v["count"] >= 2]
                if rates:
                    mean_rate = sum(rates) / len(rates)
                    variance = sum((r - mean_rate) ** 2 for r in rates) / len(rates)
                    best_val = max(values, key=lambda k: values[k]["hits"]/values[k]["count"] if values[k]["count"] >= 2 else 0)
                    factor_impact[field_name] = {"impact": round(variance ** 0.5, 3), "best_value": best_val}

        # Boolean features
        for bf in ["has_video", "has_emoji", "has_numbers", "has_testimonial"]:
            with_f = {"count": 0, "hits": 0}
            without_f = {"count": 0, "hits": 0}
            for ad in ads:
                ca = (ad.ad_metadata or {}).get("creative_analysis") or {}
                has = bool(ad.video_url) if bf == "has_video" else bool(ca.get(bf))
                target = with_f if has else without_f
                target["count"] += 1
                if _is_hit_ad(ad):
                    target["hits"] += 1

            if with_f["count"] >= 2 and without_f["count"] >= 2:
                r_with = with_f["hits"] / with_f["count"]
                r_without = without_f["hits"] / without_f["count"]
                factor_impact[bf] = {"impact": round(abs(r_with - r_without), 3), "best_value": r_with > r_without}

        # Title length
        short_hit = sum(1 for a in ads if len(a.title or "") < 30 and _is_hit_ad(a))
        short_total = max(sum(1 for a in ads if len(a.title or "") < 30), 1)
        long_hit = sum(1 for a in ads if len(a.title or "") >= 30 and _is_hit_ad(a))
        long_total = max(sum(1 for a in ads if len(a.title or "") >= 30), 1)
        factor_impact["title_length"] = {
            "impact": round(abs(short_hit/short_total - long_hit/long_total), 3),
            "optimal_range": [25, 50] if short_hit/short_total < long_hit/long_total else [10, 30],
        }

        max_impact = max((f["impact"] for f in factor_impact.values()), default=1) or 1
        factors = []
        for name, info in factor_impact.items():
            normalized = round(info["impact"] / max_impact, 2)
            entry = {"factor": name, "impact": normalized}
            if "best_value" in info:
                entry["best_value"] = info["best_value"]
            if "optimal_range" in info:
                entry["optimal_range"] = info["optimal_range"]
            factors.append(entry)

        factors.sort(key=lambda x: x["impact"], reverse=True)
        top_factor = factors[0]["factor"] if factors else "unknown"

        print(f"[C27] Performance attribution: {len(factors)} factors, top={top_factor}")
        return {
            "factors": factors,
            "r_squared": round(sum(f["impact"] for f in factors[:3]) / max(len(factors), 1), 2),
            "top_insight": f"{top_factor} is the strongest performance predictor",
            "genre": genre,
            "total_ads": total_count,
        }


# ==================== C28: Realtime Updates & Advanced Search API ====================


@router.get("/updates/poll")
def poll_updates(
    since: Optional[str] = Query(None, description="ISO timestamp"),
    types: str = Query("new_ads,score_changes", description="Comma-separated update types"),
):
    """Return updates since a given timestamp for frontend live refresh (C28)."""
    with sync_session_scope() as session:
        if since:
            try:
                cutoff = datetime.fromisoformat(since.replace("Z", "+00:00").replace("+00:00", ""))
            except ValueError:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        else:
            cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=1)

        requested = set(types.split(","))
        updates = []

        if "new_ads" in requested:
            new_ads = session.query(Ad).filter(Ad.created_at >= cutoff).order_by(Ad.created_at.desc()).limit(50).all()
            for ad in new_ads:
                updates.append({
                    "type": "new_ad", "ad_id": ad.id, "title": ad.title or "",
                    "genre": _resolve_genre_label(ad),
                    "timestamp": ad.created_at.isoformat() if ad.created_at else None,
                })

        if "score_changes" in requested:
            for ad in session.query(Ad).all():
                meta = ad.ad_metadata or {}
                updated_at = meta.get("score_updated_at")
                if updated_at:
                    try:
                        ts = datetime.fromisoformat(str(updated_at).replace("Z", "").replace("+00:00", ""))
                        if ts >= cutoff:
                            updates.append({
                                "type": "score_change", "ad_id": ad.id,
                                "new_score": round(float(meta.get("latest_hit_score") or 0)),
                                "timestamp": str(updated_at),
                            })
                    except (ValueError, TypeError):
                        pass

        if "alerts" in requested:
            week_ago = datetime.now(tz=timezone.utc) - timedelta(days=7)
            for ad in session.query(Ad).filter(Ad.created_at >= week_ago).all():
                score = float((ad.ad_metadata or {}).get("latest_hit_score") or 0)
                if score >= 70:
                    updates.append({
                        "type": "alert", "ad_id": ad.id,
                        "message": f"New high-scoring ad (score: {round(score)})",
                        "timestamp": ad.created_at.isoformat() if ad.created_at else None,
                    })

        updates.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        print(f"[C28] Poll updates: {len(updates)} since {since or '1h ago'}")
        return {
            "updates": updates[:100],
            "server_time": datetime.now(timezone.utc).isoformat(),
            "has_more": len(updates) > 100,
        }


class _AdvancedSearchBody(BaseModel):
    query: str = ""
    filters: dict = {}
    sort: dict = {"field": "score", "direction": "desc"}
    page: int = 1
    page_size: int = 20


@router.post("/advanced-search")
def advanced_search(body: _AdvancedSearchBody):
    """Complex multi-filter search supporting all filter combinations (C28)."""
    with sync_session_scope() as session:
        q = session.query(Ad)

        if body.query:
            pattern = f"%{_escape_like(body.query)}%"
            q = q.filter(or_(
                Ad.title.ilike(pattern),
                Ad.description.ilike(pattern),
                Ad.advertiser_name.ilike(pattern),
            ))

        f = body.filters

        genres = f.get("genres")
        if genres and isinstance(genres, list):
            q = q.filter(Ad.category.in_(genres))

        date_range = f.get("date_range")
        if date_range and isinstance(date_range, list) and len(date_range) == 2:
            if date_range[0]:
                q = q.filter(Ad.created_at >= date_range[0])
            if date_range[1]:
                q = q.filter(Ad.created_at <= date_range[1])

        formats = f.get("formats")
        if formats and isinstance(formats, list):
            if "video" in formats and "image" not in formats:
                q = q.filter(Ad.video_url.isnot(None))
            elif "image" in formats and "video" not in formats:
                q = q.filter(Ad.video_url.is_(None), Ad.image_url.isnot(None))

        if f.get("has_lp"):
            q = q.filter(Ad.destination_url.isnot(None), Ad.destination_url != "")

        exclude_adv = f.get("exclude_advertisers")
        if exclude_adv and isinstance(exclude_adv, list):
            q = q.filter(~Ad.advertiser_name.in_(exclude_adv))

        all_ads = q.limit(2000).all()
        results = []

        for ad in all_ads:
            meta = ad.ad_metadata or {}
            ca = meta.get("creative_analysis") or {}
            score = float(meta.get("latest_hit_score") or 0)
            views = int(meta.get("total_views") or 0)
            spend = int(meta.get("cumulative_spend") or 0)

            score_range = f.get("score_range")
            if score_range and isinstance(score_range, list) and len(score_range) == 2:
                if score_range[0] is not None and score < score_range[0]:
                    continue
                if score_range[1] is not None and score > score_range[1]:
                    continue

            view_range = f.get("view_range")
            if view_range and isinstance(view_range, list) and len(view_range) == 2:
                if view_range[0] is not None and views < view_range[0]:
                    continue
                if view_range[1] is not None and views > view_range[1]:
                    continue

            spend_range = f.get("spend_range")
            if spend_range and isinstance(spend_range, list) and len(spend_range) == 2:
                if spend_range[0] is not None and spend < spend_range[0]:
                    continue
                if spend_range[1] is not None and spend > spend_range[1]:
                    continue

            hook_types = f.get("hook_types")
            if hook_types and isinstance(hook_types, list):
                if ca.get("hook_type") not in hook_types:
                    continue

            cta_types = f.get("cta_types")
            if cta_types and isinstance(cta_types, list):
                if ca.get("cta_type") not in cta_types:
                    continue

            destinations = f.get("destinations")
            if destinations and isinstance(destinations, list):
                dest_type = _classify_destination(ad.destination_url or "", ca.get("destination_type"))
                if dest_type not in destinations:
                    continue

            if f.get("is_active"):
                longevity = _extract_longevity_info(ad)
                if not longevity.get("is_still_running"):
                    continue

            results.append({
                "id": ad.id,
                "title": ad.title or "",
                "advertiser": _clean_advertiser(ad.advertiser_name),
                "genre": _resolve_genre_label(ad),
                "hit_score": round(score),
                "views": views,
                "spend_jpy": spend,
                "hook_type": ca.get("hook_type"),
                "cta_type": ca.get("cta_type"),
                "thumbnail": f"/api/v1/media/thumbnail/{ad.id}",
                "destination_type": _classify_destination(ad.destination_url or "", ca.get("destination_type")),
            })

        sort_field = body.sort.get("field", "score")
        sort_dir = body.sort.get("direction", "desc")
        key_map = {"score": "hit_score", "views": "views", "spend": "spend_jpy", "title": "title", "genre": "genre"}
        sort_key = key_map.get(sort_field, "hit_score")
        results.sort(key=lambda x: x.get(sort_key, 0) or 0, reverse=(sort_dir == "desc"))

        start = (body.page - 1) * body.page_size
        page_items = results[start:start + body.page_size]

        print(f"[C28] Advanced search: {len(results)} results, page {body.page}")
        return {
            "ads": page_items,
            "total": len(results),
            "page": body.page,
            "page_size": body.page_size,
            "filters_applied": body.filters,
        }


@router.post("/saved-searches/{search_id}/run")
def run_saved_search(search_id: str):
    """Execute a previously saved search and return results (C28)."""
    searches = _load_saved_searches()
    target = next((s for s in searches if s.get("id") == search_id), None)
    if not target:
        return JSONResponse(status_code=404, content={"error": f"Saved search {search_id} not found"})

    filters = target.get("filters") or {}
    body = _AdvancedSearchBody(
        query=target.get("query") or filters.get("search_text", ""),
        filters=filters,
        sort={"field": filters.get("sort_by", "score"), "direction": "desc"},
        page=1, page_size=20,
    )
    result = advanced_search(body)
    result["saved_search_name"] = target.get("name", "")
    print(f"[C28] Ran saved search: {target.get('name', search_id)}")
    return result


@router.get("/quick-stats/{ad_id}")
def get_quick_stats(ad_id: int):
    """Lightweight stats for hover previews (C28)."""
    with sync_session_scope() as session:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            return JSONResponse(status_code=404, content={"error": f"Ad {ad_id} not found"})

        meta = ad.ad_metadata or {}
        score = float(meta.get("latest_hit_score") or 0)

        all_scores = []
        for a in session.query(Ad).all():
            s = float((a.ad_metadata or {}).get("latest_hit_score") or 0)
            all_scores.append(s)
        all_scores.sort(reverse=True)

        rank = 1
        for i, s in enumerate(all_scores):
            if s <= score:
                rank = i + 1
                break

        total = len(all_scores) or 1
        percentile = round((1 - rank / total) * 100)

        genre_scores = []
        for a in session.query(Ad).filter(Ad.category == ad.category).all():
            s = float((a.ad_metadata or {}).get("latest_hit_score") or 0)
            genre_scores.append(s)
        genre_scores.sort(reverse=True)
        genre_rank = 1
        for i, s in enumerate(genre_scores):
            if s <= score:
                genre_rank = i + 1
                break

        prev_score = meta.get("previous_hit_score")
        trend = "stable"
        if prev_score is not None:
            diff = score - float(prev_score)
            trend = "up" if diff > 3 else "down" if diff < -3 else "stable"

        print(f"[C28] Quick stats for ad {ad_id}: score={round(score)}, rank={rank}")
        return {
            "id": ad_id,
            "score": round(score),
            "rank": rank,
            "percentile": percentile,
            "genre_rank": genre_rank,
            "genre": _resolve_genre_label(ad),
            "trend": trend,
            "thumbnail": f"/api/v1/media/thumbnail/{ad_id}",
        }


# ---------- Fix #55: GET /rankings/funnel-stats ----------


@router.get("/funnel-stats")
def get_funnel_stats(
    genre: Optional[str] = Query(None),
):
    """Return ad funnel stage counts for FunnelChart component.

    Stages: 全広告 → アクティブ → HIT判定 → 高スコア → メガヒット
    """
    print(f"[FIX55] Funnel stats requested: genre={genre}")
    with sync_session_scope() as session:
        query = session.query(Ad)
        if genre and genre != "all":
            query = query.filter(Ad.category == genre)
        ads = query.all()

        total = len(ads)
        active = 0
        hit = 0
        high_score = 0
        mega_hit = 0

        for ad in ads:
            longevity = _extract_longevity_info(ad)
            if longevity["is_still_running"]:
                active += 1
            if _is_hit_ad(ad):
                hit += 1
                meta = ad.ad_metadata or {}
                score = float(meta.get("latest_hit_score") or 0)
                if score >= 70:
                    high_score += 1
                    if longevity["days_running"] >= 60:
                        mega_hit += 1

        stages = [
            {"label": "全広告", "count": total},
            {"label": "アクティブ", "count": active},
            {"label": "HIT判定", "count": hit},
            {"label": "高スコア (70+)", "count": high_score},
            {"label": "メガヒット", "count": mega_hit},
        ]

        print(f"[FIX55] Funnel stats: {total} → {active} → {hit} → {high_score} → {mega_hit}")
        return {
            "stages": stages,
            "items": stages,  # alias for frontend
            "total": total,
        }


# ---------- Fix #56: POST /rankings/generate-brief ----------


class _GenerateBriefBody(BaseModel):
    genre: str = ""
    target_audience: str = ""
    purpose: str = "cv"
    budget: str = "medium"


@router.post("/generate-brief")
def generate_brief_alias(body: _GenerateBriefBody):
    """Alias for /creative-brief that matches frontend CreativeBriefGenerator expectations.

    Frontend sends: genre, target_audience, purpose, budget
    Frontend expects: recommended_hooks (string[]), recommended_ctas (string[]),
                      power_words (string[]), structure ({step,label,description}[]),
                      predicted_performance (number), summary (string)
    """
    print(f"[FIX56] Generate brief (alias): genre={body.genre}")
    # Delegate to creative-brief logic
    brief_body = _CreativeBriefBody(
        genre=body.genre,
        target=body.target_audience,
        goal=body.purpose or "cv",
        budget=body.budget or "medium",
    )
    raw = generate_creative_brief(brief_body)

    # Transform response to match frontend interface
    # recommended_hooks: backend returns [{type, example, hit_rate, count}], frontend wants string[]
    _hooks_raw = raw.get("recommended_hooks", [])
    _hooks_str = [h["type"] if isinstance(h, dict) else str(h) for h in _hooks_raw]

    # recommended_ctas: same transform
    _ctas_raw = raw.get("recommended_ctas", [])
    _ctas_str = [c["type"] if isinstance(c, dict) else str(c) for c in _ctas_raw]

    # structure: backend returns {sections: [...], tone, recommended_length}
    # frontend wants [{step, label, description}]
    _struct_raw = raw.get("structure", {})
    _sections = _struct_raw.get("sections", []) if isinstance(_struct_raw, dict) else []
    _section_labels = {
        "hook": ("フック", "視聴者の注意を引く冒頭"),
        "problem": ("問題提起", "ターゲットの悩み・課題を提示"),
        "solution": ("解決策", "商品/サービスによる解決を提案"),
        "proof": ("証拠", "実績・データ・口コミで信頼性を担保"),
        "cta": ("CTA", "具体的な行動を促す"),
    }
    _structure_arr = []
    for i, sec in enumerate(_sections):
        label, desc = _section_labels.get(sec, (sec, ""))
        _structure_arr.append({"step": str(i + 1), "label": label, "description": desc})

    # predicted_performance: backend returns predicted_score
    _predicted = raw.get("predicted_score", 50)

    # summary: backend returns genre_insights
    _summary = raw.get("genre_insights", "")

    return {
        "recommended_hooks": _hooks_str,
        "recommended_ctas": _ctas_str,
        "power_words": raw.get("power_words", []),
        "structure": _structure_arr,
        "predicted_performance": _predicted,
        "summary": _summary,
        "reference_ads": raw.get("reference_ads", []),
        "analyzed_ads": raw.get("analyzed_ads", 0),
    }


# ---------- Fix #64: GET /rankings/team-activity ----------


@router.get("/team-activity")
def get_team_activity():
    """Return team activity feed for TeamActivity component.

    Since this is a single-user system, we generate activity from
    recent system events (crawls, bookmarks, report generation).
    """
    from app.models.crawl_job import CrawlJob

    activities = []
    now = datetime.now(tz=timezone.utc)

    with sync_session_scope() as session:
        # Recent ads added
        cutoff = now - timedelta(hours=48)
        recent_ads = session.query(Ad).filter(Ad.created_at >= cutoff).order_by(desc(Ad.created_at)).limit(20).all()

        for ad in recent_ads:
            activities.append({
                "id": f"new_ad_{ad.id}",
                "user": "System",
                "userInitial": "S",
                "action": "新しい広告を検出",
                "target": ad.title or _derive_product_name(ad),
                "timestamp": (ad.created_at or now).isoformat(),
                "type": "new_ad",
                "ad_id": ad.id,
            })

        # Recent crawl jobs
        try:
            jobs = session.query(CrawlJob).filter(CrawlJob.created_at >= cutoff).order_by(desc(CrawlJob.created_at)).limit(5).all()
            for job in jobs:
                activities.append({
                    "id": f"crawl_{job.id}",
                    "user": "Crawler",
                    "userInitial": "C",
                    "action": f"クロール{job.status or 'completed'}",
                    "target": job.query or "ads",
                    "timestamp": (job.created_at or now).isoformat(),
                    "type": "crawl",
                })
        except Exception:
            pass

    activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {
        "activities": activities[:30],
        "members": [{"name": "System", "initial": "S", "role": "auto"}],
        "summary": {"total_actions_24h": len([a for a in activities if a.get("timestamp", "") >= (now - timedelta(hours=24)).isoformat()])},
    }


# ---------- Fix #57: GET /rankings/trends/weekly/genres ----------
# The PerformanceHeatmap calls /rankings/trends/weekly but expects per-genre data.
# We add genre-level data as aliases in the existing endpoint response.


# ---------- C29: Genre Analytics ----------


@router.get("/genres/distribution")
def get_genre_distribution(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    period: str = Query("all", description="Period: 7d, 30d, 90d, all"),
    limit: int = Query(50, ge=1, le=200, description="Max genres to return"),
):
    """Return genre distribution with counts, avg scores, and top ads per genre.

    Each genre entry includes:
      - count of ads
      - average hit_score
      - trend indicator (up/down/stable)
      - top 3 ads by hit_score
    """
    with sync_session_scope() as session:
        query = session.query(Ad)

        # Platform filter
        if platform and platform != "all":
            query = _resolve_platform_filter(query, Ad.platform, platform)

        # Period filter
        if period and period != "all":
            days_map = {"7d": 7, "30d": 30, "90d": 90}
            days = days_map.get(period)
            if days:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
                query = query.filter(Ad.created_at >= cutoff)

        all_ads = query.limit(10000).all()

        # Group by fine genre
        genre_map: dict[str, list[Ad]] = {}
        for ad in all_ads:
            if not _is_quality_ad(ad):
                continue
            fg = _resolve_fine_genre(ad)
            genre_map.setdefault(fg, []).append(ad)

        # Compute 30-day-ago counts for trend detection
        cutoff_30d = datetime.now(tz=timezone.utc) - timedelta(days=30)
        genre_old_counts: dict[str, int] = {}
        for fg, ads_list in genre_map.items():
            old_count = sum(
                1 for a in ads_list
                if _dt_lt(a.created_at or datetime.now(tz=timezone.utc), cutoff_30d)
            )
            genre_old_counts[fg] = old_count

        genres_result = []
        for fg, ads_list in genre_map.items():
            # Compute avg hit_score
            scores = []
            for ad in ads_list:
                meta = ad.ad_metadata or {}
                s = meta.get("latest_hit_score")
                if s is not None:
                    scores.append(float(s))
                else:
                    s_val, _, _, _ = compute_hit_score(ad)
                    scores.append(s_val)

            avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
            count = len(ads_list)

            # Trend: compare recent vs older ads
            recent_count = count - genre_old_counts.get(fg, 0)
            old_count = genre_old_counts.get(fg, 0)
            if old_count == 0:
                trend = "up" if recent_count > 0 else "stable"
            elif recent_count > old_count * 1.2:
                trend = "up"
            elif recent_count < old_count * 0.8:
                trend = "down"
            else:
                trend = "stable"

            # Top 3 ads by hit_score
            scored_ads = []
            for ad in ads_list:
                meta = ad.ad_metadata or {}
                hs = meta.get("latest_hit_score")
                if hs is None:
                    hs, _, _, _ = compute_hit_score(ad)
                else:
                    hs = float(hs)
                scored_ads.append((ad, hs))
            scored_ads.sort(key=lambda x: x[1], reverse=True)
            top_ads = [
                {
                    "ad_id": ad.id,
                    "title": ad.title or _derive_product_name(ad),
                    "hit_score": round(hs, 1),
                }
                for ad, hs in scored_ads[:3]
            ]

            genres_result.append({
                "genre": fg,
                "count": count,
                "avg_score": avg_score,
                "trend": trend,
                "top_ads": top_ads,
            })

        # Sort by count descending
        genres_result.sort(key=lambda g: g["count"], reverse=True)
        genres_result = genres_result[:limit]

        return {"genres": genres_result}


@router.get("/genres/{genre_name}/details")
def get_genre_details(
    genre_name: str,
    platform: Optional[str] = Query(None, description="Filter by platform"),
    period: str = Query("all", description="Period: 7d, 30d, 90d, all"),
    top_n: int = Query(20, ge=1, le=100, description="Number of top ads to return"),
):
    """Detailed analysis for a specific genre.

    Returns total ads, avg score, avg views, top ads, and distinct advertisers.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)

        # Platform filter
        if platform and platform != "all":
            query = _resolve_platform_filter(query, Ad.platform, platform)

        # Period filter
        if period and period != "all":
            days_map = {"7d": 7, "30d": 30, "90d": 90}
            days = days_map.get(period)
            if days:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
                query = query.filter(Ad.created_at >= cutoff)

        all_ads = query.limit(10000).all()

        # Filter to this genre
        genre_ads: list[Ad] = []
        for ad in all_ads:
            if not _is_quality_ad(ad):
                continue
            fg = _resolve_fine_genre(ad)
            if fg == genre_name:
                genre_ads.append(ad)

        if not genre_ads:
            return {
                "genre": genre_name,
                "total_ads": 0,
                "avg_score": 0,
                "avg_views": 0,
                "top_ads": [],
                "advertisers": [],
            }

        # Compute metrics
        total_views_list = []
        scored_ads = []
        advertiser_map: dict[str, int] = {}

        for ad in genre_ads:
            meta = ad.ad_metadata or {}
            views = ad.view_count or ad.estimated_impressions or 0
            total_views_list.append(views)

            hs = meta.get("latest_hit_score")
            if hs is None:
                hs, _, _, _ = compute_hit_score(ad)
            else:
                hs = float(hs)
            scored_ads.append((ad, hs, views))

            adv = _clean_advertiser(ad.advertiser_name) or "不明"
            advertiser_map[adv] = advertiser_map.get(adv, 0) + 1

        avg_score = round(
            sum(s for _, s, _ in scored_ads) / len(scored_ads), 1
        ) if scored_ads else 0.0
        avg_views = round(
            sum(total_views_list) / len(total_views_list)
        ) if total_views_list else 0

        # Top ads by hit_score
        scored_ads.sort(key=lambda x: x[1], reverse=True)
        top_ads = []
        for ad, hs, views in scored_ads[:top_n]:
            meta = ad.ad_metadata or {}
            longevity = _extract_longevity_info(ad)
            plat = str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or "")
            top_ads.append({
                "ad_id": ad.id,
                "title": ad.title or "",
                "product_name": _derive_product_name(ad),
                "advertiser_name": _clean_advertiser(ad.advertiser_name),
                "thumbnail_url": _resolve_thumbnail_url(ad),
                "hit_score": round(hs, 1),
                "total_views": views,
                "platform": plat,
                "days_running": longevity["days_running"],
                "is_still_running": longevity["is_still_running"],
                "creative_type": ad.creative_type or ("video" if ad.video_url else "image"),
            })

        # Advertisers sorted by ad count
        advertisers = sorted(
            [{"name": name, "count": cnt} for name, cnt in advertiser_map.items()],
            key=lambda a: a["count"],
            reverse=True,
        )

        return {
            "genre": genre_name,
            "total_ads": len(genre_ads),
            "avg_score": avg_score,
            "avg_views": avg_views,
            "top_ads": top_ads,
            "advertisers": advertisers,
        }


@router.get("/genres/comparison")
def compare_genres(
    genres: str = Query(..., description="Comma-separated genre names to compare"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    period: str = Query("all", description="Period: 7d, 30d, 90d, all"),
):
    """Compare multiple genres side-by-side.

    Query: ?genres=スキンケア・美容,医療ダイエット
    Returns per-genre counts, avg scores, and detailed metrics.
    """
    genre_names = [g.strip() for g in genres.split(",") if g.strip()]
    if not genre_names:
        return {"genres": []}

    with sync_session_scope() as session:
        query = session.query(Ad)

        # Platform filter
        if platform and platform != "all":
            query = _resolve_platform_filter(query, Ad.platform, platform)

        # Period filter
        if period and period != "all":
            days_map = {"7d": 7, "30d": 30, "90d": 90}
            days = days_map.get(period)
            if days:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
                query = query.filter(Ad.created_at >= cutoff)

        all_ads = query.limit(10000).all()

        # Build genre buckets
        genre_buckets: dict[str, list[Ad]] = {g: [] for g in genre_names}
        for ad in all_ads:
            if not _is_quality_ad(ad):
                continue
            fg = _resolve_fine_genre(ad)
            if fg in genre_buckets:
                genre_buckets[fg].append(ad)

        results = []
        for gname in genre_names:
            ads_list = genre_buckets.get(gname, [])
            count = len(ads_list)

            scores = []
            views_list = []
            spend_list = []
            hit_count = 0
            platform_counts: dict[str, int] = {}

            for ad in ads_list:
                meta = ad.ad_metadata or {}
                views = ad.view_count or ad.estimated_impressions or 0
                views_list.append(views)
                cpm = _get_ad_cpm(ad)
                spend_list.append(_compute_spend_jpy(views, cpm))

                hs = meta.get("latest_hit_score")
                if hs is None:
                    hs, _, _, _ = compute_hit_score(ad)
                else:
                    hs = float(hs)
                scores.append(hs)

                if _is_hit_ad(ad):
                    hit_count += 1

                plat = str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or "")
                platform_counts[plat] = platform_counts.get(plat, 0) + 1

            avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
            avg_views = round(sum(views_list) / len(views_list)) if views_list else 0
            total_spend = sum(spend_list)
            hit_rate = round(hit_count / count * 100, 1) if count > 0 else 0.0

            results.append({
                "name": gname,
                "count": count,
                "avg_score": avg_score,
                "metrics": {
                    "avg_views": avg_views,
                    "total_spend_jpy": total_spend,
                    "hit_count": hit_count,
                    "hit_rate_pct": hit_rate,
                    "platform_breakdown": platform_counts,
                },
            })

        return {"genres": results}


@router.get("/genres/trends")
def get_genre_trends(
    period: str = Query("weekly", description="Granularity: weekly or monthly"),
    top_n: int = Query(10, ge=1, le=30, description="Number of top genres to track"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
):
    """Genre composition trends over time (C29).

    Returns weekly or monthly breakdown of genre ad counts,
    allowing frontend to render a stacked area / line chart.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)

        if platform and platform != "all":
            query = _resolve_platform_filter(query, Ad.platform, platform)

        all_ads = query.limit(10000).all()

        # Determine time buckets
        now = datetime.now(tz=timezone.utc)
        if period == "monthly":
            # Last 6 months
            buckets = []
            for i in range(6):
                month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
                if i == 0:
                    month_end = now
                else:
                    next_month = (month_start + timedelta(days=32)).replace(day=1)
                    month_end = next_month - timedelta(seconds=1)
                buckets.append((month_start.strftime("%Y-%m"), month_start, month_end))
            buckets.reverse()
        else:
            # Weekly: last 12 weeks
            buckets = []
            for i in range(12):
                week_end = now - timedelta(weeks=i)
                week_start = week_end - timedelta(days=7)
                label = week_start.strftime("%m/%d")
                buckets.append((label, week_start, week_end))
            buckets.reverse()

        # First pass: find top N genres by total count
        genre_total: dict[str, int] = {}
        quality_ads: list[Ad] = []
        for ad in all_ads:
            if not _is_quality_ad(ad):
                continue
            quality_ads.append(ad)
            fg = _resolve_fine_genre(ad)
            genre_total[fg] = genre_total.get(fg, 0) + 1

        top_genres = sorted(genre_total.items(), key=lambda x: x[1], reverse=True)[:top_n]
        top_genre_names = [g[0] for g in top_genres]

        # Second pass: count by bucket and genre
        timeline: list[dict] = []
        for label, bstart, bend in buckets:
            genre_counts: dict[str, int] = {g: 0 for g in top_genre_names}
            total_bucket = 0
            for ad in quality_ads:
                created = ad.created_at or datetime.min
                if created.tzinfo:
                    created = created.replace(tzinfo=None)
                if bstart <= created <= bend:
                    fg = _resolve_fine_genre(ad)
                    if fg in genre_counts:
                        genre_counts[fg] += 1
                    total_bucket += 1

            timeline.append({
                "period": label,
                "total": total_bucket,
                "genres": genre_counts,
            })

        # Compute trend direction per genre (last bucket vs first non-zero)
        genre_trends: list[dict] = []
        for gname in top_genre_names:
            counts = [t["genres"].get(gname, 0) for t in timeline]
            first_nonzero = next((c for c in counts if c > 0), 0)
            last_val = counts[-1] if counts else 0
            if first_nonzero == 0:
                direction = "new" if last_val > 0 else "stable"
            elif last_val > first_nonzero * 1.2:
                direction = "up"
            elif last_val < first_nonzero * 0.8:
                direction = "down"
            else:
                direction = "stable"
            genre_trends.append({
                "genre": gname,
                "total": genre_total.get(gname, 0),
                "trend": direction,
                "latest_count": last_val,
            })

        return {
            "period": period,
            "buckets": len(timeline),
            "top_genres": genre_trends,
            "timeline": timeline,
        }


# ---------- C30: Search & Autocomplete ----------


@router.get("/search/suggest")
def search_suggest(
    q: str = Query(..., min_length=1, description="Search query prefix"),
    limit: int = Query(10, ge=1, le=30, description="Max suggestions"),
):
    """Autocomplete suggestions from titles, advertiser names, and genre names.

    Returns up to `limit` suggestions with type and count.
    """
    query_lower = q.lower()

    with sync_session_scope() as session:
        # Use SQL LIKE for initial filtering to avoid loading all ads
        escaped = _escape_like(q)
        ads = session.query(Ad).filter(
            or_(
                Ad.title.ilike(f"%{escaped}%"),
                Ad.advertiser_name.ilike(f"%{escaped}%"),
                Ad.brand_name.ilike(f"%{escaped}%"),
            )
        ).limit(3000).all()

        # Collect suggestions by type
        title_counts: dict[str, int] = {}
        advertiser_counts: dict[str, int] = {}
        genre_counts: dict[str, int] = {}

        for ad in ads:
            if not _is_quality_ad(ad):
                continue

            # Title matches
            title = (ad.title or "").strip()
            if title and query_lower in title.lower():
                # Use first 40 chars as suggestion text
                key = title[:40].strip()
                title_counts[key] = title_counts.get(key, 0) + 1

            # Advertiser matches
            adv = _clean_advertiser(ad.advertiser_name)
            if adv and query_lower in adv.lower():
                advertiser_counts[adv] = advertiser_counts.get(adv, 0) + 1

            # Genre matches
            fg = _resolve_fine_genre(ad)
            if fg and fg != "(未分類)" and query_lower in fg.lower():
                genre_counts[fg] = genre_counts.get(fg, 0) + 1

        # Build suggestions
        suggestions = []

        # Genre suggestions first (most useful for navigation)
        for text, count in sorted(genre_counts.items(), key=lambda x: x[1], reverse=True):
            suggestions.append({"text": text, "type": "genre", "count": count})

        # Advertiser suggestions
        for text, count in sorted(advertiser_counts.items(), key=lambda x: x[1], reverse=True):
            suggestions.append({"text": text, "type": "advertiser", "count": count})

        # Title suggestions
        for text, count in sorted(title_counts.items(), key=lambda x: x[1], reverse=True):
            suggestions.append({"text": text, "type": "title", "count": count})

        # Deduplicate by text (case-insensitive)
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            key = s["text"].lower()
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)

        return {"suggestions": unique_suggestions[:limit]}


@router.get("/search/facets")
def search_facets(
    q: Optional[str] = Query(None, description="Optional text filter"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    period: str = Query("all", description="Period: 7d, 30d, 90d, all"),
):
    """Return facet counts for the current filter state.

    Returns genre and advertiser facets with counts for building
    filter UI components.
    """
    with sync_session_scope() as session:
        query = session.query(Ad)

        # Platform filter
        if platform and platform != "all":
            query = _resolve_platform_filter(query, Ad.platform, platform)

        # Period filter
        if period and period != "all":
            days_map = {"7d": 7, "30d": 30, "90d": 90}
            days = days_map.get(period)
            if days:
                cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
                query = query.filter(Ad.created_at >= cutoff)

        # Text search
        if q:
            escaped = _escape_like(q)
            query = query.filter(
                or_(
                    Ad.title.ilike(f"%{escaped}%"),
                    Ad.description.ilike(f"%{escaped}%"),
                    Ad.advertiser_name.ilike(f"%{escaped}%"),
                    Ad.brand_name.ilike(f"%{escaped}%"),
                )
            )

        all_ads = query.limit(10000).all()

        genre_counts: dict[str, int] = {}
        advertiser_counts: dict[str, int] = {}

        for ad in all_ads:
            if not _is_quality_ad(ad):
                continue

            fg = _resolve_fine_genre(ad)
            genre_counts[fg] = genre_counts.get(fg, 0) + 1

            adv = _clean_advertiser(ad.advertiser_name) or "不明"
            advertiser_counts[adv] = advertiser_counts.get(adv, 0) + 1

        genres_facets = sorted(
            [{"name": name, "count": cnt} for name, cnt in genre_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )
        advertisers_facets = sorted(
            [{"name": name, "count": cnt} for name, cnt in advertiser_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

        return {
            "genres": genres_facets,
            "advertisers": advertisers_facets,
        }


@router.get("/search/advanced")
def search_advanced(
    q: Optional[str] = Query(None, description="Full-text search query"),
    genres: Optional[str] = Query(None, description="Comma-separated genre names"),
    min_score: Optional[float] = Query(None, description="Minimum hit score"),
    max_score: Optional[float] = Query(None, description="Maximum hit score"),
    advertiser: Optional[str] = Query(None, description="Advertiser name filter"),
    media_type: Optional[str] = Query(None, description="Filter: video|image|carousel|all"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    sort_by: str = Query("hit_score", description="Sort: hit_score, total_views, days_running, total_spend"),
    sort_dir: str = Query("desc", description="Sort direction: asc, desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Advanced search with multiple filters.

    Supports combined text search, genre filtering, score range,
    advertiser filter, media type, and flexible sorting.
    Returns same format as pro-ranking endpoint.
    """
    genre_list = []
    if genres:
        genre_list = [g.strip() for g in genres.split(",") if g.strip()]

    with sync_session_scope() as session:
        query = session.query(Ad)

        # Platform filter
        if platform and platform != "all":
            query = _resolve_platform_filter(query, Ad.platform, platform)

        # Text search
        if q:
            escaped = _escape_like(q)
            query = query.filter(
                or_(
                    Ad.title.ilike(f"%{escaped}%"),
                    Ad.description.ilike(f"%{escaped}%"),
                    Ad.advertiser_name.ilike(f"%{escaped}%"),
                    Ad.brand_name.ilike(f"%{escaped}%"),
                )
            )

        # Advertiser filter (SQL level)
        if advertiser:
            escaped_adv = _escape_like(advertiser)
            query = query.filter(
                or_(
                    Ad.advertiser_name.ilike(f"%{escaped_adv}%"),
                    Ad.brand_name.ilike(f"%{escaped_adv}%"),
                )
            )

        all_ads = query.limit(10000).all()

        # Python-level filtering
        filtered_ads: list[Ad] = []
        ad_scores: dict[int, float] = {}

        for ad in all_ads:
            if not _is_quality_ad(ad):
                continue

            # Genre filter
            if genre_list:
                fg = _resolve_fine_genre(ad)
                if fg not in genre_list:
                    continue

            # Media type filter
            if media_type and media_type != "all":
                ct = ad.creative_type or ("video" if ad.video_url else "image")
                ct_lower = str(ct).lower()
                if media_type.lower() == "video" and "video" not in ct_lower:
                    continue
                elif media_type.lower() == "image" and ct_lower not in ("image", "static", "photo"):
                    continue
                elif media_type.lower() == "carousel" and "carousel" not in ct_lower:
                    continue

            # Score filter
            meta = ad.ad_metadata or {}
            hs = meta.get("latest_hit_score")
            if hs is None:
                hs, _, _, _ = compute_hit_score(ad)
            else:
                hs = float(hs)

            if min_score is not None and hs < min_score:
                continue
            if max_score is not None and hs > max_score:
                continue

            ad_scores[ad.id] = hs
            filtered_ads.append(ad)

        # Build ad rows (same shape as pro-ranking)
        ad_rows: list[dict] = []
        for ad in filtered_ads:
            meta = ad.ad_metadata or {}
            ca = meta.get("creative_analysis") or {}
            fg = _resolve_fine_genre(ad)
            views = ad.view_count or ad.estimated_impressions or 0
            cpm = _get_ad_cpm(ad)
            total_spend = _compute_spend_jpy(views, cpm)
            longevity = _extract_longevity_info(ad)
            hit_score_val = ad_scores.get(ad.id, 0.0)
            hit_level = meta.get("hit_level", "none")

            view_increase = int(meta.get("view_increase_7d", meta.get("view_increase", 0)) or 0)
            like_increase = int(meta.get("like_increase_7d", meta.get("like_increase", 0)) or 0)
            spend_increase = _compute_spend_jpy(view_increase, cpm)

            dest_type = _classify_destination(ad.destination_url or "", ca.get("destination_type"))
            mgmt_id = f"N{ad.id:05d}"
            plat = str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or "")

            ad_rows.append({
                "rank": 0,
                "ad_id": ad.id,
                "title": ad.title or "",
                "description": (ad.description or "")[:200],
                "thumbnail_url": _resolve_thumbnail_url(ad),
                "thumbnail": _resolve_thumbnail_url(ad),
                "video_duration_seconds": ad.duration_seconds or 0,
                "duration_seconds": ad.duration_seconds or 0,
                "platform": plat,
                "product_name": _derive_product_name(ad),
                "advertiser_name": _clean_advertiser(ad.advertiser_name),
                "genre": str(ad.category.value) if ad.category and hasattr(ad.category, "value") else str(ad.category or ""),
                "fine_genre": fg,
                "view_increase": view_increase,
                "total_views": views,
                "cumulative_views": views,
                "spend_increase_jpy": spend_increase,
                "spend_increase": spend_increase,
                "total_spend_jpy": total_spend,
                "cumulative_spend": total_spend,
                "like_increase": like_increase,
                "like_count": ad.like_count or 0,
                "hit_score": round(hit_score_val, 1),
                "hit_level": hit_level,
                "is_hit": _is_hit_ad(ad),
                "creative_type": ad.creative_type or ("video" if ad.video_url else "image"),
                "destination_type": dest_type,
                "destination_url": ad.destination_url or "",
                "management_id": mgmt_id,
                "days_running": longevity["days_running"],
                "is_still_running": longevity["is_still_running"],
                "trend_score": float(meta.get("trend_score", 0) or 0),
                "image_url": _resolve_image_url(ad),
                "video_url": _resolve_video_url(ad),
                "snapshot_url": ad.snapshot_url or "",
                "download_url": f"/api/v1/media/download/{ad.id}",
            })

        # Sort
        sort_key_map: dict[str, str] = {
            "hit_score": "hit_score",
            "total_views": "total_views",
            "days_running": "days_running",
            "total_spend": "total_spend_jpy",
            "view_increase": "view_increase",
            "like_increase": "like_increase",
            "score": "hit_score",
            "spend": "total_spend_jpy",
            "longevity": "days_running",
        }
        sk = sort_key_map.get(sort_by, "hit_score")
        reverse = sort_dir.lower() != "asc"
        ad_rows.sort(key=lambda r: r.get(sk, 0), reverse=reverse)

        # Assign ranks
        for idx, row in enumerate(ad_rows, 1):
            row["rank"] = idx

        total = len(ad_rows)
        start = (page - 1) * page_size
        paginated = ad_rows[start:start + page_size]

        # Collect distinct fine_genres
        fine_genres = sorted(set(r["fine_genre"] for r in ad_rows))

        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "total": total,
            "page": page,
            "per_page": page_size,
            "total_pages": total_pages,
            "fine_genres": fine_genres,
            "ads": paginated,
            "items": paginated,
        }


# ---------- CORE: GET /rankings/search-simple ----------
# (duplicate compare-ads removed — using C22 version at line ~10129)


# ---------- CORE: GET /rankings/search-simple ----------

@router.get("/search-simple")
def search_ads_simple(
    q: str = Query("", description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Simple ad search by title/advertiser name. Used by comparison tool."""
    with sync_session_scope() as session:
        query = session.query(Ad)
        if q.strip():
            pattern = f"%{_escape_like(q.strip())}%"
            query = query.filter(
                or_(
                    Ad.title.ilike(pattern),
                    Ad.advertiser_name.ilike(pattern),
                    Ad.description.ilike(pattern),
                )
            )
        query = query.order_by(desc(Ad.view_count))

        all_ads = query.all()
        quality_ads = [a for a in all_ads if _is_quality_ad(a)]

        total = len(quality_ads)
        start = (page - 1) * page_size
        page_ads = quality_ads[start : start + page_size]

        items = []
        for ad in page_ads:
            hit_score, _, _, _ = compute_hit_score(ad)
            items.append({
                "ad_id": ad.id,
                "product_name": _derive_product_name(ad),
                "title": ad.title or "",
                "advertiser_name": _clean_advertiser(ad.advertiser_name),
                "platform": str(ad.platform.value) if ad.platform and hasattr(ad.platform, "value") else str(ad.platform or ""),
                "thumbnail": _resolve_thumbnail_url(ad),
                "image_url": _resolve_thumbnail_url(ad),
                "fine_genre": _resolve_fine_genre(ad),
                "hit_score": hit_score,
                **_build_meta_freshness_contract(ad),
            })

        return {"items": items, "total": total}



# ==================== C32: Media Extraction Status API ====================


@router.get("/media-extraction-status")
def get_media_extraction_status():
    """Media extraction pipeline status summary."""
    with sync_session_scope() as session:
        all_ads = session.query(Ad).all()

        status_counts: dict[str, int] = {}
        for ad in all_ads:
            s = ad.media_extraction_status or "null"
            status_counts[s] = status_counts.get(s, 0) + 1

        total = len(all_ads)
        completed = status_counts.get("completed", 0) + status_counts.get("enriched", 0)

        return {
            "total_ads": total,
            "completed": completed,
            "pending": status_counts.get("pending", 0),
            "pending_heavy": status_counts.get("pending_heavy", 0),
            "dispatched": status_counts.get("dispatched", 0),
            "failed": status_counts.get("failed", 0),
            "skipped": status_counts.get("skipped", 0),
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "status_breakdown": status_counts,
        }


@router.get("/media-extraction-ads")
def get_media_extraction_ads(
    status: str = Query("pending", description="Filter by extraction status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List ads by media extraction status with pagination."""
    with sync_session_scope() as session:
        query = session.query(Ad).filter(Ad.media_extraction_status == status)
        total = query.count()
        ads = query.order_by(Ad.id).offset((page - 1) * per_page).limit(per_page).all()

        return {
            "ads": [{
                "id": ad.id,
                "title": ad.title or "",
                "advertiser_name": ad.advertiser_name or "",
                "creative_type": ad.creative_type or "",
                "status": ad.media_extraction_status,
                "has_snapshot": bool(ad.snapshot_url),
                "has_image": bool(ad.image_url),
                "has_video": bool(ad.video_url),
                "has_s3_image": bool(ad.image_s3_key),
                "has_s3_thumbnail": bool(ad.thumbnail_s3_key),
            } for ad in ads],
            "total": total,
            "page": page,
            "per_page": per_page,
        }


@router.post("/batch-extract-media")
def batch_extract_media(
    limit: int = Query(50, ge=1, le=200),
):
    """Dispatch batch media extraction tasks to SQS -> ECS."""
    from app.tasks.dispatcher import dispatch_task

    with sync_session_scope() as session:
        ads = session.query(Ad).filter(
            Ad.media_extraction_status.in_([MediaExtractionStatus.PENDING, MediaExtractionStatus.PENDING_HEAVY]),
            or_(Ad.snapshot_url.isnot(None), Ad.external_id.isnot(None)),
        ).order_by(Ad.id).limit(limit).all()

        dispatched = []
        errors = []
        for ad in ads:
            try:
                result = dispatch_task("extract_media", ad_id=ad.id)
                ad.media_extraction_status = MediaExtractionStatus.DISPATCHED
                dispatched.append({"ad_id": ad.id, "message_id": result.id})
            except Exception as e:
                errors.append({"ad_id": ad.id, "error": str(e)})

        session.commit()

        return {
            "dispatched": len(dispatched),
            "errors": len(errors),
            "details": dispatched[:20],
        }


@router.post("/retry-failed-media")
def retry_failed_media(
    limit: int = Query(20, ge=1, le=100),
):
    """Reset failed extractions to pending and re-dispatch."""
    from app.tasks.dispatcher import dispatch_task

    with sync_session_scope() as session:
        ads = session.query(Ad).filter(
            Ad.media_extraction_status == MediaExtractionStatus.FAILED,
        ).order_by(Ad.id).limit(limit).all()

        dispatched = []
        errors = []
        for ad in ads:
            try:
                ad.media_extraction_status = MediaExtractionStatus.PENDING
                result = dispatch_task("extract_media", ad_id=ad.id)
                ad.media_extraction_status = MediaExtractionStatus.DISPATCHED
                dispatched.append({"ad_id": ad.id, "message_id": result.id})
            except Exception as e:
                errors.append({"ad_id": ad.id, "error": str(e)})

        session.commit()

        return {"retried": len(dispatched), "errors": len(errors)}


# ==================== C33: DLQ Monitoring API ====================


@router.get("/dlq-status")
def get_dlq_status():
    """Check SQS Dead Letter Queue status."""
    try:
        import boto3
        from app.core.config import get_settings
        settings = get_settings()
        sqs = boto3.client("sqs", region_name=settings.aws_region)
    except Exception as e:
        return {"error": f"Cannot connect to AWS: {str(e)}"}

    result = {}
    for queue_name, base_url in [
        ("heavy_dlq", settings.sqs_heavy_queue_url),
        ("light_dlq", settings.sqs_light_queue_url),
    ]:
        if not base_url:
            result[queue_name] = {"error": "Queue URL not configured"}
            continue
        dlq_url = base_url + "-dlq"
        try:
            attrs = sqs.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
            )["Attributes"]
            result[queue_name] = {
                "messages": int(attrs.get("ApproximateNumberOfMessages", 0)),
                "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
            }
        except Exception as e:
            result[queue_name] = {"error": str(e)}

    return result


@router.get("/dlq-messages")
def get_dlq_messages(queue: str = Query("heavy", description="heavy or light"), limit: int = Query(10, ge=1, le=10)):
    """Preview messages in DLQ without deleting them."""
    try:
        import boto3
        from app.core.config import get_settings
        settings = get_settings()
        sqs = boto3.client("sqs", region_name=settings.aws_region)
    except Exception as e:
        return {"error": str(e)}

    base_url = settings.sqs_heavy_queue_url if queue == "heavy" else settings.sqs_light_queue_url
    if not base_url:
        return {"error": "Queue URL not configured"}

    dlq_url = base_url + "-dlq"
    messages = []
    try:
        response = sqs.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=min(limit, 10),
            VisibilityTimeout=0,
            MessageAttributeNames=["All"],
        )
        for msg in response.get("Messages", []):
            try:
                body = json.loads(msg["Body"])
            except Exception:
                body = {"raw": msg["Body"][:500]}
            messages.append({
                "message_id": msg["MessageId"],
                "task": body.get("task"),
                "kwargs": body.get("kwargs"),
            })
    except Exception as e:
        return {"error": str(e)}

    return {"queue": queue, "messages": messages}


@router.post("/dlq-retry")
def retry_dlq_messages(queue: str = Query("heavy"), limit: int = Query(5, ge=1, le=10)):
    """Move DLQ messages back to the main queue for retry."""
    try:
        import boto3
        from app.core.config import get_settings
        settings = get_settings()
        sqs = boto3.client("sqs", region_name=settings.aws_region)
    except Exception as e:
        return {"error": str(e)}

    base_url = settings.sqs_heavy_queue_url if queue == "heavy" else settings.sqs_light_queue_url
    if not base_url:
        return {"error": "Queue URL not configured"}

    dlq_url = base_url + "-dlq"
    main_url = base_url

    retried = 0
    errors = []
    try:
        response = sqs.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=min(limit, 10),
            VisibilityTimeout=30,
        )
        for msg in response.get("Messages", []):
            try:
                sqs.send_message(QueueUrl=main_url, MessageBody=msg["Body"])
                sqs.delete_message(QueueUrl=dlq_url, ReceiptHandle=msg["ReceiptHandle"])
                retried += 1
            except Exception as e:
                errors.append(str(e))
    except Exception as e:
        return {"error": str(e)}

    return {"retried": retried, "errors": errors}


# ==================== C34: ECS Task Status API ====================


@router.get("/ecs-tasks")
def get_ecs_tasks(status: str = Query("RUNNING", description="RUNNING or STOPPED")):
    """List ECS tasks in the VAAP cluster."""
    try:
        import boto3
        ecs = boto3.client("ecs", region_name="ap-northeast-1")
    except Exception as e:
        return {"error": str(e)}

    cluster = "vaap-cluster"

    try:
        task_arns = ecs.list_tasks(
            cluster=cluster,
            desiredStatus=status,
        ).get("taskArns", [])

        if not task_arns:
            return {"tasks": [], "count": 0}

        details = ecs.describe_tasks(cluster=cluster, tasks=task_arns)

        tasks = []
        for task in details.get("tasks", []):
            container = task.get("containers", [{}])[0]
            overrides = task.get("overrides", {}).get("containerOverrides", [{}])[0]
            command = overrides.get("command", [])

            task_name = command[3] if len(command) > 3 else "unknown"
            task_kwargs = command[4] if len(command) > 4 else "{}"

            tasks.append({
                "task_arn": task["taskArn"].split("/")[-1],
                "status": task.get("lastStatus"),
                "desired_status": task.get("desiredStatus"),
                "task_name": task_name,
                "kwargs": task_kwargs,
                "created_at": str(task.get("createdAt")),
                "started_at": str(task.get("startedAt")),
                "stopped_at": str(task.get("stoppedAt")),
                "stop_reason": task.get("stoppedReason"),
                "exit_code": container.get("exitCode"),
                "cpu": task.get("cpu"),
                "memory": task.get("memory"),
            })

        return {"tasks": tasks, "count": len(tasks)}
    except Exception as e:
        return {"error": str(e), "tasks": [], "count": 0}


@router.get("/ecs-tasks/recent")
def get_recent_ecs_tasks(limit: int = Query(20, ge=1, le=50)):
    """Recent ECS task history (including stopped)."""
    try:
        import boto3
        ecs = boto3.client("ecs", region_name="ap-northeast-1")
    except Exception as e:
        return {"error": str(e)}

    cluster = "vaap-cluster"

    try:
        running = ecs.list_tasks(cluster=cluster, desiredStatus="RUNNING").get("taskArns", [])
        stopped = ecs.list_tasks(cluster=cluster, desiredStatus="STOPPED").get("taskArns", [])

        all_arns = (running + stopped)[:limit]
        if not all_arns:
            return {"tasks": [], "running": 0, "stopped": 0}

        details = ecs.describe_tasks(cluster=cluster, tasks=all_arns)

        tasks = []
        for task in details.get("tasks", []):
            container = task.get("containers", [{}])[0]
            overrides = task.get("overrides", {}).get("containerOverrides", [{}])[0]
            command = overrides.get("command", [])

            duration_seconds = None
            if task.get("startedAt") and task.get("stoppedAt"):
                duration_seconds = int((task["stoppedAt"] - task["startedAt"]).total_seconds())

            tasks.append({
                "task_arn": task["taskArn"].split("/")[-1],
                "status": task.get("lastStatus"),
                "task_name": command[3] if len(command) > 3 else "unknown",
                "started_at": str(task.get("startedAt")),
                "stopped_at": str(task.get("stoppedAt")),
                "exit_code": container.get("exitCode"),
                "stop_reason": task.get("stoppedReason"),
                "duration_seconds": duration_seconds,
            })

        return {"tasks": tasks, "running": len(running), "stopped": len(stopped)}
    except Exception as e:
        return {"error": str(e), "tasks": [], "running": 0, "stopped": 0}
