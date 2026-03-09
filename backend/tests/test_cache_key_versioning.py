from app.core.cache_key import build_cache_key
from app.services.ai.claude_client import ClaudeClient


def test_build_cache_key_with_version_and_parts():
    key = build_cache_key(namespace="rankings", version="v3", parts=["genre", "beauty"])
    assert key == "rankings:v3:genre:beauty"


def test_claude_client_usage_keys_include_version_prefix():
    ClaudeClient._hourly_usage.clear()
    ClaudeClient._daily_usage.clear()

    client = ClaudeClient(
        api_key="dummy",
        model="dummy",
        requests_per_hour=10,
        tokens_per_day=10000,
        cache_key_version="v9",
    )
    err = client._consume_limits(user_scope="user:1", estimated_tokens=100)
    assert err is None

    assert "ai_chat_limit_hourly:v9:user_1" in ClaudeClient._hourly_usage
    assert "ai_chat_limit_daily:v9:user_1" in ClaudeClient._daily_usage

