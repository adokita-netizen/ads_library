"""Priority-queue based crawl orchestration with resilience controls."""

from __future__ import annotations

import heapq
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Awaitable, Callable, Optional

import structlog

from app.services.crawling.crawl_stats import CrawlStats
from app.services.crawling.rate_limiter import AdaptiveRateLimiter

logger = structlog.get_logger()


class CrawlPriority(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class RateLimitError(Exception):
    """Raised by crawl execute callback when 429-like condition occurs."""


@dataclass(order=True)
class CrawlJob:
    sort_key: tuple[int, datetime] = field(init=False, repr=False)
    keyword: str = field(compare=False)
    platform: str = field(compare=False)
    priority: CrawlPriority = field(compare=False, default=CrawlPriority.MEDIUM)
    limit: int = field(compare=False, default=20)
    created_at: datetime = field(compare=False, default_factory=lambda: datetime.now(timezone.utc))
    retry_count: int = field(compare=False, default=0)
    metadata: dict = field(compare=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.sort_key = (int(self.priority), self.created_at)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout_seconds: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._failures: dict[str, int] = defaultdict(int)
        self._open_until: dict[str, datetime] = {}

    def is_open(self, platform: str) -> bool:
        open_until = self._open_until.get(platform)
        if not open_until:
            return False
        if datetime.now(timezone.utc) < open_until:
            return True
        self._open_until.pop(platform, None)
        self._failures[platform] = 0
        return False

    def record_failure(self, platform: str) -> None:
        self._failures[platform] += 1
        if self._failures[platform] >= self.failure_threshold:
            self._open_until[platform] = datetime.now(timezone.utc) + timedelta(
                seconds=self.recovery_timeout_seconds
            )
            logger.error(
                "crawl_circuit_open",
                platform=platform,
                recovery_timeout_seconds=self.recovery_timeout_seconds,
                failures=self._failures[platform],
            )

    def record_success(self, platform: str) -> None:
        self._failures[platform] = 0
        self._open_until.pop(platform, None)


ExecuteCrawlFn = Callable[[CrawlJob], Awaitable[dict]]


class CrawlOrchestrator:
    """Run prioritized crawl jobs with adaptive wait + circuit breaker."""

    def __init__(
        self,
        execute_crawl: ExecuteCrawlFn,
        rate_limiter: Optional[AdaptiveRateLimiter] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        max_retries: int = 3,
    ):
        self._execute_crawl = execute_crawl
        self.queue: list[CrawlJob] = []
        self.rate_limiter = rate_limiter or AdaptiveRateLimiter()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.max_retries = max_retries
        self.stats = CrawlStats()

    def enqueue(self, job: CrawlJob) -> None:
        heapq.heappush(self.queue, job)

    def enqueue_many(self, jobs: list[CrawlJob]) -> None:
        for job in jobs:
            self.enqueue(job)

    async def run(self) -> dict:
        while self.queue:
            job = heapq.heappop(self.queue)
            platform = job.platform

            if self.circuit_breaker.is_open(platform):
                self.stats.record_circuit_skip(platform)
                logger.warning("crawl_skipped_circuit_open", platform=platform, keyword=job.keyword)
                continue

            await self.rate_limiter.wait(platform)
            self.stats.record_executed(platform)

            try:
                result = await self._execute_crawl(job)
                self.circuit_breaker.record_success(platform)
                self.rate_limiter.record_success(platform)
                self.stats.record_success(platform)
                logger.info(
                    "crawl_job_succeeded",
                    platform=platform,
                    keyword=job.keyword,
                    retry_count=job.retry_count,
                    result=result,
                )
            except RateLimitError:
                self.stats.record_rate_limited(platform)
                self.rate_limiter.record_rate_limit(platform)
                job.retry_count += 1
                if job.retry_count < self.max_retries:
                    self.stats.record_retry(platform)
                    self.enqueue(job)
                else:
                    self.stats.record_failed(platform)
                    logger.warning(
                        "crawl_job_failed_after_rate_limit_retries",
                        platform=platform,
                        keyword=job.keyword,
                        retry_count=job.retry_count,
                    )
            except Exception as exc:
                self.circuit_breaker.record_failure(platform)
                self.stats.record_failed(platform)
                logger.error(
                    "crawl_job_failed",
                    platform=platform,
                    keyword=job.keyword,
                    retry_count=job.retry_count,
                    error=str(exc),
                )

        return self.stats.snapshot()

