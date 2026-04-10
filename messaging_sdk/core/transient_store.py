"""
Small in-memory TTL stores for one-time and short-lived security state.

These stores are process-local. They improve security for single-instance and
development deployments, but they are not a substitute for Redis or database
backing in a horizontally scaled production environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any


@dataclass
class _Entry:
    value: Any
    expires_at: float


class ExpiringStore:
    def __init__(self):
        self._items: dict[str, _Entry] = {}
        self._lock = Lock()

    def _prune(self) -> None:
        now = monotonic()
        expired = [key for key, entry in self._items.items() if entry.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)

    def put(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._prune()
            self._items[key] = _Entry(value=value, expires_at=monotonic() + ttl_seconds)

    def pop(self, key: str) -> Any | None:
        with self._lock:
            self._prune()
            entry = self._items.pop(key, None)
            return None if entry is None else entry.value

    def get(self, key: str) -> Any | None:
        with self._lock:
            self._prune()
            entry = self._items.get(key)
            return None if entry is None else entry.value

    def contains(self, key: str) -> bool:
        with self._lock:
            self._prune()
            return key in self._items

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


class RateLimiter:
    def __init__(self):
        self._counters = ExpiringStore()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        current = self._counters.get(key)
        if current is None:
            self._counters.put(key, 1, window_seconds)
            return True
        if int(current) >= limit:
            return False
        self._counters.put(key, int(current) + 1, window_seconds)
        return True

    def clear(self) -> None:
        self._counters.clear()


used_token_store = ExpiringStore()
mobile_auth_code_store = ExpiringStore()
rate_limiter = RateLimiter()
