from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_score_parameter_validation_forbids_extra_fields():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/score-parameter-validation",
        json={
            "ad_ids": [1],
            "candidate": {"weights": {"trend": 1.2}},
            "unexpected": True,
        },
    )
    assert res.status_code == 422


def test_score_parameter_ab_review_rejects_string_ids():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/score-parameter-ab-review",
        json={
            "ad_ids": ["1"],
            "candidate": {"weights": {"trend": 1.2}},
        },
    )
    assert res.status_code == 422


def test_top_hit_quality_review_forbids_extra_fields():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/top-hit-quality-review",
        json={"limit": 30, "path": "/api/v1/rankings/products"},
    )
    assert res.status_code == 422


def test_top_hit_quality_review_rejects_string_limit():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/top-hit-quality-review",
        json={"limit": "30"},
    )
    assert res.status_code == 422
