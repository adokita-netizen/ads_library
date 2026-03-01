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
    """Process SQS records and launch ECS tasks.

    Returns batchItemFailures for partial batch failure support.
    Failed messages stay in the queue and are retried by SQS.
    """
    results = []
    batch_item_failures = []

    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")

        try:
            body = json.loads(record["body"])
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("sqs_message_parse_error", message_id=message_id, error=str(e))
            batch_item_failures.append({"itemIdentifier": message_id})
            continue

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

            if not task_arns:
                # ECS RunTask returned no tasks — mark as failed for SQS retry
                logger.error("ecs_run_task_no_arns", task=task_name, message_id=message_id)
                batch_item_failures.append({"itemIdentifier": message_id})

            results.append({
                "task": task_name,
                "status": "launched" if task_arns else "failed",
                "task_arns": task_arns,
                "failures": failures,
            })

        except Exception as e:
            logger.error("ecs_run_task_error", task=task_name, error=str(e), exc_info=True)
            batch_item_failures.append({"itemIdentifier": message_id})
            results.append({
                "task": task_name,
                "status": "error",
                "error": str(e),
            })

    if batch_item_failures:
        logger.warning("sqs_batch_partial_failure",
                       total=len(event.get("Records", [])),
                       failed=len(batch_item_failures))

    return {"batchItemFailures": batch_item_failures}
