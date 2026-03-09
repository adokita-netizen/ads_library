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


def test_bedrock_decision_success_and_rule_override_contract(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "_db_session_scope", lambda: _session_scope(session))

    success_ad = Ad(
        external_id="c115-bedrock-success",
        title="GLP-1 医療ダイエット",
        advertiser_name="Clinic A",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "bedrock",
            "language_confidence": 0.95,
            "product_category": "beauty",
            "product_subcategory": "medical_weight_loss",
            "product_category_source": "bedrock",
            "product_category_confidence": 0.93,
            "topic_label": "medical_diet",
            "topic_source": "bedrock",
            "topic_confidence": 0.91,
            "priority_score": 88,
            "priority_score_source": "bedrock",
            "classification_source": "bedrock",
            "bedrock_model_name": "anthropic.claude-3-5-sonnet",
            "prompt_version": "classification-v1",
            "bedrock_classified_at": "2026-03-08T09:00:00+00:00",
            "creative_analysis": {"offer_type": "discount"},
            "funnel_type": "single_lp",
        },
    )
    override_ad = Ad(
        external_id="c115-rule-override",
        title="美容クリニック 比較",
        advertiser_name="Clinic B",
        platform=AdPlatformEnum.INSTAGRAM,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "rule_override",
            "product_category": "beauty",
            "product_subcategory": "skin_care",
            "product_category_source": "rule_override",
            "topic_label": "beauty_offer",
            "topic_source": "rule_override",
            "priority_score": 54,
            "priority_score_source": "rule_override",
            "review_required": True,
            "review_reason": "taxonomy_override_review",
            "classification_model_name": "anthropic.claude-3-5-sonnet",
            "prompt_version": "classification-v1",
            "classified_at": "2026-03-08T08:30:00+00:00",
            "offer_type": "trial",
            "funnel_type": "article_to_lp",
        },
    )
    session.add_all([success_ad, override_ad])
    session.commit()

    success = rankings.get_bedrock_decision(success_ad.id)
    assert success["status"] == "success"
    assert success["language"] == "ja"
    assert success["product_category"] == "beauty"
    assert success["product_subcategory"] == "medical_weight_loss"
    assert success["offer_type"] == "discount"
    assert success["funnel_type"] == "single_lp"
    assert success["priority_score"] == 88.0
    assert success["priority_reason"] == "bedrock_priority_score"
    assert success["review_required"] is False
    assert success["confidence_band"] == "high"
    assert success["prompt_version"] == "classification-v1"

    override = rankings.get_bedrock_decision(override_ad.id)
    assert override["source_priority"][0] == "rule_override"
    assert override["priority_reason"] == "rule_override"
    assert override["review_required"] is True
    assert override["review_reason"] == "taxonomy_override_review"
    assert override["model_name"] == "anthropic.claude-3-5-sonnet"


def test_bedrock_decision_timeout_partial_and_invalid_json_fallback_contract(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "_db_session_scope", lambda: _session_scope(session))

    timeout_ad = Ad(
        external_id="c115-timeout",
        title="美容クリニック",
        advertiser_name="Clinic C",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "rule",
            "product_category": "beauty",
            "product_category_source": "rule",
            "classification_status": "timeout",
            "prompt_version": "classification-v1",
        },
    )
    partial_ad = Ad(
        external_id="c115-partial",
        title="GLP-1",
        advertiser_name="Clinic D",
        platform=AdPlatformEnum.INSTAGRAM,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "bedrock",
            "product_category": "beauty",
            "product_category_source": "bedrock",
            "topic_source": "bedrock",
            "priority_score": 67,
            "classification_source": "bedrock",
            "prompt_version": "classification-v1",
        },
    )
    invalid_json_ad = Ad(
        external_id="c115-invalid-json",
        title="比較LP",
        advertiser_name="Clinic E",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "rule",
            "product_category": "beauty",
            "product_subcategory": "clinic",
            "product_category_source": "rule",
            "classification_status": "invalid_json",
            "classification_model_name": "anthropic.claude-3-5-sonnet",
            "priority_score": 41,
            "offer_type": "consultation",
            "prompt_version": "classification-v1",
        },
    )
    session.add_all([timeout_ad, partial_ad, invalid_json_ad])
    session.commit()

    timeout = rankings.get_bedrock_decision(timeout_ad.id)
    assert timeout["status"] == "timeout"
    assert timeout["fallback_applied"] is True
    assert timeout["error_code"] == "timeout"
    assert timeout["review_required"] is True
    assert timeout["review_reason"] == "bedrock_timeout"

    partial = rankings.get_bedrock_decision(partial_ad.id)
    assert partial["status"] == "partial"
    assert partial["fallback_applied"] is True
    assert partial["error_code"] == "partial_bedrock_result"
    assert partial["review_required"] is True
    assert partial["review_reason"] == "partial_bedrock_result"

    invalid_json = rankings.get_bedrock_decision(invalid_json_ad.id)
    assert invalid_json["status"] == "fallback"
    assert invalid_json["fallback_applied"] is True
    assert invalid_json["error_code"] == "invalid_json"
    assert invalid_json["review_required"] is True
    assert invalid_json["review_reason"] == "invalid_json"
