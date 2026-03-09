# A-R2-4: DB接続リトライ統一 (CI-001)
# 優先度: P0 | 前提: なし | ブロック: なし (並行可)

## 目的
API / Worker / Lambda で DB 接続失敗時の再試行ポリシーを統一する。

## 対象ファイル
- `backend/app/core/database.py` (修正)

## 現状確認
database.py には既に pool_pre_ping=True がある（A33で実装済み）。
しかし接続失敗時の明示的なリトライロジックが統一されていない。

## 実装

### database.py にリトライヘルパーを追加
```python
import time
import logging

logger = logging.getLogger(__name__)

def get_session_with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """指数バックオフ付きDBセッション取得"""
    last_error = None
    for attempt in range(max_retries):
        try:
            session = SyncSessionLocal()
            # 接続テスト
            session.execute(text("SELECT 1"))
            return session
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                logger.warning(
                    "DB connection failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, max_retries, delay,
                    extra={"error": str(e), "attempt": attempt + 1}
                )
                time.sleep(delay)
            else:
                logger.error(
                    "DB connection failed after %d attempts",
                    max_retries,
                    extra={"error": str(e), "attempts": max_retries},
                    exc_info=True
                )
    raise last_error
```

### 適用箇所
1. `lambda_handler.py` の `_init_database()` — 既にAgent A の領域
2. `backend/app/tasks/metrics_tasks.py` — 各タスク冒頭のセッション取得
3. API の dependency injection (`get_db`) — database.py 内

### get_db 修正
```python
def get_db():
    db = get_session_with_retry()
    try:
        yield db
    finally:
        db.close()
```

## 完了条件
- [x] get_session_with_retry() が database.py に追加されている
- [x] get_db() がリトライ付きセッション取得を使っている
- [x] lambda_handler.py がリトライ付きで初期化している
- [x] 3回失敗時に構造化ログが出力される
- [x] status.md に記録
