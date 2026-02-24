"""Tests for rate limiting, logout, token blacklist, and config security."""

import time
import pytest
from unittest.mock import patch

from app.core.config import Settings, _INSECURE_SECRET_KEYS
from app.core.security import (
    add_to_blacklist,
    is_blacklisted,
    create_access_token,
    verify_token,
    _token_blacklist,
)
from app.api.endpoints.auth import _check_rate_limit, _rate_limit_store

from fastapi import HTTPException


class TestRateLimiting:
    """Test in-memory rate limiter."""

    def setup_method(self):
        _rate_limit_store.clear()

    def test_allows_within_limit(self):
        for _ in range(3):
            _check_rate_limit("test:ip1", max_requests=3, window_seconds=60)

    def test_blocks_over_limit(self):
        for _ in range(3):
            _check_rate_limit("test:ip2", max_requests=3, window_seconds=60)
        with pytest.raises(HTTPException) as exc_info:
            _check_rate_limit("test:ip2", max_requests=3, window_seconds=60)
        assert exc_info.value.status_code == 429

    def test_different_keys_independent(self):
        for _ in range(5):
            _check_rate_limit("login:192.168.1.1", max_requests=5, window_seconds=60)
        # Different IP should still be allowed
        _check_rate_limit("login:192.168.1.2", max_requests=5, window_seconds=60)

    def test_expired_entries_cleaned(self):
        """Entries outside the window should be cleaned."""
        key = "test:expire"
        _rate_limit_store[key] = [time.monotonic() - 120]  # 2 min ago
        _check_rate_limit(key, max_requests=1, window_seconds=60)
        # Should succeed because old entry was cleaned

    def test_register_limit_stricter_than_login(self):
        """Register allows 3/min, login allows 5/min."""
        for _ in range(3):
            _check_rate_limit("register:test_ip", max_requests=3, window_seconds=60)
        with pytest.raises(HTTPException):
            _check_rate_limit("register:test_ip", max_requests=3, window_seconds=60)

        for _ in range(5):
            _check_rate_limit("login:test_ip", max_requests=5, window_seconds=60)
        with pytest.raises(HTTPException):
            _check_rate_limit("login:test_ip", max_requests=5, window_seconds=60)


class TestTokenBlacklist:
    """Test token blacklist for logout."""

    def setup_method(self):
        _token_blacklist.clear()

    def test_add_to_blacklist(self):
        token = create_access_token({"sub": "1"})
        add_to_blacklist(token, time.time() + 3600)
        assert is_blacklisted(token) is True

    def test_blacklisted_token_rejected(self):
        token = create_access_token({"sub": "1"})
        add_to_blacklist(token, time.time() + 3600)
        assert verify_token(token) is None

    def test_non_blacklisted_token_accepted(self):
        token = create_access_token({"sub": "1"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "1"

    def test_expired_tokens_cleaned(self):
        token = "expired_token"
        _token_blacklist[token] = time.time() - 100  # Already expired
        add_to_blacklist("new_token", time.time() + 3600)
        assert token not in _token_blacklist

    def test_blacklist_multiple_tokens(self):
        tokens = []
        for i in range(5):
            t = create_access_token({"sub": str(i)})
            tokens.append(t)
            add_to_blacklist(t, time.time() + 3600)
        for t in tokens:
            assert is_blacklisted(t)
            assert verify_token(t) is None


class TestSecretKeyValidation:
    """Test secret key security checks."""

    def test_default_key_insecure(self):
        settings = Settings(_env_file=None)
        assert settings.is_secret_key_secure is False

    def test_short_key_insecure(self):
        settings = Settings(secret_key="short")
        assert settings.is_secret_key_secure is False

    def test_known_insecure_keys(self):
        for key in _INSECURE_SECRET_KEYS:
            settings = Settings(secret_key=key)
            assert settings.is_secret_key_secure is False

    def test_strong_key_secure(self):
        settings = Settings(secret_key="a" * 32)
        assert settings.is_secret_key_secure is True

    def test_very_strong_key_secure(self):
        settings = Settings(secret_key="x8f2k9d4m7p1q3n6w0j5b8c2v4h7t9ya")
        assert settings.is_secret_key_secure is True

    def test_rate_limit_defaults(self):
        settings = Settings()
        assert settings.rate_limit_login == "5/minute"
        assert settings.rate_limit_register == "3/minute"
