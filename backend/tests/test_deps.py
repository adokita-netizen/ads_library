"""Tests for FastAPI dependency functions (auth, session management)."""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import create_access_token, create_refresh_token
from app.api.deps import get_current_user_sync


class TestGetCurrentUserSync:
    """Test the synchronous auth dependency."""

    def test_no_credentials_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=None)
        assert exc_info.value.status_code == 401
        assert "認証が必要です" in exc_info.value.detail

    def test_invalid_token_raises_401(self):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=creds)
        assert exc_info.value.status_code == 401
        assert "トークンが無効" in exc_info.value.detail

    def test_valid_access_token(self):
        token = create_access_token({"sub": "42", "email": "user@test.com"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = get_current_user_sync(credentials=creds)
        assert result["user_id"] == 42
        assert result["email"] == "user@test.com"

    def test_refresh_token_rejected(self):
        """Refresh tokens must not work for API authentication."""
        token = create_refresh_token({"sub": "1"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=creds)
        assert exc_info.value.status_code == 401

    def test_token_without_sub_raises_401(self):
        token = create_access_token({"email": "nosub@test.com"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=creds)
        assert exc_info.value.status_code == 401
        assert "ユーザー情報がありません" in exc_info.value.detail

    def test_expired_token_rejected(self):
        token = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(seconds=-10)
        )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=creds)
        assert exc_info.value.status_code == 401

    def test_email_missing_returns_empty_string(self):
        """When email is not in the token, default to empty string."""
        token = create_access_token({"sub": "5"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = get_current_user_sync(credentials=creds)
        assert result["user_id"] == 5
        assert result["email"] == ""
