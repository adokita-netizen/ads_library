"""Webhook delivery service with optional HMAC signature."""

import hashlib
import hmac
import json

import httpx
from app.services.integrations.circuit_breaker import CircuitBreaker

_WEBHOOK_BREAKER = CircuitBreaker(failure_threshold=3, reset_timeout_seconds=60)


class WebhookSender:
    """Send event payloads to external webhook endpoints."""

    async def send(self, webhook_url: str, event: str, payload: dict, secret: str | None = None) -> dict:
        if not _WEBHOOK_BREAKER.allow_request():
            return {
                "success": False,
                "error": "circuit_open",
                "circuit_breaker": _WEBHOOK_BREAKER.snapshot(),
            }

        headers = {"Content-Type": "application/json", "X-VAAP-Event": event}

        if secret:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-VAAP-Signature"] = f"sha256={signature}"

        max_attempts = 3
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = await client.post(webhook_url, json=payload, headers=headers)
                    success = resp.status_code < 400
                    if success:
                        _WEBHOOK_BREAKER.on_success()
                        return {
                            "success": True,
                            "status_code": resp.status_code,
                            "attempts": attempt,
                            "circuit_breaker": _WEBHOOK_BREAKER.snapshot(),
                        }

                    # Retry only transient 5xx responses.
                    if resp.status_code >= 500 and attempt < max_attempts:
                        continue

                    _WEBHOOK_BREAKER.on_failure()
                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "attempts": attempt,
                        "circuit_breaker": _WEBHOOK_BREAKER.snapshot(),
                    }
                except Exception as e:
                    if attempt < max_attempts:
                        continue
                    _WEBHOOK_BREAKER.on_failure()
                    return {
                        "success": False,
                        "error": str(e),
                        "attempts": attempt,
                        "circuit_breaker": _WEBHOOK_BREAKER.snapshot(),
                    }
