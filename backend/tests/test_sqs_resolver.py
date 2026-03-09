"""Tests for SQS queue URL auto-resolution."""

from app.tasks.dispatcher import _CELERY_TASK_MAP, LIGHT_TASKS
from app.tasks.sqs_resolver import resolve_queue_url


class _FakeSQS:
    def __init__(self, by_name=None, queue_urls=None):
        self.by_name = by_name or {}
        self.queue_urls = queue_urls or []

    def get_queue_url(self, QueueName):
        if QueueName not in self.by_name:
            raise RuntimeError("QueueDoesNotExist")
        return {"QueueUrl": self.by_name[QueueName]}

    def list_queues(self, QueueNamePrefix):
        return {"QueueUrls": [u for u in self.queue_urls if f"/{QueueNamePrefix}" in u]}


def test_resolve_queue_url_returns_configured_url_without_aws_calls():
    url, mode = resolve_queue_url(
        "heavy",
        configured_url="https://sqs.ap-northeast-1.amazonaws.com/123/vaap-production-heavy-tasks",
        app_env="production",
        aws_region="ap-northeast-1",
        sqs_client=_FakeSQS(),
    )
    assert mode == "configured_url"
    assert url.endswith("heavy-tasks")


def test_resolve_queue_url_by_get_queue_url(monkeypatch):
    monkeypatch.setenv("PROJECT_NAME", "vaap")
    monkeypatch.setenv("ENVIRONMENT", "production")
    sqs = _FakeSQS(
        by_name={
            "vaap-production-light-tasks": "https://sqs.ap-northeast-1.amazonaws.com/123/vaap-production-light-tasks"
        }
    )
    url, mode = resolve_queue_url(
        "light",
        configured_url="",
        app_env="production",
        aws_region="ap-northeast-1",
        sqs_client=sqs,
    )
    assert mode == "aws_get_queue_url"
    assert url is not None and url.endswith("light-tasks")


def test_resolve_queue_url_by_list_queues_fallback(monkeypatch):
    monkeypatch.setenv("PROJECT_NAME", "vaap")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    sqs = _FakeSQS(
        by_name={},
        queue_urls=[
            "https://sqs.ap-northeast-1.amazonaws.com/123/vaap-production-heavy-tasks",
            "https://sqs.ap-northeast-1.amazonaws.com/123/vaap-production-light-tasks",
        ],
    )
    url, mode = resolve_queue_url(
        "heavy",
        configured_url="",
        app_env="production",
        aws_region="ap-northeast-1",
        sqs_client=sqs,
    )
    assert mode == "aws_list_queues"
    assert url is not None and url.endswith("heavy-tasks")


def test_daily_ops_health_check_is_dispatchable_task():
    assert "daily_ops_health_check" in LIGHT_TASKS
    assert _CELERY_TASK_MAP["daily_ops_health_check"] == "app.tasks.ops_tasks.daily_ops_health_check_task"
