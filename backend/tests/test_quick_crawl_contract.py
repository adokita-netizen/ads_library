import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from app.core import database as db
from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum


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


class _FakeQuery:
    def __init__(self, store: dict):
        self._store = store

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._store.get("job")


class _FakeSession:
    def __init__(self, store: dict):
        self._store = store

    def add(self, obj):
        self._store["job"] = obj

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._store)


def test_quick_crawl_body_default_contract():
    rankings = _import_rankings_module()
    body = rankings._QuickCrawlBody(query=" GLP-1 ")
    assert body.limit == 20
    assert body.platforms is None
    assert body.country == "JP"


def test_quick_crawl_success_contract_defaults_meta_and_country(monkeypatch):
    rankings = _import_rankings_module()
    store: dict = {}
    monkeypatch.setattr(rankings, "SyncSessionLocal", lambda: _FakeSession(store))

    async def _fake_crawl(_query: str, platforms: list[str], _limit: int, country: str = "JP", **_kwargs):
        assert platforms == ["facebook", "instagram"]
        assert country == "JP"
        return {"facebook": [1, 2, 3], "instagram": [4, 5, 6]}

    monkeypatch.setattr(rankings, "_crawl_platforms_no_expand", _fake_crawl)
    monkeypatch.setattr(
        rankings,
        "_save_crawled_ads",
        lambda _results, query=None: {
            "new_ads_count": 4,
            "inserted_count": 4,
            "updated_count": 2,
        },
    )

    body = rankings._QuickCrawlBody(query="GLP-1", limit=10)
    result = rankings.quick_crawl(body)
    assert result["status"] == "completed"
    assert result["platforms"] == ["facebook", "instagram"]
    assert result["country"] == "JP"
    assert result["fetched_ads_count"] == 6
    assert result["saved_ads_count"] == 6
    assert result["searchable_ads_count"] == 6
    assert result["dropped_after_filter_count"] == 0
    assert result["error_code"] is None
    assert result["failure_reason"] is None


def test_quick_crawl_failure_contract_contains_error_code_and_reason(monkeypatch):
    rankings = _import_rankings_module()
    store: dict = {}
    monkeypatch.setattr(rankings, "SyncSessionLocal", lambda: _FakeSession(store))

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("timeout while crawling")

    monkeypatch.setattr(rankings, "_crawl_platforms_no_expand", _boom)
    monkeypatch.setattr(
        rankings,
        "_save_crawled_ads",
        lambda _results, query=None: {
            "new_ads_count": 0,
            "inserted_count": 0,
            "updated_count": 0,
        },
    )

    body = rankings._QuickCrawlBody(query="GLP-1", platforms=["facebook"])
    response = rankings.quick_crawl(body)
    assert response.status_code == 500
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["status"] == "failed"
    assert payload["platforms"] == ["facebook"]
    assert payload["country"] == "JP"
    assert payload["error_code"] == "timeout"
    assert payload["failure_reason"] == "timeout"


def test_quick_crawl_tolerates_invalid_platform_result_without_500(monkeypatch):
    rankings = _import_rankings_module()
    store: dict = {}
    monkeypatch.setattr(rankings, "SyncSessionLocal", lambda: _FakeSession(store))

    async def _fake_crawl(*_args, **_kwargs):
        return {"facebook": None, "instagram": []}

    monkeypatch.setattr(rankings, "_crawl_platforms_no_expand", _fake_crawl)

    body = rankings._QuickCrawlBody(query="ダイエット", platforms=["facebook", "instagram"])
    result = rankings.quick_crawl(body)
    assert result["status"] == "completed"
    assert result["fetched_ads_count"] == 0
    assert result["saved_ads_count"] == 0
    assert result["skipped_invalid_count"] >= 1


def test_fan_out_meta_results_reuses_single_meta_fetch():
    rankings = _import_rankings_module()

    class _Ad:
        def __init__(self, platform: str, metadata: dict):
            self.platform = platform
            self.metadata = metadata

    ads = [
        _Ad("facebook", {"publisher_platforms": ["facebook"]}),
        _Ad("instagram", {"publisher_platforms": ["instagram"]}),
        _Ad("facebook", {"publisher_platforms": ["facebook", "instagram"]}),
        _Ad("facebook", {}),
    ]

    result = rankings._fan_out_meta_results(
        ads,
        ["facebook", "instagram"],
        limit_map={"facebook": 10, "instagram": 10},
        default_limit=10,
    )

    assert len(result["facebook"]) == 3
    assert len(result["instagram"]) == 2
    assert result["facebook"][-1] is ads[3]


