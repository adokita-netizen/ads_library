"""Celery tasks for optimization analysis and recommendation generation."""

import asyncio

import structlog

from app.tasks.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=1)
def generate_recommendations_task(self):
    """Generate optimization recommendations for all active accounts — daily at 07:00 JST."""
    logger.info("optimization_recommendations_started", task_id=self.request.id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_generate_recommendations())
        loop.close()

        logger.info("optimization_recommendations_completed", result=result)
        return result

    except Exception as e:
        logger.error("optimization_recommendations_failed", error=str(e))
        return {"status": "error", "error": str(e)}


@celery_app.task(bind=True, max_retries=1)
def update_ab_test_metrics_task(self):
    """Update A/B test variant metrics — every 4 hours."""
    logger.info("ab_test_metrics_update_started", task_id=self.request.id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_update_ab_test_metrics())
        loop.close()

        logger.info("ab_test_metrics_update_completed", result=result)
        return result

    except Exception as e:
        logger.error("ab_test_metrics_update_failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def _run_generate_recommendations():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.meta_ad_account import MetaAdAccount
    from app.services.meta_marketing.optimizer import MetaOptimizer

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(MetaAdAccount).where(MetaAdAccount.is_active == True)
            )
            accounts = result.scalars().all()

            total_recs = 0
            for account in accounts:
                optimizer = MetaOptimizer(db)
                recs = await optimizer.analyze_and_recommend(account.account_id, user_id=account.user_id)
                total_recs += len(recs)

            await db.commit()
            return {"accounts_analyzed": len(accounts), "recommendations_generated": total_recs}
        except Exception:
            await db.rollback()
            raise


async def _run_update_ab_test_metrics():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.ab_test import ABTestExperiment
    from app.services.meta_marketing.ab_test_service import ABTestService

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(ABTestExperiment).where(ABTestExperiment.status == "running")
            )
            experiments = result.scalars().all()

            updated = 0
            for exp in experiments:
                service = ABTestService(db)
                await service.update_variant_metrics(exp.id)
                await service.check_significance(exp.id)
                updated += 1

            await db.commit()
            return {"experiments_updated": updated}
        except Exception:
            await db.rollback()
            raise
