"""AWS Lambda handler: SQS heavy-tasks queue → ECS RunTask.

Triggered by SQS messages on the heavy-tasks queue.
Launches an ECS Fargate task with the appropriate command override.
"""

import json
import os

import boto3
import structlog

logger = structlog.get_logger()

ecs = boto3.client("ecs", region_name=os.environ.get("AWS_REGION", "ap-northeast-1"))

CLUSTER = os.environ.get("ECS_CLUSTER", "vaap-cluster")
TASK_DEFINITION = os.environ.get("ECS_TASK_DEFINITION", "vaap-worker")
CONTAINER_NAME = os.environ.get("ECS_CONTAINER_NAME", "vaap-worker")
SUBNETS = os.environ.get("ECS_SUBNETS", "").split(",")
SECURITY_GROUPS = os.environ.get("ECS_SECURITY_GROUPS", "").split(",")


def handler(event, context):
    """Process SQS records and launch ECS tasks."""
    results = []

    for record in event.get("Records", []):
        body = json.loads(record["body"])
        task_name = body.get("task", "unknown")
        task_kwargs = body.get("kwargs", {})

        logger.info("dispatching_ecs_task", task=task_name, kwargs_keys=list(task_kwargs.keys()))

        try:
            response = ecs.run_task(
                cluster=CLUSTER,
                taskDefinition=TASK_DEFINITION,
                launchType="FARGATE",
                count=1,
                overrides={
                    "containerOverrides": [
                        {
                            "name": CONTAINER_NAME,
                            "command": [
                                "python", "-m", "app.tasks.runner",
                                task_name,
                                json.dumps(task_kwargs),
                            ],
                        }
                    ],
                },
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": [s.strip() for s in SUBNETS if s.strip()],
                        "securityGroups": [s.strip() for s in SECURITY_GROUPS if s.strip()],
                        "assignPublicIp": "ENABLED",
                    }
                },
            )

            task_arns = [t["taskArn"] for t in response.get("tasks", [])]
            failures = response.get("failures", [])

            if failures:
                logger.warning("ecs_run_task_failures", task=task_name, failures=failures)

            results.append({
                "task": task_name,
                "status": "launched" if task_arns else "failed",
                "task_arns": task_arns,
                "failures": failures,
            })

        except Exception as e:
            logger.error("ecs_run_task_error", task=task_name, error=str(e), exc_info=True)
            results.append({
                "task": task_name,
                "status": "error",
                "error": str(e),
            })

    return {"results": results}
