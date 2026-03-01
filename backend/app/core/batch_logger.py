"""A82 (CI-095): Standard batch execution metadata logger.

Provides a context manager and decorator for recording batch job
execution history: who ran it, when, how many records processed,
duration, and outcome.

Logs are stored in exports/batch_history.jsonl (one JSON object per line).

Usage:
    from app.core.batch_logger import batch_run, log_batch_run

    # As context manager
    with batch_run("aggregate_metrics") as run:
        run.set_input({"target_date": "2026-03-01"})
        # ... do work ...
        run.set_result(created=42, skipped=10)

    # As decorator
    @log_batch_run("collect_metrics")
    def my_batch_job():
        return {"created": 42}
"""

import json
import os
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any

import logging

logger = logging.getLogger(__name__)

_HISTORY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "exports",
)
_HISTORY_FILE = os.path.join(_HISTORY_DIR, "batch_history.jsonl")


class BatchRun:
    """Tracks metadata for a single batch execution."""

    def __init__(self, job_name: str):
        self.job_name = job_name
        self.started_at = datetime.now(timezone.utc)
        self.start_time = time.monotonic()
        self.input_params: dict[str, Any] = {}
        self.result: dict[str, Any] = {}
        self.status = "running"
        self.error: str | None = None
        self.hostname = socket.gethostname()

    def set_input(self, params: dict[str, Any]):
        """Record input parameters."""
        self.input_params = params

    def set_result(self, **kwargs):
        """Record result metrics (e.g., created=42, skipped=10)."""
        self.result.update(kwargs)

    def _finalize(self, status: str, error: str | None = None):
        self.status = status
        self.error = error
        elapsed = time.monotonic() - self.start_time

        record = {
            "job_name": self.job_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(elapsed, 2),
            "status": self.status,
            "hostname": self.hostname,
            "input": self.input_params,
            "result": self.result,
        }
        if self.error:
            record["error"] = self.error

        _append_record(record)
        return record


def _append_record(record: dict):
    """Append a record to the batch history JSONL file."""
    try:
        os.makedirs(_HISTORY_DIR, exist_ok=True)
        with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning("batch_history_write_failed: %s", e)


@contextmanager
def batch_run(job_name: str):
    """Context manager that records batch execution metadata.

    Usage:
        with batch_run("my_job") as run:
            run.set_input({"date": "2026-03-01"})
            run.set_result(processed=100)
    """
    run = BatchRun(job_name)
    try:
        yield run
        run._finalize("completed")
    except Exception as e:
        run._finalize("failed", error=str(e))
        raise


def log_batch_run(job_name: str):
    """Decorator that logs batch execution metadata.

    The decorated function's return value is used as result metadata
    if it returns a dict.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            run = BatchRun(job_name)
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict):
                    run.result = result
                run._finalize("completed")
                return result
            except Exception as e:
                run._finalize("failed", error=str(e))
                raise
        return wrapper
    return decorator


def get_recent_runs(job_name: str | None = None, limit: int = 20) -> list[dict]:
    """Read recent batch runs from history file."""
    runs = []
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if job_name is None or record.get("job_name") == job_name:
                        runs.append(record)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return runs[-limit:]
