"""ECS task runner entry point.

Usage from ECS RunTask container override:
    python -m app.tasks.runner <task_name> '<json_kwargs>'

Example:
    python -m app.tasks.runner crawl_ads '{"query": "skincare", "platforms": ["youtube"]}'
"""

import json
import sys

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


def run_task(task_name: str, kwargs: dict) -> dict:
    """Execute a task function directly (bypassing Celery)."""
    task_map = _get_task_map()
    task_func = task_map.get(task_name)
    if not task_func:
        raise ValueError(f"Unknown task: {task_name}. Available: {list(task_map.keys())}")

    logger.info("ecs_task_starting", task=task_name, kwargs_keys=list(kwargs.keys()))

    # Celery tasks decorated with @celery_app.task(bind=True) expect `self` as first arg.
    # When calling directly, we pass None — the task function should handle this gracefully,
    # or we call the underlying function. For ECS execution, we call the raw function.
    # The actual Celery task objects are callable and accept kwargs directly.
    result = task_func(**kwargs)

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
