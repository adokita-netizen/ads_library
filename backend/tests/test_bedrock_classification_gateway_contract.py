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


def test_bedrock_classification_gateway_success_and_timeout_contract(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    success_ad = Ad(
        external_id="c114-bedrock-ok",
        title="GLP-1 医療ダイエット",
        advertiser_name="Clinic A",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "bedrock",
            "language_confidence": 0.95,
            "product_category": "beauty",
            "product_category_source": "bedrock",
            "product_category_confidence": 0.93,
            "topic_label": "medical_diet",
            "topic_source": "bedrock",
            "topic_confidence": 0.91,
            "bedrock_model_name": "anthropic.claude-3-5-sonnet",
            "bedrock_classified_at": "2026-03-08T09:00:00+00:00",
        },
    )
    timeout_ad = Ad(
        external_id="c114-bedrock-timeout",
        title="美容クリニック",
        advertiser_name="Clinic B",
        platform=AdPlatformEnum.INSTAGRAM,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "rule",
            "product_category": "beauty",
            "product_category_source": "rule",
            "classification_status": "timeout",
            "manual_review": True,
        },
    )
    session.add_all([success_ad, timeout_ad])
    session.commit()

    success = rankings.get_bedrock_classification_gateway(success_ad.id)
    assert success["status"] == "success"
    assert success["language"] == "ja"
    assert success["product_category"] == "beauty"
    assert success["topic_label"] == "medical_diet"
    assert success["model_name"] == "anthropic.claude-3-5-sonnet"
    assert success["fallback_applied"] is False

    timeout = rankings.get_bedrock_classification_gateway(timeout_ad.id)
    assert timeout["status"] == "timeout"
    assert timeout["fallback_applied"] is True
    assert timeout["error_code"] == "timeout"
    assert "rule_fallback_used" in timeout["reasons"]
    assert "manual_review_required" in timeout["reasons"]
