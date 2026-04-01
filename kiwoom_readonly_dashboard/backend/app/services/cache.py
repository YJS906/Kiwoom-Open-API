"""Simple in-memory TTL cache."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar


T = TypeVar("T")


@dataclass
class CacheItem:
    value: Any
    expires_at: float


class TTLCache:
    """A small async-friendly TTL cache."""

    def __init__(self) -> None:
        self._data: dict[str, CacheItem] = {}
        self._lock = asyncio.Lock()

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            return None
        if item.expires_at < time.monotonic():
            self._data.pop(key, None)
            return None
        return item.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> Any:
        self._data[key] = CacheItem(value=value, expires_at=time.monotonic() + ttl_seconds)
        return value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    async def get_or_set(
        self,
        key: str,
        ttl_seconds: int,
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached

        async with self._lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            value = await factory()
            self.set(key, value, ttl_seconds)
            return value

