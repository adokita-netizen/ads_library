"""Adaptive per-platform crawl rate limiter."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


class AdaptiveRateLimiter:
    """Adjust per-platform delay based on recent outcomes."""

    def __init__(self, base_delay: float = 2.0, max_delay: float = 60.0, min_factor: float = 0.9):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.min_factor = min_factor
        self._delays: dict[str, float] = defaultdict(lambda: base_delay)
        self._rate_limit_count: dict[str, int] = defaultdict(int)
        self._last_request: dict[str, datetime] = {}

    async def wait(self, platform: str) -> None:
        now = datetime.now(timezone.utc)
        last = self._last_request.get(platform)
        if last is not None:
            elapsed = (now - last).total_seconds()
            delay = self._delays[platform]
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        self._last_request[platform] = datetime.now(timezone.utc)

    def record_rate_limit(self, platform: str) -> None:
        self._rate_limit_count[platform] += 1
        self._delays[platform] = min(self._delays[platform] * 2.0, self.max_delay)
        logger.warning(
            "adaptive_rate_limit_increase",
            platform=platform,
            delay_seconds=round(self._delays[platform], 2),
            rate_limit_count=self._rate_limit_count[platform],
        )

    def record_success(self, platform: str) -> None:
        self._delays[platform] = max(self.base_delay, self._delays[platform] * self.min_factor)

    def get_delay(self, platform: str) -> float:
        return self._delays[platform]

