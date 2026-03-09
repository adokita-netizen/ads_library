# C34: ECS タスク実行ステータスAPI

## 目的
ECS Fargate で実行中/完了/失敗のタスクを確認できるAPI。
メディア抽出やクロールの実行状況をリアルタイムに把握。

## 対象ファイル
- `backend/app/api/endpoints/rankings.py` (末尾に追加)

## タスク

### 1. GET /rankings/ecs-tasks
ECS クラスター上のタスク一覧を返す。

```python
@router.get("/ecs-tasks")
async def get_ecs_tasks(status: str = "RUNNING"):
    """List ECS tasks in the VAAP cluster."""
    import boto3
    ecs = boto3.client("ecs", region_name="ap-northeast-1")

    cluster = "vaap-cluster"

    # List task ARNs
    task_arns = ecs.list_tasks(
        cluster=cluster,
        desiredStatus=status,  # RUNNING, STOPPED
    ).get("taskArns", [])

    if not task_arns:
        return {"tasks": [], "count": 0}

    # Describe tasks
    details = ecs.describe_tasks(cluster=cluster, tasks=task_arns)

    tasks = []
    for task in details.get("tasks", []):
        container = task.get("containers", [{}])[0]
        overrides = task.get("overrides", {}).get("containerOverrides", [{}])[0]
        command = overrides.get("command", [])

        # Extract task name from command: ["python", "-m", "app.tasks.runner", "extract_media", '{"ad_id": 123}']
        task_name = command[3] if len(command) > 3 else "unknown"
        task_kwargs = command[4] if len(command) > 4 else "{}"

        tasks.append({
            "task_arn": task["taskArn"].split("/")[-1],
            "status": task.get("lastStatus"),
            "desired_status": task.get("desiredStatus"),
            "task_name": task_name,
            "kwargs": task_kwargs,
            "created_at": str(task.get("createdAt")),
            "started_at": str(task.get("startedAt")),
            "stopped_at": str(task.get("stoppedAt")),
            "stop_reason": task.get("stoppedReason"),
            "exit_code": container.get("exitCode"),
            "cpu": task.get("cpu"),
            "memory": task.get("memory"),
        })

    return {"tasks": tasks, "count": len(tasks)}
```

### 2. GET /rankings/ecs-tasks/recent
直近のタスク実行履歴（STOPPED含む）。

```python
@router.get("/ecs-tasks/recent")
async def get_recent_ecs_tasks(limit: int = 20):
    """Recent ECS task history (including stopped)."""
    import boto3
    ecs = boto3.client("ecs", region_name="ap-northeast-1")

    cluster = "vaap-cluster"

    # Get both running and stopped
    running = ecs.list_tasks(cluster=cluster, desiredStatus="RUNNING").get("taskArns", [])
    stopped = ecs.list_tasks(cluster=cluster, desiredStatus="STOPPED").get("taskArns", [])

    all_arns = (running + stopped)[:limit]
    if not all_arns:
        return {"tasks": [], "running": 0, "stopped": 0}

    details = ecs.describe_tasks(cluster=cluster, tasks=all_arns)

    tasks = []
    for task in details.get("tasks", []):
        container = task.get("containers", [{}])[0]
        overrides = task.get("overrides", {}).get("containerOverrides", [{}])[0]
        command = overrides.get("command", [])

        tasks.append({
            "task_arn": task["taskArn"].split("/")[-1],
            "status": task.get("lastStatus"),
            "task_name": command[3] if len(command) > 3 else "unknown",
            "started_at": str(task.get("startedAt")),
            "stopped_at": str(task.get("stoppedAt")),
            "exit_code": container.get("exitCode"),
            "stop_reason": task.get("stoppedReason"),
            "duration_seconds": None,  # computed below
        })

        # Compute duration
        if task.get("startedAt") and task.get("stoppedAt"):
            duration = (task["stoppedAt"] - task["startedAt"]).total_seconds()
            tasks[-1]["duration_seconds"] = int(duration)

    return {
        "tasks": tasks,
        "running": len(running),
        "stopped": len(stopped),
    }
```

## 制約
- `rankings.py` 末尾に追加のみ
- boto3 ECS クライアントを使用
- クラスター名は `vaap-cluster`（terraform/ecs.tf と一致させる）
