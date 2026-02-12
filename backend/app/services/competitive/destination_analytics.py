"""Destination analytics service - LP reuse tracking, creative variation analysis."""

from datetime import date, timedelta
from typing import Optional

import structlog
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics
from app.models.landing_page import LandingPage, LPAnalysis

logger = structlog.get_logger()


class DestinationAnalyticsService:
    """Analyze ad destinations (LPs) - reuse, creative variation, spend distribution."""

    def get_lp_reuse_analytics(
        self,
        session: Session,
        genre: Optional[str] = None,
        min_advertisers: int = 1,
        limit: int = 50,
    ) -> list[dict]:
        """Find LPs used by multiple advertisers with spend analysis.

        DPro equivalent: 遷移先アナリティクス - 同様LPを使う広告アカウント数
        """
        # Group LPs by URL hash (same LP = same url_hash)
        query = (
            session.query(
                LandingPage.url_hash,
                func.max(LandingPage.url).label("url"),
                func.max(LandingPage.domain).label("domain"),
                func.max(LandingPage.title).label("title"),
                func.max(LandingPage.genre).label("genre"),
                func.max(LandingPage.product_name).label("product_name"),
                func.count(func.distinct(LandingPage.advertiser_name)).label("advertiser_count"),
                func.count(func.distinct(LandingPage.ad_id)).label("ad_count"),
                func.array_agg(func.distinct(LandingPage.advertiser_name)).label("advertisers"),
            )
            .filter(LandingPage.ad_id.isnot(None))
        )

        if genre:
            query = query.filter(LandingPage.genre == genre)

        results = (
            query.group_by(LandingPage.url_hash)
            .having(func.count(func.distinct(LandingPage.advertiser_name)) >= min_advertisers)
            .order_by(desc("advertiser_count"))
            .limit(limit)
            .all()
        )

        return [
            {
                "url_hash": r.url_hash,
                "url": r.url,
                "domain": r.domain,
                "title": r.title,
                "genre": r.genre,
                "product_name": r.product_name,
                "advertiser_count": r.advertiser_count,
                "ad_count": r.ad_count,
                "advertisers": [a for a in (r.advertisers or []) if a],
            }
            for r in results
        ]

    def get_lp_creative_variation(
        self,
        session: Session,
        lp_id: int,
    ) -> dict:
        """Analyze creative variations pointing to the same LP.

        DPro equivalent: 同一LPでもクリエイティブ差で予想消化額がどう変わるか
        """
        lp = session.query(LandingPage).filter(LandingPage.id == lp_id).first()
        if not lp:
            return {"error": "LP not found"}

        # Get all ads pointing to this LP (or same url_hash)
        ads = (
            session.query(Ad)
            .join(LandingPage, LandingPage.ad_id == Ad.id)
            .filter(LandingPage.url_hash == lp.url_hash)
            .all()
        )

        ad_details = []
        for ad in ads:
            # Get spend metrics
            today = date.today()
            start = today - timedelta(days=30)
            metrics = (
                session.query(
                    func.sum(AdDailyMetrics.estimated_spend_increase).label("total_spend"),
                    func.sum(AdDailyMetrics.view_count_increase).label("total_views"),
                )
                .filter(
                    AdDailyMetrics.ad_id == ad.id,
                    AdDailyMetrics.metric_date >= start,
                )
                .first()
            )

            ad_details.append({
                "ad_id": ad.id,
                "title": ad.title,
                "platform": str(ad.platform),
                "advertiser_name": ad.advertiser_name,
                "duration_seconds": ad.duration_seconds,
                "total_spend_30d": round(metrics.total_spend or 0) if metrics else 0,
                "total_views_30d": metrics.total_views or 0 if metrics else 0,
                "created_at": ad.created_at.isoformat() if ad.created_at else None,
            })

        # Sort by spend
        ad_details.sort(key=lambda x: -x["total_spend_30d"])

        # Get LP quality scores
        lp_analysis = session.query(LPAnalysis).filter(
            LPAnalysis.landing_page_id == lp.id
        ).first()

        return {
            "lp_id": lp.id,
            "url": lp.url,
            "domain": lp.domain,
            "title": lp.title,
            "genre": lp.genre,
            "quality_score": lp_analysis.overall_quality_score if lp_analysis else None,
            "creative_count": len(ad_details),
            "advertiser_count": len(set(a["advertiser_name"] for a in ad_details if a["advertiser_name"])),
            "total_spend_30d": sum(a["total_spend_30d"] for a in ad_details),
            "creatives": ad_details,
        }

    def get_advertiser_destination_portfolio(
        self,
        session: Session,
        advertiser_name: str,
    ) -> dict:
        """Analyze all destinations used by one advertiser.

        Shows which LPs/funnels an advertiser uses and how spend is distributed.
        """
        lps = (
            session.query(
                LandingPage.id,
                LandingPage.url,
                LandingPage.domain,
                LandingPage.title,
                LandingPage.genre,
                LandingPage.product_name,
                func.count(LandingPage.ad_id).label("ad_count"),
            )
            .filter(LandingPage.advertiser_name.ilike(f"%{advertiser_name}%"))
            .group_by(
                LandingPage.id, LandingPage.url, LandingPage.domain,
                LandingPage.title, LandingPage.genre, LandingPage.product_name,
            )
            .order_by(desc("ad_count"))
            .all()
        )

        destinations = []
        for lp in lps:
            # Get spend for ads pointing to this LP
            today = date.today()
            start = today - timedelta(days=30)
            spend = (
                session.query(func.sum(AdDailyMetrics.estimated_spend_increase))
                .join(LandingPage, LandingPage.ad_id == AdDailyMetrics.ad_id)
                .filter(
                    LandingPage.id == lp.id,
                    AdDailyMetrics.metric_date >= start,
                )
                .scalar()
            ) or 0

            destinations.append({
                "lp_id": lp.id,
                "url": lp.url,
                "domain": lp.domain,
                "title": lp.title,
                "genre": lp.genre,
                "product_name": lp.product_name,
                "ad_count": lp.ad_count,
                "estimated_spend_30d": round(spend),
            })

        total_spend = sum(d["estimated_spend_30d"] for d in destinations)
        return {
            "advertiser_name": advertiser_name,
            "destination_count": len(destinations),
            "total_estimated_spend_30d": total_spend,
            "destinations": destinations,
        }

    def get_genre_destination_overview(
        self,
        session: Session,
        genre: str,
        period_days: int = 30,
    ) -> dict:
        """Genre-level destination analysis - market saturation, top LPs."""
        today = date.today()
        start = today - timedelta(days=period_days)

        # Total LPs in genre
        total_lps = session.query(func.count(LandingPage.id)).filter(
            LandingPage.genre == genre,
        ).scalar() or 0

        # Total advertisers
        total_advertisers = session.query(
            func.count(func.distinct(LandingPage.advertiser_name))
        ).filter(
            LandingPage.genre == genre,
        ).scalar() or 0

        # Top domains
        top_domains = (
            session.query(
                LandingPage.domain,
                func.count(LandingPage.id).label("lp_count"),
                func.count(func.distinct(LandingPage.advertiser_name)).label("adv_count"),
            )
            .filter(LandingPage.genre == genre)
            .group_by(LandingPage.domain)
            .order_by(desc("lp_count"))
            .limit(10)
            .all()
        )

        # Average quality
        avg_quality = session.query(
            func.avg(LPAnalysis.overall_quality_score)
        ).join(
            LandingPage, LPAnalysis.landing_page_id == LandingPage.id
        ).filter(
            LandingPage.genre == genre,
        ).scalar()

        return {
            "genre": genre,
            "total_lps": total_lps,
            "total_advertisers": total_advertisers,
            "avg_quality_score": round(avg_quality, 1) if avg_quality else None,
            "top_domains": [
                {
                    "domain": d.domain,
                    "lp_count": d.lp_count,
                    "advertiser_count": d.adv_count,
                }
                for d in top_domains
            ],
        }
