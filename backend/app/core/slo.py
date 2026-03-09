"""SLO (Service Level Objective) definitions and violation detection.

CI-092: Per-endpoint SLO definitions with automatic logging.
"""

from collections import deque
from threading import Lock
import math
import re

import structlog

logger = structlog.get_logger()

# SLO definitions: pattern -> (p95_target_ms, error_rate_threshold)
# Patterns are matched against request path.
ENDPOINT_SLOS: dict[str, tuple[int, float]] = {
    "/health": (200, 0.01),
    "/api/v1/ads$": (500, 0.05),
    "/api/v1/ads/\\d+$": (300, 0.05),
    "/api/v1/ads/health/": (500, 0.05),
    "/api/v1/rankings/dashboard-summary": (1000, 0.05),
    "/api/v1/rankings/score-distribution": (1000, 0.05),
    "/api/v1/rankings/hit-ads": (2000, 0.05),
    "/api/v1/rankings/": (1500, 0.05),
    "/api/v1/media/thumbnail/": (500, 0.10),
    "/api/v1/media/image/": (500, 0.10),
    "/api/v1/media/video/": (2000, 0.10),
    "/api/v1/media/gallery": (1000, 0.05),
    "/api/v1/media/": (1000, 0.05),
    "/api/v1/ai-chat/": (5000, 0.10),
    "/api/": (2000, 0.05),
}

# Default SLO for unmatched endpoints
DEFAULT_SLO = (3000, 0.10)
ROLLING_WINDOW_SIZE = 50

_metrics_lock = Lock()
_rolling_metrics: dict[str, deque[dict]] = {}


def _resolve_pattern(path: str) -> str:
    for pattern in ENDPOINT_SLOS:
        if re.search(pattern, path):
            return pattern
    return "*"


def _record_request(path: str, elapsed_ms: float, status_code: int) -> dict:
    bucket = _resolve_pattern(path)
    sample = {"elapsed_ms": float(elapsed_ms), "status_code": int(status_code)}
    with _metrics_lock:
        window = _rolling_metrics.setdefault(bucket, deque(maxlen=ROLLING_WINDOW_SIZE))
        window.append(sample)
        items = list(window)

    latencies = sorted(item["elapsed_ms"] for item in items)
    if latencies:
        percentile_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
        p95_ms = round(latencies[percentile_index], 1)
    else:
        p95_ms = 0.0
    error_count = sum(1 for item in items if item["status_code"] >= 500)
    error_rate = round(error_count / len(items), 4) if items else 0.0

    return {
        "bucket": bucket,
        "sample_count": len(items),
        "p95_ms": p95_ms,
        "error_rate": error_rate,
    }


def get_slo(path: str) -> tuple[int, float]:
    """Return (p95_target_ms, error_rate_threshold) for a given path."""
    for pattern, slo in ENDPOINT_SLOS.items():
        if re.search(pattern, path):
            return slo
    return DEFAULT_SLO


def check_slo_violation(path: str, elapsed_ms: float, status_code: int) -> None:
    """Log a warning if the response violates SLO targets."""
    target_ms, error_threshold = get_slo(path)
    metrics = _record_request(path, elapsed_ms, status_code)

    if elapsed_ms > target_ms:
        logger.warning(
            "slo_violation",
            path=path,
            elapsed_ms=round(elapsed_ms, 1),
            target_ms=target_ms,
            status_code=status_code,
        )
    if metrics["sample_count"] >= 10 and metrics["p95_ms"] > target_ms:
        logger.warning(
            "slo_p95_violation",
            path=path,
            bucket=metrics["bucket"],
            p95_ms=metrics["p95_ms"],
            target_ms=target_ms,
            sample_count=metrics["sample_count"],
        )
    if metrics["sample_count"] >= 10 and metrics["error_rate"] > error_threshold:
        logger.warning(
            "slo_error_rate_violation",
            path=path,
            bucket=metrics["bucket"],
            error_rate=metrics["error_rate"],
            error_threshold=error_threshold,
            sample_count=metrics["sample_count"],
        )


def get_slo_status(path: str) -> dict:
    """Return current rolling SLO status for a path."""
    target_ms, error_threshold = get_slo(path)
    bucket = _resolve_pattern(path)
    with _metrics_lock:
        items = list(_rolling_metrics.get(bucket, ()))

    latencies = sorted(float(item["elapsed_ms"]) for item in items)
    if latencies:
        percentile_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
        p95_ms = round(latencies[percentile_index], 1)
    else:
        p95_ms = 0.0
    error_count = sum(1 for item in items if int(item["status_code"]) >= 500)
    error_rate = round(error_count / len(items), 4) if items else 0.0

    if not items:
        status = "no_data"
    elif p95_ms > target_ms or error_rate > error_threshold:
        status = "violated"
    else:
        status = "ok"

    return {
        "path": path,
        "bucket": bucket,
        "targets": {
            "p95_ms": target_ms,
            "error_rate": error_threshold,
        },
        "window": {
            "sample_count": len(items),
            "p95_ms": p95_ms,
            "error_rate": error_rate,
            "error_count": error_count,
        },
        "status": status,
    }


def get_all_slo_statuses() -> list[dict]:
    """Return SLO status snapshots for all configured endpoint patterns."""
    return [get_slo_status(pattern) for pattern in ENDPOINT_SLOS]


def reset_slo_metrics() -> None:
    """Clear rolling SLO metrics. Used by tests."""
    with _metrics_lock:
        _rolling_metrics.clear()
