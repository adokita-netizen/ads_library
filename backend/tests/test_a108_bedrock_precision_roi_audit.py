from datetime import date, datetime, timezone

from app.models.ad import Ad, AdCategoryEnum, AdPlatformEnum, AdStatusEnum
from app.services.data_quality_report import build_creative_library_audit


def _mk_ad(
    external_id: str,
    *,
    title: str,
    platform: AdPlatformEnum,
    category: AdCategoryEnum,
    spend=None,
    impressions=None,
    metadata: dict | None = None,
) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=platform,
        category=category,
        status=AdStatusEnum.PENDING,
        advertiser_name="bedrock tester",
        spend=spend,
        impressions=impressions,
        ad_metadata=metadata or {},
        updated_at=datetime(2026, 3, 8, 9, tzinfo=timezone.utc),
    )


def test_a108_bedrock_precision_roi_audit_builds_summary_and_review_policy(session, monkeypatch, tmp_path):
    import app.services.data_quality_report as data_quality_report

    monkeypatch.setattr(data_quality_report, "_AUDIT_REPORTS_FILE", tmp_path / "creative_library_audit_reports.json")

    session.add_all(
        [
            _mk_ad(
                "a108-rule",
                title="美容クリニックの新プラン",
                platform=AdPlatformEnum.FACEBOOK,
                category=AdCategoryEnum.BEAUTY,
                spend=4000,
                impressions=1200,
                metadata={
                    "language": "ja",
                    "language_source": "rule",
                    "jp_char_ratio": 0.9,
                    "product_category": "beauty",
                    "product_category_source": "rule",
                    "topic_label": "medical_diet",
                    "topic_tags": ["medical_diet"],
                    "topic_source": "rule",
                    "priority_score": 72,
                    "extract_quality_score": 80,
                },
            ),
            _mk_ad(
                "a108-bedrock-good",
                title="GLP-1 医療ダイエット",
                platform=AdPlatformEnum.INSTAGRAM,
                category=AdCategoryEnum.BEAUTY,
                spend=5500,
                impressions=1400,
                metadata={
                    "language": "ja",
                    "language_source": "bedrock",
                    "jp_char_ratio": 0.8,
                    "language_confidence": 0.95,
                    "product_category": "beauty",
                    "product_category_source": "bedrock",
                    "product_category_confidence": 0.93,
                    "topic_label": "medical_diet",
                    "topic_tags": ["medical_diet"],
                    "topic_source": "bedrock",
                    "topic_confidence": 0.91,
                    "priority_score": 78,
                    "priority_score_source": "bedrock",
                    "extract_quality_score": 88,
                },
            ),
            _mk_ad(
                "a108-bedrock-bad",
                title="GLP-1 医療ダイエット",
                platform=AdPlatformEnum.FACEBOOK,
                category=AdCategoryEnum.BEAUTY,
                metadata={
                    "language": "en",
                    "language_source": "bedrock",
                    "jp_char_ratio": 0.7,
                    "language_confidence": 0.94,
                    "product_category": "finance",
                    "product_category_source": "bedrock",
                    "product_category_confidence": 0.92,
                    "topic_label": "finance",
                    "topic_tags": ["medical_diet"],
                    "topic_source": "bedrock",
                    "topic_confidence": 0.93,
                    "priority_score": 68,
                    "priority_score_source": "bedrock",
                    "review_required": True,
                    "extract_quality_score": 35,
                },
            ),
            _mk_ad(
                "a108-review",
                title="新プラン",
                platform=AdPlatformEnum.YOUTUBE,
                category=AdCategoryEnum.FINANCE,
                metadata={
                    "jp_char_ratio": 0.05,
                    "priority_score": 85,
                    "extract_quality_score": 20,
                    "needs_topic_review": True,
                },
            ),
        ]
    )
    session.commit()

    report = build_creative_library_audit(session, target_date=date(2026, 3, 8), persist=True)["creative_library_audit"]
    audit = report["bedrock_precision_roi_audit"]

    assert audit["summary"]["total_ads"] == 4
    assert audit["summary"]["rule_only_count"] == 1
    assert audit["summary"]["bedrock_used_count"] == 1
    assert audit["summary"]["manual_review_count"] == 2
    assert audit["summary"]["bedrock_valuable_count"] >= 2
    assert audit["accuracy_proxy"]["language"]["mismatch_count"] == 1
    assert audit["accuracy_proxy"]["product_category"]["mismatch_count"] == 1
    assert audit["accuracy_proxy"]["topic_label"]["mismatch_count"] == 1
    assert audit["by_product_false_positives"][0]["product_category"] == "finance"
    assert audit["by_product_false_negatives"][0]["product_category"] == "beauty"
    assert any(item["ad_id"] == 3 for item in audit["manual_review_queue"])
    assert any("high-priority ad is missing" in item for item in audit["review_required_policy"]["send_if"])
    assert any("ad is high priority" in item for item in audit["bedrock_value_policy"]["call_if"])
    assert audit["priority_score_roi"]["avg_priority_with_actual_metrics"] > 0
    assert audit["priority_score_roi"]["real_metrics_capture_by_priority_bucket"][0]["label"] == "high"
