"""Celery tasks for automated alert detection."""

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(name="app.tasks.alert_tasks.detect_alerts_task")
def detect_alerts_task():
    """Run all alert detections (spend surge, LP swap, new competitors, trends)."""
    from app.core.database import SyncSessionLocal
    from app.core.distributed_lock import acquire_distributed_lock, release_distributed_lock
    from app.services.competitive.alert_detector import AlertDetector

    job_name = "detect_alerts"
    token = acquire_distributed_lock(job_name, ttl=300)
    if token is None:
        logger.warning("alert_detection_skipped_locked", job=job_name)
        return {"status": "skipped", "reason": "already_running"}

    logger.info("alert_detection_start")
    session = SyncSessionLocal()
    try:
        detector = AlertDetector()
        alerts = detector.run_all_detections(session)
        session.commit()
        logger.info("alert_detection_complete", alert_count=len(alerts))
        return {"alert_count": len(alerts)}
    except Exception as exc:
        session.rollback()
        logger.error("alert_detection_failed", error=str(exc))
        raise
    finally:
        session.close()
        release_distributed_lock(job_name, token)


@shared_task(name="app.tasks.alert_tasks.evaluate_alert_rules_task")
def evaluate_alert_rules_task():
    """Evaluate rule-based alerts (A-R2-6 AlertEngine)."""
    from app.core.database import SyncSessionLocal
    from app.core.distributed_lock import acquire_distributed_lock, release_distributed_lock
    from app.services.alert_engine import AlertEngine, seed_default_rules

    job_name = "evaluate_alert_rules"
    token = acquire_distributed_lock(job_name, ttl=300)
    if token is None:
        logger.warning("alert_rules_skipped_locked", job=job_name)
        return {"status": "skipped", "reason": "already_running"}

    session = SyncSessionLocal()
    try:
        # Ensure default rules exist
        seeded = seed_default_rules(session)
        if seeded:
            session.commit()
            logger.info("alert_rules_seeded", count=seeded)

        engine = AlertEngine(session)
        count = engine.evaluate_all_rules()
        session.commit()
        logger.info("alert_rules_evaluated", alerts_generated=count)
        return {"status": "completed", "alerts_generated": count}
    except Exception as exc:
        session.rollback()
        logger.error("alert_rules_failed", error=str(exc))
        raise
    finally:
        session.close()
        release_distributed_lock(job_name, token)
