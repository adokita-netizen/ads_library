"""Ranking service - compute product/genre rankings from time-series metrics."""

from datetime import date, timedelta
from typing import Optional

import structlog
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking

logger = structlog.get_logger()


class RankingService:
    """Compute and manage product/genre rankings."""

    def compute_rankings(
        self,
        session: Session,
        period: str = "weekly",
        genre: Optional[str] = None,
    ) -> list[ProductRanking]:
        """Compute rankings for a given period."""
        today = date.today()

        if period == "daily":
            start = today - timedelta(days=1)
            end = today
        elif period == "weekly":
            start = today - timedelta(days=7)
            end = today
        else:  # monthly
            start = today - timedelta(days=30)
            end = today

        # Aggregate metrics per ad
        query = (
            session.query(
                AdDailyMetrics.ad_id,
                func.max(AdDailyMetrics.product_name).label("product_name"),
                func.max(AdDailyMetrics.advertiser_name).label("advertiser_name"),
                func.max(AdDailyMetrics.genre).label("genre"),
                func.max(AdDailyMetrics.platform).label("platform"),
                func.sum(AdDailyMetrics.view_count_increase).label("total_view_increase"),
                func.sum(AdDailyMetrics.estimated_spend_increase).label("total_spend_increase"),
                func.max(AdDailyMetrics.view_count).label("cumulative_views"),
                func.max(AdDailyMetrics.estimated_spend).label("cumulative_spend"),
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

        # Build new rankings
        rankings = []
        for rank, row in enumerate(results, 1):
            prev_rank = prev_rankings.get(row.ad_id)
            rank_change = (prev_rank - rank) if prev_rank else None

            # Hit detection: high velocity + rank in top 20
            total_view_increase = row.total_view_increase or 0
            total_spend_increase = row.total_spend_increase or 0
            is_hit = rank <= 20 and total_spend_increase > 100000
            hit_score = min(100, (total_spend_increase / 10000) * (1 / max(rank, 1)) * 10) if total_spend_increase else 0

            # Trend score: based on growth velocity
            days_in_period = (end - start).days or 1
            trend_score = min(100, (total_view_increase / days_in_period) / 100)

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
        today = date.today()

        if period == "daily":
            start = today - timedelta(days=1)
        elif period == "weekly":
            start = today - timedelta(days=7)
        else:
            start = today - timedelta(days=30)

        query = session.query(ProductRanking).filter(
            ProductRanking.period == period,
            ProductRanking.period_start == start,
        )

        if genre:
            query = query.filter(ProductRanking.genre == genre)
        if platform:
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
        today = date.today()
        start = today - timedelta(days=7)

        query = session.query(ProductRanking).filter(
            ProductRanking.period == "weekly",
            ProductRanking.period_start == start,
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
        today = date.today()
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 7)
        start = today - timedelta(days=days)

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
