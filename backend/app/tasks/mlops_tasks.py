"""MLOps task wrappers for scheduled retraining and monitoring.

Primary mode:
- EventBridge -> light_tasks Lambda -> ECS RunTask (worker container)
Fallback mode:
- local subprocess execution (for dev environments without ECS wiring)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import structlog

logger = structlog.get_logger()


def _run_script(script_name: str, args: list[str] | None = None) -> dict:
    args = args or []
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_path = os.path.join(base_dir, "scripts", script_name)
    cmd = [sys.executable, script_path, *args]
    result = subprocess.run(
        cmd,
        cwd=base_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-4000:],
    }


def _run_on_ecs(command: list[str]) -> dict:
    import boto3

    cluster = os.getenv("ECS_CLUSTER", "").strip()
    task_definition = os.getenv("ECS_TASK_DEFINITION", "").strip()
    container_name = os.getenv("ECS_CONTAINER_NAME", "").strip()
    subnets = [s.strip() for s in os.getenv("ECS_SUBNETS", "").split(",") if s.strip()]
    security_groups = [s.strip() for s in os.getenv("ECS_SECURITY_GROUPS", "").split(",") if s.strip()]

    if not (cluster and task_definition and container_name and subnets and security_groups):
        return {"status": "skipped", "reason": "missing_ecs_env"}

    ecs = boto3.client("ecs", region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
    response = ecs.run_task(
        cluster=cluster,
        launchType="FARGATE",
        taskDefinition=task_definition,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": container_name,
                    "command": command,
                }
            ]
        },
    )

    failures = response.get("failures", [])
    tasks = response.get("tasks", [])
    if failures:
        return {"status": "error", "failures": failures}
    task_arn = tasks[0].get("taskArn") if tasks else None
    return {"status": "started", "task_arn": task_arn}


def mlops_retrain_task(kwargs: dict | None = None) -> dict:
    kwargs = kwargs or {}
    args = []
    if "min_accuracy" in kwargs:
        args += ["--min-accuracy", str(kwargs["min_accuracy"])]
    if "max_accuracy_drop" in kwargs:
        args += ["--max-accuracy-drop", str(kwargs["max_accuracy_drop"])]

    ecs_cmd = ["python", "scripts/mlops_retrain_pipeline.py", *args]
    ecs_res = _run_on_ecs(ecs_cmd)
    if ecs_res.get("status") == "started":
        payload = {"status": "started", "mode": "ecs", **ecs_res}
        logger.info("mlops_retrain_task_started", **payload)
        return payload

    # Fallback for local/dev
    res = _run_script("mlops_retrain_pipeline.py", args=args)
    ok = res["returncode"] in (0, 2)  # 2=rejected by gate, pipeline itself succeeded
    payload = {
        "status": "completed" if ok else "error",
        "mode": "local",
        "gate_passed": res["returncode"] == 0,
        "returncode": res["returncode"],
    }
    logger.info("mlops_retrain_task_done", **payload)
    payload["output"] = res
    return payload


def mlops_monitoring_task(kwargs: dict | None = None) -> dict:
    _ = kwargs or {}
    ecs_cmd = ["python", "scripts/mlops_monitoring_snapshot.py"]
    ecs_res = _run_on_ecs(ecs_cmd)
    if ecs_res.get("status") == "started":
        payload = {"status": "started", "mode": "ecs", **ecs_res}
        logger.info("mlops_monitoring_task_started", **payload)
        return payload

    # Fallback for local/dev
    res = _run_script("mlops_monitoring_snapshot.py")
    ok = res["returncode"] == 0
    payload = {
        "status": "completed" if ok else "error",
        "mode": "local",
        "returncode": res["returncode"],
    }
    logger.info("mlops_monitoring_task_done", **payload)
    payload["output"] = res
    try:
        out_json = json.loads((res.get("stdout_tail") or "").strip() or "{}")
        payload["snapshot"] = out_json
    except Exception:
        pass
    return payload
