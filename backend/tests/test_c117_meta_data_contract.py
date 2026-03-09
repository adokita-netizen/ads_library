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


def test_c117_meta_freshness_contract_is_consistent_across_rankings_responses(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "_db_session_scope", lambda: _session_scope(session))

    ad = Ad(
        external_id="c117-meta-freshness",
        title="Meta freshness 医療ダイエット",
        advertiser_name="Meta Advertiser",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        thumbnail_url="https://cdn.example.com/thumb.jpg",
        spend=5200,
        impressions=2300,
        ad_metadata={
            "metric_source": "api",
            "creative_source": "playwright_render_ad",
            "lp_source": "httpx",
            "last_meta_success_at": datetime.now(timezone.utc).isoformat(),
            "meta_quality_state": "real",
            "meta_recovery_reason": "detail_enrich_failed",
            "priority_score": 77,
            "priority_score_source": "bedrock",
            "review_required": True,
            "review_reason": "manual_review_required",
            "prompt_version": "classification-v1",
        },
        updated_at=datetime.now(timezone.utc),
    )
    stale_ad = Ad(
        external_id="c117-meta-stale",
        title="Stale Meta freshness 広告",
        advertiser_name="Meta Advertiser 2",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        thumbnail_url="https://cdn.example.com/thumb2.jpg",
        ad_metadata={
            "metric_source": "api",
            "creative_source": "api",
            "lp_source": "api",
            "last_meta_success_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            "meta_recovery_reason": "token_expired",
        },
        updated_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    session.add_all([ad, stale_ad])
    session.commit()

    detail = rankings._build_ad_detail(ad)
    for field in (
        "metric_source",
        "creative_source",
        "lp_source",
        "metric_status",
        "creative_status",
        "lp_status",
        "freshness_status",
        "last_meta_success_at",
        "meta_quality_state",
        "meta_recovery_reason",
    ):
        assert field in detail

    freshness = rankings.get_meta_freshness(stale_ad.id)
    assert freshness["metric_source"] == "api"
    assert freshness["creative_source"] == "api"
    assert freshness["lp_source"] == "api"
    assert freshness["freshness_status"] == "stale"
    assert freshness["meta_quality_state"] == "stale"
    assert freshness["meta_recovery_reason"] == "token_expired"

    search = rankings.search_ads_simple(q="Meta Advertiser", page=1, page_size=20)
    assert search["total"] >= 1
    item = search["items"][0]
    assert "metric_source" in item
    assert "creative_source" in item
    assert "lp_source" in item
    assert "meta_quality_state" in item
