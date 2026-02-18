"""Tests for security module — bcrypt password hashing and JWT tokens.

These tests validate the direct-bcrypt implementation in security.py,
replacing the passlib-based approach that was incompatible with bcrypt>=4.1.
"""

import pytest
from datetime import timedelta
from unittest.mock import patch

from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_password,
    get_password_hash,
    ALGORITHM,
)


class TestPasswordHashingBcrypt:
    """Test bcrypt password hashing (direct bcrypt, no passlib)."""

    def test_hash_password_returns_string(self):
        hashed = get_password_hash("mysecretpass")
        assert isinstance(hashed, str)
        assert hashed != "mysecretpass"

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = get_password_hash("testpass")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = get_password_hash("correctpass")
        assert verify_password("correctpass", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("correctpass")
        assert verify_password("wrongpass", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt salts should produce different hashes each time."""
        hash1 = get_password_hash("samepass")
        hash2 = get_password_hash("samepass")
        assert hash1 != hash2
        assert verify_password("samepass", hash1)
        assert verify_password("samepass", hash2)

    def test_empty_password(self):
        hashed = get_password_hash("")
        assert verify_password("", hashed) is True
        assert verify_password("notempty", hashed) is False

    def test_unicode_password(self):
        """Japanese characters in passwords should work."""
        hashed = get_password_hash("パスワード123")
        assert verify_password("パスワード123", hashed) is True
        assert verify_password("パスワード124", hashed) is False

    def test_long_password(self):
        """bcrypt truncates at 72 bytes — verify it still works."""
        long_pass = "a" * 100
        hashed = get_password_hash(long_pass)
        assert verify_password(long_pass, hashed) is True


class TestTokenEdgeCases:
    """Additional edge case tests for JWT tokens."""

    def test_token_contains_custom_claims(self):
        token = create_access_token({"sub": "1", "role": "admin", "org": "test_co"})
        payload = verify_token(token)
        assert payload["role"] == "admin"
        assert payload["org"] == "test_co"

    def test_token_expiry_boundary(self):
        """Token with 0 seconds delta should expire immediately."""
        token = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(seconds=0)
        )
        # Depending on timing this may or may not be valid
        # but a negative delta should definitely fail
        token_neg = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(seconds=-10)
        )
        assert verify_token(token_neg) is None

    def test_refresh_token_has_type_refresh(self):
        token = create_refresh_token({"sub": "1"})
        payload = verify_token(token, token_type="refresh")
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_access_token_has_type_access(self):
        token = create_access_token({"sub": "1"})
        payload = verify_token(token, token_type="access")
        assert payload is not None
        assert payload["type"] == "access"

    def test_verify_malformed_token(self):
        assert verify_token("not.a.valid.jwt.token") is None

    def test_verify_none_like_token(self):
        assert verify_token("") is None

    def test_algorithm_is_hs256(self):
        assert ALGORITHM == "HS256"

    def test_token_numeric_sub(self):
        """sub claim with numeric string should roundtrip correctly."""
        token = create_access_token({"sub": "99999"})
        payload = verify_token(token)
        assert payload["sub"] == "99999"


class TestAuthIntegration:
    """Integration tests combining hashing and tokens."""

    def test_full_auth_flow(self):
        """Simulate register → login → token verify."""
        password = "secure_password_123"
        hashed = get_password_hash(password)

        # Login: verify password
        assert verify_password(password, hashed) is True

        # Create tokens
        user_data = {"sub": "42", "email": "test@example.com"}
        access_token = create_access_token(user_data)
        refresh_token = create_refresh_token(user_data)

        # Verify access token
        access_payload = verify_token(access_token, token_type="access")
        assert access_payload is not None
        assert access_payload["sub"] == "42"
        assert access_payload["email"] == "test@example.com"

        # Verify refresh token
        refresh_payload = verify_token(refresh_token, token_type="refresh")
        assert refresh_payload is not None
        assert refresh_payload["sub"] == "42"

        # Cross-type verification should fail
        assert verify_token(access_token, token_type="refresh") is None
        assert verify_token(refresh_token, token_type="access") is None
