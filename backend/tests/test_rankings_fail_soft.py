from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_score_distribution_returns_stale_cache_when_compute_fails(monkeypatch):
    cache_key = rankings.build_cache_key(
        namespace="rankings_score_distribution",
        version=rankings.settings.cache_key_version,
        parts=["default"],
    )
    stale_payload = {"total_ads": 3, "distribution": [{"range": "0-9", "count": 1}], "stats": {}, "by_genre": {}}
    rankings._SHORT_TTL_CACHE[cache_key] = (0.0, stale_payload)

    @contextmanager
    def broken_scope():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(rankings, "_db_session_scope", broken_scope)

    client = _build_client()
    res = client.get("/api/v1/rankings/score-distribution")

    assert res.status_code == 200
    data = res.json()
    assert data["total_ads"] == 3
    assert data["_degraded"] is True
    assert data["_degraded_reason"] == "stale_cache"
    assert data["_stale"] is True


def test_dashboard_summary_returns_empty_degraded_payload_without_cache(monkeypatch):
    cache_key = rankings.build_cache_key(
        namespace="rankings_dashboard_summary",
        version=rankings.settings.cache_key_version,
        parts=["default"],
    )
    rankings._SHORT_TTL_CACHE.pop(cache_key, None)

    @contextmanager
    def broken_scope():
        raise RuntimeError("db unavailable")
        yield

    monkeypatch.setattr(rankings, "_db_session_scope", broken_scope)

    client = _build_client()
    res = client.get("/api/v1/rankings/dashboard-summary")

    assert res.status_code == 200
    data = res.json()
    assert data["total_ads"] == 0
    assert data["active_ads"] == 0
    assert data["_degraded"] is True
    assert data["_degraded_reason"] == "fresh_compute_failed"
    assert data["_stale"] is False


def test_fail_soft_policy_endpoint_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/fail-soft-policy")

    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    assert "stale_cache" in data["reason_codes"]
    assert "fresh_compute_failed" in data["reason_codes"]
    assert any(item["path"] == "/dashboard-summary" for item in data["items"])
    assert any(item["path"] == "/score-distribution" for item in data["items"])


def test_fail_soft_policy_filter_returns_single_match():
    client = _build_client()
    res = client.get("/api/v1/rankings/fail-soft-policy", params={"path": "score-distribution"})

    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 1
    assert data["items"][0]["path"] == "/score-distribution"
    assert data["items"][0]["stale_cache_allowed"] is True
