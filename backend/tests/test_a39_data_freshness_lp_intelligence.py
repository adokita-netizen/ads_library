from datetime import datetime, timedelta, timezone
import importlib

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
from app.tasks import metrics_tasks
from scripts.backfill_a39_operational_metadata import backfill_a39_operational_metadata
from scripts.audit_crawl_search_consistency import build_crawl_search_consistency_audit
from scripts.audit_data_freshness import build_data_freshness_audit


def test_a39_metadata_normalization_on_save(session):
    ad = Ad(
        external_id="a39-meta-1",
        title="LP metadata normalized",
        destination_url="https://example.com/lp",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "last_checked_at": "2026-03-08T00:00:00",
            "crawl_source": "batch_crawl_japanese",
            "lp_fetch_reason": "too_many_redirects",
            "final_url": "https://example.com/final",
            "title": "Landing title",
            "meta_description": "Landing description",
            "canonical": "https://example.com/canonical",
            "og_image_url": "https://example.com/og.png",
            "lang": "ja",
        },
    )
    session.add(ad)
    session.commit()
    session.refresh(ad)

    meta = ad.ad_metadata
    assert meta["last_crawled_at"].startswith("2026-03-08T00:00:00")
    assert meta["crawl_source"] == "scheduled_crawl"
    assert meta["freshness_ttl_sec"] == 259200
    assert meta["lp_fetch_error_code"] == "redirect_loop"
    assert meta["lp_info"]["final_url"] == "https://example.com/final"
    assert meta["lp_info"]["title"] == "Landing title"
    assert meta["lp_info"]["canonical"] == "https://example.com/canonical"


def test_a39_data_freshness_audit_builds_summary(session):
    now = datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)
    recent = Ad(
        external_id="a39-fresh-1",
        title="fresh",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        updated_at=now - timedelta(hours=1),
        ad_metadata={
            "last_crawled_at": (now - timedelta(hours=2)).isoformat(),
            "lp_info": {"final_url": "https://example.com", "title": "ok"},
        },
    )
    stale = Ad(
        external_id="a39-fresh-2",
        title="stale",
        platform=AdPlatformEnum.INSTAGRAM,
        status=AdStatusEnum.PENDING,
        updated_at=now - timedelta(days=3),
        advertiser_name="adv",
        ad_metadata={"last_crawled_at": (now - timedelta(days=2)).isoformat()},
    )
    session.add_all([recent, stale])
    session.commit()

    report = build_data_freshness_audit(session, now=now, stale_after_hours=24, top_n=5)
    assert report["summary"]["total_ads"] == 2
    assert report["summary"]["updated_24h_count"] == 1
    assert report["summary"]["lp_info_missing_count"] == 1
    assert report["platform_breakdown"][0]["platform"] == "instagram"
    assert report["stale_ads_top_n"][0]["title"] == "stale"


def test_a39_crawl_search_consistency_audit_builds_gap_report(session):
    CrawlJob.__table__.create(bind=session.bind, checkfirst=True)
    job_ok = CrawlJob(
        job_id="a39-job-ok",
        status=CrawlJobStatusEnum.COMPLETED,
        query="GLP-1",
        total_ads_found=10,
        progress_detail={"inserted_count": 10, "searchable_ads_count": 9},
    )
    job_gap = CrawlJob(
        job_id="a39-job-gap",
        status=CrawlJobStatusEnum.COMPLETED,
        query="美容",
        total_ads_found=20,
        progress_detail={"inserted_count": 20, "searchable_ads_count": 12},
    )
    job_fail = CrawlJob(
        job_id="a39-job-failed",
        status=CrawlJobStatusEnum.FAILED,
        query="健康",
        failure_reason="timeout",
        progress_detail={"inserted_count": 0, "searchable_ads_count": 0},
    )
    session.add_all([job_ok, job_gap, job_fail])
    session.commit()

    report = build_crawl_search_consistency_audit(session, days=30, top_n=10)
    assert report["summary"]["jobs_seen"] == 3
    assert report["summary"]["inconsistent_jobs"] == 2
    assert report["root_cause_counts"]["search_reflection_gap"] == 1
    assert report["root_cause_counts"]["failed:timeout"] == 1
    assert report["inconsistent_jobs_top_n"][0]["job_id"] == "a39-job-gap"


