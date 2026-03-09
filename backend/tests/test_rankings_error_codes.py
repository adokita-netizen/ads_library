from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_error_code_dictionary_contract():
    client = _build_client()
    res = client.get("/api/v1/rankings/error-codes")
    assert res.status_code == 200
    data = res.json()

    assert "count" in data
    assert "categories" in data
    assert "scopes" in data
    assert "items" in data
    assert data["count"] == len(data["items"])
    assert "user" in data["categories"]
    assert "media" in data["scopes"]

    by_code = {item["code"]: item for item in data["items"]}
    assert by_code["validation_error"]["http_status"] == 422
    assert by_code["gateway_auth_required"]["scope"] == "gateway"
    assert by_code["minimum_count_not_met"]["category"] == "data_quality"
    assert by_code["no_cached_media"]["operator_action"]
    assert by_code["database_error"]["severity"] == "critical"
    assert by_code["timeout"]["owner"] == "crawl_ops"
    assert by_code["fresh_compute_failed"]["runbook"].endswith("#fresh_compute_failed")
    assert by_code["validation_error"]["first_response"] == "validate_request"


def test_error_code_dictionary_filters_by_category():
    client = _build_client()
    res = client.get("/api/v1/rankings/error-codes", params={"category": "data_quality"})
    assert res.status_code == 200
    data = res.json()

    assert data["count"] > 0
    assert all(item["category"] == "data_quality" for item in data["items"])
    assert any(item["code"] == "topic_confidence_low" for item in data["items"])


def test_error_code_dictionary_filters_by_scope():
    client = _build_client()
    res = client.get("/api/v1/rankings/error-codes", params={"scope": "rankings_cache"})
    assert res.status_code == 200
    data = res.json()

    assert data["count"] == 2
    assert all(item["scope"] == "rankings_cache" for item in data["items"])
    assert {item["code"] for item in data["items"]} == {"stale_cache", "fresh_compute_failed"}
