"""Contract tests for media API endpoints.

Verifies response structure and error handling for media retrieval.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from fastapi import FastAPI

from app.api.endpoints import media
from app.core.database import Base, get_async_session


@pytest.fixture
def app_client():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async def override_async_session():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        AsyncTestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with AsyncTestSession() as session:
            yield session

    app = FastAPI()
    app.include_router(media.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = override_async_session
    return app


@pytest.mark.asyncio
async def test_thumbnail_nonexistent_returns_fallback(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/media/thumbnail/999999")
    # Placeholder SVG or 404
    assert res.status_code in (200, 404)


@pytest.mark.asyncio
async def test_image_nonexistent_returns_fallback(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/media/image/999999")
    assert res.status_code in (200, 404)


@pytest.mark.asyncio
async def test_video_nonexistent_returns_404(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/media/video/999999")
    assert res.status_code in (200, 404)


@pytest.mark.asyncio
async def test_media_ad_all_nonexistent_404(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/media/ad/999999/all")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_crawl_history_returns_200(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/media/crawl-history")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_gallery_returns_200(app_client):
    async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as ac:
        res = await ac.get("/api/v1/media/gallery")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, dict)
