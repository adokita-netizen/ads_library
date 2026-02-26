"""Optimization engine — analyze performance data and generate actionable recommendations."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_campaign import MetaAd, MetaAdSet, MetaCampaign, MetaInsight
from app.models.optimization import OptimizationRecommendation

logger = structlog.get_logger()


class MetaOptimizer:
    """Analyze live Meta ad data and generate optimization recommendations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_and_recommend(self, account_id: str, user_id: int = 0) -> list[dict]:
        """Run all analysis checks and generate recommendations.

        Checks:
        1. Budget efficiency — CPA-based reallocation
        2. Creative fatigue — CTR/CVR decline detection
        3. Scaling opportunity — rising performance
        4. Audience saturation — frequency analysis
        """
        recommendations = []

        recommendations.extend(await self._check_budget_efficiency(account_id, user_id))
        recommendations.extend(await self._check_creative_fatigue(account_id, user_id))
        recommendations.extend(await self._check_scaling_opportunities(account_id, user_id))
        recommendations.extend(await self._check_audience_saturation(account_id, user_id))

        logger.info("optimization_analysis_complete", account_id=account_id, recommendations=len(recommendations))
        return recommendations

    async def _check_budget_efficiency(self, account_id: str, user_id: int) -> list[dict]:
        """Check CPA across ad sets and recommend budget reallocation."""
        recommendations = []

        # Get 7-day CPA per ad set
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.sum(MetaInsight.spend).label("total_spend"),
                func.sum(MetaInsight.clicks).label("total_clicks"),
                func.sum(MetaInsight.conversions).label("total_conversions"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "adset",
                MetaInsight.date_start >= seven_days_ago,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.sum(MetaInsight.spend) > 0)
        )

        ad_set_metrics = []
        for row in result.all():
            spend = float(row.total_spend or 0)
            conversions = int(row.total_conversions or 0)
            cpa = spend / conversions if conversions > 0 else float("inf")
            ad_set_metrics.append({
                "entity_id": row.entity_id,
                "spend": spend,
                "clicks": int(row.total_clicks or 0),
                "conversions": conversions,
                "cpa": cpa,
            })

        if len(ad_set_metrics) < 2:
            return recommendations

        # Find median CPA
        cpas = [m["cpa"] for m in ad_set_metrics if m["cpa"] != float("inf")]
        if not cpas:
            return recommendations

        median_cpa = sorted(cpas)[len(cpas) // 2]

        for m in ad_set_metrics:
            if m["cpa"] == float("inf"):
                continue  # コンバージョン未設定の広告セットはスキップ
            if m["cpa"] > median_cpa * 2 and m["spend"] > 1000:
                # High CPA → recommend budget decrease
                rec = OptimizationRecommendation(
                    user_id=user_id,
                    account_id=account_id,
                    entity_type="adset",
                    entity_id=m["entity_id"],
                    recommendation_type="budget_decrease",
                    severity="high",
                    title=f"広告セットのCPAが高い (¥{m['cpa']:,.0f})",
                    description=f"この広告セットのCPAは中央値の2倍以上です。予算の削減を検討してください。",
                    rationale=f"7日間CPA: ¥{m['cpa']:,.0f} vs 中央値: ¥{median_cpa:,.0f}",
                    predicted_impact={
                        "metric": "cpa",
                        "current": m["cpa"],
                        "predicted": median_cpa,
                        "change_percent": round((median_cpa - m["cpa"]) / m["cpa"] * 100, 1),
                    },
                    action_payload={
                        "endpoint": f"/{m['entity_id']}",
                        "method": "POST",
                        "data": {"daily_budget": "REDUCE_20_PERCENT"},
                    },
                    status="pending",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=3),
                )
                self.db.add(rec)
                recommendations.append({"type": "budget_decrease", "entity_id": m["entity_id"]})

            elif m["cpa"] < median_cpa * 0.5 and m["conversions"] >= 5:
                # Low CPA → recommend scaling
                rec = OptimizationRecommendation(
                    user_id=user_id,
                    account_id=account_id,
                    entity_type="adset",
                    entity_id=m["entity_id"],
                    recommendation_type="budget_increase",
                    severity="medium",
                    title=f"広告セットの効率が良い (CPA: ¥{m['cpa']:,.0f})",
                    description=f"この広告セットは効率的です。予算の増額でスケールを検討してください。",
                    rationale=f"7日間CPA: ¥{m['cpa']:,.0f} (中央値の半分以下)",
                    predicted_impact={
                        "metric": "conversions",
                        "current": m["conversions"],
                        "predicted": int(m["conversions"] * 1.3),
                        "change_percent": 30,
                    },
                    action_payload={
                        "endpoint": f"/{m['entity_id']}",
                        "method": "POST",
                        "data": {"daily_budget": "INCREASE_20_PERCENT"},
                    },
                    status="pending",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=3),
                )
                self.db.add(rec)
                recommendations.append({"type": "budget_increase", "entity_id": m["entity_id"]})

        await self.db.flush()
        return recommendations

    async def _check_creative_fatigue(self, account_id: str, user_id: int) -> list[dict]:
        """Detect creative fatigue by analyzing CTR decline over time."""
        recommendations = []

        # Get daily CTR for each ad over last 14 days
        fourteen_days_ago = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        # First week average
        result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.avg(MetaInsight.ctr).label("avg_ctr_week1"),
                func.sum(MetaInsight.impressions).label("impressions_week1"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "ad",
                MetaInsight.date_start >= fourteen_days_ago,
                MetaInsight.date_start < seven_days_ago,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.sum(MetaInsight.impressions) > 500)
        )
        week1_data = {row.entity_id: {"ctr": float(row.avg_ctr_week1 or 0)} for row in result.all()}

        # Second week average
        result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.avg(MetaInsight.ctr).label("avg_ctr_week2"),
                func.sum(MetaInsight.impressions).label("impressions_week2"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "ad",
                MetaInsight.date_start >= seven_days_ago,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.sum(MetaInsight.impressions) > 500)
        )

        for row in result.all():
            if row.entity_id not in week1_data:
                continue

            ctr_week1 = week1_data[row.entity_id]["ctr"]
            ctr_week2 = float(row.avg_ctr_week2 or 0)

            if ctr_week1 <= 0:
                continue

            decline = (ctr_week2 - ctr_week1) / ctr_week1 * 100

            if decline < -20:
                # CTR declined more than 20% — possible fatigue
                severity = "critical" if decline < -40 else "high"
                rec = OptimizationRecommendation(
                    user_id=user_id,
                    account_id=account_id,
                    entity_type="ad",
                    entity_id=row.entity_id,
                    recommendation_type="creative_refresh",
                    severity=severity,
                    title=f"クリエイティブ疲労の兆候 (CTR {decline:+.1f}%)",
                    description=f"CTRが先週比{decline:.1f}%低下しています。クリエイティブの更新を検討してください。",
                    rationale=f"先週CTR: {ctr_week1:.2f}% → 今週: {ctr_week2:.2f}%",
                    predicted_impact={
                        "metric": "ctr",
                        "current": ctr_week2,
                        "predicted": ctr_week1,
                        "change_percent": round(-decline, 1),
                    },
                    action_payload={
                        "endpoint": f"/{row.entity_id}",
                        "method": "POST",
                        "data": {"status": "PAUSED"},
                    },
                    status="pending",
                    expires_at=datetime.now(timezone.utc) + timedelta(days=2),
                )
                self.db.add(rec)
                recommendations.append({"type": "creative_refresh", "entity_id": row.entity_id})

        await self.db.flush()
        return recommendations

    async def _check_scaling_opportunities(self, account_id: str, user_id: int) -> list[dict]:
        """Find ads with rising CTR that could be scaled."""
        recommendations = []

        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")

        # Recent 3-day performance
        result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.avg(MetaInsight.ctr).label("avg_ctr"),
                func.sum(MetaInsight.clicks).label("total_clicks"),
                func.sum(MetaInsight.impressions).label("total_impressions"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "ad",
                MetaInsight.date_start >= three_days_ago,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.avg(MetaInsight.ctr) > 2.0)  # Above 2% CTR
            .having(func.sum(MetaInsight.impressions) > 1000)
        )

        for row in result.all():
            rec = OptimizationRecommendation(
                user_id=user_id,
                account_id=account_id,
                entity_type="ad",
                entity_id=row.entity_id,
                recommendation_type="scale_ad",
                severity="medium",
                title=f"高パフォーマンス広告 (CTR: {float(row.avg_ctr):.2f}%)",
                description=f"直近3日間のCTRが高いです。予算増額によるスケールを検討してください。",
                rationale=f"3日間平均CTR: {float(row.avg_ctr):.2f}%, クリック: {row.total_clicks}",
                status="pending",
                expires_at=datetime.now(timezone.utc) + timedelta(days=2),
            )
            self.db.add(rec)
            recommendations.append({"type": "scale_ad", "entity_id": row.entity_id})

        await self.db.flush()
        return recommendations

    async def _check_audience_saturation(self, account_id: str, user_id: int) -> list[dict]:
        """Detect audience saturation via rising frequency."""
        recommendations = []

        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

        result = await self.db.execute(
            select(
                MetaInsight.entity_id,
                func.avg(MetaInsight.frequency).label("avg_frequency"),
            )
            .where(
                MetaInsight.account_id == account_id,
                MetaInsight.entity_type == "adset",
                MetaInsight.date_start >= seven_days_ago,
            )
            .group_by(MetaInsight.entity_id)
            .having(func.avg(MetaInsight.frequency) > 3.0)  # High frequency threshold
        )

        for row in result.all():
            freq = float(row.avg_frequency)
            severity = "critical" if freq > 5 else "high" if freq > 4 else "medium"
            rec = OptimizationRecommendation(
                user_id=user_id,
                account_id=account_id,
                entity_type="adset",
                entity_id=row.entity_id,
                recommendation_type="bid_adjust",
                severity=severity,
                title=f"オーディエンス飽和の兆候 (頻度: {freq:.1f})",
                description=f"フリークエンシーが{freq:.1f}に達しています。ターゲティングの拡大を検討してください。",
                rationale=f"7日間平均フリークエンシー: {freq:.1f} (推奨上限: 3.0)",
                status="pending",
                expires_at=datetime.now(timezone.utc) + timedelta(days=3),
            )
            self.db.add(rec)
            recommendations.append({"type": "bid_adjust", "entity_id": row.entity_id})

        await self.db.flush()
        return recommendations

    async def apply_recommendation(self, recommendation_id: int, client=None) -> dict:
        """Apply an accepted recommendation via Meta API."""
        result = await self.db.execute(
            select(OptimizationRecommendation).where(
                OptimizationRecommendation.id == recommendation_id,
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            return {"error": "レコメンドが見つかりません"}

        if rec.status != "accepted":
            return {"error": "レコメンドが承認されていません"}

        if not rec.action_payload or not client:
            rec.status = "applied"
            rec.applied_at = datetime.now(timezone.utc)
            await self.db.flush()
            return {"applied": True, "message": "レコメンドを適用しました（手動対応が必要な場合があります）"}

        payload = rec.action_payload
        try:
            endpoint = payload.get("endpoint", "")
            data = payload.get("data", {})
            await client.post(endpoint, data=data)

            rec.status = "applied"
            rec.applied_at = datetime.now(timezone.utc)
            await self.db.flush()

            logger.info("recommendation_applied", recommendation_id=recommendation_id)
            return {"applied": True, "message": "Meta APIに変更を適用しました"}

        except Exception as e:
            logger.error("recommendation_apply_failed", recommendation_id=recommendation_id, error=str(e))
            return {"applied": False, "error": str(e)}
