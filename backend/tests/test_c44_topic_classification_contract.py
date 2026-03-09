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


def _mk_ad(external_id: str, title: str, metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_classify_topic_raw_representative_samples():
    rankings = _import_rankings_module()

    samples = [
        ("GLP-1 医療ダイエット", "medical_diet"),
        ("新NISAで資産運用を始める", "finance"),
        ("英語学習スクール講座", "education"),
        ("EC通販の初回購入キャンペーン", "ec_d2c"),
        ("アプリを無料インストール", "app"),
    ]

    for text, expected in samples:
        body = rankings._TopicClassifyBody(text=text)
        res = rankings.classify_topic(body)
        assert expected in res["topic_tags"]
        assert isinstance(res["confidence"], float)
        assert "model_version" in res


def test_classify_topic_by_ad_id_persists_contract_fields(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = _mk_ad("c44_ad_1", "GLP-1 メディカルダイエット")
    session.add(ad)
    session.commit()

    body = rankings._TopicClassifyBody(ad_id=ad.id)
    res = rankings.classify_topic(body)
    session.refresh(ad)
    meta = ad.ad_metadata or {}

    assert res["ad_id"] == ad.id
    assert "topic_tags" in meta
    assert "topic_confidence" in meta
    assert "topic_evidence" in meta
    assert "hit_drivers" in meta
    assert isinstance(meta["topic_tags"], list)
    assert isinstance(meta["topic_evidence"], list)


def test_topic_gap_report_response_shape_and_gap(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    # Expected finance by text, but classified as education => false negative for finance.
    ad1 = _mk_ad(
        "c44_gap_1",
        "NISA 資産運用 はじめ方",
        metadata={"topic_label": "education"},
    )
    # Correctly classified education.
    ad2 = _mk_ad(
        "c44_gap_2",
        "英語スクールの学習講座",
        metadata={"topic_label": "education"},
    )
    session.add_all([ad1, ad2])
    session.commit()

    res = rankings.topic_gap_report(false_negative_limit=10)
    assert "summary" in res
    assert "categories" in res
    assert isinstance(res["categories"], list)
    finance = next((c for c in res["categories"] if c["topic_label"] == "finance"), None)
    assert finance is not None
    assert "expected_volume" in finance
    assert "classified_volume" in finance
    assert "gap" in finance
    assert "false_negative_candidates" in finance
    assert any(c["ad_id"] == ad1.id for c in finance["false_negative_candidates"])
