from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import rankings
from app.tasks import dispatcher


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(rankings.router, prefix="/api/v1")
    return TestClient(app)


class _LPRefreshQuery:
    def __init__(self, ad):
        self._ad = ad

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return [self._ad]


class _LPRefreshSession:
    def __init__(self, ad):
        self._ad = ad

    def query(self, *args, **kwargs):
        return _LPRefreshQuery(self._ad)


@contextmanager
def _lp_refresh_scope(ad):
    yield _LPRefreshSession(ad)


def test_trace_propagation_policy_contract():
    client = _build_client()

    res = client.get("/api/v1/rankings/trace-propagation-policy")

    assert res.status_code == 200
    data = res.json()
    assert data["lanes"] == ["request_context", "task_dispatch"]
    assert any(item["path"] == "/lp-info/refresh" for item in data["items"])
    assert any(item["transport"] == "dispatch_task kwargs" for item in data["items"])


def test_lp_refresh_response_and_dispatch_include_trace_id(monkeypatch):
    ad = SimpleNamespace(
        id=101,
        ad_metadata={},
        destination_url="https://example.com/lp",
        advertiser_name="Trace Advertiser",
        brand_name=None,
        category=None,
    )
    captured = {}

    def fake_dispatch(task_name, kwargs):
        captured["task_name"] = task_name
        captured["kwargs"] = dict(kwargs)
        return dispatcher.DispatchResult(task_id="msg-101")

    monkeypatch.setattr(rankings, "_db_session_scope", lambda: _lp_refresh_scope(ad))
    monkeypatch.setattr(dispatcher, "_dispatch_celery", fake_dispatch)
    monkeypatch.setattr(dispatcher, "get_current_trace_id", lambda: "trace-lp-101")
    monkeypatch.setattr(rankings, "get_current_trace_id", lambda: "trace-lp-101")

    client = _build_client()
    res = client.post("/api/v1/rankings/lp-info/refresh", json={"ad_ids": [101], "force": True})

    assert res.status_code == 200
    data = res.json()
    assert data["trace_id"] == "trace-lp-101"
    assert data["details"][0]["trace_id"] == "trace-lp-101"
    assert captured["task_name"] == "crawl_and_analyze_lp"
    assert captured["kwargs"]["trace_id"] == "trace-lp-101"
