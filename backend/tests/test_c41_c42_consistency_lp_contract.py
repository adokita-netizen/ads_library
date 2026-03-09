import json
from contextlib import contextmanager

from app.core import database as db
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.crawl_job import CrawlJob, CrawlJobStatusEnum
from app.models.landing_page import LandingPage, LPStatusEnum, LPTypeEnum


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


def test_quick_crawl_consistency_by_job_id(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))
    CrawlJob.__table__.create(bind=session.bind, checkfirst=True)

    job = CrawlJob(
        job_id="c41-job-001",
        status=CrawlJobStatusEnum.COMPLETED,
        query="GLP-1",
        total_platforms=2,
        completed_platforms=2,
        total_ads_found=12,
        progress_detail={
            "inserted_count": 10,
            "searchable_ads_count": 8,
        },
    )
    session.add(job)
    session.commit()

    res = rankings.get_quick_crawl_consistency("c41-job-001")
    assert res["job_id"] == "c41-job-001"
    assert res["db_inserted_count"] == 10
    assert res["search_visible_count"] == 8
    assert res["delta"] == 2
    assert res["is_consistent"] is True


def test_lp_info_observable_fields_and_refresh_dispatch(session, monkeypatch):
    rankings = _import_rankings_module()
    monkeypatch.setattr(rankings, "sync_session_scope", lambda: _session_scope(session))

    ad1 = Ad(
        external_id="c41_lp_1",
        title="LPあり広告",
        destination_url="https://example.com/lp1",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={},
    )
    ad2 = Ad(
        external_id="c41_lp_2",
        title="LP再取得広告",
        destination_url="https://example.com/lp2",
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata={},
    )
    session.add_all([ad1, ad2])
    session.flush()

    lp = LandingPage(
        ad_id=ad1.id,
        url="https://example.com/lp1",
        final_url="https://example.com/lp1-final",
        url_hash="hash-c41-lp-1",
        domain="example.com",
        title="LPタイトル",
        meta_description="LP説明",
        og_image_url="https://example.com/og.jpg",
        lp_type=LPTypeEnum.ARTICLE,
        status=LPStatusEnum.COMPLETED,
        lp_metadata={"canonical": "https://example.com/lp1-canonical", "http_status": 200},
    )
    session.add(lp)
    session.commit()

    info = rankings.get_lp_info(ad1.id)
    assert info["fetch_status"] == "completed"
    assert info["title"] == "LPタイトル"
    assert info["canonical"] == "https://example.com/lp1-canonical"
    assert info["final_url"] == "https://example.com/lp1-final"
    assert info["http_status"] == 200

    class _Result:
        def __init__(self, id_):
            self.id = id_

    dispatched_payloads = []

    def _dispatch(task_name: str, **kwargs):
        assert task_name == "crawl_and_analyze_lp"
        dispatched_payloads.append(kwargs)
        if kwargs.get("ad_id") == ad2.id:
            return _Result("msg-ok-1")
        raise RuntimeError("timeout on lp refresh")

    monkeypatch.setattr("app.tasks.dispatcher.dispatch_task", _dispatch, raising=False)
    refresh = rankings.refresh_lp_info(
        rankings._LPInfoRefreshBody(ad_ids=[ad2.id, ad1.id, 999999], force=True)
    )
    assert refresh["requested"] == 3
    assert refresh["dispatched"] == 1
    assert refresh["errors"] == 1
    assert refresh["missing_ad_ids"] == [999999]
    ad2_payload = next(payload for payload in dispatched_payloads if payload["ad_id"] == ad2.id)
    assert ad2_payload["url"] == ad2.destination_url
    assert ad2_payload["advertiser_name"] == (ad2.advertiser_name or ad2.brand_name or "")
    assert ad2_payload["auto_analyze"] is True


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


def test_quick_crawl_low_volume_returns_recovery_action(monkeypatch):
    rankings = _import_rankings_module()
    store: dict = {}
    monkeypatch.setattr(rankings, "SyncSessionLocal", lambda: _FakeSession(store))

    async def _fake_crawl(*_args, **_kwargs):
        return {"facebook": [], "instagram": []}

    monkeypatch.setattr(rankings, "_crawl_platforms_no_expand", _fake_crawl)
    monkeypatch.setattr(
        rankings,
        "_save_crawled_ads",
        lambda *_args, **_kwargs: {
            "new_ads_count": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "skipped_invalid_count": 0,
        },
    )

    res = rankings.quick_crawl(rankings._QuickCrawlBody(query="GLP-1"))
    if hasattr(res, "body"):
        payload = json.loads(res.body.decode("utf-8"))
    else:
        payload = res
    assert payload["status"] == "completed"
    assert payload["recovery_action"] == "fallback_queries_applied"
    assert isinstance(payload["completed_at"], str)
