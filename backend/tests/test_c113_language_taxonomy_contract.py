from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum


def _import_rankings_module():
    if not hasattr(db, "sync_session_scope"):
        @contextmanager
        def _scope():
            sess = db.SyncSessionLocal()
            try:
                yield sess
            finally:
                sess.close()
        db.sync_session_scope = _scope
    from app.api.endpoints import rankings
    return rankings


@contextmanager
def _session_scope(session):
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


def test_c113_hit_ads_and_search_language_taxonomy_contract(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    session.add_all(
        [
            Ad(
                external_id="c113-ja",
                title="GLP-1 医療ダイエット",
                description="日本語広告",
                advertiser_name="Clinic A",
                destination_url="https://example.com/lp",
                image_url="https://example.com/a.jpg",
                snapshot_url="https://example.com/a-s.jpg",
                platform=AdPlatformEnum.FACEBOOK,
                status=AdStatusEnum.PENDING,
                ad_metadata={
                    "language": "ja",
                    "language_source": "bedrock",
                    "language_confidence": 0.95,
                    "product_category": "beauty",
                    "product_subcategory": "medical_weight_loss",
                },
            ),
            Ad(
                external_id="c113-nonja",
                title="Medical diet campaign",
                description="Free consultation",
                advertiser_name="Clinic B",
                destination_url="https://example.com/lp2",
                image_url="https://example.com/b.jpg",
                snapshot_url="https://example.com/b-s.jpg",
                platform=AdPlatformEnum.INSTAGRAM,
                status=AdStatusEnum.PENDING,
                ad_metadata={
                    "language": "en",
                    "language_source": "bedrock",
                    "product_category": "beauty",
                },
            ),
            Ad(
                external_id="c113-unknown",
                title="GLP-1 campaign",
                description="",
                advertiser_name="Clinic C",
                destination_url="https://example.com/lp3",
                image_url="https://example.com/c.jpg",
                snapshot_url="https://example.com/c-s.jpg",
                platform=AdPlatformEnum.YOUTUBE,
                status=AdStatusEnum.PENDING,
                ad_metadata={},
            ),
        ]
    )
    session.commit()

    hit_res = rankings.get_hit_ads(limit=10)
    titles = {item["title"] for item in hit_res["items"]}
    assert "GLP-1 医療ダイエット" in titles
    assert "Medical diet campaign" not in titles

    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    client = TestClient(app)
    search_res = client.get("/api/v1/rankings/search", params={"q": "GLP-1"})
    assert search_res.status_code == 200
    data = search_res.json()
    ad_items = [item for item in data["results"] if item.get("type") == "ad"]
    assert ad_items
    assert {item["title"] for item in ad_items} == {"GLP-1 医療ダイエット"}
    item = ad_items[0]
    assert item["language"] == "ja"
    assert item["language_status"] == "ja"
    assert item["language_source"] == "bedrock"
    assert item["product_category"] == "beauty"
    assert item["product_subcategory"] == "medical_weight_loss"
    assert item["exclude_from_analysis"] is False

    unknown_payload = rankings._build_rankings_language_taxonomy(session.query(Ad).filter(Ad.external_id == "c113-unknown").one())
    assert unknown_payload["language"] == "unknown"
    assert unknown_payload["language_status"] == "non-ja"
    assert unknown_payload["exclude_from_analysis"] is True
    assert unknown_payload["exclude_reason"] == "non_japanese"
