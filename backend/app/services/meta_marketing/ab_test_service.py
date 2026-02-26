"""A/B test service — experiment management, metric updates, and statistical significance."""

import math
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ab_test import ABTestExperiment, ABTestVariant
from app.models.meta_campaign import MetaInsight

logger = structlog.get_logger()


class ABTestService:
    """Manage A/B test experiments for Meta ads."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_experiment(
        self,
        user_id: int,
        account_id: str,
        name: str,
        test_type: str = "creative",
        hypothesis: Optional[str] = None,
        primary_metric: str = "ctr",
        confidence_level: float = 0.95,
        min_sample_size: int = 1000,
        variants: Optional[list[dict]] = None,
    ) -> ABTestExperiment:
        """Create a new A/B test experiment with variants."""
        experiment = ABTestExperiment(
            user_id=user_id,
            account_id=account_id,
            name=name,
            test_type=test_type,
            hypothesis=hypothesis,
            primary_metric=primary_metric,
            confidence_level=confidence_level,
            min_sample_size=min_sample_size,
            status="draft",
        )
        self.db.add(experiment)
        await self.db.flush()
        await self.db.refresh(experiment)

        # Create variants
        if variants:
            for i, v in enumerate(variants):
                variant = ABTestVariant(
                    experiment_id=experiment.id,
                    name=v.get("name", f"Variant {chr(65 + i)}"),
                    variant_type="control" if i == 0 else "test",
                    variation_description=v.get("description"),
                    creative_config=v.get("creative_config"),
                    ad_meta_id=v.get("ad_meta_id"),
                    creative_meta_id=v.get("creative_meta_id"),
                )
                self.db.add(variant)

        await self.db.flush()
        logger.info("ab_test_created", experiment_id=experiment.id, name=name)
        return experiment

    async def update_variant_metrics(self, experiment_id: int) -> dict:
        """Update variant metrics from Meta insights data."""
        result = await self.db.execute(
            select(ABTestExperiment)
            .options(selectinload(ABTestExperiment.variants))
            .where(ABTestExperiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if not experiment:
            return {"error": "実験が見つかりません"}

        updated = 0
        for variant in experiment.variants:
            if not variant.ad_meta_id:
                continue

            # Sum insights for this ad
            result = await self.db.execute(
                select(
                    MetaInsight.impressions,
                    MetaInsight.clicks,
                    MetaInsight.spend,
                    MetaInsight.conversions,
                )
                .where(
                    MetaInsight.entity_type == "ad",
                    MetaInsight.entity_id == variant.ad_meta_id,
                )
            )
            rows = result.all()
            total_impressions = sum(r[0] or 0 for r in rows)
            total_clicks = sum(r[1] or 0 for r in rows)
            total_spend = sum(r[2] or 0 for r in rows)
            total_conversions = sum(r[3] or 0 for r in rows)

            variant.impressions = total_impressions
            variant.clicks = total_clicks
            variant.spend = total_spend
            variant.conversions = total_conversions
            variant.ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
            variant.cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
            variant.cpa = (total_spend / total_conversions) if total_conversions > 0 else 0
            updated += 1

        await self.db.flush()
        logger.info("ab_test_metrics_updated", experiment_id=experiment_id, variants_updated=updated)
        return {"updated": updated}

    async def check_significance(self, experiment_id: int) -> dict:
        """Check statistical significance between variants using chi-squared test.

        Returns p-value and winner determination.
        """
        result = await self.db.execute(
            select(ABTestExperiment)
            .options(selectinload(ABTestExperiment.variants))
            .where(ABTestExperiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if not experiment or len(experiment.variants) < 2:
            return {"significant": False, "message": "バリアントが不足しています"}

        # Get control and test variants
        control = next((v for v in experiment.variants if v.variant_type == "control"), None)
        test_variants = [v for v in experiment.variants if v.variant_type == "test"]

        if not control or not test_variants:
            return {"significant": False, "message": "コントロールまたはテストバリアントが見つかりません"}

        # Check minimum sample size
        total_impressions = sum(v.impressions for v in experiment.variants)
        if total_impressions < experiment.min_sample_size:
            return {
                "significant": False,
                "message": f"サンプルサイズが不足 ({total_impressions}/{experiment.min_sample_size})",
                "current_sample": total_impressions,
                "required_sample": experiment.min_sample_size,
            }

        # Chi-squared test for each test variant vs control
        results = []
        for test in test_variants:
            p_value = _chi_squared_test(
                control.clicks, control.impressions - control.clicks,
                test.clicks, test.impressions - test.clicks,
            )
            is_significant = p_value < (1 - experiment.confidence_level)
            winner = None
            if is_significant:
                metric = experiment.primary_metric
                if metric == "ctr":
                    winner = test.name if test.ctr > control.ctr else control.name
                elif metric == "cpa":
                    winner = test.name if (test.cpa < control.cpa and test.cpa > 0) else control.name
                else:
                    winner = test.name if test.ctr > control.ctr else control.name

            results.append({
                "test_variant": test.name,
                "p_value": round(p_value, 4),
                "is_significant": is_significant,
                "winner": winner,
                "control_metric": control.ctr,
                "test_metric": test.ctr,
                "lift": round((test.ctr - control.ctr) / max(control.ctr, 0.001) * 100, 1),
            })

        # Overall winner
        significant_results = [r for r in results if r["is_significant"]]
        overall_winner = None
        if significant_results:
            best = max(significant_results, key=lambda r: r["lift"])
            overall_winner = best["winner"]

        return {
            "significant": bool(significant_results),
            "results": results,
            "overall_winner": overall_winner,
            "total_sample": total_impressions,
        }

    async def complete_experiment(self, experiment_id: int) -> dict:
        """Complete an experiment — declare winner, pause losers."""
        significance = await self.check_significance(experiment_id)

        result = await self.db.execute(
            select(ABTestExperiment)
            .options(selectinload(ABTestExperiment.variants))
            .where(ABTestExperiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if not experiment:
            return {"error": "実験が見つかりません"}

        experiment.status = "completed"
        experiment.completed_at = datetime.now(timezone.utc)

        if significance.get("overall_winner"):
            winner_name = significance["overall_winner"]
            for variant in experiment.variants:
                if variant.name == winner_name:
                    variant.is_winner = True
                    experiment.winner_variant_id = variant.id

            # Get significance from results
            sig_results = significance.get("results", [])
            if sig_results:
                experiment.statistical_significance = min(r["p_value"] for r in sig_results)

        await self.db.flush()
        logger.info("ab_test_completed", experiment_id=experiment_id, winner=significance.get("overall_winner"))
        return {
            "completed": True,
            "winner": significance.get("overall_winner"),
            "significance": significance,
        }


def _chi_squared_test(success_a: int, failure_a: int, success_b: int, failure_b: int) -> float:
    """Simple chi-squared test for 2x2 contingency table.

    Returns p-value (approximate using normal approximation).
    """
    n_a = success_a + failure_a
    n_b = success_b + failure_b
    n = n_a + n_b

    if n_a == 0 or n_b == 0 or n == 0:
        return 1.0

    # Pooled proportion
    p = (success_a + success_b) / n

    # Standard error
    se = math.sqrt(p * (1 - p) * (1/n_a + 1/n_b))
    if se == 0:
        return 1.0

    # Z-statistic
    p_a = success_a / n_a
    p_b = success_b / n_b
    z = abs(p_a - p_b) / se

    # Approximate p-value using error function (two-tailed)
    p_value = 2 * (1 - _normal_cdf(z))
    return max(p_value, 0.0)


def _normal_cdf(x: float) -> float:
    """Approximate normal CDF using Abramowitz and Stegun formula."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
