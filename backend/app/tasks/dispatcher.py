"""Task dispatcher: routes tasks to Celery (local) or SQS (AWS) based on TASK_BACKEND env var."""

import importlib
import json
import os
import threading
import uuid
from typing import Any

import structlog

from app.core.trace import get_current_trace_id

logger = structlog.get_logger()

TASK_BACKEND = os.getenv("TASK_BACKEND", "celery")  # "celery" or "sqs" or "local"

# Task classification: "heavy" → SQS heavy queue → ECS RunTask, "light" → SQS light queue → Lambda
HEAVY_TASKS = frozenset({
    "crawl_ads",
    "analyze_ad",
    "crawl_and_analyze_lp",
    "extract_media",
})

LIGHT_TASKS = frozenset({
    "compute_rankings",
    "detect_alerts",
    "daily_ops_health_check",
    "generate_script",
    "generate_copy",
    "analyze_own_lp_content",
    "batch_crawl_lps",
    "download_thumbnail",
    "enrich_ad_creative",
})

# Map task names to their Celery task paths (for celery backend)
_CELERY_TASK_MAP = {
    "crawl_ads": "app.tasks.crawl_tasks.crawl_ads_task",
    "analyze_ad": "app.tasks.analysis_tasks.analyze_ad_task",
    "crawl_and_analyze_lp": "app.tasks.lp_tasks.crawl_and_analyze_lp_task",
    "extract_media": "app.tasks.media_tasks.extract_media_task",
    "download_thumbnail": "app.tasks.media_tasks.download_thumbnail_task",
    "enrich_ad_creative": "app.tasks.media_tasks.enrich_ad_creative_task",
    "analyze_own_lp_content": "app.tasks.lp_tasks.analyze_own_lp_content_task",
    "batch_crawl_lps": "app.tasks.lp_tasks.batch_crawl_lps_task",
    "compute_rankings": "app.tasks.ranking_tasks.compute_rankings_task",
    "detect_alerts": "app.tasks.alert_tasks.detect_alerts_task",
    "daily_ops_health_check": "app.tasks.ops_tasks.daily_ops_health_check_task",
    "generate_script": "app.tasks.generation_tasks.generate_script_task",
    "generate_copy": "app.tasks.generation_tasks.generate_copy_task",
}


class DispatchResult:
    """Result of a task dispatch, mimicking Celery AsyncResult interface."""

    def __init__(self, task_id: str):
        self.id = task_id


class InlineTaskResult(DispatchResult):
    """Result of an inline task execution."""

    def __init__(self, task_id: str, payload: Any):
        super().__init__(task_id=task_id)
        self.payload = payload


def dispatch_task(task_name: str, backend: str | None = None, **kwargs: Any) -> DispatchResult:
    """Dispatch a task to the appropriate backend.

    Args:
        task_name: Logical task name (e.g., "analyze_ad", "crawl_ads").
        **kwargs: Task arguments.

    Returns:
        DispatchResult with a task/message ID.
    """
    trace_id = kwargs.get("trace_id") or get_current_trace_id()
    if trace_id and "trace_id" not in kwargs:
        kwargs["trace_id"] = trace_id
    selected_backend = (backend or TASK_BACKEND).lower()
    if selected_backend == "sqs":
        return _dispatch_sqs(task_name, kwargs)
    if selected_backend == "local":
        return _dispatch_local(task_name, kwargs)
    try:
        return _dispatch_celery(task_name, kwargs)
    except Exception as exc:
        if not _should_fallback_to_local(exc):
            raise
        logger.warning(
            "task_dispatch_falling_back_to_local",
            task=task_name,
            error=str(exc)[:200],
            trace_id=kwargs.get("trace_id"),
        )
        return _dispatch_local(task_name, kwargs)


def _dispatch_celery(task_name: str, kwargs: dict[str, Any]) -> DispatchResult:
    """Dispatch via Celery .send_task()."""
    from app.tasks.worker import celery_app

    celery_task_name = _CELERY_TASK_MAP.get(task_name)
    if not celery_task_name:
        raise ValueError(f"Unknown task: {task_name}")

    result = celery_app.send_task(celery_task_name, kwargs=kwargs)
    logger.info("task_dispatched_celery", task=task_name, task_id=result.id, trace_id=kwargs.get("trace_id"))
    return DispatchResult(task_id=result.id)


