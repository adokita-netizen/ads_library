"""Operational health-check tasks for continuous data accumulation."""

from __future__ import annotations

from datetime import date, datetime

import structlog
from sqlalchemy import text

logger = structlog.get_logger()

try:
    from celery import shared_task
except Exception:  # pragma: no cover
    def shared_task(*args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _collect_db_health() -> dict:
    from app.core.database import SyncSessionLocal

    session = SyncSessionLocal()
    try:
        total_ads = session.execute(text("SELECT COUNT(*) FROM ads")).scalar()
        latest_metric_date = session.execute(text("SELECT MAX(metric_date) FROM ad_daily_metrics")).scalar()
        metrics_today = session.execute(
            text("SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = CURRENT_DATE")
        ).scalar()
        metrics_yesterday = session.execute(
            text("SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = CURRENT_DATE - 1")
        ).scalar()

        stale_days = None
        metric_day = latest_metric_date
        if isinstance(metric_day, str):
            try:
                metric_day = datetime.fromisoformat(metric_day).date()
            except Exception:
                metric_day = None
        if isinstance(metric_day, datetime):
            metric_day = metric_day.date()
        if isinstance(metric_day, date):
            stale_days = (date.today() - metric_day).days

        return {
            "total_ads": _safe_int(total_ads),
            "latest_metric_date": str(latest_metric_date) if latest_metric_date else None,
            "stale_days": _safe_int(stale_days) if stale_days is not None else None,
            "metrics_today": _safe_int(metrics_today),
            "metrics_yesterday": _safe_int(metrics_yesterday),
        }
    finally:
        session.close()


def _queue_health(sqs_client, queue_url: str | None, name: str) -> dict:
    if not queue_url:
        return {"queue": name, "configured": False}
    try:
        attrs = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )["Attributes"]
    except Exception as exc:
        return {"queue": name, "configured": True, "queue_url": queue_url, "error": str(exc)}

    dlq_url = f"{queue_url}-dlq"
    dlq_attrs = {}
    dlq_error = None
    try:
        dlq_attrs = sqs_client.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )["Attributes"]
    except Exception as exc:
        dlq_error = str(exc)

    payload = {
        "queue": name,
        "configured": True,
        "queue_url": queue_url,
        "visible_messages": _safe_int(attrs.get("ApproximateNumberOfMessages")),
        "inflight_messages": _safe_int(attrs.get("ApproximateNumberOfMessagesNotVisible")),
        "dlq_url": dlq_url,
        "dlq_visible_messages": _safe_int(dlq_attrs.get("ApproximateNumberOfMessages")),
        "dlq_inflight_messages": _safe_int(dlq_attrs.get("ApproximateNumberOfMessagesNotVisible")),
    }
    if dlq_error:
        payload["dlq_error"] = dlq_error
    return payload


def _collect_sqs_health() -> dict:
    from app.core.config import get_settings
    from app.tasks.sqs_resolver import resolve_queue_url

    settings = get_settings()

    try:
        import boto3

        sqs = boto3.client("sqs", region_name=settings.aws_region)
        heavy_url, heavy_mode = resolve_queue_url(
            "heavy",
            configured_url=settings.sqs_heavy_queue_url,
            app_env=settings.app_env,
            aws_region=settings.aws_region,
            sqs_client=sqs,
        )
        light_url, light_mode = resolve_queue_url(
            "light",
            configured_url=settings.sqs_light_queue_url,
            app_env=settings.app_env,
            aws_region=settings.aws_region,
            sqs_client=sqs,
        )
        heavy = _queue_health(sqs, heavy_url, "heavy")
        light = _queue_health(sqs, light_url, "light")
        heavy["resolution_mode"] = heavy_mode
        light["resolution_mode"] = light_mode
        return {"enabled": True, "queues": [heavy, light]}
    except Exception as exc:
        return {"enabled": False, "error": str(exc)}


