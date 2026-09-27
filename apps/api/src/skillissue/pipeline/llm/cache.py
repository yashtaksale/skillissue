"""Prompt cache with 30-day TTL (T-4.5)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

DEFAULT_TTL_SECONDS = 30 * 24 * 3600  # 30 days


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class LLMCache:
    """In-memory LLM response cache keyed by content hash.

    Default TTL: 30 days. Suitable for unit tests and a single scan
    run; for production use a Redis-backed implementation.
    """

    def __init__(self, *, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.expires_at < time.time():
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = CacheEntry(value=value, expires_at=time.time() + self._ttl)

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    @property
    def stats(self) -> dict[str, int | float]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._store),
            "hit_rate": self.hit_rate,
        }
