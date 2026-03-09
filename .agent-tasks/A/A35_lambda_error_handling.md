# A35: lambda_handler エラーハンドリング改善

## 問題
- `_run_cleanup()` の各ステップで部分失敗時にそのまま続行 → 不整合データ残留
- JSONレスポンスに `default=str` で例外スタックトレースが平文で返る → セキュリティリスク
- `_init_database()` のcreate_allが毎コールドスタートで実行 → 不要な遅延

## 対象ファイル
- `backend/lambda_handler.py`

## 修正

### 1. 本番環境でのエラーレスポンスマスク
```python
def _safe_error_response(e: Exception) -> dict:
    """Return sanitized error response (hide stack trace in production)."""
    if os.getenv("APP_ENV") == "production":
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}
    return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
```

### 2. cleanup 各ステップのトランザクション分離
```python
# 各ステップを独立トランザクションで実行
for step_fn in [_step_delete_foreign, _step_deduplicate, _step_fix_creative_type, _step_flag_remaining]:
    try:
        step_result = step_fn(session)
        results["steps"].append(step_result)
    except Exception as e:
        session.rollback()
        results["steps"].append({"name": step_fn.__name__, "error": str(e)})
```

### 3. _init_database の条件付き実行
```python
_DB_INITIALIZED = False

def _init_database():
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    # ... existing code ...
    _DB_INITIALIZED = True
```

## 制約
- `lambda_handler.py` のみ修正
- 既存のアクション分岐構造は変更しない
