"""Tests for ops health recovery dispatch behavior."""

from app.tasks import ops_tasks


def test_recovery_not_triggered_when_fresh():
    db = {"stale_days": 1}
    sqs = {"enabled": True, "queues": [{"queue": "heavy", "configured": True}]}
    result = ops_tasks._maybe_trigger_recovery(db, sqs)
    assert result["triggered"] is False
    assert result["reason"] == "fresh_enough"


def test_recovery_not_triggered_when_heavy_queue_unconfigured():
    db = {"stale_days": 3}
    sqs = {"enabled": True, "queues": [{"queue": "heavy", "configured": False}]}
    result = ops_tasks._maybe_trigger_recovery(db, sqs)
    assert result["triggered"] is False
    assert result["reason"] == "heavy_queue_unconfigured"


def test_recovery_dispatches_crawl_when_stale(monkeypatch):
    class _Result:
        id = "task-123"

    captured = {}

    def _fake_dispatch(task_name, **kwargs):
        captured["task_name"] = task_name
        captured["kwargs"] = kwargs
        return _Result()

    monkeypatch.setattr("app.tasks.dispatcher.dispatch_task", _fake_dispatch)
    monkeypatch.setattr(ops_tasks, "_recovery_already_triggered_today", lambda: False)
    monkeypatch.setattr(ops_tasks, "_record_recovery_event", lambda payload: None)

    db = {"stale_days": 2}
    sqs = {"enabled": True, "queues": [{"queue": "heavy", "configured": True}]}
    result = ops_tasks._maybe_trigger_recovery(db, sqs)

    assert result["triggered"] is True
    assert result["task"] == "crawl_ads"
    assert result["task_id"] == "task-123"
    assert captured["task_name"] == "crawl_ads"
    assert captured["kwargs"]["limit_per_platform"] == 20


def test_recovery_not_triggered_twice_same_day(monkeypatch):
    monkeypatch.setattr(ops_tasks, "_recovery_already_triggered_today", lambda: True)
    db = {"stale_days": 2}
    sqs = {"enabled": True, "queues": [{"queue": "heavy", "configured": True}]}
    result = ops_tasks._maybe_trigger_recovery(db, sqs)
    assert result["triggered"] is False
    assert result["reason"] == "already_triggered_today"
