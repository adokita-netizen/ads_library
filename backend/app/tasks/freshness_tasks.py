"""Celery tasks for data freshness scoring and auto-recrawl scheduling."""

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(name="app.tasks.freshness_tasks.refresh_data_freshness_task")
def refresh_data_freshness_task():
    """Compute freshness scores, generate daily report, and flag stale ads."""
    from app.core.database import SyncSessionLocal
    from app.core.distributed_lock import acquire_distributed_lock, release_distributed_lock
    from app.services.data_freshness import DataFreshnessService

    job_name = "refresh_data_freshness"
    token = acquire_distributed_lock(job_name, ttl=600)
    if token is None:
        logger.warning("freshness_refresh_skipped_locked", job=job_name)
        return {"status": "skipped", "reason": "already_running"}

    session = SyncSessionLocal()
    try:
        service = DataFreshnessService(session)
        score_summary = service.compute_freshness_scores()
        daily_report = service.generate_daily_report()
        scheduled = service.schedule_auto_recrawl()
        session.commit()
        payload = {
            "status": "completed",
            "score_summary": score_summary,
            "daily_report": daily_report,
            "scheduled_auto_recrawl": scheduled,
        }
        logger.info("freshness_refresh_complete", **payload)
        return payload
    except Exception as exc:
        session.rollback()
        logger.error("freshness_refresh_failed", error=str(exc))
        raise
    finally:
        session.close()
        release_distributed_lock(job_name, token)
