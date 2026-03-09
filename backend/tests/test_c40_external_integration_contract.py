import asyncio
import json


def test_slack_configure_and_test_contract(monkeypatch, tmp_path):
    from app.api.endpoints import integrations as api

    monkeypatch.setattr(api, "_SLACK_CONFIG_FILE", tmp_path / "slack.json")

    configured = asyncio.run(
        api.configure_slack(
            api.SlackConfigRequest(webhook_url="https://hooks.slack.com/services/T/B/X", channel="#ops"),
            current_user={"user_id": 1},
        )
    )
    assert configured["success"] is True
    assert configured["config"]["channel"] == "#ops"

    async def _ok_send_test(self, webhook_url: str, channel: str | None = None):
        assert webhook_url.startswith("https://hooks.slack.com/")
        assert channel == "#ops"
        return {"success": True, "status_code": 200}

    monkeypatch.setattr("app.services.integrations.slack_notifier.SlackNotifier.send_test", _ok_send_test, raising=False)
    tested = asyncio.run(api.test_slack(current_user={"user_id": 1}))
    assert tested["success"] is True
    assert tested["status_code"] == 200


def test_webhook_crud_and_scheduled_export_contract(monkeypatch, tmp_path):
    from app.api.endpoints import integrations as api

    monkeypatch.setattr(api, "_WEBHOOKS_FILE", tmp_path / "webhooks.json")
    monkeypatch.setattr(api, "_SCHEDULED_EXPORT_FILE", tmp_path / "scheduled.json")
    monkeypatch.setattr(api, "_SLACK_CONFIG_FILE", tmp_path / "slack.json")

    created = asyncio.run(
        api.create_webhook(
            api.WebhookCreateRequest(
                url="https://example.com/hook",
                events=["new_hit", "crawl_completed"],
                secret="sec",
                is_active=True,
            ),
            current_user={"user_id": 7},
        )
    )
    assert created["success"] is True
    wid = created["webhook"]["id"]

    listed = asyncio.run(api.list_webhooks(current_user={"user_id": 7}))
    assert listed["total"] == 1
    assert listed["webhooks"][0]["has_secret"] is True

    async def _send_ok(self, webhook_url: str, event: str, payload: dict, secret: str | None = None):
        assert event == "scheduled_export_created"
        assert webhook_url == "https://example.com/delivery"
        return {"success": True, "status_code": 200}

    monkeypatch.setattr("app.services.integrations.webhook_sender.WebhookSender.send", _send_ok, raising=False)
    sched = asyncio.run(
        api.create_scheduled_export(
            api.ScheduledExportRequest(
                name="weekly report",
                schedule="weekly",
                format="csv",
                filters={"genre": "beauty"},
                delivery=api.ScheduledExportDelivery(type="webhook", target="https://example.com/delivery"),
            ),
            current_user={"user_id": 7},
        )
    )
    assert sched["success"] is True
    assert sched["scheduled_export"]["schedule"] == "weekly"

    deleted = asyncio.run(api.delete_webhook(wid, current_user={"user_id": 7}))
    assert deleted["success"] is True
    assert deleted["deleted_id"] == wid


def test_webhook_sender_hmac_and_retry(monkeypatch):
    from app.services.integrations import webhook_sender as ws_mod

    class _Resp:
        def __init__(self, status_code: int):
            self.status_code = status_code

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0
            self.captured_headers = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            self.calls += 1
            self.captured_headers = headers
            if self.calls == 1:
                raise RuntimeError("network error")
            if self.calls == 2:
                return _Resp(500)
            return _Resp(200)

    fake_client = _FakeClient()

    class _Factory:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ws_mod.httpx, "AsyncClient", _Factory)

    sender = ws_mod.WebhookSender()
    res = asyncio.run(
        sender.send(
            webhook_url="https://example.com/hook",
            event="new_hit",
            payload={"a": 1},
            secret="secret123",
        )
    )
    assert res["success"] is True
    assert res["attempts"] == 3
    assert fake_client.captured_headers["X-VAAP-Event"] == "new_hit"
    assert fake_client.captured_headers["X-VAAP-Signature"].startswith("sha256=")

