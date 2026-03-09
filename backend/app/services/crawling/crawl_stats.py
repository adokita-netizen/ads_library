"""Simple in-memory crawl orchestration statistics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class CrawlStats:
    executed: int = 0
    success: int = 0
    failed: int = 0
    rate_limited: int = 0
    skipped_circuit_open: int = 0
    retried: int = 0
    by_platform: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))

    def record_executed(self, platform: str) -> None:
        self.executed += 1
        self.by_platform[platform]["executed"] += 1

    def record_success(self, platform: str) -> None:
        self.success += 1
        self.by_platform[platform]["success"] += 1

    def record_failed(self, platform: str) -> None:
        self.failed += 1
        self.by_platform[platform]["failed"] += 1

    def record_rate_limited(self, platform: str) -> None:
        self.rate_limited += 1
        self.by_platform[platform]["rate_limited"] += 1

    def record_circuit_skip(self, platform: str) -> None:
        self.skipped_circuit_open += 1
        self.by_platform[platform]["circuit_skipped"] += 1

    def record_retry(self, platform: str) -> None:
        self.retried += 1
        self.by_platform[platform]["retried"] += 1

    def snapshot(self) -> dict:
        return {
            "executed": self.executed,
            "success": self.success,
            "failed": self.failed,
            "rate_limited": self.rate_limited,
            "skipped_circuit_open": self.skipped_circuit_open,
            "retried": self.retried,
            "by_platform": {k: dict(v) for k, v in self.by_platform.items()},
        }

