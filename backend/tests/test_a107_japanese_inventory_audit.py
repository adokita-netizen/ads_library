from datetime import date, datetime, timezone

from app.models.ad import Ad, AdCategoryEnum, AdPlatformEnum, AdStatusEnum
from app.services.data_quality_report import build_creative_library_audit


def _mk_ad(external_id: str, *, title: str, platform: AdPlatformEnum, metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=platform,
        category=AdCategoryEnum.OTHER,
        status=AdStatusEnum.PENDING,
        advertiser_name="lang tester",
        ad_metadata=metadata or {},
        updated_at=datetime.now(timezone.utc),
    )


def test_a107_japanese_inventory_audit_builds_counts_and_review_queue(session, monkeypatch, tmp_path):
    import app.services.data_quality_report as data_quality_report

    monkeypatch.setattr(data_quality_report, "_AUDIT_REPORTS_FILE", tmp_path / "creative_library_audit_reports.json")

    session.add_all([
        _mk_ad(
            "a107-jp",
            title="医療ダイエットで痩せる",
            platform=AdPlatformEnum.FACEBOOK,
            metadata={"language": "ja", "language_source": "bedrock", "jp_char_ratio": 0.8},
        ),
        _mk_ad(
            "a107-nonjp",
            title="medical diet campaign",
            platform=AdPlatformEnum.INSTAGRAM,
            metadata={"language": "en", "language_source": "bedrock", "jp_char_ratio": 0.0, "exclude_from_analysis": True, "exclude_reason": "non_japanese"},
        ),
        _mk_ad(
            "a107-mismatch",
            title="GLP-1 医療ダイエット",
            platform=AdPlatformEnum.FACEBOOK,
            metadata={"language": "en", "language_source": "bedrock", "jp_char_ratio": 0.4},
        ),
        _mk_ad(
            "a107-unknown",
            title="GLP-1 campaign",
            platform=AdPlatformEnum.YOUTUBE,
            metadata={"jp_char_ratio": 0.05},
        ),
    ])
    session.commit()

    report = build_creative_library_audit(session, target_date=date(2026, 3, 8), persist=True)["creative_library_audit"]
    audit = report["japanese_inventory_audit"]

    assert audit["summary"]["total_ads"] == 4
    assert audit["summary"]["jp_count"] == 1
    assert audit["summary"]["non_jp_count"] == 2
    assert audit["summary"]["unknown_count"] == 1
    assert audit["summary"]["excluded_count"] == 1
    assert audit["summary"]["manual_review_count"] >= 2
    assert audit["summary"]["coverage"]["jp_char_ratio"]["count"] == 4
    assert audit["summary"]["coverage"]["language_source"]["count"] == 3
    assert audit["bedrock_rule_mismatch_samples"][0]["ad_id"] == 3
    assert any(item["ad_id"] == 3 for item in audit["manual_review_queue"])
    assert "exclude_if" in audit["exclusion_policy"]
