from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.ad_metrics import AdDailyMetrics


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_score_parameter_validation_contract(session):
    ad = Ad(
        external_id="c74_contract",
        title="Validation target",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        advertiser_name="Validator",
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=45),
        ad_metadata={"days_running": 45, "is_still_running": True},
        image_url="https://example.com/image.jpg",
    )
    session.add(ad)
    session.flush()
    session.add(
        AdDailyMetrics(
            ad_id=ad.id,
            metric_date=datetime.now(timezone.utc).date(),
            view_count_increase=1200,
            estimated_spend_increase=40000,
            genre="other",
        )
    )
    session.commit()

    client = _build_client()
    res = client.post(
        "/api/v1/rankings/score-parameter-validation",
        json={
            "ad_ids": [ad.id],
            "candidate": {
                "weights": {"trend": 1.5, "creative": 0.5},
                "thresholds": {"hit_score": 40, "mega_hit_score": 80},
            },
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["requested_count"] == 1
    assert data["evaluated_count"] == 1
    assert data["baseline"]["weights"]["trend"] == 1.0
    assert data["candidate"]["weights"]["trend"] == 1.5
    item = data["items"][0]
    assert item["ad_id"] == ad.id
    assert "baseline" in item
    assert "candidate" in item
    assert "delta" in item


def test_score_parameter_validation_rejects_invalid_candidate():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/score-parameter-validation",
        json={
            "ad_ids": [1],
            "candidate": {"thresholds": {"mega_hit_score": 20, "hit_score": 40}},
        },
    )
    assert res.status_code == 400
    assert "mega_hit_score must be >= hit_score" in res.json()["detail"]
