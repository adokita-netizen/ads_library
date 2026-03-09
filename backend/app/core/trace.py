"""Shared request/trace ID context helpers."""

from contextvars import ContextVar, Token

_current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)


def set_current_trace_id(trace_id: str | None) -> Token:
    return _current_trace_id.set(str(trace_id) if trace_id else None)


def reset_current_trace_id(token: Token) -> None:
    _current_trace_id.reset(token)


def get_current_trace_id() -> str | None:
    return _current_trace_id.get()


def build_trace_headers(trace_id: str | None = None) -> dict[str, str]:
    resolved = trace_id or get_current_trace_id()
    if not resolved:
        return {}
    return {"X-Request-ID": resolved, "X-Trace-ID": resolved}
