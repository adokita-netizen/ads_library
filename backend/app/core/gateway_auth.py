"""API gateway authentication helpers."""

from __future__ import annotations

from fastapi import Request


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def is_protected_path(path: str, protected_prefixes: list[str]) -> bool:
    current = (path or "").strip()
    for prefix in protected_prefixes:
        if prefix and current.startswith(prefix):
            return True
    return False


def extract_request_api_key(request: Request) -> str | None:
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return token or None
    return None


def is_gateway_authorized(request: Request, allowed_keys: list[str]) -> bool:
    if not allowed_keys:
        return False
    provided = extract_request_api_key(request)
    if not provided:
        return False
    return provided in set(allowed_keys)

