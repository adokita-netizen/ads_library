"""Simple in-memory circuit breaker for external integrations."""

import time
from threading import Lock


class CircuitBreaker:
    """Three-state circuit breaker: closed, open, half_open."""

    def __init__(self, failure_threshold: int = 3, reset_timeout_seconds: int = 60):
        self.failure_threshold = max(1, int(failure_threshold))
        self.reset_timeout_seconds = max(1, int(reset_timeout_seconds))
        self._state = "closed"
        self._failure_count = 0
        self._opened_at = 0.0
        self._lock = Lock()

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                now = time.time()
                if now - self._opened_at >= self.reset_timeout_seconds:
                    self._state = "half_open"
                    return True
                return False
            # half_open: allow one probe request
            return True

    def on_success(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._opened_at = 0.0

    def on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.time()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "reset_timeout_seconds": self.reset_timeout_seconds,
            }

