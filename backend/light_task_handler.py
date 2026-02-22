"""AWS Lambda handler for light tasks.

Invoked by:
- EventBridge Scheduler (daily jobs: rankings, alerts)
- SQS light-tasks queue (on-demand: generate_script, generate_copy, etc.)
"""

import json

import structlog

logger = structlog.get_logger()


def handler(event, context):
    """Route to the appropriate light task function."""
    # Determine task name from EventBridge or SQS
    task_name = None
    kwargs = {}

    if "task" in event:
        # Direct EventBridge invocation: {"task": "compute_rankings"}
        task_name = event["task"]
        kwargs = event.get("kwargs", {})
    elif "Records" in event:
        # SQS trigger
        record = event["Records"][0]
        body = json.loads(record["body"])
        task_name = body.get("task")
        kwargs = body.get("kwargs", {})
    else:
        logger.error("unknown_event_format", event_keys=list(event.keys()))
        return {"status": "error", "message": "Unknown event format"}

    logger.info("light_task_starting", task=task_name)

    try:
        result = _execute_task(task_name, kwargs)
        logger.info("light_task_completed", task=task_name)
        return {"status": "completed", "task": task_name, "result": result}
    except Exception as e:
        logger.error("light_task_failed", task=task_name, error=str(e))
        return {"status": "error", "task": task_name, "error": str(e)}


def _execute_task(task_name: str, kwargs: dict):
    """Execute a light task by name."""
    if task_name == "compute_rankings":
        from app.tasks.ranking_tasks import compute_rankings_task
        return compute_rankings_task()

    elif task_name == "detect_alerts":
        from app.tasks.alert_tasks import detect_alerts_task
        return detect_alerts_task()

    elif task_name == "generate_script":
        from app.tasks.generation_tasks import generate_script_task
        return generate_script_task(**kwargs)

    elif task_name == "generate_copy":
        from app.tasks.generation_tasks import generate_copy_task
        return generate_copy_task(**kwargs)

    elif task_name == "analyze_own_lp_content":
        from app.tasks.lp_tasks import analyze_own_lp_content_task
        return analyze_own_lp_content_task(**kwargs)

    elif task_name == "batch_crawl_lps":
        from app.tasks.lp_tasks import batch_crawl_lps_task
        return batch_crawl_lps_task(**kwargs)

    else:
        raise ValueError(f"Unknown light task: {task_name}")
