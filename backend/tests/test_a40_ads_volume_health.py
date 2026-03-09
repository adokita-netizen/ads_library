from datetime import datetime, timedelta, timezone

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
from app.tasks.metrics_tasks import audit_incomplete_ads
from scripts import audit_ads_volume_errors
from scripts.audit_ads_volume_errors import build_ads_volume_health_report


def test_a40_audit_incomplete_ads_marks_missing_fields(session):
    ad_ok = Ad(
        external_id="a40-ok",
        title="ok",
        advertiser_name="adv",
        destination_url="https://example.com",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={},
    )
    ad_bad = Ad(
        external_id="a40-bad",
        title="",
        advertiser_name="",
        destination_url=None,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={},
    )
    session.add_all([ad_ok, ad_bad])
    session.commit()

    report = audit_incomplete_ads(session)
    session.refresh(ad_bad)
    session.refresh(ad_ok)

    assert report["incomplete_ads"] == 1
    assert report["field_missing_counts"]["title"] == 1
    assert report["field_missing_counts"]["advertiser_name"] == 1
    assert report["field_missing_counts"]["destination_url"] == 1
    assert ad_bad.ad_metadata["is_incomplete_record"] is True
    assert "missing_title" in ad_bad.ad_metadata["incomplete_reason"]
    assert ad_ok.ad_metadata["is_incomplete_record"] is False


def test_a40_health_report_summarizes_volume_failures_and_backlog(session):
    CrawlJob.__table__.create(bind=session.bind, checkfirst=True)
    now = datetime.now(timezone.utc)
    recent_day = now - timedelta(days=1)
    old_day = now - timedelta(days=3)

    ad_ok = Ad(
        external_id="a40-health-ok",
        title="ok",
        advertiser_name="adv",
        destination_url="https://example.com",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={"needs_media_retry": True},
    )
    ad_incomplete = Ad(
        external_id="a40-health-bad",
        title="",
        advertiser_name="",
        destination_url=None,
        platform=AdPlatformEnum.INSTAGRAM,
        status=AdStatusEnum.PENDING,
        ad_metadata={"is_incomplete_record": True},
    )
    session.add_all([ad_ok, ad_incomplete])
    session.flush()

    job_recent = CrawlJob(
        job_id="a40-job-1",
        status=CrawlJobStatusEnum.COMPLETED,
        query="美容",
        progress_detail={"new_ads_count": 40},
        created_at=recent_day,
        updated_at=recent_day,
    )
    job_old = CrawlJob(
        job_id="a40-job-2",
        status=CrawlJobStatusEnum.FAILED,
        query="健康",
        failure_reason="timeout",
        progress_detail={"new_ads_count": 10},
        created_at=old_day,
        updated_at=old_day,
    )
    session.add_all([job_recent, job_old])
    session.commit()

    report = build_ads_volume_health_report(session, days=7, min_ads=5, target_min_ads_per_day=100)
    summary = report["summary"]

    assert summary["total_ads"] == 2
    assert summary["previous_day_new_ads"] == 40
    assert summary["target_met_previous_day"] is False
    assert summary["save_failure_count"] == 1
    assert summary["reprocess_pending_count"] == 2
    assert summary["incomplete_record_count"] == 1
    assert report["save_failure_reasons"]["timeout"] == 1
    assert "below_target_min_ads" in report["warnings"]
    assert "save_failures_present" in report["warnings"]


def test_a40_daily_recovery_plan_builds_and_executes(monkeypatch):
    calls = []

    def _fake_run_quick_crawl(api_base: str, query: str, limit: int, timeout_sec: int) -> dict:
        calls.append((api_base, query, limit, timeout_sec))
        return {
            "query": query,
            "ok": True,
            "status_code": 200,
            "fetched_ads_count": 12,
            "new_ads_count": 7,
        }

    monkeypatch.setattr(audit_ads_volume_errors, "_run_quick_crawl", _fake_run_quick_crawl)

    report = audit_ads_volume_errors.build_daily_recovery_plan(
        previous_day_new_ads=40,
        target_min_ads_per_day=100,
        focus_keywords=["GLP-1"],
        execute_recovery=True,
        api_base="http://localhost:8000/api/v1",
        recovery_limit=20,
        timeout_sec=180,
    )

    assert report["should_trigger"] is True
    assert report["deficit"] == 60
    assert len(report["planned_queries"]) >= 3
    assert report["executed"] is True
    assert report["added_new_ads"] == 7 * len(report["planned_queries"])
    assert len(calls) == len(report["planned_queries"])
