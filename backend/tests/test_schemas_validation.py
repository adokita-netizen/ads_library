"""Tests for Pydantic schema validation — auth, ad, and response schemas."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.auth import UserCreate, UserLogin, TokenResponse, UserResponse
from app.schemas.ad import (
    AdCreate,
    AdResponse,
    AdListResponse,
    AdSearchRequest,
    CrawlRequest,
    CrawlResponse,
)


class TestUserCreateSchema:
    """Test UserCreate validation."""

    def test_valid_user(self):
        user = UserCreate(
            email="test@example.com",
            password="password123",
            full_name="Test User",
        )
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="password123", full_name="Test")

    def test_short_password(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@example.com", password="short", full_name="Test")

    def test_password_exactly_8_chars(self):
        user = UserCreate(
            email="test@example.com", password="12345678", full_name="Test"
        )
        assert len(user.password) == 8

    def test_company_optional(self):
        user = UserCreate(
            email="test@example.com", password="password123", full_name="Test"
        )
        assert user.company is None

    def test_company_provided(self):
        user = UserCreate(
            email="test@example.com",
            password="password123",
            full_name="Test",
            company="TestCo",
        )
        assert user.company == "TestCo"


class TestUserLoginSchema:
    """Test UserLogin validation."""

    def test_valid_login(self):
        login = UserLogin(email="user@example.com", password="mypassword")
        assert login.email == "user@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserLogin(email="bad", password="pass")


class TestTokenResponseSchema:
    """Test TokenResponse schema."""

    def test_default_token_type(self):
        resp = TokenResponse(access_token="abc", refresh_token="def")
        assert resp.token_type == "bearer"

    def test_custom_token_type(self):
        resp = TokenResponse(access_token="a", refresh_token="b", token_type="custom")
        assert resp.token_type == "custom"


class TestAdCreateSchema:
    """Test AdCreate schema."""

    def test_minimal_ad(self):
        ad = AdCreate(platform="youtube")
        assert ad.platform == "youtube"
        assert ad.title is None
        assert ad.tags == []

    def test_full_ad(self):
        ad = AdCreate(
            title="Test Ad",
            description="Description",
            platform="tiktok",
            category="beauty",
            video_url="https://example.com/video.mp4",
            advertiser_name="Advertiser",
            brand_name="Brand",
            tags=["tag1", "tag2"],
        )
        assert ad.title == "Test Ad"
        assert len(ad.tags) == 2


class TestAdResponseSchema:
    """Test AdResponse schema with metadata extraction."""

    def test_from_dict_with_metadata(self):
        data = {
            "id": 1,
            "platform": "youtube",
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "ad_metadata": {
                "destination_url": "https://example.com/lp",
                "destination_type": "記事LP",
            },
        }
        resp = AdResponse.model_validate(data)
        assert resp.destination_url == "https://example.com/lp"
        assert resp.destination_type == "記事LP"

    def test_from_dict_without_metadata(self):
        data = {
            "id": 2,
            "platform": "tiktok",
            "status": "analyzed",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        resp = AdResponse.model_validate(data)
        assert resp.destination_url is None
        assert resp.destination_type is None


class TestAdListResponseSchema:
    """Test AdListResponse pagination schema."""

    def test_empty_list(self):
        resp = AdListResponse(ads=[], total=0, page=1, page_size=20)
        assert resp.total == 0
        assert len(resp.ads) == 0

    def test_pagination_values(self):
        resp = AdListResponse(ads=[], total=100, page=3, page_size=20)
        assert resp.page == 3
        assert resp.page_size == 20


class TestAdSearchRequestSchema:
    """Test AdSearchRequest defaults."""

    def test_defaults(self):
        req = AdSearchRequest(query="beauty")
        assert req.page == 1
        assert req.page_size == 20
        assert req.platforms is None

    def test_custom_values(self):
        req = AdSearchRequest(
            query="beauty",
            platforms=["youtube", "tiktok"],
            page=2,
            page_size=50,
        )
        assert len(req.platforms) == 2
        assert req.page == 2


class TestCrawlRequestValidation:
    """Extended CrawlRequest validation tests."""

    def test_query_required(self):
        with pytest.raises(ValidationError):
            CrawlRequest()

    def test_empty_query(self):
        """Empty string should be accepted (no min_length constraint)."""
        req = CrawlRequest(query="")
        assert req.query == ""

    def test_japanese_query(self):
        req = CrawlRequest(query="美容 コスメ 広告")
        assert "美容" in req.query

    def test_category_optional(self):
        req = CrawlRequest(query="test")
        assert req.category is None

    def test_category_provided(self):
        req = CrawlRequest(query="test", category="beauty")
        assert req.category == "beauty"


class TestCrawlResponseSchema:
    """Test CrawlResponse schema."""

    def test_completed_response(self):
        resp = CrawlResponse(
            task_id="abc-123",
            status="completed",
            message="クロール完了",
        )
        assert resp.status == "completed"

    def test_started_response(self):
        resp = CrawlResponse(
            task_id="task-456",
            status="started",
            message="クロールを開始しました",
        )
        assert resp.status == "started"
