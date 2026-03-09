from contextlib import contextmanager

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.services.ad360_unification import audit_ad360_completeness, build_ad360_sections, summarize_ad360_completeness


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
        advertiser_name="広告主",
        destination_url="https://example.com/lp",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_a46_ad360_sections_and_completeness_use_lp_fallbacks():
    ad = _mk_ad(
        "a46_1",
        "GLP-1 広告",
        metadata={
            "topic_tags": ["medical_diet"],
            "topic_evidence": ["glp-1"],
            "hit_drivers": ["appeal_medical_authority"],
            "latest_hit_score": 81,
            "lp_info": {"final_url": "https://example.com/final", "headline": "LP"},
        },
    )
    sections = build_ad360_sections(ad)
    completeness = summarize_ad360_completeness(sections, threshold=0.8)

    assert sections["lp"]["data"]["final_url"] == "https://example.com/final"
    assert sections["analysis"]["data"]["topic_tags"] == ["medical_diet"]
    assert completeness["required_field_count"] > 0
    assert "lp.final_url" not in completeness["missing_required_fields"]


def test_a46_audit_ad360_completeness_marks_reprocess_and_quarantine(session):
    poor = Ad(
        external_id="a46_poor",
        title="",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={},
    )
    good = _mk_ad(
        "a46_good",
        "AGA 広告",
        metadata={
            "topic_tags": ["aga"],
            "topic_evidence": ["aga"],
            "hit_drivers": ["appeal_medical_authority"],
            "latest_hit_score": 77,
            "lp_info": {"final_url": "https://example.com/final"},
        },
    )
    session.add_all([poor, good])
    session.commit()

    report = audit_ad360_completeness(session, threshold=0.8)
    session.commit()
    session.refresh(poor)
    session.refresh(good)

    assert poor.id in report["queued_reprocess_ad_ids"]
    assert poor.ad_metadata["ad360_needs_reprocess"] is True
    assert poor.ad_metadata["quarantine_reason"] == "ad360_low_completeness"
    assert good.ad_metadata["ad360_completeness"] > 0.0


def test_a46_ad360_endpoint_returns_completeness_block(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad = _mk_ad(
        "a46_endpoint",
        "NISA 広告",
        metadata={
            "topic_tags": ["finance"],
            "topic_evidence": ["新nisa"],
            "hit_drivers": ["appeal_price"],
            "latest_hit_score": 73,
            "lp_info": {"final_url": "https://example.com/final"},
        },
    )
    session.add(ad)
    session.commit()

    res = rankings.get_ad360(ad.id)
    assert "completeness" in res
    assert "completeness_pct" in res["completeness"]
    assert isinstance(res["completeness"]["missing_required_fields"], list)
