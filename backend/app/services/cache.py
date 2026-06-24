import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Minimal in-memory TTL cache. Phase 3 scope: one process, no persistence.

    Production path is a Redis cache layer (see PLAN.md Stack table); this
    is the POC stand-in for the documented 1hr compliance/shortage cache.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, _Entry[T]] = {}

    def has(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry is None:
            return False
        if time.monotonic() >= entry.expires_at:
            del self._store[key]
            return False
        return True

    def get(self, key: str) -> T | None:
        return self._store[key].value if self.has(key) else None

    def set(self, key: str, value: T) -> None:
        self._store[key] = _Entry(value=value, expires_at=time.monotonic() + self.ttl_seconds)

    def age_seconds(self, key: str) -> float | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        return self.ttl_seconds - (entry.expires_at - time.monotonic())