def test_a39_backfill_normalizes_existing_ads(session):
    ad = Ad(
        external_id="a39-backfill-1",
        title="backfill",
        destination_url="https://example.com/start",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={
            "last_checked_at": "2026-03-08T00:00:00",
            "crawl_source": "batch_crawl_japanese",
            "final_url": "https://example.com/final",
            "lp_fetch_reason": "connect_error",
        },
    )
    session.add(ad)
    session.commit()

    session.execute(Ad.__table__.update().where(Ad.id == ad.id).values(metadata={
        "last_checked_at": "2026-03-08T00:00:00",
        "crawl_source": "batch_crawl_japanese",
        "final_url": "https://example.com/final",
        "lp_fetch_reason": "connect_error",
    }))
    session.commit()
    session.expire_all()

    report = backfill_a39_operational_metadata(session, execute=True)
    refreshed = session.get(Ad, ad.id)
    assert report["updated_ads"] >= 1
    assert refreshed.ad_metadata["crawl_source"] == "scheduled_crawl"
    assert refreshed.ad_metadata["lp_fetch_error_code"] == "dns_error"
    assert refreshed.ad_metadata["lp_info"]["final_url"] == "https://example.com/final"


def test_a39_collect_daily_metrics_task_returns_audits(monkeypatch):
    class _FakeSession:
        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    monkeypatch.setattr(metrics_tasks, "collect_metrics_for_ads", lambda session: 3)
    monkeypatch.setattr(metrics_tasks, "enrich_topic_metadata_for_ads", lambda session: 2)
    monkeypatch.setattr(
        metrics_tasks,
        "audit_incomplete_ads",
        lambda session: {"incomplete_ads": 0, "field_missing_counts": {}, "field_missing_rates": {}, "updated_ads": 0, "total_ads": 0},
    )
    monkeypatch.setattr(metrics_tasks, "build_topic_gap_report", lambda session: {"summary": {"gap": 1}})
    monkeypatch.setattr(
        metrics_tasks,
        "build_false_negative_hunt_report",
        lambda session: {
            "summary": {"candidate_count": 2},
            "queue_result": {"queued_count": 1},
        },
    )
    monkeypatch.setattr(metrics_tasks, "queue_low_quality_reextractions", lambda session: {"queued_count": 3, "queued_ad_ids": [1, 2, 3]})
    monkeypatch.setattr(
        metrics_tasks,
        "build_meta_creative_extraction_report",
        lambda session, persist=True, top_n=10: {"summary": {"needs_reextract_count": 4}},
    )
    monkeypatch.setattr(
        metrics_tasks,
        "build_creative_library_audit",
        lambda session, persist=True: {
            "creative_library_audit": {
                "summary": {"missing_media_count": 4},
                "failure_reason_counts": {"lp_unresolved": 2},
                "slo_status": {"overall_status": "warning"},
                "live_ingestion_audit": {"daily_new_ads": 5},
                "numeric_truth_audit": {
                    "summary": {
                        "stale_real_metrics_count": 1,
                        "estimated_only_count": 2,
                        "missing_numeric_count": 3,
                    }
                },
                "japanese_inventory_audit": {
                    "summary": {
                        "jp_rate": 0.7,
                        "manual_review_count": 1,
                    }
                },
                "bedrock_precision_roi_audit": {
                    "summary": {
                        "manual_review_count": 2,
                        "bedrock_used_count": 5,
                        "bedrock_valuable_count": 3,
                    }
                },
            }
        },
    )
    monkeypatch.setattr(metrics_tasks, "build_data_freshness_audit", lambda session, top_n=10: {"summary": {"updated_24h_rate": 0.8}})
    monkeypatch.setattr(
        metrics_tasks,
        "build_crawl_search_consistency_audit",
        lambda session, days=7, top_n=10: {"summary": {"consistency_rate": 0.9}},
    )

    db_mod = importlib.import_module("app.core.database")
    lock_mod = importlib.import_module("app.core.distributed_lock")

    monkeypatch.setattr(db_mod, "get_session_with_retry", lambda: _FakeSession(), raising=False)
    monkeypatch.setattr(lock_mod, "acquire_distributed_lock", lambda job_name, ttl=900: "token-1", raising=False)
    monkeypatch.setattr(lock_mod, "release_distributed_lock", lambda job_name, token: None, raising=False)

    payload = metrics_tasks.collect_daily_metrics_task()
    assert payload["status"] == "completed"
    assert payload["false_negative_hunt"]["summary"]["candidate_count"] == 2
    assert payload["extraction_retry_queue"]["queued_count"] == 3
    assert payload["meta_creative_extraction_audit"]["summary"]["needs_reextract_count"] == 4
    assert payload["numeric_truth_audit"]["summary"]["estimated_only_count"] == 2
    assert payload["japanese_inventory_audit"]["summary"]["jp_rate"] == 0.7
    assert payload["bedrock_precision_roi_audit"]["summary"]["bedrock_used_count"] == 5
    assert payload["data_freshness_audit"]["summary"]["updated_24h_rate"] == 0.8
    assert payload["crawl_search_consistency_audit"]["summary"]["consistency_rate"] == 0.9
