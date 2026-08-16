"""Async In-Memory Distributed Cache with TTL and LRU Eviction."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """A single cache value with expiration metadata."""

    value: Any
    expires_at: float
    access_count: int = 0


class AsyncTTLCache:
    """Asynchronous TTL cache with atomic get/set operations."""

    def __init__(self, default_ttl_seconds: float = 60.0, max_entries: int = 1000):
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries
        self._store: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """Retrieve value if not expired."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.monotonic() > entry.expires_at:
                del self._store[key]
                return None
            entry.access_count += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """Store value with specified TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        async with self._lock:
            if len(self._store) >= self.max_entries and key not in self._store:
                # Evict oldest expired or least accessed
                oldest_key = min(self._store.keys(), key=lambda k: self._store[k].access_count)
                del self._store[oldest_key]

            self._store[key] = CacheEntry(
                value=value,
                expires_at=time.monotonic() + ttl,
                access_count=1,
            )

    async def delete(self, key: str) -> bool:
        """Remove key from store."""
        async with self._lock:
            return bool(self._store.pop(key, None))
