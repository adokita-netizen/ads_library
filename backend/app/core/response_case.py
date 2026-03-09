"""Utilities for dual snake_case/camelCase API response output."""

from __future__ import annotations

import re
from typing import Any

_CAMEL_BOUNDARY_RE = re.compile(r"(?<!^)(?=[A-Z])")


def snake_to_camel(key: str) -> str:
    """Convert snake_case key to camelCase."""
    if "_" not in key:
        return key
    parts = key.split("_")
    if not parts:
        return key
    head = parts[0]
    tail = "".join(part[:1].upper() + part[1:] for part in parts[1:] if part)
    return f"{head}{tail}"


def camel_to_snake(key: str) -> str:
    """Convert camelCase/PascalCase key to snake_case."""
    if not key or "_" in key:
        return key
    return _CAMEL_BOUNDARY_RE.sub("_", key).lower()


def with_dual_case_keys(value: Any) -> Any:
    """Recursively duplicate dict keys into both snake_case and camelCase forms.

    Existing keys are preserved and never overwritten.
    """
    if isinstance(value, list):
        return [with_dual_case_keys(item) for item in value]

    if not isinstance(value, dict):
        return value

    out: dict[Any, Any] = {}
    for key, raw_val in value.items():
        converted_val = with_dual_case_keys(raw_val)
        out[key] = converted_val

        if not isinstance(key, str):
            continue

        camel_key = snake_to_camel(key)
        if camel_key not in out:
            out[camel_key] = converted_val

        snake_key = camel_to_snake(key)
        if snake_key not in out:
            out[snake_key] = converted_val

    return out
