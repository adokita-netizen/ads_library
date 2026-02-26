"""Creative analysis for own Meta ads — AI analysis, competitor comparison, and insights."""

from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_campaign import MetaAd, MetaInsight

logger = structlog.get_logger()


class CreativeAnalyzer:
    """Analyze own Meta ad creatives and compare with competitors."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_own_ad(self, meta_ad_id: str) -> dict:
        """Trigger AI analysis on a Meta ad by linking it to the internal Ad pipeline.

        Steps:
        1. Find MetaAd by meta_id
        2. Check if linked to internal Ad record
        3. If not linked, create one from creative data
        4. Dispatch analysis task

        Returns analysis status and linked ad info.
        """
        result = await self.db.execute(
            select(MetaAd).where(MetaAd.meta_id == meta_ad_id)
        )
        meta_ad = result.scalar_one_or_none()
        if not meta_ad:
            return {"error": "Meta広告が見つかりません", "analyzed": False}

        # Check if already linked
        if meta_ad.linked_ad_id:
            return {
                "analyzed": True,
                "linked_ad_id": meta_ad.linked_ad_id,
                "message": "既に分析パイプラインにリンクされています",
            }

        # Create internal Ad record from creative data
        from app.models.ad import Ad

        media_url = meta_ad.creative_video_url or meta_ad.creative_image_url
        creative_type = "video" if meta_ad.creative_video_url else "image"

        ad = Ad(
            external_id=f"meta_{meta_ad.meta_id}",
            title=meta_ad.creative_title or meta_ad.name,
            description=meta_ad.creative_body,
            platform="facebook",
            creative_type=creative_type,
            video_url=meta_ad.creative_video_url,
            image_url=meta_ad.creative_image_url,
            snapshot_url=meta_ad.creative_thumbnail_url,
            advertiser_name=None,
            status="pending",
            tags=["meta_marketing", "own_ad"],
            ad_metadata={"meta_ad_id": meta_ad.meta_id, "account_id": meta_ad.account_id},
        )
        self.db.add(ad)
        await self.db.flush()
        await self.db.refresh(ad)

        # Link MetaAd to internal Ad
        meta_ad.linked_ad_id = ad.id
        await self.db.flush()

        # Dispatch analysis task
        try:
            from app.tasks.dispatcher import dispatch_task
            dispatch_task("analyze_ad", ad_id=ad.id)
        except Exception as e:
            logger.warning("meta_ad_analysis_dispatch_failed", error=str(e))

        return {
            "analyzed": True,
            "linked_ad_id": ad.id,
            "message": "分析パイプラインに送信しました",
        }

    async def compare_with_competitors(self, meta_ad_id: str, category: Optional[str] = None) -> dict:
        """Compare own ad performance with competitor averages.

        Compares hook_score, winning_score, sentiment across ads in the same category.
        """
        result = await self.db.execute(
            select(MetaAd).where(MetaAd.meta_id == meta_ad_id)
        )
        meta_ad = result.scalar_one_or_none()
        if not meta_ad:
            return {"error": "Meta広告が見つかりません"}

        # Get own ad analysis if linked
        own_analysis = None
        if meta_ad.linked_ad_id:
            from app.models.analysis import AdAnalysis
            result = await self.db.execute(
                select(AdAnalysis).where(AdAnalysis.ad_id == meta_ad.linked_ad_id)
            )
            own_analysis = result.scalar_one_or_none()

        # Get competitor averages from the same category
        from app.models.analysis import AdAnalysis
        from app.models.ad import Ad

        query = select(
            func.avg(AdAnalysis.hook_score).label("avg_hook_score"),
            func.avg(AdAnalysis.winning_score).label("avg_winning_score"),
            func.avg(AdAnalysis.sentiment_score).label("avg_sentiment_score"),
            func.count(AdAnalysis.id).label("competitor_count"),
        ).join(Ad, Ad.id == AdAnalysis.ad_id)

        if category:
            query = query.where(Ad.category == category)

        # Exclude own ads
        query = query.where(~Ad.tags.op("?")("meta_marketing"))

        result = await self.db.execute(query)
        row = result.one_or_none()

        comparison = {
            "meta_ad_id": meta_ad_id,
            "own_ad_name": meta_ad.name,
            "own_scores": {},
            "competitor_averages": {},
            "advantages": [],
            "disadvantages": [],
            "suggestions": [],
        }

        if own_analysis:
            comparison["own_scores"] = {
                "hook_score": own_analysis.hook_score,
                "winning_score": own_analysis.winning_score,
                "sentiment_score": own_analysis.sentiment_score,
            }

        if row and row.competitor_count and row.competitor_count > 0:
            comparison["competitor_averages"] = {
                "hook_score": round(float(row.avg_hook_score or 0), 2),
                "winning_score": round(float(row.avg_winning_score or 0), 2),
                "sentiment_score": round(float(row.avg_sentiment_score or 0), 2),
                "sample_size": row.competitor_count,
            }

            # Determine advantages/disadvantages
            if own_analysis:
                if own_analysis.hook_score and row.avg_hook_score:
                    if own_analysis.hook_score > float(row.avg_hook_score):
                        comparison["advantages"].append("フックスコアが競合平均を上回っています")
                    else:
                        comparison["disadvantages"].append("フックスコアが競合平均を下回っています")
                        comparison["suggestions"].append("冒頭3秒のインパクトを強化してください")

                if own_analysis.winning_score and row.avg_winning_score:
                    if own_analysis.winning_score > float(row.avg_winning_score):
                        comparison["advantages"].append("勝ちスコアが競合平均を上回っています")
                    else:
                        comparison["disadvantages"].append("勝ちスコアが競合平均を下回っています")
                        comparison["suggestions"].append("CTAの明確化やストーリー構成の見直しを検討してください")

        return comparison

    async def get_creative_insights_summary(self, account_id: str) -> dict:
        """Get account-level creative performance insights.

        Analyzes: best performing creative types, fatigue candidates, refresh recommendations.
        """
        # Get all ads for the account with insights
        result = await self.db.execute(
            select(
                MetaAd.creative_type,
                func.count(MetaAd.id).label("count"),
            )
            .where(MetaAd.account_id == account_id)
            .group_by(MetaAd.creative_type)
        )
        type_distribution = {row[0] or "unknown": row[1] for row in result.all()}

        # Get top performing ads by spend efficiency
        result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.sum(MetaInsight.spend).label("total_spend"),
                func.sum(MetaInsight.clicks).label("total_clicks"),
                func.sum(MetaInsight.impressions).label("total_impressions"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "ad",
            )
            .group_by(MetaInsight.entity_id)
            .having(func.sum(MetaInsight.impressions) > 100)
            .order_by(func.sum(MetaInsight.clicks).desc())
            .limit(10)
        )
        top_performers = []
        for row in result.all():
            ctr = (row.total_clicks / row.total_impressions * 100) if row.total_impressions > 0 else 0
            top_performers.append({
                "entity_id": row.entity_id,
                "total_spend": round(float(row.total_spend or 0), 2),
                "total_clicks": row.total_clicks or 0,
                "total_impressions": row.total_impressions or 0,
                "ctr": round(ctr, 2),
            })

        return {
            "account_id": account_id,
            "creative_type_distribution": type_distribution,
            "total_ads": sum(type_distribution.values()),
            "top_performers": top_performers,
        }
