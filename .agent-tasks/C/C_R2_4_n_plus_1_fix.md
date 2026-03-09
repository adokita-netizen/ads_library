# C-R2-4: N+1 Query Fix (CI-013)
# 優先度: P0 | 前提: なし | ブロック: なし (並行可)

## 目的
ランキングAPI の代表クエリで N+1 問題を検出し、解消する。

## 対象ファイル
- `backend/app/api/endpoints/rankings.py` (修正)
- `backend/app/services/ranking/ranking_service.py` (修正)

## 手順

### Step 1: SQL計測ログの追加
```python
# rankings.py の冒頭に計測ヘルパー
import time
import logging
logger = logging.getLogger(__name__)

class QueryCounter:
    def __init__(self):
        self.count = 0
        self.total_time = 0

    def __enter__(self):
        from sqlalchemy import event
        @event.listens_for(db.bind, "before_cursor_execute")
        def before(conn, cursor, statement, parameters, context, executemany):
            context._query_start = time.time()
            self.count += 1

        @event.listens_for(db.bind, "after_cursor_execute")
        def after(conn, cursor, statement, parameters, context, executemany):
            self.total_time += time.time() - context._query_start

        return self

    def __exit__(self, *args):
        logger.info(f"Queries: {self.count}, Total time: {self.total_time:.3f}s")
```

### Step 2: 主要エンドポイントの SQL 回数計測
```
計測対象:
1. GET /pro-ranking?page=1&per_page=20
2. GET /hit-ads?genre=all&limit=20
3. GET /dashboard-summary
4. GET /genre-comparison
5. GET /score-distribution
```

### Step 3: N+1 解消パターン
```python
# Before (N+1):
ads = session.query(Ad).limit(20).all()
for ad in ads:
    metrics = session.query(AdDailyMetrics).filter(...).first()  # N回

# After (JOIN):
from sqlalchemy.orm import joinedload, selectinload

ads = session.query(Ad).options(
    selectinload(Ad.daily_metrics),
    selectinload(Ad.rankings),
).limit(20).all()

# または subquery で一括取得:
from sqlalchemy import func
latest_metrics = session.query(
    AdDailyMetrics.ad_id,
    func.max(AdDailyMetrics.date).label('latest_date')
).group_by(AdDailyMetrics.ad_id).subquery()

ads_with_metrics = session.query(Ad, AdDailyMetrics).join(
    latest_metrics,
    Ad.id == latest_metrics.c.ad_id
).join(
    AdDailyMetrics,
    (AdDailyMetrics.ad_id == latest_metrics.c.ad_id) &
    (AdDailyMetrics.date == latest_metrics.c.latest_date)
).limit(20).all()
```

### Step 4: EXPLAIN ANALYZE で確認
```python
# 修正後に各クエリの実行計画を確認
result = session.execute(text("EXPLAIN ANALYZE " + query_str))
for row in result:
    print(row[0])
```

## 完了条件
- [x] 主要5エンドポイントの SQL 回数を計測し、Before を記録
- [x] N+1 が検出されたクエリを joinedload/selectinload で修正
- [x] 修正後の SQL 回数を計測し、30%以上削減を確認
- [x] Before/After の比較を status.md に記録
