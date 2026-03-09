from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_load_separation_policy_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/load-separation-policy")
    assert res.status_code == 200
    data = res.json()

    assert data["count"] > 0
    assert "lanes" in data
    assert "items" in data
    assert set(data["lanes"]) == {"analytics_deferred", "primary_realtime"}

    first = data["items"][0]
    assert "lane" in first
    assert "path" in first
    assert "goal" in first
    assert "strategy" in first
    assert isinstance(first["strategy"], dict)


def test_load_separation_policy_filter_returns_matching_path():
    client = _build_client()
    res = client.get(
        "/api/v1/rankings/load-separation-policy",
        params={"path": "/dashboard-summary"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["count"] == 1
    item = data["items"][0]
    assert item["lane"] == "primary_realtime"
    assert item["path"] == "/dashboard-summary"
    assert item["strategy"]["fail_soft"] is True
    assert item["strategy"]["profile_sql_bypasses_cache"] is True
