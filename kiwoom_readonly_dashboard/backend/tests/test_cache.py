"""Cache service tests."""

from __future__ import annotations

import asyncio

from app.services.cache import TTLCache


async def test_ttl_cache_returns_cached_value() -> None:
    cache = TTLCache()
    calls = {"count": 0}

    async def factory() -> int:
        calls["count"] += 1
        return 42

    first = await cache.get_or_set("answer", 60, factory)
    second = await cache.get_or_set("answer", 60, factory)

    assert first == 42
    assert second == 42
    assert calls["count"] == 1


async def test_ttl_cache_expires_value() -> None:
    cache = TTLCache()
    calls = {"count": 0}

    async def factory() -> int:
        calls["count"] += 1
        return calls["count"]

    first = await cache.get_or_set("value", 0, factory)
    await asyncio.sleep(0.01)
    second = await cache.get_or_set("value", 0, factory)

    assert first == 1
    assert second == 2
