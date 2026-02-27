"""Daily metrics collection task.

Scans all Ad records and generates AdDailyMetrics rows so that
the ranking system has data to work with.
"""

from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy.orm import Session

import re

from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics

try:
    from app.tasks.worker import celery_app
except ImportError:
    class _FakeCelery:
        def task(self, *a, **kw):
            def decorator(fn):
                fn.delay = lambda *a2, **kw2: None
                fn.apply_async = lambda *a2, **kw2: None
                return fn
            return decorator
    celery_app = _FakeCelery()

logger = structlog.get_logger()

JST = timezone(timedelta(hours=9))


_SPONSOR_RE = re.compile(r"^(.+?)\s*スポンサー[:：]\s*", re.UNICODE)


def _derive_product_name(ad: Ad) -> str:
    """Derive a clean, short product/brand name for display.

    Priority:
      1. brand_name (always clean when present)
      2. advertiser_name (clean up "スポンサー:" prefix)
      3. title — only if short (≤40 chars, looks like a name, not ad copy)
      4. First line of description (truncated)
      5. "不明"
    """
    # 1. brand_name
    if ad.brand_name:
        return ad.brand_name.strip()

    # 2. advertiser_name — strip "Xスポンサー: Y" → "Y"
    adv = (ad.advertiser_name or "").strip()
    if adv:
        m = _SPONSOR_RE.match(adv)
        if m:
            # "コスメ、メイク スポンサー: Medicube Japan" → "Medicube Japan"
            after = adv[m.end():].strip()
            adv = after or m.group(1).strip()

    # 3. title — use only if it's short and looks like a name
    title = (ad.title or "").strip()
    if title and len(title) <= 40 and "\n" not in title:
        # If we also have advertiser, prefer advertiser but append title context
        if adv and adv.lower() != title.lower():
            return adv
        return title

    # 4. advertiser_name is the safest fallback
    if adv:
        return adv

    # 5. description first line
    if ad.description:
        first_line = ad.description.split("\n")[0].strip()
        if first_line:
            return first_line[:40]

    return "不明"


def _category_to_genre(category) -> str | None:
    """Map AdCategoryEnum to Japanese genre label used by SpendEstimator."""
    if category is None:
        return None
    val = category.value if hasattr(category, "value") else str(category)
    mapping = {
        "beauty": "美容・コスメ",
        "health": "健康食品",
        "food": "健康食品",
        "finance": "金融",
        "education": "教育",
        "gaming": "ゲーム",
        "real_estate": "不動産",
        "ec_d2c": "EC・D2C",
        "app": "アプリ",
        "technology": "テクノロジー",
        "travel": "旅行",
        "other": "その他",
    }
    return mapping.get(val, val)


def _estimate_views_from_signals(ad, metadata: dict, target_date: date) -> int:
    """Estimate realistic view count from ad signals when no API data available.

    Uses ad age, platform count, destination URL presence, and description
    length to produce varied per-ad estimates instead of uniform baselines.

    Key improvement: logarithmic growth curve + date-based jitter ensures
    that cumulative values differ each day, producing non-zero
    view_count_increase values for the ranking system.
    """
    import hashlib
    import math

    # Days the ad has been active
    days_active = 1
    if ad.first_seen_at:
        target_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        first_seen = ad.first_seen_at if ad.first_seen_at.tzinfo else ad.first_seen_at.replace(tzinfo=timezone.utc)
        delta = (target_dt - first_seen).days
        days_active = max(1, delta)

    # Platform count (multi-platform = wider reach)
    plats = metadata.get("publisher_platforms", [])
    platform_multiplier = 1.0 + 0.3 * (len(plats) - 1) if len(plats) > 1 else 1.0

    # Destination URL indicates active LP / conversion-focused campaign
    has_destination = 1.3 if metadata.get("destination_url") else 0.8

    # Longer descriptions often correlate with higher-effort campaigns
    desc_len = len(ad.description or "")
    desc_factor = min(1.5, 0.7 + desc_len / 500)

    # Deterministic per-ad hash to add natural variation (±40%)
    h = int(hashlib.md5(str(ad.id).encode()).hexdigest()[:8], 16)
    hash_factor = 0.6 + (h % 800) / 1000  # 0.6 – 1.4

    # Base daily view rate: 500-3000 depending on signals
    base_daily = 800 * platform_multiplier * has_destination * desc_factor * hash_factor

    # Logarithmic growth: older ads accumulate more views but growth rate slows
    # cumulative ≈ base_daily * days_active * (1 + ln(days_active))
    cumulative = base_daily * days_active * (1 + math.log(max(1, days_active)))

    # Date + ad ID jitter (±15%) so cumulative differs each day
    # This ensures view_count_increase > 0 on subsequent days
    date_hash = int(
        hashlib.md5(f"{ad.id}:{target_date}".encode()).hexdigest()[:8], 16
    )
    daily_jitter = 0.85 + (date_hash % 300) / 1000  # 0.85 – 1.15
    cumulative *= daily_jitter

    cumulative = int(cumulative)

    # Clamp to reasonable range
    return max(500, min(cumulative, 5_000_000))


