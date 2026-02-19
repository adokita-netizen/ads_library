"""Authentication and security utilities."""

import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"

# ==================== Token Blacklist (Redis + in-memory fallback) ====================

_token_blacklist: dict[str, float] = {}
_redis_client = None
_redis_unavailable = False
_BLACKLIST_PREFIX = "token_blacklist:"


def _get_redis():
    """Get Redis client for token blacklist (lazy init)."""
    global _redis_client, _redis_unavailable
    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        _redis_client = redis.from_url(settings.redis_url, socket_timeout=2, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception:
        _redis_unavailable = True
        return None


def _token_hash(token: str) -> str:
    """Hash token for Redis key (don't store raw JWTs)."""
    return hashlib.sha256(token.encode()).hexdigest()[:32]


def add_to_blacklist(token: str, exp: float):
    """Add a token to the blacklist until its expiration."""
    ttl = max(1, int(exp - time.time()))
    r = _get_redis()
    if r is not None:
        try:
            r.setex(f"{_BLACKLIST_PREFIX}{_token_hash(token)}", ttl, "1")
            return
        except Exception:
            pass
    # Fallback to in-memory
    _token_blacklist[token] = exp
    _cleanup_blacklist()


def is_blacklisted(token: str) -> bool:
    """Check if a token has been revoked."""
    r = _get_redis()
    if r is not None:
        try:
            return r.exists(f"{_BLACKLIST_PREFIX}{_token_hash(token)}") > 0
        except Exception:
            pass
    return token in _token_blacklist


def _cleanup_blacklist():
    """Remove expired tokens from the in-memory blacklist."""
    now = time.time()
    expired = [t for t, exp in _token_blacklist.items() if exp < now]
    for t in expired:
        _token_blacklist.pop(t, None)


# ==================== Token Operations ====================


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    try:
        if is_blacklisted(token):
            return None
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except JWTError:
        return None


# ==================== Password Operations ====================


def _encode_password(password: str) -> bytes:
    """Encode password to bytes, truncating to 72 bytes (bcrypt limit)."""
    return password.encode("utf-8")[:72]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        _encode_password(plain_password), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        _encode_password(password), bcrypt.gensalt()
    ).decode("utf-8")
