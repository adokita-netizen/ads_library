from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings
from app.core.rate_limit import _rate_limit_store


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


class _EmptyQuery:
    def all(self):
        return []

    def filter(self, *args, **kwargs):
        return self

    def scalar(self):
        return 0


class _EmptySession:
    def query(self, *args, **kwargs):
        return _EmptyQuery()


@contextmanager
def _empty_scope():
    yield _EmptySession()


def test_dashboard_summary_rate_limit(monkeypatch):
    _rate_limit_store.clear()
    monkeypatch.setattr(rankings.settings, "rate_limit_rankings_read", "1/minute")
    monkeypatch.setattr(rankings, "_db_session_scope", _empty_scope)

    client = _build_client()

    first = client.get("/api/v1/rankings/dashboard-summary")
    second = client.get("/api/v1/rankings/dashboard-summary")

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert second.headers["X-RateLimit-Limit"] == "1"


def test_products_rate_limit(monkeypatch):
    class DummyService:
        def get_rankings(self, session, **kwargs):
            return [], 1

    _rate_limit_store.clear()
    monkeypatch.setattr(rankings.settings, "rate_limit_rankings_heavy", "1/minute")
    monkeypatch.setattr(rankings, "_db_session_scope", _empty_scope)
    monkeypatch.setattr(rankings, "RankingService", DummyService)

    client = _build_client()

    first = client.get("/api/v1/rankings/products")
    second = client.get("/api/v1/rankings/products")

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert second.headers["X-RateLimit-Limit"] == "1"


def test_rate_limit_policy_endpoint_contract():
    client = _build_client()

    res = client.get("/api/v1/rankings/rate-limit-policy")

    assert res.status_code == 200
    data = res.json()
    assert "count" in data
    assert "lanes" in data
    assert data["lanes"] == ["heavy", "read"]
    assert "items" in data
    assert any(item["path"] == "/dashboard-summary" and item["lane"] == "read" for item in data["items"])
    assert any(item["path"] == "/products" and item["lane"] == "heavy" for item in data["items"])


def test_rate_limit_policy_endpoint_filter():
    client = _build_client()

    res = client.get("/api/v1/rankings/rate-limit-policy", params={"path": "products"})

    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 1
    assert data["items"][0]["path"] == "/products"
    assert data["items"][0]["lane"] == "heavy"
