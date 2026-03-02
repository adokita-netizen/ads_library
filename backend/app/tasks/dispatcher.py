"""Task dispatcher: routes tasks to Celery (local) or SQS (AWS) based on TASK_BACKEND env var."""

import json
import os
import uuid
from typing import Any

import structlog

logger = structlog.get_logger()

TASK_BACKEND = os.getenv("TASK_BACKEND", "celery")  # "celery" or "sqs"

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
    "generate_script": "app.tasks.generation_tasks.generate_script_task",
    "generate_copy": "app.tasks.generation_tasks.generate_copy_task",
}


class DispatchResult:
    """Result of a task dispatch, mimicking Celery AsyncResult interface."""

    def __init__(self, task_id: str):
        self.id = task_id


def dispatch_task(task_name: str, **kwargs: Any) -> DispatchResult:
    """Dispatch a task to the appropriate backend.

    Args:
        task_name: Logical task name (e.g., "analyze_ad", "crawl_ads").
        **kwargs: Task arguments.

    Returns:
        DispatchResult with a task/message ID.
    """
    if TASK_BACKEND == "sqs":
        return _dispatch_sqs(task_name, kwargs)
    else:
        return _dispatch_celery(task_name, kwargs)


def _dispatch_celery(task_name: str, kwargs: dict[str, Any]) -> DispatchResult:
    """Dispatch via Celery .send_task()."""
    from app.tasks.worker import celery_app

    celery_task_name = _CELERY_TASK_MAP.get(task_name)
    if not celery_task_name:
        raise ValueError(f"Unknown task: {task_name}")

    result = celery_app.send_task(celery_task_name, kwargs=kwargs)
    logger.info("task_dispatched_celery", task=task_name, task_id=result.id)
    return DispatchResult(task_id=result.id)


def _dispatch_sqs(task_name: str, kwargs: dict[str, Any]) -> DispatchResult:
    """Dispatch via SQS."""
    import boto3
    from app.core.config import get_settings

    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)

    if task_name in HEAVY_TASKS:
        queue_url = settings.sqs_heavy_queue_url
    else:
        queue_url = settings.sqs_light_queue_url

    if not queue_url:
        raise RuntimeError(f"SQS queue URL not configured for task: {task_name}")

    message_id = str(uuid.uuid4())
    message_body = json.dumps({
        "task": task_name,
        "kwargs": kwargs,
        "message_id": message_id,
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
    )
    return DispatchResult(task_id=sqs_message_id)
