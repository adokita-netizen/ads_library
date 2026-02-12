"""Tests for application configuration."""

from app.core.config import Settings, get_settings


class TestConfigPlatformKeys:
    """Verify all platform API key settings exist."""

    def test_settings_class_has_platform_keys(self):
        """All platform API key fields should be defined in Settings."""
        field_names = set(Settings.model_fields.keys())

        assert "meta_access_token" in field_names
        assert "tiktok_access_token" in field_names
        assert "youtube_api_key" in field_names
        assert "x_twitter_bearer_token" in field_names
        assert "line_api_access_token" in field_names
        assert "yahoo_ads_api_key" in field_names
        assert "yahoo_ads_api_secret" in field_names
        assert "pinterest_access_token" in field_names
        assert "smartnews_ads_api_key" in field_names
        assert "google_ads_developer_token" in field_names
        assert "google_ads_client_id" in field_names
        assert "google_ads_client_secret" in field_names
        assert "google_ads_refresh_token" in field_names
        assert "gunosy_ads_api_key" in field_names

    def test_platform_keys_default_none(self):
        """All platform API keys should default to None."""
        settings = get_settings()

        assert settings.meta_access_token is None
        assert settings.tiktok_access_token is None
        assert settings.youtube_api_key is None
        assert settings.x_twitter_bearer_token is None
        assert settings.line_api_access_token is None
        assert settings.yahoo_ads_api_key is None
        assert settings.pinterest_access_token is None
        assert settings.smartnews_ads_api_key is None
        assert settings.google_ads_developer_token is None
        assert settings.gunosy_ads_api_key is None

    def test_core_settings_defaults(self):
        settings = get_settings()
        assert settings.app_env == "test"  # Set by conftest
        assert settings.api_v1_prefix == "/api/v1"
