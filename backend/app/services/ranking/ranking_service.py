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


def _today_jst() -> date:
    return datetime.now(JST).date()


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

        # Get previous rankings for rank_change calculation
        prev_rankings = {}
        prev_period_start = start - (end - start)
        prev = session.query(ProductRanking).filter(
            ProductRanking.period == period,
            ProductRanking.period_start == prev_period_start,
        ).all()
        for pr in prev:
            prev_rankings[pr.ad_id] = pr.rank_position

        # Compute dynamic thresholds for relative hit detection
        spend_values = sorted(
            [(r.total_spend_increase or 0) for r in results],
            reverse=True,
        )
        p85_idx = max(0, int(len(spend_values) * 0.15) - 1) if spend_values else 0
        spend_threshold = spend_values[p85_idx] if spend_values else 0
        max_spend = spend_values[0] if spend_values else 1

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

            # Hit detection: relative percentile-based
            # Top 20 rank + spend above 85th percentile + non-zero spend
            is_hit = (
                rank <= 20
                and total_spend_increase > spend_threshold
                and total_spend_increase > 0
            )

            # Hit score: weighted by spend relative to max, adjusted by rank
            if total_spend_increase > 0 and max_spend > 0:
                hit_score = min(
                    100,
                    (total_spend_increase / max_spend) * 100 * (1 / rank ** 0.3),
                )
            else:
                hit_score = 0

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
