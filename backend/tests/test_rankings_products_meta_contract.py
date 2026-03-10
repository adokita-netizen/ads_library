from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_products_endpoint_builds_meta_contract_from_ad(monkeypatch):
    class DummyService:
        def get_rankings(self, session, **kwargs):
            ranking = SimpleNamespace(
                rank_position=1,
                previous_rank=None,
                rank_change=None,
                ad_id=101,
                product_name="Product",
                advertiser_name="Advertiser",
                genre="beauty",
                platform="instagram",
                total_view_increase=1200,
                total_spend_increase=5000,
                cumulative_views=3000,
                cumulative_spend=9000,
                is_hit=True,
                hit_score=88,
                trend_score=72,
                extra_metadata={"score_breakdown": {"velocity": 80}, "hit_level": "hit"},
            )
            return [ranking], 1

    class DummyQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self._rows

    class DummySession:
        def query(self, model):
            ad = SimpleNamespace(
                id=101,
                thumbnail_url="https://example.com/thumb.jpg",
                thumbnail_s3_key=None,
                duration_seconds=30,
                external_id="AD-101",
                video_url="https://example.com/video.mp4",
                image_url="https://example.com/image.jpg",
                image_s3_key=None,
                snapshot_url="https://example.com/snap.jpg",
                s3_key=None,
                creative_type="ugc",
                like_count=42,
                category="beauty",
                destination_url="https://example.com/lp",
                description="long description",
                title="title",
                first_seen_at=None,
                created_at=None,
                last_seen_at=None,
                ad_metadata={
                    "metric_source": "meta_api",
                    "creative_source": "meta_api",
                    "lp_source": "lp_crawler",
                    "meta_quality_state": "real",
                    "meta_recovery_reason": "live_refresh",
                    "last_meta_success_at": "2026-03-10T00:00:00+00:00",
                    "estimation_method": "heuristic",
                    "destination_url": "https://example.com/lp",
                    "destination_type": "lp",
                    "creative_analysis": {"hook_type": "question", "offer_type": "discount"},
                },
            )
            return DummyQuery([ad])

    @contextmanager
    def fake_scope():
        yield DummySession()

    monkeypatch.setattr(rankings, "RankingService", DummyService)
    monkeypatch.setattr(rankings, "sync_session_scope", fake_scope)

    client = _build_client()
    response = client.get("/api/v1/rankings/products")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["metric_source"] == "meta_api"
    assert item["creative_source"] == "meta_api"
    assert item["lp_source"] == "lp_crawler"
    assert item["meta_quality_state"] == "real"
    assert item["meta_recovery_reason"] == "live_refresh"
