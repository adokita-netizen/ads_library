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


def test_top_hit_quality_review_reports_drift(session):
    ad = Ad(
        external_id="ci125_top",
        title="Top review ad",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        advertiser_name="CI125",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        first_seen_at=datetime.now(timezone.utc) - timedelta(days=50),
        ad_metadata={
            "days_running": 50,
            "is_still_running": True,
            "latest_hit_score": 10,
            "hit_level": "none",
        },
        image_url="https://example.com/image.jpg",
    )
    session.add(ad)
    session.flush()
    session.add(
        AdDailyMetrics(
            ad_id=ad.id,
            metric_date=datetime.now(timezone.utc).date(),
            estimated_spend_increase=120000,
            view_count_increase=3000,
            genre="other",
        )
    )
    session.commit()

    client = _build_client()
    res = client.post("/api/v1/rankings/top-hit-quality-review", json={"limit": 30})
    assert res.status_code == 200
    data = res.json()

    assert data["reviewed_count"] >= 1
    assert "summary" in data
    item = next(entry for entry in data["items"] if entry["ad_id"] == ad.id)
    assert item["stored"]["hit_level"] == "none"
    assert item["recomputed"]["hit_level"] in {"hit", "mega_hit"}
    assert item["level_changed"] is True
    assert item["hit_flipped"] is True


def test_top_hit_quality_review_clamps_limit():
    client = _build_client()
    res = client.post("/api/v1/rankings/top-hit-quality-review", json={"limit": 999})
    assert res.status_code == 200
    assert res.json()["limit"] == 100
