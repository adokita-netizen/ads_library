# B33: dispatcher.py MessageGroupId バグ修正

## 目的
SQS 標準キュー（非 FIFO）への送信時に `MessageGroupId=None` を渡してエラーになるバグを修正。

## 対象ファイル
- `backend/app/tasks/dispatcher.py` （L109〜L113 のみ）

## バグの詳細

### 現在のコード（L109-113）
```python
response = sqs.send_message(
    QueueUrl=queue_url,
    MessageBody=message_body,
    MessageGroupId=task_name if queue_url.endswith(".fifo") else None,
)
```

### 問題
- SQS 標準キューは `MessageGroupId` パラメータ自体を受け付けない
- `None` を渡しても AWS が `InvalidParameterValue` エラーを返す
- FIFO キューでのみこのパラメータが有効

## 修正方法

L109〜L113 を以下に置換：

```python
send_message_params = {
    "QueueUrl": queue_url,
    "MessageBody": message_body,
}
if queue_url.endswith(".fifo"):
    send_message_params["MessageGroupId"] = task_name
    send_message_params["MessageDeduplicationId"] = message_id

response = sqs.send_message(**send_message_params)
```

## 変更点まとめ
1. `send_message` の引数を辞書で組み立てる
2. FIFO キューの場合のみ `MessageGroupId` と `MessageDeduplicationId` を辞書に追加
3. 標準キューでは `MessageGroupId` パラメータ自体が送信されない

## 制約
- `_dispatch_sqs` 関数の該当箇所（5行）のみ修正
- 他の関数・インポート・定数は一切変更しない
