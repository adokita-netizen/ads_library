"""Tests for Pydantic schemas and API request validation."""

import pytest
from pydantic import ValidationError

from app.schemas.ad import CrawlRequest


class TestCrawlRequestSchema:
    """Test the CrawlRequest schema defaults and validation."""

    def test_default_platforms(self):
        req = CrawlRequest(query="テスト")
        assert len(req.platforms) == 11
        assert "youtube" in req.platforms
        assert "tiktok" in req.platforms
        assert "facebook" in req.platforms
        assert "instagram" in req.platforms
        assert "yahoo" in req.platforms
        assert "x_twitter" in req.platforms
        assert "line" in req.platforms
        assert "pinterest" in req.platforms
        assert "smartnews" in req.platforms
        assert "google_ads" in req.platforms
        assert "gunosy" in req.platforms

    def test_custom_platforms(self):
        req = CrawlRequest(query="テスト", platforms=["youtube", "tiktok"])
        assert len(req.platforms) == 2

    def test_limit_validation(self):
        req = CrawlRequest(query="テスト", limit_per_platform=50)
        assert req.limit_per_platform == 50

    def test_limit_max(self):
        with pytest.raises(ValidationError):
            CrawlRequest(query="テスト", limit_per_platform=200)

    def test_limit_min(self):
        with pytest.raises(ValidationError):
            CrawlRequest(query="テスト", limit_per_platform=0)

    def test_auto_analyze_default(self):
        req = CrawlRequest(query="テスト")
        assert req.auto_analyze is False
