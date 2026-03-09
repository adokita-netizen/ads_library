from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings
from app.core import slo


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_slo_status_dictionary_contract():
    slo.reset_slo_metrics()
    client = _build_client()

    res = client.get("/api/v1/rankings/slo-status")
    assert res.status_code == 200
    data = res.json()

    assert data["count"] > 0
    assert "default_target" in data
    assert "items" in data
    assert data["count"] == len(data["items"])

    first = data["items"][0]
    assert "path" in first
    assert "bucket" in first
    assert "targets" in first
    assert "window" in first
    assert "status" in first
    assert first["status"] in {"ok", "violated", "no_data"}


def test_slo_status_path_filter_reports_violation_after_rolling_samples():
    slo.reset_slo_metrics()
    path = "/api/v1/rankings/dashboard-summary"
    for _ in range(12):
        slo.check_slo_violation(path, 1500, 200)

    client = _build_client()
    res = client.get("/api/v1/rankings/slo-status", params={"path": path})
    assert res.status_code == 200
    data = res.json()

    assert data["count"] == 1
    item = data["items"][0]
    assert item["path"] == path
    assert item["bucket"] == "/api/v1/rankings/dashboard-summary"
    assert item["targets"]["p95_ms"] == 1000
    assert item["window"]["sample_count"] == 12
    assert item["window"]["p95_ms"] == 1500.0
    assert item["status"] == "violated"


def test_slo_status_path_filter_reports_error_rate_violation():
    slo.reset_slo_metrics()
    path = "/api/v1/media/image/123"
    for _ in range(8):
        slo.check_slo_violation(path, 100, 200)
    for _ in range(2):
        slo.check_slo_violation(path, 100, 500)

    client = _build_client()
    res = client.get("/api/v1/rankings/slo-status", params={"path": path})
    assert res.status_code == 200
    item = res.json()["items"][0]

    assert item["bucket"] == "/api/v1/media/image/"
    assert item["window"]["error_count"] == 2
    assert item["window"]["error_rate"] == 0.2
    assert item["targets"]["error_rate"] == 0.1
    assert item["status"] == "violated"
