"""Celery tasks for automated alert detection."""

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(name="app.tasks.alert_tasks.detect_alerts_task")
def detect_alerts_task():
    """Run all alert detections (spend surge, LP swap, new competitors, trends)."""
    from app.core.database import SyncSessionLocal
    from app.services.competitive.alert_detector import AlertDetector

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
