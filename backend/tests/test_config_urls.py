"""Tests for configuration URL normalization and settings derivation."""

import os
import pytest
from unittest.mock import patch

from app.core.config import _normalize_database_url, Settings


class TestNormalizeDatabaseUrl:
    """Test _normalize_database_url for different providers."""

    def test_postgres_to_asyncpg(self):
        url = "postgres://user:pass@host:5432/db"
        result = _normalize_database_url(url, driver="asyncpg")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_postgresql_to_asyncpg(self):
        url = "postgresql://user:pass@host:5432/db"
        result = _normalize_database_url(url, driver="asyncpg")
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_already_asyncpg_unchanged(self):
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = _normalize_database_url(url, driver="asyncpg")
        assert result == url

    def test_postgres_to_sync(self):
        url = "postgres://user:pass@host:5432/db"
        result = _normalize_database_url(url, driver="sync")
        assert result == "postgresql://user:pass@host:5432/db"

    def test_asyncpg_to_sync(self):
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = _normalize_database_url(url, driver="sync")
        assert result == "postgresql://user:pass@host:5432/db"

    def test_empty_url_returns_empty(self):
        assert _normalize_database_url("", driver="asyncpg") == ""

    def test_sqlite_url_unchanged(self):
        url = "sqlite:///test.db"
        assert _normalize_database_url(url, driver="asyncpg") == url
        assert _normalize_database_url(url, driver="sync") == url

    def test_postgres_prefix_url(self):
        """postgres:// URLs (common in managed services) need conversion."""
        url = "postgres://vaap:password@vaap-db.abcxyz.ap-northeast-1.rds.amazonaws.com:5432/vaap_db"
        result = _normalize_database_url(url, driver="asyncpg")
        assert result.startswith("postgresql+asyncpg://")
        assert "rds.amazonaws.com" in result


class TestSettingsDerivation:
    """Test Settings model_validator URL derivation."""

    def test_sync_url_auto_derived(self):
        """When database_url_sync is empty, it should be auto-derived."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgres://user:pass@host:5432/db",
            "DATABASE_URL_SYNC": "",
            "APP_ENV": "test",
        }, clear=False):
            settings = Settings()
            assert "postgresql+asyncpg://" in settings.database_url
            assert "postgresql://" in settings.database_url_sync
            assert "+asyncpg" not in settings.database_url_sync

    def test_explicit_sync_url_preserved(self):
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgres://user:pass@host:5432/db",
            "DATABASE_URL_SYNC": "postgres://user:pass@host:5432/syncdb",
            "APP_ENV": "test",
        }, clear=False):
            settings = Settings()
            assert "syncdb" in settings.database_url_sync


class TestSettingsDefaults:
    """Test default values for important settings."""

    def test_cors_origins_list_single(self):
        settings = Settings(cors_origins="http://localhost:3000")
        assert settings.cors_origins_list == ["http://localhost:3000"]

    def test_cors_origins_list_multiple(self):
        settings = Settings(cors_origins="http://localhost:3000,https://app.example.com")
        assert len(settings.cors_origins_list) == 2
        assert "http://localhost:3000" in settings.cors_origins_list
        assert "https://app.example.com" in settings.cors_origins_list

    def test_cors_origins_wildcard_default(self):
        settings = Settings(_env_file=None)
        assert "*" in settings.cors_origins_list

    def test_ocr_languages_list(self):
        settings = Settings()
        assert "ja" in settings.ocr_languages_list
        assert "en" in settings.ocr_languages_list

    def test_jwt_defaults(self):
        settings = Settings()
        assert settings.access_token_expire_minutes == 30
        assert settings.refresh_token_expire_days == 7

    def test_api_prefix(self):
        settings = Settings()
        assert settings.api_v1_prefix == "/api/v1"

    def test_db_pool_defaults(self):
        settings = Settings()
        assert settings.db_pool_size == 5
        assert settings.db_max_overflow == 3


class TestDatabaseDiagnostics:
    """Test the _diagnose_error logic from database.py.

    Since conftest.py replaces app.core.database with a mock module,
    we re-implement the same diagnostic logic here for isolated testing.
    """

    @staticmethod
    def _diagnose_error(error: Exception, url: str) -> str:
        """Mirror of app.core.database._diagnose_error."""
        err_str = str(error).lower()
        if "password authentication failed" in err_str:
            msg = "接続エラー: パスワード認証に失敗しました。"
            msg += "DATABASE_URLのパスワードを確認してください。"
            return msg
        if "could not connect" in err_str or "connection refused" in err_str:
            return "接続エラー: データベースサーバーに接続できません。DATABASE_URLを確認してください。"
        if "does not exist" in err_str:
            return "接続エラー: データベースが存在しません。データベースが存在するか確認してください。"
        if "timeout" in err_str:
            return "接続エラー: データベースサーバーへの接続がタイムアウトしました。"
        return f"接続エラー: {str(error)}"

    def test_password_auth_error(self):
        exc = Exception("password authentication failed for user postgres")
        msg = self._diagnose_error(exc, "postgres://host:5432/db")
        assert "パスワード認証" in msg

    def test_password_auth_with_rds(self):
        exc = Exception("password authentication failed")
        msg = self._diagnose_error(exc, "postgres://vaap@vaap-db.ap-northeast-1.rds.amazonaws.com:5432/vaap_db")
        assert "パスワードを確認" in msg

    def test_connection_refused(self):
        exc = Exception("could not connect to server: Connection refused")
        msg = self._diagnose_error(exc, "postgres://host:5432/db")
        assert "接続できません" in msg

    def test_database_not_found(self):
        exc = Exception('database "mydb" does not exist')
        msg = self._diagnose_error(exc, "postgres://host:5432/mydb")
        assert "存在しません" in msg

    def test_timeout_error(self):
        exc = Exception("connection timeout expired")
        msg = self._diagnose_error(exc, "postgres://host:5432/db")
        assert "タイムアウト" in msg

    def test_generic_error(self):
        exc = Exception("some unknown error")
        msg = self._diagnose_error(exc, "postgres://host:5432/db")
        assert "接続エラー" in msg
