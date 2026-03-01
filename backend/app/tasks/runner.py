"""ECS task runner entry point.

Usage from ECS RunTask container override:
    python -m app.tasks.runner <task_name> '<json_kwargs>'

Example:
    python -m app.tasks.runner crawl_ads '{"query": "skincare", "platforms": ["youtube"]}'
"""

import json
import os
import signal
import sys
import uuid

import structlog

logger = structlog.get_logger()


def _get_task_map() -> dict:
    """Lazy-load task functions to avoid importing heavy modules at module level."""
    from app.tasks.analysis_tasks import analyze_ad_task
    from app.tasks.crawl_tasks import crawl_ads_task
    from app.tasks.lp_tasks import (
        crawl_and_analyze_lp_task,
        analyze_own_lp_content_task,
        batch_crawl_lps_task,
    )
    from app.tasks.media_tasks import enrich_ad_creative_task, extract_media_task
    from app.tasks.generation_tasks import generate_script_task, generate_copy_task
    from app.tasks.ranking_tasks import compute_rankings_task
    from app.tasks.alert_tasks import detect_alerts_task

    return {
        "crawl_ads": crawl_ads_task,
        "analyze_ad": analyze_ad_task,
        "crawl_and_analyze_lp": crawl_and_analyze_lp_task,
        "analyze_own_lp_content": analyze_own_lp_content_task,
        "batch_crawl_lps": batch_crawl_lps_task,
        "compute_rankings": compute_rankings_task,
        "detect_alerts": detect_alerts_task,
        "generate_script": generate_script_task,
        "generate_copy": generate_copy_task,
        "enrich_ad_creative": enrich_ad_creative_task,
        "extract_media": extract_media_task,
    }


class _FakeRequest:
    """Minimal stand-in for celery.app.task.Context."""

    def __init__(self):
        self.id = f"ecs-{uuid.uuid4()}"
        self.retries = 0


class _FakeCeleryTask:
    """Stand-in for Celery Task instance for ECS direct execution."""

    def __init__(self, max_retries=2):
        self.request = _FakeRequest()
        self.max_retries = max_retries

    def retry(self, exc=None, **kwargs):
        if exc:
            raise exc
        raise RuntimeError("Task retry requested but no Celery broker (ECS)")


def _is_bound_celery_task(task_func) -> bool:
    """Check if a task function is a Celery task with bind=True."""
    try:
        from celery import Task
        if isinstance(task_func, Task):
            import inspect
            sig = inspect.signature(task_func.run)
            first_param = list(sig.parameters.keys())[0] if sig.parameters else None
            return first_param == "self"
    except Exception:
        pass
    return False


TASK_TIMEOUT = int(os.environ.get("ECS_TASK_TIMEOUT", "1800"))  # 30 min default


class TaskTimeoutError(Exception):
    """Raised when a task exceeds its timeout."""


def _timeout_handler(signum, frame):
    raise TaskTimeoutError(f"Task exceeded {TASK_TIMEOUT}s timeout")


def run_task(task_name: str, kwargs: dict) -> dict:
    """Execute a task function directly (bypassing Celery)."""
    task_map = _get_task_map()
    task_func = task_map.get(task_name)
    if not task_func:
        raise ValueError(f"Unknown task: {task_name}. Available: {list(task_map.keys())}")

    logger.info("ecs_task_starting", task=task_name, kwargs_keys=list(kwargs.keys()),
                timeout_seconds=TASK_TIMEOUT)

    # Set timeout via SIGALRM (Unix only; on Windows this is a no-op)
    has_alarm = hasattr(signal, "SIGALRM")
    if has_alarm:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(TASK_TIMEOUT)

    try:
        if _is_bound_celery_task(task_func):
            fake_self = _FakeCeleryTask()
            logger.info("ecs_task_using_fake_self", task=task_name, task_id=fake_self.request.id)
            result = task_func.run(fake_self, **kwargs)
        else:
            result = task_func(**kwargs)
    finally:
        if has_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    logger.info("ecs_task_completed", task=task_name, result_type=type(result).__name__)
    return result if isinstance(result, dict) else {"status": "completed"}


def main():
    if len(sys.argv) < 2:
        logger.error("missing_task_name", usage="python -m app.tasks.runner <task_name> [json_kwargs]")
        sys.exit(1)

    task_name = sys.argv[1]
    kwargs = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    logger.info("ecs_runner_started", task=task_name)
    try:
        result = run_task(task_name, kwargs)
        logger.info("ecs_runner_completed", task=task_name, result=result)
    except Exception as e:
        logger.error("ecs_runner_failed", task=task_name, error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
