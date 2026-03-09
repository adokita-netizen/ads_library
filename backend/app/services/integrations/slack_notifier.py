"""Slack notifier service."""

import httpx

from app.services.integrations.circuit_breaker import CircuitBreaker

_SLACK_BREAKER = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=60)


class SlackNotifier:
    """Send notifications to Slack incoming webhook."""

    async def send_test(self, webhook_url: str, channel: str | None = None) -> dict:
        if not _SLACK_BREAKER.allow_request():
            return {
                "success": False,
                "error": "circuit_open",
                "circuit_breaker": _SLACK_BREAKER.snapshot(),
            }

        payload = {
            "text": "VAAP Test Notification",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "VAAP - Test Notification"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": "Slack integration is working!"}},
            ],
        }
        if channel:
            payload["channel"] = channel

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(webhook_url, json=payload)
                success = resp.status_code < 400
                if success:
                    _SLACK_BREAKER.on_success()
                else:
                    _SLACK_BREAKER.on_failure()
                return {
                    "success": success,
                    "status_code": resp.status_code,
                    "response_text": resp.text[:300],
                    "circuit_breaker": _SLACK_BREAKER.snapshot(),
                }
            except Exception as e:
                _SLACK_BREAKER.on_failure()
                return {"success": False, "error": str(e), "circuit_breaker": _SLACK_BREAKER.snapshot()}
