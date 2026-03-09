from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


def test_compact_product_ranking_item_drops_heavy_fields():
    item = {
        "rank": 1,
        "product_name": "Product",
        "score_breakdown": {"velocity": 80},
        "image_url": "https://example.com/image.jpg",
        "video_url": "https://example.com/video.mp4",
        "download_urls": {"video": "/api/v1/media/video/1"},
        "data_quality": {"completeness_pct": 80},
        "description": "long body",
    }

    compact = rankings._compact_product_ranking_item(item, compact=True)

    assert compact["rank"] == 1
    assert compact["product_name"] == "Product"
    assert "score_breakdown" not in compact
    assert "image_url" not in compact
    assert "video_url" not in compact
    assert "download_urls" not in compact
    assert "data_quality" not in compact
    assert "description" not in compact


def test_products_compact_endpoint_omits_heavy_fields(monkeypatch):
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
    monkeypatch.setattr(rankings, "_db_session_scope", fake_scope)

    client = _build_client()

    regular = client.get("/api/v1/rankings/products")
    compact = client.get("/api/v1/rankings/products", params={"compact": "true"})

    assert regular.status_code == 200
    assert compact.status_code == 200

    regular_item = regular.json()["items"][0]
    compact_item = compact.json()["items"][0]

    assert "score_breakdown" in regular_item
    assert "download_urls" in regular_item
    assert "data_quality" in regular_item

    assert "score_breakdown" not in compact_item
    assert "download_urls" not in compact_item
    assert "data_quality" not in compact_item
    assert "description" not in compact_item
    assert "title" not in compact_item
    assert compact_item["product_name"] == "Product"
    assert compact_item["thumbnail"] == "/api/v1/media/thumbnail/101"
