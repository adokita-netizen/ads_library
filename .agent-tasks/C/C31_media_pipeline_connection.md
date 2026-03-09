# C31: メディア抽出パイプライン接続（3ファイル修正）

## 目的
Lambda → SQS → ECS → Playwright → DB更新 のメディア抽出パイプラインを動作可能にする。

## フロー図
```
Lambda (action=extract_media)
  → DBから media_extraction_status="pending" の広告を取得
  → dispatch_task("extract_media") → SQS heavy queue
  → sqs_ecs_trigger.py (Lambda) → ECS RunTask
  → runner.py → extract_media_task → MediaExtractor (Playwright)
  → DB更新 (media_extraction_status=completed)
```

## 対象ファイル（3つ）

---

### 修正1: backend/app/tasks/runner.py — Celery bind=True 対応

**問題**: `extract_media_task` は `@celery_app.task(bind=True)` デコレータ付き。
`run_task()` で `task_func(**kwargs)` と呼ぶと、bind=True のため `self`（Celery タスクインスタンス）が不足してエラーになる。
タスク内部で `self.request.id` や `self.retry(exc=e)` を使用している。

**修正方法**:

ファイル先頭に `import uuid` を追加し、`_get_task_map()` の前に以下を追加：

```python
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
```

`run_task()` 内の呼び出し部分（L60）を変更：

```python
# 変更前:
result = task_func(**kwargs)

# 変更後:
if _is_bound_celery_task(task_func):
    fake_self = _FakeCeleryTask()
    logger.info("ecs_task_using_fake_self", task=task_name, task_id=fake_self.request.id)
    result = task_func.run(fake_self, **kwargs)
else:
    result = task_func(**kwargs)
```

---

### 修正2: backend/app/services/media_extraction.py — Docker 用 Chromium 起動オプション

**問題**: Docker コンテナ内では `--no-sandbox` が必須。現在は `chromium.launch(headless=True)` のみ。

**修正箇所**: `_extract_via_playwright()` メソッド内の L106

```python
# 変更前:
browser = await p.chromium.launch(headless=True)

# 変更後:
browser = await p.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--single-process",
    ],
)
```

---

### 修正3: backend/lambda_handler.py — extract_media アクション追加

**問題**: `action == "extract_media"` のハンドラが存在しない。

**修正箇所1**: `handler()` 関数内、crawl の前（L69 の前）に追加

```python
# Direct invocation for batch media extraction (pending ads → SQS → ECS)
if isinstance(event, dict) and event.get("action") == "extract_media":
    return _run_extract_media(event)
```

**修正箇所2**: ファイル末尾に `_run_extract_media` 関数を追加

```python
def _run_extract_media(event: dict) -> dict:
    """Batch dispatch media extraction for ads with pending status."""
    from sqlalchemy import text
    from app.core.database import SyncSessionLocal
    from app.tasks.dispatcher import dispatch_task

    limit = event.get("limit", 50)
    statuses = event.get("statuses", ["pending", "pending_heavy"])

    session = SyncSessionLocal()
    try:
        rows = session.execute(text("""
            SELECT id, external_id, snapshot_url, media_extraction_status
            FROM ads
            WHERE media_extraction_status = ANY(:statuses)
            AND (snapshot_url IS NOT NULL OR external_id IS NOT NULL)
            ORDER BY id
            LIMIT :limit
        """), {"statuses": statuses, "limit": limit}).fetchall()

        dispatched = []
        errors = []
        for row in rows:
            ad_id = row[0]
            try:
                result = dispatch_task("extract_media", ad_id=ad_id)
                dispatched.append({"ad_id": ad_id, "message_id": result.id})
            except Exception as e:
                errors.append({"ad_id": ad_id, "error": str(e)})
                logger.error("extract_media_dispatch_failed", ad_id=ad_id, error=str(e))

        remaining = session.execute(text("""
            SELECT count(*) FROM ads
            WHERE media_extraction_status = ANY(:statuses)
        """), {"statuses": statuses}).scalar()

        return {
            "statusCode": 200,
            "body": json.dumps({
                "dispatched": len(dispatched),
                "errors": len(errors),
                "remaining": remaining,
                "details": dispatched[:10],
                "error_details": errors[:10],
            }, default=str)
        }
    except Exception as e:
        logger.error("extract_media_batch_error", error=str(e))
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
    finally:
        session.close()
```

## テスト方法
```bash
# Lambda経由でバッチ起動
aws lambda invoke --function-name vaap-production-api \
  --payload '{"action": "extract_media", "limit": 3}' \
  output.json
```

## 制約
- `runner.py`: `run_task()` と周辺のみ修正。`_get_task_map()` は変更しない
- `media_extraction.py`: `chromium.launch()` の引数のみ変更。`_parse_html()` 等は触らない
- `lambda_handler.py`: 既存の handler 分岐・関数は変更しない。追加のみ