def _judge_overall(db: dict, sqs: dict) -> str:
    if db.get("stale_days") is not None and db["stale_days"] > 2:
        return "warning"
    if sqs.get("enabled"):
        for q in sqs.get("queues", []):
            if q.get("dlq_visible_messages", 0) > 0:
                return "warning"
    return "ok"


def _ensure_ops_events_table(session) -> None:
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS ops_task_events (
                id INTEGER PRIMARY KEY,
                event_type TEXT NOT NULL,
                event_date TEXT NOT NULL,
                payload TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
    )


def _recovery_already_triggered_today() -> bool:
    from app.core.database import SyncSessionLocal

    today = date.today().isoformat()
    session = SyncSessionLocal()
    try:
        _ensure_ops_events_table(session)
        count = session.execute(
            text(
                """
                SELECT COUNT(*) FROM ops_task_events
                WHERE event_type = :event_type
                  AND event_date = :event_date
                """
            ),
            {"event_type": "recovery_crawl_dispatched", "event_date": today},
        ).scalar()
        return _safe_int(count) > 0
    finally:
        session.close()


def _record_recovery_event(payload: str) -> None:
    from app.core.database import SyncSessionLocal

    now_iso = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    session = SyncSessionLocal()
    try:
        _ensure_ops_events_table(session)
        session.execute(
            text(
                """
                INSERT INTO ops_task_events (event_type, event_date, payload, created_at)
                VALUES (:event_type, :event_date, :payload, :created_at)
                """
            ),
            {
                "event_type": "recovery_crawl_dispatched",
                "event_date": today,
                "payload": payload,
                "created_at": now_iso,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _maybe_trigger_recovery(db: dict, sqs: dict) -> dict:
    """Trigger a lightweight recovery crawl when metrics are stale."""
    stale_days = db.get("stale_days")
    if stale_days is None or stale_days <= 1:
        return {"triggered": False, "reason": "fresh_enough"}

    if not sqs.get("enabled"):
        return {"triggered": False, "reason": "sqs_unavailable"}

    heavy_queue = next((q for q in sqs.get("queues", []) if q.get("queue") == "heavy"), None)
    if not heavy_queue or not heavy_queue.get("configured"):
        return {"triggered": False, "reason": "heavy_queue_unconfigured"}

    if _recovery_already_triggered_today():
        return {"triggered": False, "reason": "already_triggered_today"}

    try:
        from app.tasks.dispatcher import dispatch_task

        result = dispatch_task(
            "crawl_ads",
            backend="sqs",
            query="",
            platforms=[
                "youtube",
                "tiktok",
                "facebook",
                "instagram",
                "line",
                "google_ads",
            ],
            category=None,
            limit_per_platform=20,
            auto_analyze=True,
        )
        logger.warning(
            "ops_recovery_crawl_dispatched",
            stale_days=stale_days,
            task_id=result.id,
        )
        response = {
            "triggered": True,
            "reason": "stale_metrics",
            "task": "crawl_ads",
            "task_id": result.id,
            "limit_per_platform": 20,
        }
        _record_recovery_event(str(response))
        return response
    except Exception as exc:
        logger.error("ops_recovery_crawl_failed", stale_days=stale_days, error=str(exc))
        return {"triggered": False, "reason": "dispatch_failed", "error": str(exc)}


@shared_task(name="app.tasks.ops_tasks.daily_ops_health_check_task")
def daily_ops_health_check_task():
    """Collect daily operations health for data accumulation reliability."""
    logger.info("daily_ops_health_check_start")
    db = _collect_db_health()
    sqs = _collect_sqs_health()
    overall = _judge_overall(db, sqs)
    recovery = _maybe_trigger_recovery(db, sqs)

    report = {
        "overall": overall,
        "database": db,
        "sqs": sqs,
        "recovery": recovery,
    }

    logger.info(
        "daily_ops_health_check_complete",
        overall=overall,
        metrics_today=db.get("metrics_today"),
        stale_days=db.get("stale_days"),
    )
    return report
