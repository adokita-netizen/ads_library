"""Shared FastAPI dependencies — authentication, authorization, sessions."""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SyncSessionLocal, get_async_session
from app.core.security import verify_token
from app.models.user import User

# Bearer token scheme (appears in Swagger UI)
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Async version (for endpoints that use AsyncSession)
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_async_session),
) -> User:
    """Extract and validate JWT → return the authenticated User row."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="認証が必要です")

    payload = verify_token(credentials.credentials, token_type="access")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="トークンが無効または期限切れです")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="トークンにユーザー情報がありません")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ユーザーが見つからないか無効です")

    return user


# ---------------------------------------------------------------------------
# Sync version (for endpoints that use SyncSessionLocal directly)
# ---------------------------------------------------------------------------

def get_current_user_sync(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Lightweight sync auth — returns {"user_id": int, "email": str}."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="認証が必要です")

    payload = verify_token(credentials.credentials, token_type="access")
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="トークンが無効または期限切れです")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="トークンにユーザー情報がありません")

    return {"user_id": int(user_id), "email": payload.get("email", "")}


# ---------------------------------------------------------------------------
# Optional auth (returns None when no token provided)
# ---------------------------------------------------------------------------

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_async_session),
) -> Optional[User]:
    """Return User if valid token present, None otherwise."""
    if credentials is None:
        return None
    payload = verify_token(credentials.credentials, token_type="access")
    if payload is None:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == int(user_id)))
    return result.scalar_one_or_none()
