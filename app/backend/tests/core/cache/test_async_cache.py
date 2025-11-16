"""Regression tests for async caching behavior."""

import pytest

from src.core.cache.decorator import redis_cache_decorator


def test_sync_functions_are_not_supported() -> None:
    with pytest.raises(TypeError):

        @redis_cache_decorator(ttl=60, namespace="test.sync")
        def sync_add(a: int, b: int) -> int:
            return a + b


@pytest.mark.asyncio
async def test_async_function_is_cached() -> None:
    counter = {"count": 0}

    @redis_cache_decorator(ttl=60, namespace="test.async")
    async def async_add(a: int, b: int) -> int:
        counter["count"] += 1
        return a + b

    result1 = await async_add(1, 2)
    assert result1 == 3
    assert counter["count"] == 1

    result2 = await async_add(1, 2)
    assert result2 == 3
    assert counter["count"] == 1
