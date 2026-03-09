from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.services.media_extraction import EXTRACTOR_VERSION


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def _mk_ad(**overrides) -> Ad:
    payload = {
        "external_id": "ci118_ad",
        "title": "Extractor tracked ad",
        "platform": AdPlatformEnum.FACEBOOK,
        "status": AdStatusEnum.PENDING,
        "advertiser_name": "CI118",
        "media_extraction_status": "completed",
        "created_at": datetime(2026, 3, 8, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 8, tzinfo=timezone.utc),
        "ad_metadata": {},
    }
    payload.update(overrides)
    return Ad(**payload)


def test_media_extraction_status_exposes_version_breakdown(session):
    session.add_all(
        [
            _mk_ad(
                external_id="ci118_a",
                ad_metadata={"extractor_version": EXTRACTOR_VERSION},
            ),
            _mk_ad(
                external_id="ci118_b",
                media_extraction_status="failed",
                ad_metadata={"extractor_version": "inline_enrich_v1.0.0"},
            ),
        ]
    )
    session.commit()

    client = _build_client()
    res = client.get("/api/v1/rankings/media-extraction-status")
    assert res.status_code == 200
    data = res.json()

    assert data["current_extractor_version"] == EXTRACTOR_VERSION
    assert data["extractor_version_breakdown"][EXTRACTOR_VERSION] >= 1
    assert data["extractor_version_breakdown"]["inline_enrich_v1.0.0"] >= 1
    assert EXTRACTOR_VERSION in data["extractor_changelog"]


def test_media_extraction_ads_include_extractor_version_fields(session):
    session.add(
        _mk_ad(
            external_id="ci118_list",
            media_extraction_status="completed",
            ad_metadata={
                "extractor_version": EXTRACTOR_VERSION,
                "creative_fetch_source": "playwright",
                "extractor_version_history": [
                    {
                        "version": EXTRACTOR_VERSION,
                        "status": "success",
                        "source": "playwright",
                        "recorded_at": "2026-03-08T00:00:00+00:00",
                    }
                ],
            },
        )
    )
    session.commit()

    client = _build_client()
    res = client.get("/api/v1/rankings/media-extraction-ads", params={"status": "completed"})
    assert res.status_code == 200
    data = res.json()

    row = next(item for item in data["ads"] if item["id"])
    assert row["extractor_version"] == EXTRACTOR_VERSION
    assert row["creative_fetch_source"] == "playwright"
    assert row["extractor_version_history"][0]["version"] == EXTRACTOR_VERSION
