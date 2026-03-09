# D33: インテリジェント・クロール・オーケストレーション

## 概要
クロールジョブの優先度制御、適応型レート制限、障害検知 & サーキットブレーカーを実装し、
安定的に大量の広告データを収集できるクロール基盤を構築する。

## 背景
現在58件の広告しかなく、データ量がプロダクト価値のボトルネック。
単純にクロール頻度を上げるとプラットフォームからブロックされるリスクがある。
「賢く・安定的に・大量に」データを収集する仕組みが必要。

## タスク

### Task 1: クロール優先度キュー
```python
# backend/app/services/crawling/crawl_orchestrator.py (新規)

class CrawlOrchestrator:
    """クロールジョブの優先度を管理し、最適な順序で実行する"""

    PRIORITY_WEIGHTS = {
        "new_keyword": 100,        # 新しいキーワードの初回クロール
        "trending_genre": 80,      # トレンドジャンルの更新
        "competitor_monitor": 70,  # 競合広告主の監視
        "scheduled_refresh": 50,   # 定期更新
        "backfill": 30,            # 欠損データの補完
        "low_priority": 10,        # 低優先度の網羅的クロール
    }

    def schedule_crawl(self, keyword: str, platform: str, priority_type: str,
                       user_id: int = None) -> CrawlJob:
        """優先度付きでクロールジョブを作成"""

    def get_next_jobs(self, limit: int = 5) -> list[CrawlJob]:
        """優先度順に次に実行するジョブを取得"""
        # priority_score DESC, created_at ASC

    def rebalance_queue(self):
        """
        キュー内のジョブ優先度を再計算:
        - 長時間待機しているジョブの優先度を引き上げ（飢餓防止）
        - 同一プラットフォームのジョブが連続しないよう分散
        """
```

### Task 2: 適応型レート制限
```python
# backend/app/services/crawling/rate_limiter.py (新規)

class AdaptiveRateLimiter:
    """プラットフォームごとの応答を監視し、レートを自動調整する"""

    def __init__(self):
        self.platform_states = {}  # {platform: PlatformState}

    def can_request(self, platform: str) -> bool:
        """リクエスト可能かチェック"""

    def record_response(self, platform: str, status_code: int, response_time: float):
        """レスポンスを記録し、レートを調整する"""
        state = self.platform_states[platform]

        if status_code == 429:
            state.increase_delay(factor=2.0)   # 倍にする
            state.consecutive_429 += 1
        elif status_code == 200 and state.current_delay > state.base_delay:
            state.decrease_delay(factor=0.9)    # 徐々に戻す
        elif response_time > 10.0:
            state.increase_delay(factor=1.5)   # レスポンス遅い = 負荷高い

class PlatformState:
    platform: str
    base_delay: float = 2.0          # 秒（デフォルト）
    current_delay: float = 2.0
    max_delay: float = 60.0
    consecutive_429: int = 0
    circuit_open: bool = False        # サーキットブレーカー
    circuit_open_until: datetime = None
    total_requests: int = 0
    total_failures: int = 0
```

### Task 3: サーキットブレーカー
```python
# rate_limiter.py に追加

class CircuitBreaker:
    """
    連続失敗が閾値を超えたらプラットフォームへのリクエストを一時停止する。

    CLOSED → OPEN: 連続5回の429/5xx
    OPEN → HALF-OPEN: 5分後に1リクエストだけ許可
    HALF-OPEN → CLOSED: 成功したら復帰
    HALF-OPEN → OPEN: 失敗したら再度5分停止
    """

    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # 秒
        self.state = "closed"  # closed, open, half-open

    def record_success(self):
        if self.state == "half-open":
            self.state = "closed"
        self.consecutive_failures = 0

    def record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.state = "open"
            self.open_until = datetime.utcnow() + timedelta(seconds=self.recovery_timeout)

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if datetime.utcnow() > self.open_until:
                self.state = "half-open"
                return True
            return False
        return True  # half-open: 1リクエスト許可
```

### Task 4: クロール統計ダッシュボードデータ
```python
# backend/app/services/crawling/crawl_stats.py (新規)

class CrawlStatsService:
    """クロールのパフォーマンス統計を提供する"""

    def get_stats(self, session, days=7) -> dict:
        return {
            "total_jobs": ...,
            "successful": ...,
            "failed": ...,
            "ads_collected": ...,
            "by_platform": {
                "meta": {"jobs": 10, "ads": 120, "avg_time": 45},
                "youtube": {"jobs": 5, "ads": 80, "avg_time": 30},
            },
            "rate_limit_hits": ...,
            "circuit_breaker_trips": ...,
            "queue_depth": ...,
            "avg_job_duration": ...,
        }
```

### Task 5: crawler_manager.py に統合
- 既存の `CrawlerManager` に `CrawlOrchestrator` と `AdaptiveRateLimiter` を統合
- クロール実行前に `rate_limiter.can_request()` をチェック
- クロール完了後に `rate_limiter.record_response()` を呼ぶ
- 失敗パターンに基づきサーキットブレーカーを作動

## 完了条件
- [ ] 優先度付きクロールキューが動作する
- [ ] プラットフォームごとの適応型レート制限が動作する
- [ ] サーキットブレーカーが連続失敗で作動する
- [ ] クロール統計データが取得できる
- [ ] 既存の crawler_manager.py に統合済み

## 触っていいファイル
- backend/app/services/crawling/crawl_orchestrator.py (新規)
- backend/app/services/crawling/rate_limiter.py (新規)
- backend/app/services/crawling/crawl_stats.py (新規)
- backend/app/services/crawling/crawler_manager.py (統合)
- backend/app/tasks/crawl_tasks.py (呼び出し修正)

## 注意
- 既存のクローラー（meta_crawler.py等）のインターフェースは変更しない
- crawler_manager.py の修正は最小限に（ラッパーとして使う）
