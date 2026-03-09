from contextlib import contextmanager
from types import SimpleNamespace

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, MediaExtractionStatus


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
    yield session


def _mk_ad(
    *,
    external_id: str,
    title: str,
    platform: AdPlatformEnum = AdPlatformEnum.FACEBOOK,
    status: AdStatusEnum = AdStatusEnum.PENDING,
    media_status: str | None = None,
    snapshot_url: str | None = "https://example.com/snapshot",
    metadata: dict | None = None,
) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=platform,
        status=status,
        snapshot_url=snapshot_url,
        media_extraction_status=media_status,
        ad_metadata=metadata or {},
    )


def test_batch_extract_media_dispatches_retry_candidates(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    retry_ad = _mk_ad(
        external_id="retry_only_1",
        title="GLP-1 再抽出候補",
        media_status=MediaExtractionStatus.COMPLETED,
        metadata={"needs_media_retry": True, "extract_quality_score": 20},
    )
    session.add(retry_ad)
    session.commit()

    import app.tasks.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher, "dispatch_task", lambda *_args, **_kwargs: SimpleNamespace(id="msg-retry-1"))

    result = rankings.batch_extract_media(limit=1)
    session.refresh(retry_ad)

    assert result["dispatched"] == 1
    assert result["errors"] == 0
    assert result["retry_candidates_dispatched"] == 1
    assert retry_ad.media_extraction_status == MediaExtractionStatus.DISPATCHED
    assert (retry_ad.ad_metadata or {}).get("needs_media_retry") is False
    assert int((retry_ad.ad_metadata or {}).get("media_retry_count", 0)) >= 1


def test_batch_extract_media_mixed_pending_and_retry(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    pending_ad = _mk_ad(
        external_id="pending_1",
        title="通常 pending 広告",
        media_status=MediaExtractionStatus.PENDING,
        metadata={},
    )
    retry_ad = _mk_ad(
        external_id="retry_2",
        title="低品質再抽出広告",
        media_status=MediaExtractionStatus.COMPLETED,
        metadata={"needs_media_retry": True, "extract_quality_score": 15},
    )
    session.add_all([pending_ad, retry_ad])
    session.commit()

    import app.tasks.dispatcher as dispatcher
    monkeypatch.setattr(
        dispatcher,
        "dispatch_task",
        lambda *_args, **kwargs: SimpleNamespace(id=f"msg-{kwargs.get('ad_id')}"),
    )

    result = rankings.batch_extract_media(limit=2)
    session.refresh(pending_ad)
    session.refresh(retry_ad)

    assert result["dispatched"] == 2
    assert result["retry_candidates_dispatched"] == 1
    assert pending_ad.media_extraction_status == MediaExtractionStatus.DISPATCHED
    assert retry_ad.media_extraction_status == MediaExtractionStatus.DISPATCHED
    assert (retry_ad.ad_metadata or {}).get("needs_media_retry") is False


def test_topic_filter_returns_expected_set_and_detail_has_topic_fields(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    match_ad = _mk_ad(
        external_id="topic_match_1",
        title="GLP-1 ダイエットの新常識",
        media_status=MediaExtractionStatus.COMPLETED,
        metadata={
            "topic_label": "medical_diet",
            "topic_confidence": 0.93,
            "matched_terms": ["GLP-1", "医療ダイエット"],
            "needs_topic_review": False,
            "latest_hit_score": 72,
        },
    )
    non_match_ad = _mk_ad(
        external_id="topic_other_1",
        title="脱毛キャンペーン",
        media_status=MediaExtractionStatus.COMPLETED,
        metadata={
            "topic_label": "hair_removal",
            "topic_confidence": 0.88,
            "matched_terms": ["脱毛"],
            "needs_topic_review": False,
            "latest_hit_score": 60,
        },
    )
    session.add_all([match_ad, non_match_ad])
    session.commit()

    response = rankings.get_pro_ranking(
        fine_genre=None,
        genre=None,
        platform=None,
        sort_by="total_views",
        period="all",
        snapshot_date=None,
        search_text=None,
        q=None,
        page=1,
        per_page=20,
        video_format=None,
        ad_format=None,
        destination_type=None,
        transition_type=None,
        destination_domain=None,
        topic="glp-1",
        is_affiliate=None,
        view_count_min=None,
        view_count_max=None,
        like_count_min=None,
        like_count_max=None,
        spend_min_jpy=None,
        spend_max_jpy=None,
        date_from=None,
        date_to=None,
        exclude_advertisers=None,
        exclude_domains=None,
    )
    items = response.get("items", [])

    assert len(items) == 1
    assert items[0]["ad_id"] == match_ad.id
    assert items[0]["topic_label"] == "medical_diet"
    assert items[0]["topic_confidence"] == 0.93
    assert items[0]["matched_terms"] == ["GLP-1", "医療ダイエット"]
    assert items[0]["needs_topic_review"] is False

    detail = rankings._build_ad_detail(match_ad)
    assert detail["topic_label"] == "medical_diet"
    assert detail["topic_confidence"] == 0.93
    assert detail["matched_terms"] == ["GLP-1", "医療ダイエット"]
    assert detail["needs_topic_review"] is False