def _should_fallback_to_local(exc: Exception) -> bool:
    if isinstance(exc, ModuleNotFoundError):
        return True
    message = str(exc).lower()
    return "no module named 'celery'" in message or "celery is not installed" in message


def _dispatch_local(task_name: str, kwargs: dict[str, Any]) -> DispatchResult:
    task = _resolve_local_task(task_name)
    task_id = str(uuid.uuid4())
    thread = threading.Thread(
        target=_run_local_task,
        args=(task_name, task, task_id, dict(kwargs)),
        daemon=True,
    )
    thread.start()
    logger.info("task_dispatched_local", task=task_name, task_id=task_id, trace_id=kwargs.get("trace_id"))
    return DispatchResult(task_id=task_id)


def run_task_inline(task_name: str, **kwargs: Any) -> InlineTaskResult:
    task = _resolve_local_task(task_name)
    task_id = str(uuid.uuid4())
    payload = _execute_task(task_name, task, task_id, dict(kwargs))
    return InlineTaskResult(task_id=task_id, payload=payload)


def _resolve_local_task(task_name: str) -> Any:
    celery_task_name = _CELERY_TASK_MAP.get(task_name)
    if not celery_task_name:
        raise ValueError(f"Unknown task: {task_name}")

    module_name, attr_name = celery_task_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def _run_local_task(task_name: str, task: Any, task_id: str, kwargs: dict[str, Any]) -> None:
    try:
        _execute_task(task_name, task, task_id, kwargs)
        logger.info("task_completed_local", task=task_name, task_id=task_id, trace_id=kwargs.get("trace_id"))
    except Exception as exc:
        logger.error(
            "task_failed_local",
            task=task_name,
            task_id=task_id,
            error=str(exc)[:200],
            trace_id=kwargs.get("trace_id"),
        )


def _execute_task(task_name: str, task: Any, task_id: str, kwargs: dict[str, Any]) -> Any:
    if hasattr(task, "request"):
        task.request.id = task_id
    if hasattr(task, "run"):
        return task.run(**kwargs)
    return task(**kwargs)


def _dispatch_sqs(task_name: str, kwargs: dict[str, Any]) -> DispatchResult:
    """Dispatch via SQS."""
    import boto3
    from app.core.config import get_settings
    from app.tasks.sqs_resolver import resolve_queue_url

    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)

    if task_name in HEAVY_TASKS:
        queue_url, resolution = resolve_queue_url(
            "heavy",
            configured_url=settings.sqs_heavy_queue_url,
            app_env=settings.app_env,
            aws_region=settings.aws_region,
            sqs_client=sqs,
        )
    else:
        queue_url, resolution = resolve_queue_url(
            "light",
            configured_url=settings.sqs_light_queue_url,
            app_env=settings.app_env,
            aws_region=settings.aws_region,
            sqs_client=sqs,
        )

    if not queue_url:
        raise RuntimeError(
            f"SQS queue URL unresolved for task: {task_name}. "
            "Set SQS_HEAVY_QUEUE_URL/SQS_LIGHT_QUEUE_URL or configure queue names."
        )

    message_id = str(uuid.uuid4())
    message_body = json.dumps({
        "task": task_name,
        "kwargs": kwargs,
        "message_id": message_id,
        "trace_id": kwargs.get("trace_id"),
    })

    send_kwargs = {
        "QueueUrl": queue_url,
        "MessageBody": message_body,
    }
    if queue_url.endswith(".fifo"):
        # Use per-message group ID to allow parallel processing
        # (task_name would serialize all tasks of the same type)
        send_kwargs["MessageGroupId"] = str(kwargs.get("ad_id", message_id))
        send_kwargs["MessageDeduplicationId"] = message_id

    response = sqs.send_message(**send_kwargs)

    sqs_message_id = response.get("MessageId", message_id)
    logger.info(
        "task_dispatched_sqs",
        task=task_name,
        queue=("heavy" if task_name in HEAVY_TASKS else "light"),
        message_id=sqs_message_id,
        queue_resolution=resolution,
        trace_id=kwargs.get("trace_id"),
    )
    return DispatchResult(task_id=sqs_message_id)
