from datetime import datetime, timedelta, timezone

from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
from app.tasks import crawl_tasks
from scripts.run_live_ad_ingestion_wave import _cleanup_stale_inline_jobs
from scripts.run_live_ad_ingestion_wave import _summarize_wave_result


def test_d107_meta_only_policy_tightens_duplicate_and_freshness_windows():
    hourly = crawl_tasks.get_live_ingestion_policy(["facebook", "instagram"], mode="hourly")
    nightly = crawl_tasks.get_live_ingestion_policy(["facebook"], mode="nightly")

    assert hourly["scope"] == "meta_only"
    assert hourly["duplicate_guard_hours"] == 2
    assert hourly["freshness_hours"] == 36
    assert hourly["keyword_strategy"] == "static_first"
    assert nightly["duplicate_guard_hours"] == 8
    assert nightly["backfill_limit"] > hourly["backfill_limit"]


def test_d107_live_ingestion_wave_uses_meta_policy_values(monkeypatch):
    class _DummySession:
        def close(self):
            return None

    duplicate_hours = []
    backfill_calls = []

    monkeypatch.setattr(crawl_tasks, "SyncSessionLocal", lambda: _DummySession())
    monkeypatch.setattr(crawl_tasks, "get_connected_platforms", lambda: ["facebook", "instagram"])
    monkeypatch.setattr(
        crawl_tasks,
        "get_today_keywords",
        lambda prioritize_stale, session, limit, dynamic_quota=None: ["glp-1", "aga"],
    )
    monkeypatch.setattr(
        crawl_tasks,
        "is_duplicate_crawl",
        lambda session, keyword, hours=6: duplicate_hours.append(hours) or False,
    )
    monkeypatch.setattr(
        crawl_tasks,
        "queue_incomplete_fresh_ads",
        lambda session, limit, freshness_hours=72: backfill_calls.append(
            {"limit": limit, "freshness_hours": freshness_hours}
        ) or {"queued": 1, "ad_ids": [101], "reason_counts": {"snapshot_only": 1}},
    )
    monkeypatch.setattr(crawl_tasks, "_collect_recent_query_stats", lambda session, hours=72: {})
    monkeypatch.setattr(
        crawl_tasks,
        "get_meta_token_runtime_health",
        lambda session: {
            "checked": True,
            "status": "healthy",
            "token_source": "db",
            "recent_auth_failures": 0,
            "latest_auth_failure_at": None,
            "warning": None,
            "fallback_policy": "meta_api_first",
        },
    )
    monkeypatch.setattr(crawl_tasks.crawl_ads_task, "apply_async", lambda kwargs: None, raising=False)

    task_runner = getattr(crawl_tasks.run_live_ingestion_wave_task, "run", crawl_tasks.run_live_ingestion_wave_task)
    if getattr(crawl_tasks.run_live_ingestion_wave_task, "run", None):
        res = task_runner(
            platforms=["facebook", "instagram"],
            keyword_limit=2,
            limit_per_platform=10,
            country="JP",
            queue_backfill=True,
            mode="hourly",
        )
    else:
        res = task_runner(
            None,
            platforms=["facebook", "instagram"],
            keyword_limit=2,
            limit_per_platform=10,
            country="JP",
            queue_backfill=True,
            mode="hourly",
        )

    assert res["policy"]["scope"] == "meta_only"
    assert duplicate_hours == [2, 2]
    assert backfill_calls[0]["freshness_hours"] == 36
    assert res["meta_token"]["status"] == "healthy"


def test_d107_wave_summary_aggregates_new_merge_and_backfill_counts():
    summary = _summarize_wave_result(
        {
            "results": [
                {
                    "saved_count": 3,
                    "merged_count": 2,
                    "creative_backfill_count": 1,
                    "lp_backfill_count": 1,
                },
                {
                    "saved_count": 4,
                    "merged_count": 1,
                    "creative_backfill_count": 2,
                    "lp_backfill_count": 0,
                },
            ],
            "backfill": {"queued": 5},
            "queued_keywords": ["glp-1", "aga"],
            "skipped_keywords": ["seo"],
        }
    )

    assert summary == {
        "new_saves": 7,
        "merged_updates": 3,
        "backfilled_creatives": 3,
        "backfilled_lps": 1,
        "queued_backfill_ads": 5,
        "queued_keywords": 2,
        "skipped_keywords": 1,
    }


def test_d107_cleanup_stale_inline_jobs_marks_only_old_inline_running_jobs_failed(session):
    CrawlJob.__table__.create(bind=session.bind, checkfirst=True)
    now = datetime.now(timezone.utc)

    stale_inline = CrawlJob(
        job_id="inline-メディカルダイエット-abc12345",
        status=CrawlJobStatusEnum.RUNNING,
        query="メディカルダイエット",
        platforms=["facebook"],
        total_platforms=1,
        completed_platforms=0,
        total_ads_found=0,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2),
    )
    fresh_inline = CrawlJob(
        job_id="inline-glp-1-def67890",
        status=CrawlJobStatusEnum.RUNNING,
        query="glp-1",
        platforms=["facebook"],
        total_platforms=1,
        completed_platforms=0,
        total_ads_found=0,
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )
    stale_non_inline = CrawlJob(
        job_id="job-plain-123",
        status=CrawlJobStatusEnum.RUNNING,
        query="aga",
        platforms=["facebook"],
        total_platforms=1,
        completed_platforms=0,
        total_ads_found=0,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(hours=2),
    )
    session.add_all([stale_inline, fresh_inline, stale_non_inline])
    session.commit()

    cleaned = _cleanup_stale_inline_jobs(session, stale_after_minutes=30)
    session.expire_all()

    refreshed = {
        row.job_id: row
        for row in session.query(CrawlJob).all()
    }

    assert cleaned == 1
    assert refreshed["inline-メディカルダイエット-abc12345"].status == CrawlJobStatusEnum.FAILED
    assert refreshed["inline-メディカルダイエット-abc12345"].failure_reason == "timeout"
    assert "stale inline ingestion job" in refreshed["inline-メディカルダイエット-abc12345"].error_message
    assert refreshed["inline-glp-1-def67890"].status == CrawlJobStatusEnum.RUNNING
    assert refreshed["job-plain-123"].status == CrawlJobStatusEnum.RUNNING
