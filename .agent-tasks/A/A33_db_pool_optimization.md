# A33: DBコネクションプール最適化

## 問題
- Lambda: `pool_size=5` はコールドスタート×同時実行でRDS接続枯渇リスク
- `pool_recycle=1800`（30分）はNAT再起動に対応不十分
- ECS複数タスク × Lambda同時実行 = RDS `max_connections` 超過

## 対象ファイル
- `backend/app/core/database.py`

## 修正

### 1. 環境別プール設定
```python
# database.py のエンジン作成部分
import os
_is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

if _is_lambda:
    pool_kwargs = {"pool_size": 1, "max_overflow": 0, "pool_recycle": 300}
else:
    pool_kwargs = {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_recycle": 300,  # 1800→300に短縮
    }
```

### 2. pool_pre_ping + connect_args タイムアウト
```python
connect_args = {"connect_timeout": 5}  # 接続タイムアウト5秒
```

### 3. SyncSessionLocal のコンテキストマネージャ統一
直接 `SyncSessionLocal()` 呼び出しを `contextmanager` でラップする推奨パターンをdocstringに明記。

## 制約
- `database.py` のエンジン作成部分のみ修正
- 既存のget_db/get_sync_session インターフェースは変更しない
