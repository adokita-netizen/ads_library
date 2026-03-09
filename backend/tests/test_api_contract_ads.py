"""Contract tests for ads API endpoints.

Verifies response structure and error handling for core CRUD operations.
Uses async SQLite session to match the async endpoint signatures.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from fastapi import FastAPI

from app.api.endpoints import ads
from app.core.database import Base, get_async_session
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum


@pytest.fixture
def app_client():
    """Build async test client with proper async session override."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    AsyncTestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_async_session():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncTestSession() as session:
            yield session

    app = FastAPI()
    app.include_router(ads.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = override_async_session
    app.state.test_engine = engine
    app.state.test_sessionmaker = AsyncTestSession
    return app


@pytest.mark.asyncio
async def test_ads_metric_provenance_contract(app_client):
    async with app_client.state.test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with app_client.state.test_sessionmaker() as session:
        session.add(
            Ad(
                external_id="contract_metric_1",
                title="実数値契約テスト",
                description="provenance shape",
                advertiser_name="広告主",
                platform=AdPlatformEnum.FACEBOOK,
                status=AdStatusEnum.PENDING,
                spend=4200,
                impressions=1800,
                reach=1300,
                ad_metadata={
                    "last_crawled_at": datetime.now(timezone.utc).isoformat(),
                    "lp_score": {"score": 72},
                    "lp_score_source": "lp_analysis",
                    "extract_quality_score": 81,
                    "extract_quality_score_source": "creative_extraction",
                },
                updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    ad = data["ads"][0]

    for field in ("spend_provenance", "impressions_provenance", "reach_provenance", "lp_score_provenance", "extract_quality_score_provenance"):
        assert field in ad
        assert set(ad[field].keys()) == {
            "metric_source",
            "metric_status",
            "freshness_status",
            "measured_at",
            "confidence_label",
        }

    assert ad["language"] == "ja"
    assert ad["language_status"] == "ja"
    assert "language_confidence" in ad
    assert ad["language_source"] in {"missing", "rule_text", "bedrock", "rule"}
    assert "product_category" in ad
    assert "product_subcategory" in ad
    assert "exclude_from_analysis" in ad
    assert "exclude_reason" in ad
    for field in (
        "metric_source",
        "creative_source",
        "lp_source",
        "metric_status",
        "creative_status",
        "lp_status",
        "freshness_status",
        "last_meta_success_at",
        "meta_quality_state",
        "meta_recovery_reason",
    ):
        assert field in ad

    assert ad["spend"] == 4200
    assert ad["spend_provenance"]["metric_status"] == "real"
    assert ad["spend_provenance"]["freshness_status"] == "fresh"
    assert ad["lp_score"] == 72
    assert ad["extract_quality_score"] == 81
    assert ad["metric_status"] == "missing"
    assert ad["creative_status"] == "missing"
    assert ad["lp_status"] == "missing"


@pytest.mark.asyncio
async def test_list_returns_200(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_list_response_structure(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads")
    data = res.json()
    assert "ads" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["ads"], list)
    assert isinstance(data["total"], int)


@pytest.mark.asyncio
async def test_list_empty_db(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads")
    data = res.json()
    assert data["total"] == 0
    assert data["ads"] == []


@pytest.mark.asyncio
async def test_list_pagination_params(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads?page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["page_size"] == 5


@pytest.mark.asyncio
async def test_nonexistent_ad_returns_404(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads/999999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_data_integrity_returns_200(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads/health/data-integrity")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_data_integrity_structure(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads/health/data-integrity")
    data = res.json()
    required_keys = {"total_ads", "no_media_count", "no_title_count",
                     "no_thumbnail_count", "pending_media_extraction",
                     "health_score", "details"}
    assert required_keys.issubset(set(data.keys()))
    assert isinstance(data["health_score"], (int, float))
    assert 0 <= data["health_score"] <= 100


@pytest.mark.asyncio
async def test_data_integrity_empty_db_healthy(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads/health/data-integrity")
    data = res.json()
    assert data["total_ads"] == 0
    assert data["health_score"] == 100.0


@pytest.mark.asyncio
async def test_connected_platforms_returns_200(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/ads/connected-platforms")
    assert res.status_code == 200
    data = res.json()
    assert "connected" in data
    assert isinstance(data["connected"], list)


@pytest.mark.asyncio
async def test_upload_missing_file_returns_422(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.post("/api/v1/ads/upload")
    assert res.status_code == 422
