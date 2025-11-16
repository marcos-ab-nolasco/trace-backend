import asyncio
import json
from typing import Any

import pytest

from src.core.cache.client import get_redis_client
from src.core.cache.decorator import hash_key, redis_cache_decorator
from src.core.config import get_settings


def collect_call_counter() -> dict[str, int]:
    return {"count": 0}


async def decode_keys(pattern: str = "*") -> set[str]:
    redis_client = get_redis_client()
    keys: set[str] = set()
    async for key in redis_client.scan_iter(pattern):
        decoded = key.decode() if isinstance(key, bytes) else key
        keys.add(decoded)
    return keys


async def test_cache_returns_cached_value() -> None:
    counter = collect_call_counter()

    @redis_cache_decorator()
    async def add(a: int, b: int) -> int:
        counter["count"] += 1
        return a + b

    assert await add(1, 2) == 3
    assert await add(1, 2) == 3
    assert counter["count"] == 1
    assert len(await decode_keys()) == 1


async def test_cache_ignores_selected_positionals() -> None:
    counter = collect_call_counter()

    @redis_cache_decorator(ignore_positionals=[0])
    async def combine(_ignored: str, value: int) -> int:
        counter["count"] += 1
        return value * 2

    assert await combine("first", 3) == 6
    assert await combine("second", 3) == 6
    assert counter["count"] == 1


async def test_cache_ignores_selected_keywords() -> None:
    counter = collect_call_counter()

    @redis_cache_decorator(ignore_kw=["noise"])
    async def operate(value: int, *, noise: int, scale: int) -> int:
        counter["count"] += 1
        return value * scale

    assert await operate(5, noise=1, scale=2) == 10
    assert await operate(5, noise=999, scale=2) == 10
    assert counter["count"] == 1