def collect_metrics_for_ads(session: Session, target_date: date | None = None) -> int:
    """Generate AdDailyMetrics rows for all ads on the given date.

    Returns the number of metrics rows created/updated.
    """
    from app.services.competitive.spend_estimator import SpendEstimator

    if target_date is None:
        target_date = datetime.now(JST).date()

    estimator = SpendEstimator()
    ads = session.query(Ad).all()
    created = 0

    for ad in ads:
        # Skip if metrics already exist for this ad + date
        existing = (
            session.query(AdDailyMetrics)
            .filter(
                AdDailyMetrics.ad_id == ad.id,
                AdDailyMetrics.metric_date == target_date,
            )
            .first()
        )
        if existing:
            continue

        # Determine current view count from ad or metadata
        # Priority: real API data > metadata > estimation
        metadata = ad.ad_metadata or {}

        # Check if we have real data from the API (view_count is not None means
        # the API returned actual impressions data — respect it even if 0)
        has_real_views = ad.view_count is not None
        if has_real_views:
            view_count = ad.view_count
        else:
            view_count = (
                metadata.get("impressions_lower")
                or ad.estimated_impressions
                or 0
            )

            # If view_count is still 0 but ad exists (e.g. browser-scraped),
            # estimate a baseline from spend data or assign a minimum so the
            # ad still appears in rankings with non-zero values.
            spend_lower = metadata.get("spend_lower")
            if view_count == 0 and spend_lower and spend_lower > 0:
                # Reverse-estimate views from spend using platform avg CPM
                from app.services.competitive.spend_estimator import PLATFORM_CPM_DEFAULTS
                plat_key = (
                    ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform)
                ).lower()
                cpm = PLATFORM_CPM_DEFAULTS.get(plat_key, {}).get("avg", 400)
                view_count = int(spend_lower / cpm * 1000)

            if view_count == 0:
                # Estimate realistic view count from available signals
                view_count = _estimate_views_from_signals(ad, metadata, target_date)

        # Get previous day's metrics for calculating increase
        prev_metrics = (
            session.query(AdDailyMetrics)
            .filter(
                AdDailyMetrics.ad_id == ad.id,
                AdDailyMetrics.metric_date < target_date,
            )
            .order_by(AdDailyMetrics.metric_date.desc())
            .first()
        )

        if prev_metrics:
            view_count_increase = max(0, view_count - prev_metrics.view_count)
        else:
            # First metric record: treat current view_count as the initial increase
            view_count_increase = view_count

        # Determine spend: real data takes priority over CPM estimation
        platform_str = (
            ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform)
        )
        genre = _category_to_genre(ad.category)

        estimated_spend = 0.0
        estimated_spend_increase = 0.0
        has_real_spend = (ad.spend is not None and ad.spend > 0) or (
            metadata.get("spend_lower") is not None and metadata.get("spend_lower", 0) > 0
        )

        if has_real_spend:
            # Use real spend data from the API
            real_spend = ad.spend if (ad.spend is not None and ad.spend > 0) else metadata.get("spend_lower", 0)
            estimated_spend = real_spend
            if prev_metrics:
                estimated_spend_increase = max(0.0, real_spend - prev_metrics.estimated_spend)
            else:
                estimated_spend_increase = real_spend
        elif view_count_increase > 0:
            # No real spend data — fall back to CPM estimation
            try:
                estimate = estimator.estimate_spend(
                    session,
                    ad_id=ad.id,
                    view_count_increase=view_count_increase,
                    platform=platform_str,
                    genre=genre,
                    target_date=target_date,
                )
                estimated_spend_increase = estimate.estimated_spend
            except Exception as e:
                logger.warning(
                    "spend_estimation_failed", ad_id=ad.id, error=str(e)
                )

            # Cumulative spend = previous cumulative + today's increase
            if prev_metrics:
                estimated_spend = prev_metrics.estimated_spend + estimated_spend_increase
            else:
                estimated_spend = estimated_spend_increase

        # Determine product_name: prefer clean brand/advertiser over ad copy
        product_name = _derive_product_name(ad)

        metrics = AdDailyMetrics(
            ad_id=ad.id,
            metric_date=target_date,
            view_count=view_count,
            view_count_increase=view_count_increase,
            estimated_spend=round(estimated_spend, 2),
            estimated_spend_increase=round(estimated_spend_increase, 2),
            like_count=ad.like_count or 0,
            comment_count=0,
            share_count=0,
            genre=genre,
            product_name=product_name,
            advertiser_name=ad.advertiser_name,
            platform=platform_str,
        )
        session.add(metrics)
        created += 1

    if created > 0:
        session.flush()

    logger.info("metrics_collection_done", date=str(target_date), created=created)
    return created


@celery_app.task(name="app.tasks.metrics_tasks.collect_daily_metrics_task")
def collect_daily_metrics_task():
    """Celery task: collect daily metrics for all ads."""
    from app.core.database import SyncSessionLocal

    logger.info("daily_metrics_collection_start")
    session = SyncSessionLocal()
    try:
        created = collect_metrics_for_ads(session)
        session.commit()
        logger.info("daily_metrics_collection_complete", created=created)
        return {"status": "completed", "created": created}
    except Exception as exc:
        session.rollback()
        logger.error("daily_metrics_collection_failed", error=str(exc))
        raise
    finally:
        session.close()
