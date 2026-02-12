"""Celery tasks for daily ranking computation."""

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(name="app.tasks.ranking_tasks.compute_rankings_task")
def compute_rankings_task():
    """Compute daily/weekly/monthly product rankings from ad_daily_metrics."""
    from app.core.database import SyncSessionLocal
    from app.services.ranking.ranking_service import RankingService

    logger.info("ranking_computation_start")
    session = SyncSessionLocal()
    try:
        svc = RankingService()
        svc.compute_all_rankings(session)
        session.commit()
        logger.info("ranking_computation_complete")
    except Exception as exc:
        session.rollback()
        logger.error("ranking_computation_failed", error=str(exc))
        raise
    finally:
        session.close()
