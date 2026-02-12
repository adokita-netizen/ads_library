"""Tests for authentication dependencies and security utilities."""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_password,
    get_password_hash,
)


# ==================== Token Creation & Verification ====================


class TestTokenCreation:
    """Test JWT token creation and verification."""

    def test_create_access_token(self):
        token = create_access_token({"sub": "1", "email": "test@example.com"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_custom_expiry(self):
        token = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(hours=1)
        )
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "1"

    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "1"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_access_token(self):
        token = create_access_token({"sub": "42", "email": "user@test.com"})
        payload = verify_token(token, token_type="access")
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["email"] == "user@test.com"
        assert payload["type"] == "access"

    def test_verify_valid_refresh_token(self):
        token = create_refresh_token({"sub": "42"})
        payload = verify_token(token, token_type="refresh")
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    def test_verify_wrong_token_type(self):
        """Access token should fail verification as refresh and vice versa."""
        access = create_access_token({"sub": "1"})
        assert verify_token(access, token_type="refresh") is None

        refresh = create_refresh_token({"sub": "1"})
        assert verify_token(refresh, token_type="access") is None

    def test_verify_invalid_token(self):
        assert verify_token("invalid.jwt.token") is None

    def test_verify_empty_token(self):
        assert verify_token("") is None

    def test_verify_expired_token(self):
        token = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(seconds=-1)
        )
        assert verify_token(token) is None


# ==================== Password Hashing ====================


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password(self):
        hashed = get_password_hash("mysecretpass")
        assert isinstance(hashed, str)
        assert hashed != "mysecretpass"

    def test_verify_correct_password(self):
        hashed = get_password_hash("correctpass")
        assert verify_password("correctpass", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("correctpass")
        assert verify_password("wrongpass", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Bcrypt should produce different hashes each time (salted)."""
        hash1 = get_password_hash("samepass")
        hash2 = get_password_hash("samepass")
        assert hash1 != hash2
        # But both should verify
        assert verify_password("samepass", hash1)
        assert verify_password("samepass", hash2)


# ==================== Auth Dependency (get_current_user_sync) ====================


class TestGetCurrentUserSync:
    """Test the sync auth dependency."""

    def test_sync_auth_no_credentials(self):
        from app.api.deps import get_current_user_sync
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=None)
        assert exc_info.value.status_code == 401
        assert "認証が必要です" in exc_info.value.detail

    def test_sync_auth_invalid_token(self):
        from app.api.deps import get_current_user_sync
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=creds)
        assert exc_info.value.status_code == 401
        assert "トークンが無効" in exc_info.value.detail

    def test_sync_auth_valid_token(self):
        from app.api.deps import get_current_user_sync
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token({"sub": "99", "email": "admin@test.com"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = get_current_user_sync(credentials=creds)
        assert result["user_id"] == 99
        assert result["email"] == "admin@test.com"

    def test_sync_auth_refresh_token_rejected(self):
        """Refresh tokens should not work for API auth."""
        from app.api.deps import get_current_user_sync
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_refresh_token({"sub": "1"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=creds)
        assert exc_info.value.status_code == 401

    def test_sync_auth_token_without_sub(self):
        from app.api.deps import get_current_user_sync
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token({"email": "nosub@test.com"})
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_sync(credentials=creds)
        assert exc_info.value.status_code == 401
        assert "ユーザー情報がありません" in exc_info.value.detail
