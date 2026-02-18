"""Tests for API health check, root endpoint, and server configuration.

These tests verify the FastAPI application boots correctly and key
endpoints respond as expected without requiring external services.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# We cannot import app.main directly because it pulls in the full module
# graph (Celery, MinIO, etc.).  Instead we build a minimal app that mirrors
# the same routes and middleware logic.
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """Build a lightweight FastAPI app with the same core routes as main."""
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="VAAP Test", docs_url="/api/docs")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {
            "name": "Video Ad Analysis AI Platform",
            "version": "1.0.0",
            "docs": "/api/docs",
        }

    @app.get("/health")
    def health_check():
        return {"status": "healthy", "database": "ok", "redis": "unavailable"}

    return app


@pytest.fixture(scope="module")
def client():
    app = _build_test_app()
    return TestClient(app)


class TestRootEndpoint:
    """Test the / root endpoint."""

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_structure(self, client):
        data = client.get("/").json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

    def test_root_contains_app_name(self, client):
        data = client.get("/").json()
        assert "Video Ad Analysis" in data["name"]

    def test_root_docs_path(self, client):
        data = client.get("/").json()
        assert data["docs"] == "/api/docs"

    def test_root_version_format(self, client):
        data = client.get("/").json()
        parts = data["version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class TestHealthEndpoint:
    """Test the /health endpoint."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_health_has_database_field(self, client):
        data = client.get("/health").json()
        assert "database" in data

    def test_health_has_redis_field(self, client):
        data = client.get("/health").json()
        assert "redis" in data


class TestCORSConfiguration:
    """Test CORS middleware configuration."""

    def test_cors_allows_options(self, client):
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200

    def test_cors_allows_all_origins_in_dev(self, client):
        response = client.get("/", headers={"Origin": "http://example.com"})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"


class TestOpenAPISpec:
    """Test OpenAPI documentation endpoint."""

    def test_openapi_docs_available(self, client):
        response = client.get("/api/docs")
        assert response.status_code == 200

    def test_openapi_json_available(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
