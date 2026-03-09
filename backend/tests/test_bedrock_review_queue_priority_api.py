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


def test_bedrock_review_queue_and_high_priority_actual_metrics_contract(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "_db_session_scope", lambda: _session_scope(session))

    high_review = Ad(
        external_id="c116-high-review",
        title="GLP-1 医療ダイエット",
        advertiser_name="Clinic A",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "bedrock",
            "product_category": "beauty",
            "product_subcategory": "medical_weight_loss",
            "product_category_source": "bedrock",
            "topic_label": "medical_diet",
            "topic_source": "bedrock",
            "priority_score": 86,
            "priority_score_source": "bedrock",
            "classification_source": "bedrock",
            "review_required": True,
            "review_reason": "manual_review_required",
            "prompt_version": "classification-v1",
        },
    )
    medium_real = Ad(
        external_id="c116-medium-real",
        title="美容サプリ",
        advertiser_name="Brand B",
        platform=AdPlatformEnum.INSTAGRAM,
        status=AdStatusEnum.PENDING,
        spend=3200,
        impressions=1400,
        view_count=1500,
        ad_metadata={
            "language": "ja",
            "language_source": "rule",
            "product_category": "beauty",
            "product_subcategory": "supplement",
            "product_category_source": "rule",
            "topic_label": "beauty_offer",
            "topic_source": "rule",
            "priority_score": 55,
            "priority_score_source": "rule",
            "prompt_version": "classification-v1",
        },
    )
    manual_high = Ad(
        external_id="c116-manual-high",
        title="比較クリニック",
        advertiser_name="Clinic C",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "rule_override",
            "product_category": "beauty",
            "product_subcategory": "clinic",
            "product_category_source": "rule_override",
            "topic_label": "beauty_offer",
            "topic_source": "rule_override",
            "priority_score": 74,
            "priority_score_source": "rule_override",
            "review_required": True,
            "review_reason": "taxonomy_override_review",
            "prompt_version": "classification-v1",
        },
    )
    session.add_all([high_review, medium_real, manual_high])
    session.commit()

    review_queue = rankings.get_bedrock_review_queue(
        q=None,
        only_high_priority=False,
        only_review_required=True,
        priority_min=None,
        limit=10,
    )
    assert review_queue["total"] == 2
    assert review_queue["items"][0]["ad_id"] == high_review.id
    assert review_queue["items"][0]["priority_bucket"] == "high"
    assert review_queue["items"][0]["review_required"] is True
    assert review_queue["items"][0]["provenance"]["priority"] == "ai"
    assert review_queue["items"][1]["provenance_summary"] == "manual"

    actual_metrics = rankings.get_high_priority_actual_metrics(
        q=None,
        only_high_priority=True,
        only_review_required=False,
        priority_min=70.0,
        limit=10,
    )
    assert actual_metrics["total"] == 2
    assert actual_metrics["items"][0]["ad_id"] == high_review.id
    assert actual_metrics["items"][0]["actual_metrics_present"] is False
    assert actual_metrics["items"][0]["actual_metrics_focus"] is True
    assert all(item["priority_score"] >= 70 for item in actual_metrics["items"])


def test_search_simple_exposes_bedrock_review_fields(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "_db_session_scope", lambda: _session_scope(session))

    ad = Ad(
        external_id="c116-search",
        title="GLP-1 医療ダイエット",
        advertiser_name="Clinic Search",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "language": "ja",
            "language_source": "bedrock",
            "product_category": "beauty",
            "product_subcategory": "medical_weight_loss",
            "product_category_source": "bedrock",
            "topic_label": "medical_diet",
            "topic_source": "bedrock",
            "priority_score": 84,
            "priority_score_source": "bedrock",
            "review_required": True,
            "review_reason": "manual_review_required",
            "prompt_version": "classification-v1",
        },
    )
    session.add(ad)
    session.commit()

    result = rankings.search_ads_simple(q="Clinic Search", page=1, page_size=20)
    assert result["total"] == 1
    item = result["items"][0]
    assert item["priority_score"] == 84.0
    assert item["review_required"] is True
    assert item["review_reason"] == "manual_review_required"
    assert item["confidence_band"] == "low"
    assert item["provenance"]["priority"] == "ai"
