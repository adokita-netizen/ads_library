"""Cache key utilities with versioning convention."""

from __future__ import annotations


def build_cache_key(*, namespace: str, parts: list[str], version: str = "v1") -> str:
    clean_ns = (namespace or "default").strip().replace(":", "_")
    clean_ver = (version or "v1").strip().replace(":", "_")
    clean_parts = [str(p).strip().replace(":", "_") for p in parts if str(p).strip()]
    if not clean_parts:
        return f"{clean_ns}:{clean_ver}"
    return f"{clean_ns}:{clean_ver}:" + ":".join(clean_parts)

