# C33: SQS DLQ モニタリング & 再処理API

## 目的
SQS Dead Letter Queue (DLQ) に入った失敗メッセージを確認・再処理できるAPI。
パイプライン障害の早期検知と自動復旧。

## 対象ファイル
- `backend/app/api/endpoints/rankings.py` (末尾に追加)

## 背景
- Heavy/Light 両キューに DLQ が設定済み（3回リトライ後に移動）
- 現状 DLQ のメッセージを確認する手段がAPIにない
- 管理画面から DLQ の状況確認 & 再投入が必要

## タスク

### 1. GET /rankings/dlq-status
DLQ のメッセージ数を確認。

```python
@router.get("/dlq-status")
async def get_dlq_status():
    """Check SQS Dead Letter Queue status."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)

    result = {}
    for queue_name, queue_url in [
        ("heavy_dlq", settings.sqs_heavy_queue_url + "-dlq"),  # 命名規則に依存
        ("light_dlq", settings.sqs_light_queue_url + "-dlq"),
    ]:
        try:
            attrs = sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
            )["Attributes"]
            result[queue_name] = {
                "messages": int(attrs.get("ApproximateNumberOfMessages", 0)),
                "in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
            }
        except Exception as e:
            result[queue_name] = {"error": str(e)}

    return result
```

### 2. GET /rankings/dlq-messages
DLQ のメッセージ内容をプレビュー（最大10件）。

```python
@router.get("/dlq-messages")
async def get_dlq_messages(queue: str = "heavy", limit: int = 10):
    """Preview messages in DLQ without deleting them."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)

    queue_url = (settings.sqs_heavy_queue_url if queue == "heavy"
                 else settings.sqs_light_queue_url) + "-dlq"

    messages = []
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=min(limit, 10),
        VisibilityTimeout=0,  # Don't hide from other consumers
        MessageAttributeNames=["All"],
    )

    for msg in response.get("Messages", []):
        body = json.loads(msg["Body"])
        messages.append({
            "message_id": msg["MessageId"],
            "receipt_handle": msg["ReceiptHandle"],
            "task": body.get("task"),
            "kwargs": body.get("kwargs"),
            "sent_at": msg.get("Attributes", {}).get("SentTimestamp"),
        })

    return {"queue": queue, "messages": messages}
```

### 3. POST /rankings/dlq-retry
DLQ メッセージを元キューに再投入。

```python
@router.post("/dlq-retry")
async def retry_dlq_messages(queue: str = "heavy", limit: int = 5):
    """Move DLQ messages back to the main queue for retry."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    sqs = boto3.client("sqs", region_name=settings.aws_region)

    dlq_url = (settings.sqs_heavy_queue_url if queue == "heavy"
               else settings.sqs_light_queue_url) + "-dlq"
    main_url = (settings.sqs_heavy_queue_url if queue == "heavy"
                else settings.sqs_light_queue_url)

    retried = 0
    errors = []

    response = sqs.receive_message(
        QueueUrl=dlq_url,
        MaxNumberOfMessages=min(limit, 10),
        VisibilityTimeout=30,
    )

    for msg in response.get("Messages", []):
        try:
            sqs.send_message(QueueUrl=main_url, MessageBody=msg["Body"])
            sqs.delete_message(QueueUrl=dlq_url, ReceiptHandle=msg["ReceiptHandle"])
            retried += 1
        except Exception as e:
            errors.append(str(e))

    return {"retried": retried, "errors": errors}
```

## 設定追加が必要な場合
`backend/app/core/config.py` の Settings に DLQ URL フィールドがない場合:
- 命名規則（元キューURL + "-dlq"）で導出するか
- `terraform/sqs.tf` の出力を確認して環境変数追加

## 制約
- `rankings.py` 末尾に追加のみ
- DLQ URL の命名は terraform/sqs.tf の定義に合わせる
- `boto3` は既にインストール済み
