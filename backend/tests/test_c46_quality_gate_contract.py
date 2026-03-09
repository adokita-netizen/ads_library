from contextlib import contextmanager

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


def _mk_ad(
    *,
    external_id: str,
    title: str,
    destination_url: str,
    snapshot_url: str,
    image_url: str,
    metadata: dict | None = None,
) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        destination_url=destination_url,
        snapshot_url=snapshot_url,
        image_url=image_url,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_quality_gate_passes_with_sufficient_quality(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad1 = _mk_ad(
        external_id="qg_ok_1",
        title="GLP-1 医療ダイエット",
        destination_url="https://example.com/lp1",
        snapshot_url="https://example.com/s1",
        image_url="https://example.com/i1.jpg",
        metadata={"extract_quality_score": 80, "topic_confidence": 0.9},
    )
    ad2 = _mk_ad(
        external_id="qg_ok_2",
        title="NISA 資産運用",
        destination_url="https://example.com/lp2",
        snapshot_url="https://example.com/s2",
        image_url="https://example.com/i2.jpg",
        metadata={"extract_quality_score": 75, "topic_confidence": 0.85},
    )
    session.add_all([ad1, ad2])
    session.commit()

    body = rankings._QualityGateEvaluateBody(
        ad_ids=[ad1.id, ad2.id],
        min_count=2,
        min_required_fill_rate=0.8,
        min_image_quality_score=40,
        min_topic_confidence=0.6,
    )
    res = rankings.evaluate_quality_gate(body)
    assert res["passed"] is True
    assert res["reasons"] == []


def test_quality_gate_returns_structured_ng_reasons(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = _mk_ad(
        external_id="qg_ng_1",
        title="",
        destination_url="",
        snapshot_url="",
        image_url="",
        metadata={"extract_quality_score": 10, "topic_confidence": 0.2},
    )
    session.add(ad)
    session.commit()

    body = rankings._QualityGateEvaluateBody(
        ad_ids=[ad.id],
        min_count=3,
        min_required_fill_rate=0.9,
        min_image_quality_score=50,
        min_topic_confidence=0.7,
    )
    res = rankings.evaluate_quality_gate(body)
    assert res["passed"] is False
    codes = {r["code"] for r in res["reasons"]}
    assert "minimum_count_not_met" in codes
    assert "required_fields_fill_rate_low" in codes
    assert "image_quality_score_low" in codes
    assert "topic_confidence_low" in codes
    assert len(res["suggestions"]) >= 1

