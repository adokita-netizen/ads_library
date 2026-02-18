"""Authentication and security utilities."""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

ALGORITHM = "HS256"

# ==================== Token Blacklist ====================
# In-memory blacklist for revoked tokens. In production, use Redis.
_token_blacklist: dict[str, float] = {}


def add_to_blacklist(token: str, exp: float):
    """Add a token to the blacklist until its expiration."""
    _token_blacklist[token] = exp
    _cleanup_blacklist()


def is_blacklisted(token: str) -> bool:
    """Check if a token has been revoked."""
    return token in _token_blacklist


def _cleanup_blacklist():
    """Remove expired tokens from the blacklist."""
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
