"""Utilities for API response compression (gzip / optional brotli)."""

from __future__ import annotations

import gzip
from typing import Optional

try:
    import brotli  # type: ignore
except Exception:  # pragma: no cover
    brotli = None


COMPRESSIBLE_CONTENT_TYPES = (
    "application/json",
    "text/plain",
    "text/html",
    "text/css",
    "application/javascript",
    "application/xml",
)


def is_compressible_content_type(content_type: str) -> bool:
    if not content_type:
        return False
    ctype = content_type.split(";", 1)[0].strip().lower()
    return ctype in COMPRESSIBLE_CONTENT_TYPES


def choose_encoding(
    accept_encoding: str,
    *,
    allow_brotli: bool,
    allow_gzip: bool,
) -> Optional[str]:
    """Choose preferred encoding from Accept-Encoding."""
    header = (accept_encoding or "").lower()
    if allow_brotli and brotli is not None and "br" in header:
        return "br"
    if allow_gzip and "gzip" in header:
        return "gzip"
    return None


def compress_payload(payload: bytes, encoding: str, *, gzip_level: int, brotli_quality: int) -> bytes:
    """Compress payload by selected encoding."""
    if encoding == "gzip":
        return gzip.compress(payload, compresslevel=gzip_level)
    if encoding == "br":
        if brotli is None:
            raise RuntimeError("brotli_not_available")
        return brotli.compress(payload, quality=brotli_quality)
    raise ValueError(f"unsupported_encoding: {encoding}")


def merge_vary_accept_encoding(existing: str | None) -> str:
    """Ensure Vary header includes Accept-Encoding exactly once."""
    parts = [p.strip() for p in (existing or "").split(",") if p.strip()]
    lowered = {p.lower() for p in parts}
    if "accept-encoding" not in lowered:
        parts.append("Accept-Encoding")
    return ", ".join(parts)

