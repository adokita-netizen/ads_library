# D-R2-5: Intelligent Crawl Orchestration (D33 Phase 2)
# 優先度: P2 | 前提: D-R2-1 完了 | ブロック: なし

## 目的
優先度キュー + アダプティブレート制限 + サーキットブレーカーで
クロールの安定性と効率を向上させる。

## 対象ファイル (全て Agent D 専有)
- 新規: `backend/app/services/crawling/crawl_orchestrator.py`
- 新規: `backend/app/services/crawling/rate_limiter.py`
- 新規: `backend/app/services/crawling/crawl_stats.py`
- 新規: `backend/app/services/crawling/platform_health.py`

## 実装

### CrawlOrchestrator
```python
# backend/app/services/crawling/crawl_orchestrator.py

import heapq
from datetime import datetime, timedelta
from enum import IntEnum

class CrawlPriority(IntEnum):
    CRITICAL = 0   # HIT候補の再クロール
    HIGH = 1       # 新規ジャンルクロール
    MEDIUM = 2     # 定期更新
    LOW = 3        # バックフィル

class CrawlJob:
    def __init__(self, keyword: str, platform: str, priority: CrawlPriority, limit: int = 20):
        self.keyword = keyword
        self.platform = platform
        self.priority = priority
        self.limit = limit
        self.created_at = datetime.utcnow()
        self.retry_count = 0

    def __lt__(self, other):
        return self.priority < other.priority

class CrawlOrchestrator:
    def __init__(self, session):
        self.session = session
        self.queue: list[CrawlJob] = []
        self.rate_limiter = AdaptiveRateLimiter()
        self.circuit_breaker = CircuitBreaker()

    def enqueue(self, job: CrawlJob):
        heapq.heappush(self.queue, job)

    async def run(self):
        """キューからジョブを取り出して実行"""
        while self.queue:
            job = heapq.heappop(self.queue)

            # サーキットブレーカーチェック
            if self.circuit_breaker.is_open(job.platform):
                logger.warning(f"Circuit open for {job.platform}, skipping {job.keyword}")
                continue

            # レート制限チェック
            await self.rate_limiter.wait(job.platform)

            try:
                result = await self._execute_crawl(job)
                self.circuit_breaker.record_success(job.platform)
                self.rate_limiter.record_success(job.platform)
            except RateLimitError:
                self.rate_limiter.record_rate_limit(job.platform)
                job.retry_count += 1
                if job.retry_count < 3:
                    heapq.heappush(self.queue, job)
            except Exception as e:
                self.circuit_breaker.record_failure(job.platform)
                logger.error(f"Crawl failed: {job.keyword} on {job.platform}: {e}")
```

### AdaptiveRateLimiter (CI-054)
```python
# backend/app/services/crawling/rate_limiter.py

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta

class AdaptiveRateLimiter:
    def __init__(self):
        self.base_delay = 2.0  # seconds
        self.delays: dict[str, float] = defaultdict(lambda: 2.0)
        self.rate_limit_count: dict[str, int] = defaultdict(int)
        self.last_request: dict[str, datetime] = {}

    async def wait(self, platform: str):
        """プラットフォームごとの適応的待機"""
        now = datetime.utcnow()
        last = self.last_request.get(platform)

        if last:
            elapsed = (now - last).total_seconds()
            delay = self.delays[platform]
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

        self.last_request[platform] = datetime.utcnow()

    def record_rate_limit(self, platform: str):
        """429を受けたらディレイを倍増"""
        self.rate_limit_count[platform] += 1
        self.delays[platform] = min(self.delays[platform] * 2, 60.0)
        logger.warning(f"Rate limit on {platform}, delay increased to {self.delays[platform]}s")

    def record_success(self, platform: str):
        """成功したら徐々にディレイを縮小"""
        self.delays[platform] = max(self.base_delay, self.delays[platform] * 0.9)
```

### CircuitBreaker
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.failures: dict[str, int] = defaultdict(int)
        self.open_until: dict[str, datetime] = {}

    def is_open(self, platform: str) -> bool:
        if platform in self.open_until:
            if datetime.utcnow() < self.open_until[platform]:
                return True
            else:
                # Half-open: 1回試す
                del self.open_until[platform]
                self.failures[platform] = 0
        return False

    def record_failure(self, platform: str):
        self.failures[platform] += 1
        if self.failures[platform] >= self.failure_threshold:
            self.open_until[platform] = datetime.utcnow() + timedelta(seconds=self.recovery_timeout)
            logger.error(f"Circuit OPEN for {platform} ({self.recovery_timeout}s)")

    def record_success(self, platform: str):
        self.failures[platform] = 0
        if platform in self.open_until:
            del self.open_until[platform]
```

### PlatformHealth
```python
# backend/app/services/crawling/platform_health.py

class PlatformHealth:
    """各プラットフォームの到達性を定期チェック"""

    HEALTH_URLS = {
        "meta": "https://www.facebook.com/ads/library/",
        "youtube": "https://www.youtube.com/",
        "tiktok": "https://www.tiktok.com/",
        "google": "https://adstransparency.google.com/",
    }

    async def check_all(self) -> dict[str, bool]:
        results = {}
        async with httpx.AsyncClient() as client:
            for platform, url in self.HEALTH_URLS.items():
                try:
                    resp = await client.head(url, timeout=10, follow_redirects=True)
                    results[platform] = resp.status_code < 400
                except:
                    results[platform] = False
        return results
```

## 完了条件
- [ ] CrawlOrchestrator が優先度キューでジョブを管理できる
- [ ] AdaptiveRateLimiter が429発生時にディレイを自動調整する
- [ ] CircuitBreaker が連続失敗時にプラットフォームを一時停止する
- [ ] PlatformHealth が各プラットフォームの到達性を確認できる
- [ ] 429発生率が現状比30%以上削減される (CI-054)
- [ ] status.md に記録
