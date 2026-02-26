"""Celery tasks for Meta Marketing data synchronization."""

import asyncio

import structlog

from app.tasks.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def sync_meta_account_task(self, account_id: str, insights_days: int = 7):
    """Sync a single Meta ad account — campaigns, ad sets, ads, insights."""
    logger.info("meta_sync_task_started", account_id=account_id, task_id=self.request.id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_sync(account_id, insights_days))
        loop.close()

        logger.info("meta_sync_task_completed", account_id=account_id, result=result)
        return {"status": "completed", **result}

    except Exception as e:
        logger.error("meta_sync_task_failed", account_id=account_id, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1)
def sync_all_meta_accounts_task(self):
    """Sync all active Meta ad accounts — scheduled daily at 02:00 JST."""
    logger.info("meta_sync_all_started", task_id=self.request.id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_sync_all())
        loop.close()

        logger.info("meta_sync_all_completed", result=result)
        return result

    except Exception as e:
        logger.error("meta_sync_all_failed", error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def sync_meta_insights_task(self, account_id: str, date_from: str, date_to: str):
    """Backfill insights for a date range — used for historical data."""
    logger.info("meta_insights_backfill_started", account_id=account_id, date_from=date_from, date_to=date_to)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_insights_backfill(account_id, date_from, date_to))
        loop.close()

        logger.info("meta_insights_backfill_completed", account_id=account_id, count=result)
        return {"status": "completed", "insights": result}

    except Exception as e:
        logger.error("meta_insights_backfill_failed", account_id=account_id, error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1)
def check_meta_token_health_task(self):
    """Check Meta token health and refresh if expiring — scheduled daily at 01:00 JST."""
    logger.info("meta_token_health_check_started", task_id=self.request.id)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_token_health_check())
        loop.close()

        logger.info("meta_token_health_check_completed", result=result)
        return result

    except Exception as e:
        logger.error("meta_token_health_check_failed", error=str(e))
        return {"status": "error", "error": str(e)}


# ── Async runners ────────────────────────────────────────────────

async def _run_sync(account_id: str, insights_days: int) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.meta_marketing.client import MetaMarketingClient
    from app.services.meta_marketing.sync_service import MetaSyncService
    from app.services.meta_marketing.token_manager import MetaTokenManager

    async with AsyncSessionLocal() as db:
        try:
            # Refresh token if needed
            await MetaTokenManager.refresh_if_needed(db)
            await db.commit()

            token = await MetaTokenManager.get_access_token(db)
            if not token:
                raise RuntimeError("Meta access token not configured")

            client = MetaMarketingClient(token)
            try:
                service = MetaSyncService(client, db)
                result = await service.full_sync(account_id, insights_days=insights_days)
                await db.commit()
                return result
            finally:
                await client.close()
        except Exception:
            await db.rollback()
            raise


async def _run_sync_all() -> dict:
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.meta_ad_account import MetaAdAccount

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MetaAdAccount.account_id).where(MetaAdAccount.is_active == True)
        )
        account_ids = [row[0] for row in result.all()]

    results = {}
    for account_id in account_ids:
        try:
            r = await _run_sync(account_id, insights_days=7)
            results[account_id] = {"status": "ok", **r}
        except Exception as e:
            results[account_id] = {"status": "error", "error": str(e)}

    return {"accounts_synced": len(account_ids), "results": results}


async def _run_insights_backfill(account_id: str, date_from: str, date_to: str) -> int:
    from app.core.database import AsyncSessionLocal
    from app.services.meta_marketing.client import MetaMarketingClient
    from app.services.meta_marketing.sync_service import MetaSyncService
    from app.services.meta_marketing.token_manager import MetaTokenManager

    async with AsyncSessionLocal() as db:
        try:
            token = await MetaTokenManager.get_access_token(db)
            if not token:
                raise RuntimeError("Meta access token not configured")

            client = MetaMarketingClient(token)
            try:
                service = MetaSyncService(client, db)
                count = await service.sync_insights(account_id, date_from=date_from, date_to=date_to, level="ad")
                await db.commit()
                return count
            finally:
                await client.close()
        except Exception:
            await db.rollback()
            raise


async def _run_token_health_check() -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.meta_marketing.token_manager import MetaTokenManager

    async with AsyncSessionLocal() as db:
        try:
            result = await MetaTokenManager.refresh_if_needed(db)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise
