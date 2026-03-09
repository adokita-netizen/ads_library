from fastapi.testclient import TestClient

from app.core.trace import build_trace_headers, reset_current_trace_id, set_current_trace_id
from app.main import app
from app.tasks import dispatcher


def test_build_trace_headers_uses_context_trace_id():
    token = set_current_trace_id("trace-123")
    try:
        headers = build_trace_headers()
    finally:
        reset_current_trace_id(token)

    assert headers["X-Request-ID"] == "trace-123"
    assert headers["X-Trace-ID"] == "trace-123"


def test_dispatch_task_injects_trace_id(monkeypatch):
    captured = {}

    def fake_dispatch(task_name, kwargs):
        captured["task_name"] = task_name
        captured["kwargs"] = dict(kwargs)
        return dispatcher.DispatchResult(task_id="task-1")

    token = set_current_trace_id("trace-dispatch")
    try:
        monkeypatch.setattr(dispatcher, "_dispatch_celery", fake_dispatch)
        result = dispatcher.dispatch_task("compute_rankings", backend="celery", ad_id=1)
    finally:
        reset_current_trace_id(token)

    assert result.id == "task-1"
    assert captured["task_name"] == "compute_rankings"
    assert captured["kwargs"]["trace_id"] == "trace-dispatch"


def test_api_response_includes_trace_id_header():
    client = TestClient(app)
    res = client.get("/api/v1/rankings/timeout-policy", headers={"X-Request-ID": "trace-http-1"})

    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == "trace-http-1"
    assert res.headers["X-Trace-ID"] == "trace-http-1"
