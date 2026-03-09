"""Resolve SQS queue URLs with safe fallbacks for production deployments."""

from __future__ import annotations

import os
from typing import Any

_QUEUE_URL_CACHE: dict[str, str] = {}


def _suffix(queue_type: str) -> str:
    if queue_type not in {"heavy", "light"}:
        raise ValueError(f"Unsupported queue type: {queue_type}")
    return f"{queue_type}-tasks"


def _candidate_names(queue_type: str, app_env: str | None = None) -> list[str]:
    env_var = f"SQS_{queue_type.upper()}_QUEUE_NAME"
    explicit_name = os.getenv(env_var, "").strip()

    project = os.getenv("PROJECT_NAME", "vaap").strip() or "vaap"
    environment = os.getenv("ENVIRONMENT", "").strip()
    normalized_app_env = (app_env or "").strip().lower()
    if not environment:
        environment = normalized_app_env if normalized_app_env in {"production", "staging"} else "production"

    suffix = _suffix(queue_type)
    candidates: list[str] = []

    if explicit_name:
        candidates.append(explicit_name)
    candidates.append(f"{project}-{environment}-{suffix}")

    if environment != "production":
        candidates.append(f"{project}-production-{suffix}")

    candidates.append(suffix)
    return list(dict.fromkeys(candidates))


def resolve_queue_url(
    queue_type: str,
    *,
    configured_url: str = "",
    app_env: str | None = None,
    aws_region: str = "ap-northeast-1",
    sqs_client: Any | None = None,
) -> tuple[str | None, str]:
    """Resolve queue URL from configured URL or AWS queue name discovery.

    Returns:
        (queue_url or None, resolution_mode)
        resolution_mode: configured_url | aws_get_queue_url | aws_list_queues | unresolved
    """
    url = (configured_url or "").strip()
    if url:
        return url, "configured_url"

    cache_key = f"{queue_type}:{aws_region}:{app_env or ''}"
    cached = _QUEUE_URL_CACHE.get(cache_key)
    if cached:
        return cached, "aws_cache"

    if sqs_client is None:
        import boto3

        sqs_client = boto3.client("sqs", region_name=aws_region)

    for queue_name in _candidate_names(queue_type, app_env=app_env):
        try:
            response = sqs_client.get_queue_url(QueueName=queue_name)
            resolved = response.get("QueueUrl")
            if resolved:
                _QUEUE_URL_CACHE[cache_key] = resolved
                return resolved, "aws_get_queue_url"
        except Exception:
            continue

    try:
        suffix = _suffix(queue_type)
        prefix = os.getenv("PROJECT_NAME", "vaap").strip() or "vaap"
        response = sqs_client.list_queues(QueueNamePrefix=f"{prefix}-")
        queue_urls = response.get("QueueUrls", [])
        matched = [u for u in queue_urls if u.endswith(suffix)]
        if matched:
            resolved = matched[0]
            _QUEUE_URL_CACHE[cache_key] = resolved
            return resolved, "aws_list_queues"
    except Exception:
        pass

    return None, "unresolved"
