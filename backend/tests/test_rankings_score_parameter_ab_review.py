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


def test_score_parameter_ab_review_contract(session):
    promoted = Ad(
        external_id="c86_promoted",
        title="Promoted by lower threshold",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        advertiser_name="AB Review",
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=45),
        ad_metadata={"days_running": 45, "is_still_running": False},
    )
    stable = Ad(
        external_id="c86_stable",
        title="Stable hit",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        advertiser_name="AB Review",
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=70),
        ad_metadata={"days_running": 70, "is_still_running": True},
        image_url="https://example.com/stable.jpg",
    )
    session.add_all([promoted, stable])
    session.flush()

    today = datetime.now(timezone.utc).date()
    session.add_all(
        [
            AdDailyMetrics(
                ad_id=promoted.id,
                metric_date=today,
                view_count_increase=1200,
                estimated_spend_increase=20000,
                genre="other",
            ),
            AdDailyMetrics(
                ad_id=stable.id,
                metric_date=today,
                view_count_increase=5000,
                estimated_spend_increase=200000,
                genre="other",
            ),
        ]
    )
    session.commit()

    client = _build_client()
    res = client.post(
        "/api/v1/rankings/score-parameter-ab-review",
        json={
            "ad_ids": [promoted.id, stable.id],
            "candidate": {"thresholds": {"hit_score": 25, "mega_hit_score": 80}},
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["requested_count"] == 2
    assert data["evaluated_count"] == 2
    assert data["summary"]["baseline_hit_count"] == 1
    assert data["summary"]["candidate_hit_count"] == 2
    assert data["summary"]["hit_count_delta"] == 1
    assert data["summary"]["hit_flip_count"] == 1
    assert data["distribution"]["baseline"]["none"] == 1
    assert data["distribution"]["candidate"]["hit"] == 2
    assert promoted.id in data["changed_ads"]["promoted_ids"]
    assert data["changed_ads"]["demoted_ids"] == []
    assert len(data["items"]) == 2


def test_score_parameter_ab_review_rejects_large_request():
    client = _build_client()
    res = client.post(
        "/api/v1/rankings/score-parameter-ab-review",
        json={
            "ad_ids": list(range(1, 53)),
            "candidate": {"weights": {"trend": 1.2}},
        },
    )
    assert res.status_code == 400
    assert "at most 50 items" in res.json()["detail"]