def test_coerce_crawl_job_status_marks_stale_running_failed():
    rankings = _import_rankings_module()

    class _Job:
        status = "running"
        error_message = None
        created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        updated_at = datetime.now(timezone.utc) - timedelta(minutes=30)

    status, error_message, stale = rankings._coerce_crawl_job_status(_Job())
    assert status == "failed"
    assert stale is True
    assert "stale running job" in error_message


def test_get_crawl_status_persists_stale_running_job(session, monkeypatch):
    rankings = _import_rankings_module()
    CrawlJob.__table__.create(bind=session.bind, checkfirst=True)

    stale_job = CrawlJob(
        job_id="quick-stale-001",
        status=CrawlJobStatusEnum.RUNNING,
        query="ダイエット",
        platforms=["facebook", "instagram"],
        total_platforms=2,
        completed_platforms=0,
        total_ads_found=0,
        current_platform="facebook",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=40),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=40),
    )
    session.add(stale_job)
    session.commit()

    @contextmanager
    def _scope():
        yield session

    monkeypatch.setattr(rankings, "_db_session_scope", _scope)

    result = rankings.get_crawl_status(hours=24, limit=20)
    session.expire_all()
    refreshed = session.query(CrawlJob).filter(CrawlJob.job_id == "quick-stale-001").one()

    assert result["jobs"][0]["status"] == "failed"
    assert result["jobs"][0]["stale"] is True
    assert refreshed.status == CrawlJobStatusEnum.FAILED
    assert refreshed.failure_reason == "timeout"
    assert refreshed.current_platform is None
    assert "stale running job" in refreshed.error_message


def test_get_crawl_status_diagnostics_counts_stale_running_job_as_failed(session, monkeypatch):
    rankings = _import_rankings_module()
    CrawlJob.__table__.create(bind=session.bind, checkfirst=True)

    stale_job = CrawlJob(
        job_id="quick-stale-diag-001",
        status=CrawlJobStatusEnum.RUNNING,
        query="aga",
        platforms=["facebook"],
        total_platforms=1,
        completed_platforms=0,
        total_ads_found=0,
        current_platform="facebook",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=50),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=50),
        progress_detail={"saved_ads_count": 0},
    )
    session.add(stale_job)
    session.commit()

    @contextmanager
    def _scope():
        yield session

    monkeypatch.setattr(rankings, "_db_session_scope", _scope)
    monkeypatch.setattr(rankings, "_load_platform_query_learnings", lambda: {"platforms": {}})

    result = rankings.get_crawl_status_diagnostics(hours=24, limit=20)
    session.expire_all()
    refreshed = session.query(CrawlJob).filter(CrawlJob.job_id == "quick-stale-diag-001").one()

    assert result["summary"]["total_jobs"] == 1
    assert result["summary"]["failed"] == 1
    assert result["summary"]["completed"] == 0
    assert result["platforms"][0]["platform"] == "facebook"
    assert result["platforms"][0]["failed"] == 1
    assert refreshed.status == CrawlJobStatusEnum.FAILED
    assert refreshed.failure_reason == "timeout"


def test_classify_crawl_job_distinguishes_inline_quick_and_scheduled():
    rankings = _import_rankings_module()

    class _Job:
        def __init__(self, job_id, progress_detail=None):
            self.job_id = job_id
            self.progress_detail = progress_detail

    assert rankings._classify_crawl_job(_Job("inline-ダイエット-1234abcd")) == (
        "inline",
        "live_ingestion_inline",
    )
    assert rankings._classify_crawl_job(
        _Job("quick-job-1", progress_detail={"recovery": {"triggered": False}})
    ) == (
        "quick_crawl",
        "rankings_quick_crawl",
    )
    assert rankings._classify_crawl_job(_Job("123e4567-e89b-12d3-a456-426614174000")) == (
        "manual",
        "ads_inline_fallback",
    )
    assert rankings._classify_crawl_job(_Job("celery-task-001")) == (
        "scheduled",
        "crawl_ads_task",
    )


def test_get_crawl_status_includes_job_type_and_source(session, monkeypatch):
    rankings = _import_rankings_module()
    CrawlJob.__table__.create(bind=session.bind, checkfirst=True)

    quick_job = CrawlJob(
        job_id="quick-job-typed-001",
        status=CrawlJobStatusEnum.COMPLETED,
        query="glp-1",
        platforms=["facebook", "instagram"],
        total_platforms=2,
        completed_platforms=2,
        total_ads_found=12,
        progress_detail={"recovery": {"triggered": False}, "saved_ads_count": 12},
    )
    session.add(quick_job)
    session.commit()

    @contextmanager
    def _scope():
        yield session

    monkeypatch.setattr(rankings, "_db_session_scope", _scope)

    result = rankings.get_crawl_status(hours=24, limit=20)

    assert result["jobs"][0]["job_type"] == "quick_crawl"
    assert result["jobs"][0]["job_source"] == "rankings_quick_crawl"
