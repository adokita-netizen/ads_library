# A36: sqs_ecs_trigger 部分失敗処理改善

## 問題
- ECS RunTask failures があっても handler は成功で返る → SQSがメッセージ削除 → タスク消失
- 特定エラー (InvalidParameter等) は即DLQに送るべきだがリトライされる

## 対象ファイル
- `backend/sqs_ecs_trigger.py`

## 修正

### 1. 失敗時に例外を raise して SQS リトライを誘発
```python
def handler(event, context):
    results = []
    failures = []

    for record in event.get("Records", []):
        # ... existing logic ...
        if not task_arns:
            failures.append(record["messageId"])

    # 部分失敗時は batchItemFailures を返す（SQS partial batch response）
    if failures:
        return {
            "batchItemFailures": [
                {"itemIdentifier": mid} for mid in failures
            ]
        }

    return {"results": results}
```

### 2. Lambda イベントソースマッピング設定
```hcl
# terraform/lambda.tf に追加
resource "aws_lambda_event_source_mapping" "heavy_queue" {
  # ...
  function_response_types = ["ReportBatchItemFailures"]
}
```

## 制約
- `sqs_ecs_trigger.py` + `terraform/lambda.tf` のみ修正
