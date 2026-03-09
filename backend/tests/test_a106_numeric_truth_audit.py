from datetime import date, datetime, timedelta, timezone

from app.models.ad import Ad, AdCategoryEnum, AdPlatformEnum, AdStatusEnum
from app.services.data_quality_report import build_creative_library_audit


def _mk_ad(
    external_id: str,
    *,
    platform: AdPlatformEnum,
    category: AdCategoryEnum | None = None,
    title: str = "ad",
    spend=None,
    impressions=None,
    reach=None,
    view_count=None,
    metadata: dict | None = None,
    updated_at: datetime | None = None,
) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=platform,
        category=category,
        status=AdStatusEnum.PENDING,
        advertiser_name="numeric tester",
        spend=spend,
        impressions=impressions,
        reach=reach,
        view_count=view_count,
        ad_metadata=metadata or {},
        updated_at=updated_at or datetime.now(timezone.utc),
    )


def test_a106_numeric_truth_audit_builds_summary_and_backfill_targets(session, monkeypatch, tmp_path):
    import app.services.data_quality_report as data_quality_report

    monkeypatch.setattr(data_quality_report, "_AUDIT_REPORTS_FILE", tmp_path / "creative_library_audit_reports.json")

    session.add_all([
        _mk_ad(
            "a106-real",
            platform=AdPlatformEnum.FACEBOOK,
            category=AdCategoryEnum.BEAUTY,
            spend=5000,
            impressions=1200,
            reach=900,
            view_count=1000,
            metadata={
                "lp_score": {"score": 72},
                "extract_quality_score": 80,
                "last_crawled_at": datetime(2026, 3, 8, 9, tzinfo=timezone.utc).isoformat(),
            },
            updated_at=datetime(2026, 3, 8, 9, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a106-estimated",
            platform=AdPlatformEnum.INSTAGRAM,
            category=AdCategoryEnum.FINANCE,
            spend=4000,
            impressions=1500,
            reach=1300,
            view_count=1400,
            metadata={
                "estimation_method": "audience_based",
                "impressions_from_audience": 1500,
                "estimated_spend_jpy": 4000,
                "estimated_cpm_jpy": 800,
                "last_crawled_at": datetime(2026, 3, 8, 10, tzinfo=timezone.utc).isoformat(),
            },
            updated_at=datetime(2026, 3, 8, 10, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a106-stale-real",
            platform=AdPlatformEnum.FACEBOOK,
            category=AdCategoryEnum.BEAUTY,
            spend=3000,
            impressions=900,
            reach=700,
            view_count=800,
            metadata={
                "lp_score": 55,
                "extract_quality_score": 60,
                "last_crawled_at": (datetime(2026, 3, 8, 0, tzinfo=timezone.utc) - timedelta(days=10)).isoformat(),
            },
            updated_at=datetime(2026, 2, 26, 9, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a106-missing",
            platform=AdPlatformEnum.YOUTUBE,
            category=AdCategoryEnum.OTHER,
            metadata={},
            updated_at=datetime(2026, 3, 8, 11, tzinfo=timezone.utc),
        ),
    ])
    session.commit()

    report = build_creative_library_audit(session, target_date=date(2026, 3, 8), persist=True)["creative_library_audit"]
    numeric = report["numeric_truth_audit"]

    assert numeric["summary"]["fields"]["spend"]["real_count"] == 2
    assert numeric["summary"]["fields"]["spend"]["estimated_count"] == 1
    assert numeric["summary"]["fields"]["spend"]["missing_count"] == 1
    assert numeric["summary"]["fields"]["lp_score"]["real_count"] == 2
    assert numeric["summary"]["fields"]["lp_score"]["missing_count"] == 2
    assert numeric["summary"]["estimated_only_count"] == 1
    assert numeric["summary"]["missing_numeric_count"] == 1
    assert numeric["summary"]["stale_real_metrics_count"] == 1
    assert numeric["priority_backfill_targets"][0]["ad_id"] in {2, 4}
    assert any(row["label"] == "beauty" for row in numeric["genre_breakdown"])
