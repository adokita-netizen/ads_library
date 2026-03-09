from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def _mk_ad(**overrides) -> Ad:
    payload = {
        "external_id": "ci123_ad",
        "title": "Extraction validity ad",
        "platform": AdPlatformEnum.FACEBOOK,
        "status": AdStatusEnum.PENDING,
        "advertiser_name": "CI123",
        "media_extraction_status": "completed",
        "created_at": datetime(2026, 3, 8, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 8, tzinfo=timezone.utc),
        "ad_metadata": {},
    }
    payload.update(overrides)
    return Ad(**payload)


def test_extraction_quality_report_returns_validity_fields(session):
    session.add(
        _mk_ad(
            external_id="ci123_quality",
            image_url="https://example.com/image.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
            destination_url="https://example.com/lp",
            ad_metadata={
                "topic_confidence": 0.91,
                "creative_analysis": {"hook_type": "question"},
                "matched_terms": ["glp-1"],
                "lp_status": "alive",
                "extractor_version": "v-test",
                "creative_fetch_source": "playwright",
            },
        )
    )
    session.commit()

    client = _build_client()
    res = client.get("/api/v1/rankings/extraction-quality")
    assert res.status_code == 200
    data = res.json()

    assert "avg_validity_score" in data
    item = data["items"][0]
    assert "validity_score" in item
    assert "validity_reasons" in item
    assert isinstance(item["breakdown"], dict)


def test_media_extraction_ads_include_validity_score(session):
    session.add(
        _mk_ad(
            external_id="ci123_list",
            ad_metadata={
                "topic_confidence": 0.2,
                "creative_analysis": {},
                "extractor_version": "v-test",
            },
        )
    )
    session.commit()

    client = _build_client()
    res = client.get("/api/v1/rankings/media-extraction-ads", params={"status": "completed"})
    assert res.status_code == 200
    row = res.json()["ads"][0]

    assert "extract_validity_score" in row
    assert "extract_validity_reasons" in row
    assert isinstance(row["extract_validity_reasons"], list)
