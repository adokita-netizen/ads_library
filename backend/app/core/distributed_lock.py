"""CI-129: Redis distributed lock for batch job exclusion.

Provides a distributed lock that works across multiple processes, Lambda
invocations, and ECS containers.  Falls back to process-level locks (from
database.py) when Redis is unavailable.

Usage:
    from app.core.distributed_lock import distributed_lock, distributed_job_locked

    # Context manager
    with distributed_lock("my_job", ttl=600):
        do_work()

    # Decorator
    @distributed_job_locked("my_job", ttl=600)
    def run_batch():
        ...
"""

import logging
import time
import uuid
from contextlib import contextmanager
from functools import wraps

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 600  # 10 minutes
_LOCK_PREFIX = "vaap:lock:"

# Lazy-initialized Redis client
_redis_client = None
_redis_available: bool | None = None  # None = not yet checked


def _get_redis():
    """Lazy-initialize Redis client. Returns None if unavailable."""
    global _redis_client, _redis_available

    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        settings = get_settings()
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client.ping()
        _redis_available = True
        logger.info("distributed_lock: Redis connected (%s)", settings.redis_url.split("@")[-1] if "@" in settings.redis_url else settings.redis_url)
        return _redis_client
    except Exception as e:
        _redis_available = False
        logger.warning("distributed_lock: Redis unavailable, falling back to process-level locks: %s", e)
        return None


def acquire_distributed_lock(job_name: str, ttl: int = _DEFAULT_TTL) -> str | None:
    """Acquire a distributed lock via Redis SET NX EX.

    Returns a unique token (str) on success, None if already locked.
    The token is required for safe release (only the owner can unlock).
    """
    r = _get_redis()
    if r is None:
        # Fallback: use process-level lock from database.py
        from app.core.database import acquire_job_lock
        ok = acquire_job_lock(job_name, ttl=ttl)
        return "local" if ok else None

    key = f"{_LOCK_PREFIX}{job_name}"
    token = str(uuid.uuid4())

    acquired = r.set(key, token, nx=True, ex=ttl)
    if acquired:
        logger.info("distributed_lock_acquired job=%s ttl=%d", job_name, ttl)
        return token

    # Lock held by someone else — check remaining TTL for logging
    remaining = r.ttl(key)
    logger.warning("distributed_lock_denied job=%s remaining_ttl=%s", job_name, remaining)
    return None


def release_distributed_lock(job_name: str, token: str):
    """Release a distributed lock. Only the owner (matching token) can release.

    Uses a Lua script for atomic check-and-delete to prevent race conditions.
    """
    if token == "local":
        from app.core.database import release_job_lock
        release_job_lock(job_name)
        return

    r = _get_redis()
    if r is None:
        return

    key = f"{_LOCK_PREFIX}{job_name}"
    # Atomic: only delete if the value matches our token
    lua = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    result = r.eval(lua, 1, key, token)
    if result:
        logger.info("distributed_lock_released job=%s", job_name)
    else:
        logger.warning("distributed_lock_release_mismatch job=%s (already expired or stolen)", job_name)


def extend_lock(job_name: str, token: str, extra_ttl: int = _DEFAULT_TTL) -> bool:
    """Extend the TTL of a held lock. Returns True if extended."""
    if token == "local":
        return True  # Process locks don't expire in the same way

    r = _get_redis()
    if r is None:
        return False

    key = f"{_LOCK_PREFIX}{job_name}"
    lua = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("expire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """
    result = r.eval(lua, 1, key, token, str(extra_ttl))
    return bool(result)


@contextmanager
def distributed_lock(job_name: str, ttl: int = _DEFAULT_TTL):
    """Context manager for distributed lock.

    Raises RuntimeError if lock cannot be acquired.

    Usage:
        with distributed_lock("aggregate_metrics", ttl=600):
            run_aggregation()
    """
    token = acquire_distributed_lock(job_name, ttl=ttl)
    if token is None:
        raise RuntimeError(f"Could not acquire distributed lock: {job_name}")
    try:
        yield token
    finally:
        release_distributed_lock(job_name, token)


def distributed_job_locked(job_name: str, ttl: int = _DEFAULT_TTL):
    """Decorator: run function under distributed lock.

    If the lock cannot be acquired, returns
    {"status": "skipped", "reason": "already_running"} without raising.

    Usage:
        @distributed_job_locked("my_batch_job", ttl=600)
        def run_batch():
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = acquire_distributed_lock(job_name, ttl=ttl)
            if token is None:
                logger.warning("distributed_job_locked_skipped job=%s fn=%s", job_name, fn.__name__)
                return {"status": "skipped", "reason": "already_running"}
            try:
                return fn(*args, **kwargs)
            finally:
                release_distributed_lock(job_name, token)
        return wrapper
    return decorator


def get_lock_status(job_name: str) -> dict:
    """Check if a job is currently locked and get remaining TTL."""
    r = _get_redis()
    if r is None:
        from app.core.database import _job_locks
        is_locked = job_name in _job_locks
        return {"backend": "local", "locked": is_locked}

    key = f"{_LOCK_PREFIX}{job_name}"
    remaining = r.ttl(key)
    return {
        "backend": "redis",
        "locked": remaining > 0,
        "remaining_ttl": max(remaining, 0),
    }
