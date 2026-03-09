"""Ranking service - compute product/genre rankings from time-series metrics."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, aliased

from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking

logger = structlog.get_logger()

JST = timezone(timedelta(hours=9))
SIGNAL_KEYS = ("longevity", "spend", "active_bonus", "creative", "trend")
DEFAULT_SCORE_PARAMETERS = {
    "weights": {
        "longevity": 1.0,
        "spend": 1.0,
        "active_bonus": 1.0,
        "creative": 1.0,
        "trend": 1.0,
    },
    "thresholds": {
        "hit_score": 45.0,
        "mega_hit_score": 70.0,
        "hit_days_running": 30,
        "mega_hit_days_running": 60,
    },
}


def _today_jst() -> date:
    return datetime.now(JST).date()


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_default_score_parameters() -> dict:
    return {
        "weights": dict(DEFAULT_SCORE_PARAMETERS["weights"]),
        "thresholds": dict(DEFAULT_SCORE_PARAMETERS["thresholds"]),
    }


def validate_score_parameters(score_params: dict | None) -> dict:
    """Validate candidate ranking parameters for safe comparisons."""
    if not score_params:
        return get_default_score_parameters()

    normalized = get_default_score_parameters()
    weights = score_params.get("weights") if isinstance(score_params, dict) else None
    thresholds = score_params.get("thresholds") if isinstance(score_params, dict) else None

    if weights is not None:
        if not isinstance(weights, dict):
            raise ValueError("weights must be an object")
        for key, value in weights.items():
            if key not in SIGNAL_KEYS:
                raise ValueError(f"Unsupported weight key: {key}")
            try:
                weight = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Weight for {key} must be numeric") from exc
            if weight < 0 or weight > 3:
                raise ValueError(f"Weight for {key} must be between 0 and 3")
            normalized["weights"][key] = weight

    if thresholds is not None:
        if not isinstance(thresholds, dict):
            raise ValueError("thresholds must be an object")
        for key, value in thresholds.items():
            if key not in normalized["thresholds"]:
                raise ValueError(f"Unsupported threshold key: {key}")
            try:
                threshold_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Threshold for {key} must be numeric") from exc
            if key.endswith("days_running"):
                if threshold_value < 0 or threshold_value > 365:
                    raise ValueError(f"Threshold for {key} must be between 0 and 365")
                normalized["thresholds"][key] = int(threshold_value)
            else:
                if threshold_value < 0 or threshold_value > 100:
                    raise ValueError(f"Threshold for {key} must be between 0 and 100")
                normalized["thresholds"][key] = threshold_value

    if normalized["thresholds"]["mega_hit_score"] < normalized["thresholds"]["hit_score"]:
        raise ValueError("mega_hit_score must be >= hit_score")
    if normalized["thresholds"]["mega_hit_days_running"] < normalized["thresholds"]["hit_days_running"]:
        raise ValueError("mega_hit_days_running must be >= hit_days_running")

    return normalized


def _apply_score_parameters(signals: dict[str, float], days_running: int, score_params: dict | None) -> tuple[float, bool, str, dict]:
    params = validate_score_parameters(score_params)
    weighted_signals: dict[str, float] = {}
    for key in SIGNAL_KEYS:
        weighted_signals[key] = round((signals.get(key, 0.0) or 0.0) * params["weights"][key], 2)

    hit_score = min(100.0, max(0.0, round(sum(weighted_signals.values()), 1)))
    thresholds = params["thresholds"]
    if hit_score >= thresholds["mega_hit_score"] and days_running >= thresholds["mega_hit_days_running"]:
        hit_level = "mega_hit"
        is_hit = True
    elif hit_score >= thresholds["hit_score"] and days_running >= thresholds["hit_days_running"]:
        hit_level = "hit"
        is_hit = True
    else:
        hit_level = "none"
        is_hit = False
    return hit_score, is_hit, hit_level, weighted_signals


def compute_hit_score(
    ad: Ad,
    metrics: list | None = None,
    genre_stats: dict | None = None,
    score_params: dict | None = None,
) -> tuple[float, bool, str, dict]:
    """マルチシグナル・ヒットスコア計算（v2: 配信日数重視モデル）。

    5つのシグナルを組み合わせて0-100のスコアを算出:
      1. 配信継続力        (0-40)  — 長く配信 = ROIが出ている証拠
      2. 消化額            (0-20)  — 広告費ベース（低閾値）
      3. 配信中ボーナス     (0-20)  — 現在も配信中なら加点
      4. クリエイティブ品質 (0-10)  — 動画/画像/サムネ品質
      5. トレンド/エンゲージメント (0-10) — 直近のview成長率

    ※ Signal 3（オーディエンス）は削除 — データが存在しないため
    ※ Signal 4（配信面）は配信中ボーナスに統合

    Args:
        ad: Ad model instance.
        metrics: Optional list of AdDailyMetrics for this ad (sorted by date).
        genre_stats: Optional dict with genre-level max_spend, p50_spend, max_audience.

    Returns:
        (hit_score, is_hit, hit_level, score_breakdown)
    """
    if not ad:
        return 0.0, False, "none", {}

    meta = ad.ad_metadata or {}
    if metrics is None:
        metrics = []
    if genre_stats is None:
        genre_stats = {}

    signals: dict[str, float] = {}

    # ── 配信日数の算出 ──
    days_running = meta.get("days_running", 0)
    if days_running == 0 and ad.first_seen_at:
        now = datetime.now(timezone.utc)
        first = ad.first_seen_at
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        days_running = max(1, (now - first).days)

    is_still_running = meta.get("is_still_running", ad.last_seen_at is None)

    # ── Signal 1: 配信継続力 (0-40点) ──
    # 14日=5, 30日=15, 60日=25, 90日=35, 120日+=40
    if days_running >= 120:
        longevity = 40.0
    elif days_running >= 90:
        longevity = 35 + (days_running - 90) / 30 * 5
    elif days_running >= 60:
        longevity = 25 + (days_running - 60) / 30 * 10
    elif days_running >= 30:
        longevity = 15 + (days_running - 30) / 30 * 10
    elif days_running >= 14:
        longevity = 5 + (days_running - 14) / 16 * 10
    else:
        longevity = days_running / 14 * 5

    signals["longevity"] = round(min(40.0, longevity), 1)

    # ── Signal 2: 消化額 (0-20点) ──
    # 閾値を下げる: 1万=5, 5万=10, 10万=15, 20万+=20
    total_spend = sum(getattr(m, "estimated_spend_increase", 0) or 0 for m in metrics)
    if total_spend == 0:
        total_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0

    genre_max_spend = genre_stats.get("max_spend", 0)
    genre_p50_spend = genre_stats.get("p50_spend", 0)

    if genre_max_spend > 0 and total_spend > 0:
        spend_ratio = total_spend / genre_max_spend
        spend_score = min(20, spend_ratio * 20)
        if genre_p50_spend > 0 and total_spend > genre_p50_spend * 2:
            spend_score = min(20, spend_score + 5)
    elif total_spend > 0:
        # フォールバック: 絶対額ベースのスコア（閾値を大幅に下げる）
        if total_spend >= 200_000:
            spend_score = 20.0
        elif total_spend >= 100_000:
            spend_score = 15.0
        elif total_spend >= 50_000:
            spend_score = 10.0
        elif total_spend >= 10_000:
            spend_score = 5.0
        else:
            spend_score = min(5.0, total_spend / 10_000 * 5)
    else:
        spend_score = 0.0

    signals["spend"] = round(spend_score, 1)

    # ── Signal 3: 配信中ボーナス (0-20点) ──
    # 現在も配信中であれば大きく加点（ROIが出続けている証拠）
    active_score = 0.0
    if is_still_running:
        if days_running >= 60:
            active_score = 20.0
        elif days_running >= 30:
            active_score = 15.0
        elif days_running >= 14:
            active_score = 10.0
        elif days_running >= 7:
            active_score = 5.0
        else:
            active_score = 2.0

    signals["active_bonus"] = round(active_score, 1)

    # ── Signal 4: クリエイティブ品質 (0-10点) ──
    creative_score = 0.0
    if ad.video_url:
        creative_score += 4
    if ad.image_url:
        creative_score += 3
    if ad.thumbnail_url and "s200x200" not in (ad.thumbnail_url or "") and "favicons" not in (ad.thumbnail_url or ""):
        creative_score += 3

    signals["creative"] = min(10.0, creative_score)

    # ── Signal 5: トレンド/エンゲージメント (0-10点) ──
    trend_score = 0.0
    if len(metrics) >= 3:
        recent = metrics[-3:]
        older = metrics[:-3] if len(metrics) > 3 else metrics[:1]

        recent_avg = sum(getattr(m, "view_count_increase", 0) or 0 for m in recent) / len(recent)
        older_avg = sum(getattr(m, "view_count_increase", 0) or 0 for m in older) / max(len(older), 1)

        if older_avg > 0:
            acceleration = (recent_avg - older_avg) / older_avg
            trend_score = min(10, max(0, acceleration * 20))
        else:
            trend_score = 5.0 if recent_avg > 0 else 0.0
    elif len(metrics) >= 1:
        # メトリクスが少なくても、存在すれば少し加点
        any_views = sum(getattr(m, "view_count_increase", 0) or 0 for m in metrics)
        trend_score = 3.0 if any_views > 0 else 0.0

    signals["trend"] = round(trend_score, 1)

    # ── 合計 ──
    hit_score, is_hit, hit_level, signals = _apply_score_parameters(signals, days_running, score_params)

    return hit_score, is_hit, hit_level, signals


def compute_genre_stats(
    session: "Session",
    period_start: date,
    period_end: date,
) -> dict[str, dict]:
    """ジャンル別の統計を事前計算（マルチシグナル・スコアの正規化に使用）。

    Returns:
        {"genre_name": {"max_spend": float, "p50_spend": float, "max_audience": int, "ad_count": int}}
    """
    results = (
        session.query(
            AdDailyMetrics.genre,
            func.sum(AdDailyMetrics.estimated_spend_increase).label("total_spend"),
            func.count(func.distinct(AdDailyMetrics.ad_id)).label("ad_count"),
        )
        .filter(
            AdDailyMetrics.metric_date >= period_start,
            AdDailyMetrics.metric_date <= period_end,
        )
        .group_by(AdDailyMetrics.genre)
        .all()
    )

    # Per-ad spend for max/p50 calculation
    ad_spends = (
        session.query(
            AdDailyMetrics.genre,
            AdDailyMetrics.ad_id,
            func.sum(AdDailyMetrics.estimated_spend_increase).label("ad_spend"),
        )
        .filter(
            AdDailyMetrics.metric_date >= period_start,
            AdDailyMetrics.metric_date <= period_end,
        )
        .group_by(AdDailyMetrics.genre, AdDailyMetrics.ad_id)
        .all()
    )

    # Group per-ad spends by genre
    genre_ad_spends: dict[str, list[float]] = {}
    for row in ad_spends:
        g = row.genre or "other"
        genre_ad_spends.setdefault(g, []).append(row.ad_spend or 0)

    genre_stats: dict[str, dict] = {}
    for row in results:
        g = row.genre or "other"
        spends = sorted(genre_ad_spends.get(g, []))
        mid = len(spends) // 2
        p50 = spends[mid] if spends else 0
        genre_stats[g] = {
            "total_spend": row.total_spend or 0,
            "max_spend": max(spends) if spends else 0,
            "p50_spend": p50,
            "ad_count": row.ad_count or 0,
            "max_audience": 0,
        }

    # Audience stats from ad_metadata
    ads_with_meta = session.query(Ad).filter(Ad.ad_metadata.isnot(None)).all()
    for ad in ads_with_meta:
        m = ad.ad_metadata or {}
        audience_max = _coerce_float(m.get("estimated_audience_max", 0) or 0)
        if audience_max > 0:
            # Map Ad.category to genre string
            g = str(ad.category.value) if ad.category else "other"
            if g in genre_stats:
                genre_stats[g]["max_audience"] = max(
                    genre_stats[g]["max_audience"], audience_max
                )

    return genre_stats


def compute_hit_score_with_details(
    ad: Ad,
    metrics: list | None = None,
    genre_stats: dict | None = None,
    score_params: dict | None = None,
) -> dict:
    """Compute hit score and return enriched signal details for API display.

    Wraps compute_hit_score() and adds max_value and detail text per signal.

    Returns:
        dict with hit_score, is_hit, hit_level, days_running,
        is_still_running, estimated_spend_jpy, and enriched signals.
    """
    hit_score, is_hit, hit_level, signals = compute_hit_score(
        ad, metrics=metrics, genre_stats=genre_stats, score_params=score_params,
    )

    meta = ad.ad_metadata or {}
    days_running = meta.get("days_running", 0)
    if days_running == 0 and ad.first_seen_at:
        now = datetime.now(timezone.utc)
        first = ad.first_seen_at
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        days_running = max(1, (now - first).days)

    is_still_running = meta.get("is_still_running", ad.last_seen_at is None)

    # Estimate total spend
    total_spend = 0.0
    if metrics:
        total_spend = sum(getattr(m, "estimated_spend_increase", 0) or 0 for m in metrics)
    if total_spend == 0:
        total_spend = meta.get("estimated_total_spend_jpy") or ad.spend or 0

    # Build enriched signal details
    signal_max = {
        "longevity": 40,
        "spend": 20,
        "active_bonus": 20,
        "creative": 10,
        "trend": 10,
    }
    signal_details = {
        "longevity": f"Running for {days_running} days",
        "spend": f"Estimated spend: {int(total_spend):,} JPY",
        "active_bonus": (
            f"Still running + {days_running} days"
            if is_still_running else "Not currently running"
        ),
        "creative": _describe_creative(ad),
        "trend": _describe_trend(signals.get("trend", 0), metrics),
    }

    enriched_signals = {}
    for key in ["longevity", "spend", "active_bonus", "creative", "trend"]:
        enriched_signals[key] = {
            "score": signals.get(key, 0.0),
            "max": signal_max[key],
            "detail": signal_details[key],
        }

    return {
        "hit_score": hit_score,
        "is_hit": is_hit,
        "hit_level": hit_level,
        "applied_score_params": validate_score_parameters(score_params),
        "days_running": days_running,
        "is_still_running": is_still_running,
        "estimated_spend_jpy": int(total_spend),
        "signals": enriched_signals,
    }


def _describe_creative(ad: Ad) -> str:
    """Build a human-readable creative quality description."""
    parts = []
    if ad.video_url:
        parts.append("video")
    if ad.image_url:
        parts.append("image")
    thumb = ad.thumbnail_url or ""
    if thumb and "s200x200" not in thumb and "favicons" not in thumb:
        parts.append("thumbnail")
    if not parts:
        return "No creative assets"
    return "Has " + " + ".join(parts)


def _describe_trend(trend_score: float, metrics: list | None) -> str:
    """Build a human-readable trend description."""
    n = len(metrics) if metrics else 0
    if n == 0:
        return "No metrics data"
    if trend_score >= 7:
        return f"Strong growth ({n} data points)"
    if trend_score >= 3:
        return f"Moderate growth ({n} data points)"
    return f"Low/flat growth ({n} data points)"


class RankingService:
    """Compute and manage product/genre rankings."""

    def compute_rankings(
        self,
        session: Session,
        period: str = "weekly",
        genre: Optional[str] = None,
    ) -> list[ProductRanking]:
        """Compute rankings for a given period."""
        yesterday = _today_jst() - timedelta(days=1)

        if period == "daily":
            start = yesterday
            end = yesterday
        elif period == "weekly":
            start = yesterday - timedelta(days=6)
            end = yesterday
        else:  # monthly
            start = yesterday - timedelta(days=29)
            end = yesterday

        # Subquery: find latest metric_date per ad within range
        latest_date_sq = (
            session.query(
                AdDailyMetrics.ad_id,
                func.max(AdDailyMetrics.metric_date).label("latest_date"),
            )
            .filter(
                AdDailyMetrics.metric_date >= start,
                AdDailyMetrics.metric_date <= end,
            )
            .group_by(AdDailyMetrics.ad_id)
            .subquery()
        )

        # Alias to fetch cumulative values from latest-date row only
        LatestMetric = aliased(AdDailyMetrics)

        # Aggregate metrics per ad, joining latest-date row for cumulative values
        query = (
            session.query(
                AdDailyMetrics.ad_id,
                func.max(AdDailyMetrics.product_name).label("product_name"),
                func.max(AdDailyMetrics.advertiser_name).label("advertiser_name"),
                func.max(AdDailyMetrics.genre).label("genre"),
                func.max(AdDailyMetrics.platform).label("platform"),
                func.sum(AdDailyMetrics.view_count_increase).label("total_view_increase"),
                func.sum(AdDailyMetrics.estimated_spend_increase).label("total_spend_increase"),
                func.max(LatestMetric.view_count).label("cumulative_views"),
                func.max(LatestMetric.estimated_spend).label("cumulative_spend"),
            )
            .join(
                latest_date_sq,
                AdDailyMetrics.ad_id == latest_date_sq.c.ad_id,
            )
            .join(
                LatestMetric,
                (LatestMetric.ad_id == latest_date_sq.c.ad_id)
                & (LatestMetric.metric_date == latest_date_sq.c.latest_date),
            )
            .filter(
                AdDailyMetrics.metric_date >= start,
                AdDailyMetrics.metric_date <= end,
            )
            .group_by(AdDailyMetrics.ad_id)
        )

        if genre:
            query = query.filter(AdDailyMetrics.genre == genre)

        # Order by total spend increase (primary ranking metric)
        results = query.order_by(desc("total_spend_increase")).limit(200).all()

        # Get previous rankings for rank_change and hit_score diff calculation
        prev_rankings = {}
        prev_hit_scores = {}
        prev_period_start = start - (end - start)
        prev = session.query(ProductRanking).filter(
            ProductRanking.period == period,
            ProductRanking.period_start == prev_period_start,
        ).all()
        for pr in prev:
            prev_rankings[pr.ad_id] = pr.rank_position
            if pr.hit_score is not None:
                prev_hit_scores[pr.ad_id] = pr.hit_score

        # Pre-fetch Ad objects for all result ad_ids to compute hit scores
        result_ad_ids = [r.ad_id for r in results]
        ads_map: dict[int, Ad] = {}
        if result_ad_ids:
            ads_list = session.query(Ad).filter(Ad.id.in_(result_ad_ids)).all()
            ads_map = {ad.id: ad for ad in ads_list}

        # Pre-fetch metrics per ad for multi-signal scoring
        ad_metrics_map: dict[int, list] = {}
        if result_ad_ids:
            all_metrics = (
                session.query(AdDailyMetrics)
                .filter(
                    AdDailyMetrics.ad_id.in_(result_ad_ids),
                    AdDailyMetrics.metric_date >= start,
                    AdDailyMetrics.metric_date <= end,
                )
                .order_by(AdDailyMetrics.metric_date)
                .all()
            )
            for m in all_metrics:
                ad_metrics_map.setdefault(m.ad_id, []).append(m)

        # Compute genre-level stats for relative scoring
        g_stats = compute_genre_stats(session, start, end)

        days_in_period = (end - start).days or 1
        view_rates = [
            (r.total_view_increase or 0) / days_in_period for r in results
        ]
        max_daily_views = max(view_rates) if view_rates else 1
        max_daily_views = max(max_daily_views, 1)  # avoid division by zero

        # Build new rankings
        rankings = []
        for rank, row in enumerate(results, 1):
            prev_rank = prev_rankings.get(row.ad_id)
            rank_change = (prev_rank - rank) if prev_rank else None

            total_view_increase = row.total_view_increase or 0
            total_spend_increase = row.total_spend_increase or 0

            # Hit detection: multi-signal scoring
            ad_obj = ads_map.get(row.ad_id)
            ad_genre = row.genre or "other"
            ad_genre_stats = g_stats.get(ad_genre, {})
            ad_metrics = ad_metrics_map.get(row.ad_id, [])

            if ad_obj:
                hit_score, is_hit, hit_level, breakdown = compute_hit_score(
                    ad_obj, metrics=ad_metrics, genre_stats=ad_genre_stats,
                )
            else:
                hit_score, is_hit, hit_level, breakdown = 0.0, False, "none", {}

            # Trend score: daily view velocity relative to best performer
            daily_views = total_view_increase / days_in_period
            trend_score = min(100, (daily_views / max_daily_views) * 100)

            ranking = ProductRanking(
                period=period,
                period_start=start,
                period_end=end,
                ad_id=row.ad_id,
                product_name=row.product_name,
                advertiser_name=row.advertiser_name,
                genre=row.genre,
                platform=row.platform,
                rank_position=rank,
                previous_rank=prev_rank,
                rank_change=rank_change,
                total_view_increase=total_view_increase,
                total_spend_increase=total_spend_increase,
                cumulative_views=row.cumulative_views or 0,
                cumulative_spend=row.cumulative_spend or 0,
                is_hit=is_hit,
                hit_score=round(hit_score, 1),
                trend_score=round(trend_score, 1),
                extra_metadata={
                    "hit_level": hit_level,
                    "score_breakdown": breakdown,
                    "previous_hit_score": prev_hit_scores.get(row.ad_id),
                    "hit_score_diff": round(hit_score - prev_hit_scores[row.ad_id], 1) if row.ad_id in prev_hit_scores else None,
                },
            )
            rankings.append(ranking)

        return rankings

    def compute_all_rankings(self, session: Session) -> dict:
        """Compute rankings for all periods (daily, weekly, monthly).

        Deletes old rankings for the same period_start before inserting new ones.
        Returns summary of rankings created per period.
        """
        summary = {}
        for period in ["daily", "weekly", "monthly"]:
            try:
                rankings = self.compute_rankings(session, period=period)

                if rankings:
                    # Delete existing rankings for the same period + period_start
                    period_start = rankings[0].period_start
                    session.query(ProductRanking).filter(
                        ProductRanking.period == period,
                        ProductRanking.period_start == period_start,
                    ).delete()
                    session.flush()

                    for r in rankings:
                        session.add(r)

                summary[period] = len(rankings)
                logger.info(
                    "rankings_computed",
                    period=period,
                    count=len(rankings),
                )
            except Exception as e:
                logger.error("ranking_period_failed", period=period, error=str(e))
                summary[period] = 0

        return summary

    def get_rankings(
        self,
        session: Session,
        period: str = "weekly",
        genre: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ProductRanking], int]:
        """Get current rankings with filters."""
        # Find the most recent rankings for the given period
        # instead of requiring exact date match
        latest_start = (
            session.query(func.max(ProductRanking.period_start))
            .filter(ProductRanking.period == period)
            .scalar()
        )

        if latest_start is None:
            return [], 0

        query = session.query(ProductRanking).filter(
            ProductRanking.period == period,
            ProductRanking.period_start == latest_start,
        )

        if genre:
            query = query.filter(ProductRanking.genre == genre)
        if platform:
            if platform.lower() == "meta":
                query = query.filter(ProductRanking.platform.in_(["facebook", "instagram"]))
            else:
                query = query.filter(ProductRanking.platform == platform)

        total = query.count()
        rankings = (
            query.order_by(ProductRanking.rank_position)
            .offset(offset)
            .limit(limit)
            .all()
        )

        return rankings, total

    def get_hit_ads(
        self,
        session: Session,
        genre: Optional[str] = None,
        limit: int = 20,
    ) -> list[ProductRanking]:
        """Get currently trending/hit ads."""
        latest_start = (
            session.query(func.max(ProductRanking.period_start))
            .filter(ProductRanking.period == "weekly")
            .scalar()
        )

        if latest_start is None:
            return []

        query = session.query(ProductRanking).filter(
            ProductRanking.period == "weekly",
            ProductRanking.period_start == latest_start,
            ProductRanking.is_hit == True,  # noqa: E712
        )

        if genre:
            query = query.filter(ProductRanking.genre == genre)

        return query.order_by(desc(ProductRanking.hit_score)).limit(limit).all()

    def get_advertiser_rankings(
        self,
        session: Session,
        advertiser_name: str,
        period: str = "weekly",
    ) -> dict:
        """Get detailed analytics for a specific advertiser."""
        yesterday = _today_jst() - timedelta(days=1)
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
        start = yesterday - timedelta(days=days - 1)

        # Get all ads for this advertiser
        metrics = session.query(
            AdDailyMetrics.ad_id,
            func.max(AdDailyMetrics.product_name).label("product_name"),
            func.max(AdDailyMetrics.genre).label("genre"),
            func.max(AdDailyMetrics.platform).label("platform"),
            func.sum(AdDailyMetrics.view_count_increase).label("total_views"),
            func.sum(AdDailyMetrics.estimated_spend_increase).label("total_spend"),
            func.count(AdDailyMetrics.id).label("active_days"),
        ).filter(
            AdDailyMetrics.advertiser_name.ilike(f"%{advertiser_name}%"),
            AdDailyMetrics.metric_date >= start,
            AdDailyMetrics.metric_date <= yesterday,
        ).group_by(AdDailyMetrics.ad_id).order_by(desc("total_spend")).all()

        # Genre distribution
        genre_spend = {}
        platform_spend = {}
        total_spend = 0
        total_views = 0

        for m in metrics:
            genre = m.genre or "その他"
            platform = m.platform or "unknown"
            spend = m.total_spend or 0
            views = m.total_views or 0

            genre_spend[genre] = genre_spend.get(genre, 0) + spend
            platform_spend[platform] = platform_spend.get(platform, 0) + spend
            total_spend += spend
            total_views += views

        return {
            "advertiser_name": advertiser_name,
            "period": period,
            "total_ads": len(metrics),
            "total_spend": round(total_spend),
            "total_views": total_views,
            "genre_distribution": genre_spend,
            "platform_distribution": platform_spend,
            "top_ads": [
                {
                    "ad_id": m.ad_id,
                    "product_name": m.product_name,
                    "genre": m.genre,
                    "platform": m.platform,
                    "view_increase": m.total_views or 0,
                    "spend_increase": round(m.total_spend or 0),
                    "active_days": m.active_days,
                }
                for m in metrics[:20]
            ],
        }
