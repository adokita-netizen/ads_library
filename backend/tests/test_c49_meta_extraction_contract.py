from contextlib import contextmanager

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.analysis import AdAnalysis, TextDetection, Transcription


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


def _mk_ad(external_id: str, title: str, metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        description="説明",
        advertiser_name="広告主",
        image_url="https://example.com/image.jpg",
        video_url="https://example.com/video.mp4",
        snapshot_url="https://example.com/snapshot.jpg",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_meta_extraction_complete_case(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = _mk_ad(
        "c49_full_1",
        "Meta広告",
        metadata={"extract_quality_score": 82, "extraction_method": "meta_api"},
    )
    session.add(ad)
    session.flush()

    analysis = AdAnalysis(ad_id=ad.id)
    session.add(analysis)
    session.flush()
    session.add(
        TextDetection(
            analysis_id=analysis.id,
            frame_number=1,
            timestamp_seconds=0.2,
            text="OCRテキスト",
            confidence=0.95,
            bbox_x=0.1,
            bbox_y=0.1,
            bbox_width=0.3,
            bbox_height=0.2,
        )
    )
    session.add(
        Transcription(
            analysis_id=analysis.id,
            text="音声テキスト",
            start_time_ms=0,
            end_time_ms=1000,
            confidence=0.9,
        )
    )
    session.commit()

    res = rankings.get_meta_extraction(ad.id)
    assert res["ad_id"] == ad.id
    assert res["creative_urls"]["video"] != ""
    assert res["text_fields"]["ocr"] == ["OCRテキスト"]
    assert res["quality_score"] == 82
    assert isinstance(res["missing_fields"], list)


def test_meta_extraction_partial_case_has_stable_shape(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = Ad(
        external_id="c49_partial_1",
        title="",
        description="",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={},
    )
    session.add(ad)
    session.commit()

    res = rankings.get_meta_extraction(ad.id)
    assert set(res.keys()) == {
        "ad_id",
        "creative_urls",
        "text_fields",
        "extract_source",
        "quality_score",
        "missing_fields",
    }
    assert "creative_urls" in res["missing_fields"]
    assert "text_fields.title" in res["missing_fields"]


def test_meta_extraction_retry_failure_case_returns_reason_code(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = _mk_ad("c49_retry_1", "Retry広告", metadata={})
    session.add(ad)
    session.commit()

    def _raise_timeout(*_args, **_kwargs):
        raise RuntimeError("timeout while dispatching")

    monkeypatch.setattr("app.tasks.dispatcher.dispatch_task", _raise_timeout, raising=False)
    res = rankings.retry_meta_extraction(ad.id)
    assert res["ad_id"] == ad.id
    assert res["dispatched"] is False
    assert res["failure_reason_code"] == "timeout"
    assert isinstance(res["strategy"], list)
    assert any(step["status"] == "failed" for step in res["strategy"])

