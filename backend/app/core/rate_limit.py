"""Shared in-memory API rate limiting helpers."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def parse_rate_limit_policy(policy: str, *, default_requests: int, default_window_seconds: int) -> tuple[int, int]:
    raw = str(policy or "").strip().lower()
    if not raw:
        return default_requests, default_window_seconds

    try:
        count_text, unit = raw.split("/", 1)
        count = max(1, int(count_text.strip()))
    except Exception:
        return default_requests, default_window_seconds

    unit = unit.strip()
    if unit in {"minute", "min", "m"}:
        return count, 60
    if unit in {"hour", "h"}:
        return count, 3600
    if unit in {"second", "sec", "s"}:
        return count, 1
    return default_requests, default_window_seconds


def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int = 60,
    *,
    detail: str = "リクエストが多すぎます。しばらくしてから再試行してください。",
) -> None:
    """Simple in-memory rate limiter. Raises 429 if limit exceeded."""
    now = time.monotonic()
    timestamps = _rate_limit_store[key]
    _rate_limit_store[key] = [t for t in timestamps if now - t < window_seconds]
    if len(_rate_limit_store[key]) >= max_requests:
        retry_after = max(1, int(window_seconds - (now - _rate_limit_store[key][0])))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Window": str(window_seconds),
            },
        )
    _rate_limit_store[key].append(now)


def check_request_rate_limit(
    request: Request,
    scope: str,
    policy: str,
    *,
    default_requests: int,
    default_window_seconds: int,
    detail: str = "リクエストが多すぎます。しばらくしてから再試行してください。",
) -> tuple[int, int]:
    max_requests, window_seconds = parse_rate_limit_policy(
        policy,
        default_requests=default_requests,
        default_window_seconds=default_window_seconds,
    )
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(
        f"{scope}:{client_ip}",
        max_requests=max_requests,
        window_seconds=window_seconds,
        detail=detail,
    )
    return max_requests, window_seconds
