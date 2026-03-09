from datetime import date, datetime, timezone

from app.models.ad import Ad, AdCategoryEnum, AdPlatformEnum, AdStatusEnum
from app.services.data_quality_report import build_creative_library_audit


def _mk_ad(
    external_id: str,
    *,
    platform: AdPlatformEnum,
    title: str,
    category: AdCategoryEnum = AdCategoryEnum.BEAUTY,
    spend=None,
    impressions=None,
    reach=None,
    view_count=None,
    created_at: datetime | None = None,
    metadata: dict | None = None,
) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=platform,
        category=category,
        status=AdStatusEnum.PENDING,
        advertiser_name="meta audit tester",
        spend=spend,
        impressions=impressions,
        reach=reach,
        view_count=view_count,
        destination_url="https://example.com" if (metadata or {}).get("with_lp", True) else None,
        image_url="https://example.com/image.jpg" if (metadata or {}).get("with_creative", True) else None,
        ad_metadata=metadata or {},
        created_at=created_at or datetime(2026, 3, 8, 8, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 8, 9, tzinfo=timezone.utc),
    )


def test_a109_meta_completion_audit_builds_acceptance_summary(session, monkeypatch, tmp_path):
    import app.services.data_quality_report as data_quality_report

    monkeypatch.setattr(data_quality_report, "_AUDIT_REPORTS_FILE", tmp_path / "creative_library_audit_reports.json")

    session.add_all(
        [
            _mk_ad(
                "a109-real",
                platform=AdPlatformEnum.FACEBOOK,
                title="real meta ad",
                spend=5000,
                impressions=1200,
                reach=1000,
                view_count=1100,
                metadata={
                    "source": "api",
                    "publisher_platforms": ["facebook"],
                    "jp_char_ratio": 0.8,
                    "lp_info": {"final_url": "https://example.com/lp"},
                    "with_lp": True,
                    "with_creative": True,
                },
            ),
            _mk_ad(
                "a109-estimated-browser",
                platform=AdPlatformEnum.INSTAGRAM,
                title="estimated meta ad",
                spend=3000,
                impressions=900,
                reach=700,
                view_count=800,
                metadata={
                    "source": "browser_scraping",
                    "publisher_platforms": ["instagram"],
                    "estimation_method": "audience_based",
                    "estimated_spend_jpy": 3000,
                    "estimated_cpm_jpy": 800,
                    "impressions_from_audience": 900,
                    "jp_char_ratio": 0.7,
                    "snapshot_fallback_reason": "render_ad_http_error",
                    "crawl_source": "api",
                    "with_lp": False,
                    "with_creative": False,
                },
            ),
            _mk_ad(
                "a109-missing-new",
                platform=AdPlatformEnum.FACEBOOK,
                title="missing metrics ad",
                created_at=datetime(2026, 3, 8, 10, tzinfo=timezone.utc),
                metadata={
                    "source": "api",
                    "publisher_platforms": ["facebook"],
                    "crawl_result_count": 4,
                    "jp_char_ratio": 0.0,
                    "with_lp": True,
                    "with_creative": True,
                },
            ),
            _mk_ad(
                "a109-non-meta",
                platform=AdPlatformEnum.YOUTUBE,
                title="ignore me",
                metadata={"publisher_platforms": ["youtube"]},
            ),
        ]
    )
    session.commit()

    report = build_creative_library_audit(session, target_date=date(2026, 3, 8), persist=True)["creative_library_audit"]
    audit = report["meta_completion_audit"]

    assert audit["summary"]["total_meta_ads"] == 3
    assert audit["summary"]["real_metrics_count"] == 1
    assert audit["summary"]["estimated_metrics_count"] == 1
    assert audit["summary"]["missing_metrics_count"] == 1
    assert audit["summary"]["jp_rate"] == 0.6667
    assert audit["summary"]["new_saved_rate"] >= 0.3333
    assert audit["summary"]["saved_without_real_metrics_count"] == 2
    assert audit["summary"]["token_valid_but_api_failed_count"] == 1
    assert audit["summary"]["browser_fallback_dependency_count"] == 1
    assert audit["summary"]["numeric_mix"]["spend"]["estimated_count"] == 1
    assert audit["summary"]["numeric_mix"]["impressions"]["estimated_count"] == 1
    assert audit["summary"]["accepted_80"] is False
    assert audit["saved_without_real_metrics"][0]["metrics_state"] in {"estimated", "missing"}
    assert audit["api_failure_samples"][0]["ad_id"] == 2
    assert audit["browser_fallback_samples"][0]["ad_id"] == 2
    assert "accepted_80_if" in audit["acceptance_policy"]
