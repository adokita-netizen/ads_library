from contextlib import contextmanager

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.analysis import AdAnalysis, TextDetection, Transcription
from app.models.landing_page import LandingPage, LPAnalysis, LPStatusEnum, LPTypeEnum


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
        destination_url="https://example.com/lp",
        image_url="https://example.com/image.jpg",
        snapshot_url="https://example.com/snapshot.jpg",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_ad360_full_data_contract(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = _mk_ad(
        "c48_full_1",
        "GLP-1 広告",
        metadata={
            "latest_hit_score": 82,
            "topic_label": "medical_diet",
            "topic_confidence": 0.91,
            "topic_tags": ["medical_diet"],
            "matched_terms": ["glp-1"],
            "creative_analysis": {"hook_type": "question"},
            "extract_quality_score": 78,
        },
    )
    session.add(ad)
    session.flush()

    analysis = AdAnalysis(ad_id=ad.id, hook_text="導入フック", cta_text="今すぐ", winning_score=88.0)
    session.add(analysis)
    session.flush()
    session.add(
        TextDetection(
            analysis_id=analysis.id,
            frame_number=1,
            timestamp_seconds=0.2,
            text="GLP-1",
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
            text="これはトランスクリプトです",
            start_time_ms=0,
            end_time_ms=1000,
            confidence=0.9,
        )
    )

    lp = LandingPage(
        ad_id=ad.id,
        url="https://example.com/lp",
        url_hash="hash_c48_full",
        domain="example.com",
        title="LPタイトル",
        lp_type=LPTypeEnum.ARTICLE,
        status=LPStatusEnum.COMPLETED,
    )
    session.add(lp)
    session.flush()
    session.add(
        LPAnalysis(
            landing_page_id=lp.id,
            overall_quality_score=74.0,
            conversion_potential_score=71.0,
            trust_score=69.0,
            urgency_score=62.0,
        )
    )
    session.commit()

    res = rankings.get_ad360(ad.id)
    assert res["ad_id"] == ad.id
    assert set(res["sections"].keys()) == {"core", "creative", "text", "analysis", "lp", "quality"}
    assert res["sections"]["lp"]["data"]["has_lp"] is True
    assert res["sections"]["analysis"]["data"]["topic_label"] == "medical_diet"
    assert isinstance(res["sections"]["core"]["missing_fields"], list)


def test_ad360_missing_data_keeps_stable_structure(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = Ad(
        external_id="c48_missing_1",
        title="",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={},
    )
    session.add(ad)
    session.commit()

    res = rankings.get_ad360(ad.id)
    assert set(res["sections"].keys()) == {"core", "creative", "text", "analysis", "lp", "quality"}
    assert res["sections"]["lp"]["data"]["has_lp"] is False
    assert len(res["sections"]["creative"]["missing_fields"]) >= 1
    assert len(res["sections"]["text"]["missing_fields"]) >= 1


def test_ad360_not_found_returns_404(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    res = rankings.get_ad360(999999)
    assert getattr(res, "status_code", 200) == 404

