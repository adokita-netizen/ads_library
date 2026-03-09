"""Anthropic Claude client wrapper with basic usage limits."""

import json
from datetime import datetime, timezone
from typing import ClassVar

import httpx

from app.core.cache_key import build_cache_key


class ClaudeClient:
    """Thin async client for Anthropic Messages API."""

    _hourly_usage: ClassVar[dict[str, tuple[str, int]]] = {}
    _daily_usage: ClassVar[dict[str, tuple[str, int]]] = {}

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        max_tokens: int = 1200,
        timeout_seconds: float = 30.0,
        requests_per_hour: int = 60,
        tokens_per_day: int = 120_000,
        cache_key_version: str = "v1",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.requests_per_hour = requests_per_hour
        self.tokens_per_day = tokens_per_day
        self.cache_key_version = cache_key_version

    async def generate_message(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        user_scope: str,
    ) -> dict:
        estimated_tokens = self._estimate_tokens(system_prompt + "\n" + user_prompt)
        limit_error = self._consume_limits(user_scope=user_scope, estimated_tokens=estimated_tokens)
        if limit_error:
            return {
                "ok": False,
                "error": limit_error,
                "rate_limited": True,
                "usage": {"estimated_tokens": estimated_tokens},
            }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                )
        except Exception as exc:
            return {"ok": False, "error": f"claude_request_failed: {exc}", "rate_limited": False}

        if response.status_code >= 400:
            detail = response.text[:400]
            return {
                "ok": False,
                "error": f"claude_http_{response.status_code}: {detail}",
                "rate_limited": response.status_code == 429,
            }

        try:
            data = response.json()
        except json.JSONDecodeError:
            return {"ok": False, "error": "claude_invalid_json", "rate_limited": False}

        text_parts: list[str] = []
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        message = "".join(text_parts).strip()
        if not message:
            return {"ok": False, "error": "claude_empty_response", "rate_limited": False}

        return {
            "ok": True,
            "message": message,
            "usage": data.get("usage", {}),
            "model": data.get("model", self.model),
        }

    def _consume_limits(self, *, user_scope: str, estimated_tokens: int) -> str | None:
        now = datetime.now(timezone.utc)
        hour_key = now.strftime("%Y-%m-%dT%H")
        day_key = now.strftime("%Y-%m-%d")
        hourly_cache_key = build_cache_key(
            namespace="ai_chat_limit_hourly",
            version=self.cache_key_version,
            parts=[user_scope],
        )
        daily_cache_key = build_cache_key(
            namespace="ai_chat_limit_daily",
            version=self.cache_key_version,
            parts=[user_scope],
        )

        hour_state = self._hourly_usage.get(hourly_cache_key)
        if not hour_state or hour_state[0] != hour_key:
            hour_count = 0
        else:
            hour_count = hour_state[1]

        if hour_count + 1 > self.requests_per_hour:
            return "hourly_request_limit_exceeded"

        day_state = self._daily_usage.get(daily_cache_key)
        if not day_state or day_state[0] != day_key:
            day_tokens = 0
        else:
            day_tokens = day_state[1]

        if day_tokens + estimated_tokens > self.tokens_per_day:
            return "daily_token_limit_exceeded"

        self._hourly_usage[hourly_cache_key] = (hour_key, hour_count + 1)
        self._daily_usage[daily_cache_key] = (day_key, day_tokens + estimated_tokens)
        return None

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Rough estimate: 1 token ~= 4 chars for mixed JA/EN prompts.
        return max(1, len(text) // 4)