async def test_cache_custom_key_serializer_receives_filtered_arguments() -> None:
    seen: dict[str, Any] = {}

    def serializer(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        seen["args"] = args
        seen["kwargs"] = kwargs
        return "static"

    @redis_cache_decorator(ignore_positionals=[0], ignore_kw=["debug"], key_serializer=serializer)
    async def target(_noise: str, value: int, *, debug: bool, flag: str) -> str:
        return f"{value}:{flag}"

    assert await target("ignored", 7, debug=True, flag="ok") == "7:ok"
    assert seen["args"] == (7,)
    assert seen["kwargs"] == {"flag": "ok"}


async def test_cache_uses_custom_namespace() -> None:
    @redis_cache_decorator(namespace="custom")
    async def work(value: int) -> int:
        return value + 1

    assert await work(4) == 5
    key = next(iter(await decode_keys()))
    assert key.startswith("test_cache:custom:")


async def test_cache_defaults_namespace_to_module_and_qualname() -> None:
    @redis_cache_decorator()
    async def sample(value: int) -> int:
        return value - 1

    assert await sample(10) == 9
    key = next(iter(await decode_keys()))
    expected_namespace = f"{sample.__module__}.{sample.__qualname__}"
    assert key.startswith(f"test_cache:{expected_namespace}:")


async def test_cache_uses_validation_function() -> None:
    counter = collect_call_counter()
    validation_calls: list[tuple[tuple[Any, ...], dict[str, Any], Any]] = []

    def validation(args: tuple[Any, ...], kwargs: dict[str, Any], response: dict[str, Any]) -> bool:
        validation_calls.append((args, kwargs, response["value"]))
        return True

    @redis_cache_decorator(validation_func=validation)
    async def compute(value: int) -> int:
        counter["count"] += 1
        return value * value

    assert await compute(3) == 9
    assert await compute(3) == 9
    assert counter["count"] == 1
    assert len(validation_calls) == 1


async def test_cache_recomputes_when_validation_returns_false() -> None:
    counter = collect_call_counter()

    def validation(*_: Any) -> bool:
        return False

    @redis_cache_decorator(validation_func=validation)
    async def produce() -> int:
        counter["count"] += 1
        return counter["count"]

    assert await produce() == 1
    assert await produce() == 2
    assert counter["count"] == 2


async def test_cache_validation_errors_respected_when_not_ignored() -> None:
    def validation(*_: Any) -> bool:
        raise RuntimeError("invalid")

    @redis_cache_decorator(validation_func=validation, ignore_validation_error=False)
    async def creator() -> int:
        return 1

    assert await creator() == 1
    with pytest.raises(RuntimeError):
        await creator()


async def test_cache_validation_errors_suppressed_by_default() -> None:
    counter = collect_call_counter()

    def validation(*_: Any) -> bool:
        raise RuntimeError("validation failed")

    @redis_cache_decorator(validation_func=validation)
    async def generator() -> int:
        counter["count"] += 1
        return counter["count"]

    assert await generator() == 1
    assert await generator() == 2
    assert counter["count"] == 2


async def test_cache_respects_positive_ttl() -> None:
    redis_client = get_redis_client()
    counter = collect_call_counter()

    @redis_cache_decorator(ttl=1.0)
    async def target() -> int:
        counter["count"] += 1
        return counter["count"]

    assert await target() == 1
    key = target.cache_key_for()
    ttl_ms = await redis_client.pttl(key)
    assert ttl_ms is not None and ttl_ms > 0
    assert await target() == 1
    await asyncio.sleep(1.2)
    assert await target() == 2


async def test_cache_skips_storage_when_ttl_non_positive() -> None:
    counter = collect_call_counter()

    @redis_cache_decorator(ttl=0)
    async def target() -> int:
        counter["count"] += 1
        return counter["count"]

    assert await target() == 1
    assert await target() == 2
    assert counter["count"] == 2
    assert not await decode_keys()


async def test_cache_accepts_custom_serializer() -> None:
    dumps_calls = {"count": 0}
    loads_calls = {"count": 0}

    def dumps(value: Any) -> bytes:
        dumps_calls["count"] += 1
        return json.dumps(value).encode()

    def loads(blob: bytes) -> Any:
        loads_calls["count"] += 1
        return json.loads(blob.decode())

    @redis_cache_decorator(serializer=dumps, deserializer=loads)
    async def echo(value: int) -> int:
        return value

    assert await echo(8) == 8
    assert await echo(8) == 8
    assert dumps_calls["count"] == 1
    assert loads_calls["count"] == 1


async def test_cache_recomputes_when_serializer_returns_non_bytes() -> None:
    counter = collect_call_counter()

    def bad_serializer(_: Any) -> str:
        return "not-bytes"

    @redis_cache_decorator(serializer=bad_serializer)
    async def value() -> int:
        counter["count"] += 1
        return counter["count"]

    assert await value() == 1
    assert await value() == 2
    assert counter["count"] == 2


async def test_cache_helper_methods_expose_cache_controls() -> None:
    @redis_cache_decorator()
    async def work(value: int) -> int:
        return value * 3

    result = await work(5)
    assert result == 15

    assert await work.is_cached(5)
    assert await work.has_valid_value(5)
    timestamp = await work.get_cached_timestamp(5)
    assert isinstance(timestamp, float)

    assert await work.invalidate(5) == 1
    assert not await work.is_cached(5)
    assert await work.invalidate_all() >= 0

    settings = get_settings()
    assert work.cache_instance.prefix == settings.CACHE_PREFIX
    key = work.cache_key_for(5)
    expected_hash = hash_key((5,), {})
    expected_namespace = f"{work.__module__}.{work.__qualname__}"
    assert key == f"{settings.CACHE_PREFIX}:{expected_namespace}:{expected_hash}"
    assert work.cache_namespace == expected_namespace


async def test_cache_invalidate_all_removes_each_entry() -> None:
    @redis_cache_decorator(namespace="batch")
    async def fn(value: int) -> int:
        return value * 10

    assert await fn(1) == 10
    assert await fn(2) == 20
    assert len(await decode_keys()) == 2
    assert await fn.invalidate_all() == 2
    assert not await decode_keys()


async def test_cache_concurrent_calls_share_computation() -> None:
    counter = collect_call_counter()
    started = asyncio.Event()
    release = asyncio.Event()
    results: list[int] = []
    errors: list[Exception] = []

    @redis_cache_decorator(concurrent_max_wait_time=1.0, concurrent_check_interval=0.01)
    async def slow(value: int) -> int:
        counter["count"] += 1
        started.set()
        await release.wait()
        return value * 4

    async def worker() -> None:
        try:
            results.append(await slow(5))
        except Exception as exc:
            errors.append(exc)

    first = asyncio.create_task(worker())
    await asyncio.wait_for(started.wait(), timeout=0.5)
    second = asyncio.create_task(worker())
    await asyncio.sleep(0.05)
    release.set()
    await asyncio.gather(first, second)

    assert not errors
    assert counter["count"] == 1
    assert len(results) == 2
    assert all(value == 20 for value in results)


async def test_cache_key_for_matches_storage() -> None:
    @redis_cache_decorator(namespace="keys")
    async def fn(value: int, *, flag: str) -> str:
        return f"{value}:{flag}"

    assert await fn(3, flag="on") == "3:on"
    key = fn.cache_key_for(3, flag="on")
    stored_keys = await decode_keys()
    assert key in stored_keys
