from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

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


def test_c112_hit_ads_metric_provenance_contract(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    fresh_ad = Ad(
        external_id="c112_real_1",
        title="美容 広告 実測",
        description="fresh real metrics",
        advertiser_name="広告主A",
        destination_url="https://example.com/lp",
        image_url="https://example.com/image.jpg",
        snapshot_url="https://example.com/snapshot.jpg",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        view_count=2200,
        spend=5400,
        impressions=2400,
        reach=1700,
        ad_metadata={
            "latest_hit_score": 78,
            "lp_score": {"score": 74},
            "extract_quality_score": 88,
            "last_crawled_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    stale_estimated_ad = Ad(
        external_id="c112_est_1",
        title="美容 広告 推定",
        description="stale estimated metrics",
        advertiser_name="広告主B",
        destination_url="https://example.com/lp2",
        image_url="https://example.com/image2.jpg",
        snapshot_url="https://example.com/snapshot2.jpg",
        platform=AdPlatformEnum.INSTAGRAM,
        status=AdStatusEnum.PENDING,
        view_count=1600,
        ad_metadata={
            "latest_hit_score": 65,
            "estimated_total_spend_jpy": 3100,
            "spend_metric_source": "estimated_spend",
            "lp_score": 58,
            "extract_quality_score": 49,
            "last_crawled_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        },
    )
    session.add_all([fresh_ad, stale_estimated_ad])
    session.commit()

    res = rankings.get_hit_ads(limit=5)
    assert res["total"] >= 2
    items = {item["title"]: item for item in res["items"]}

    fresh_item = items["美容 広告 実測"]
    assert fresh_item["spend"] == 5400
    assert fresh_item["impressions"] == 2200
    assert fresh_item["reach"] == 1700
    assert fresh_item["lp_score"] == 74
    assert fresh_item["extract_quality_score"] == 88
    assert fresh_item["spend_provenance"]["metric_status"] == "real"
    assert fresh_item["spend_provenance"]["freshness_status"] == "fresh"

    stale_item = items["美容 広告 推定"]
    assert stale_item["spend"] == 3100
    assert stale_item["spend_provenance"]["metric_status"] == "estimated"
    assert stale_item["spend_provenance"]["freshness_status"] == "stale"
    assert stale_item["lp_score_provenance"]["metric_status"] == "real"

    for item in (fresh_item, stale_item):
        for field in (
            "spend_provenance",
            "impressions_provenance",
            "reach_provenance",
            "lp_score_provenance",
            "extract_quality_score_provenance",
        ):
            assert set(item[field].keys()) == {
                "metric_source",
                "metric_status",
                "freshness_status",
                "measured_at",
                "confidence_label",
            }
