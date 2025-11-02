import asyncio
import copy
import hashlib
import inspect
import math
import pickle
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from functools import lru_cache, wraps
from typing import Any, TypedDict, TypeVar, cast

from redis.asyncio import Redis

from src.core.cache.client import get_redis_client
from src.core.config import get_settings

settings = get_settings()


class CacheResponse(TypedDict):
    timestamp: float | int
    value: Any
    parameters: Any


_DEFAULT_CONCURRENT_CHECK_INTERVAL: float = 0.05
KeySerializer = Callable[[tuple[Any, ...], dict[str, Any]], str]
ValidationFunction = Callable[[tuple[Any, ...], dict[str, Any], CacheResponse], bool]


FuncType = TypeVar("FuncType", bound=Callable[..., Awaitable[Any]])


def _gen_key(obj: Any) -> str:
    return f"{type(obj)}_{obj}"


def _sorted_by_keys(dict_: dict[Any, Any]) -> dict[Any, Any]:
    sorted_keys = sorted(dict_.keys(), key=_gen_key)
    return {key: dict_[key] for key in sorted_keys}


def _sort_dicts(
    obj: Any,
) -> None:
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _sort_dicts(item)

    if isinstance(obj, dict):
        for value in obj.values():
            _sort_dicts(value)

    if isinstance(obj, dict) and not isinstance(obj, OrderedDict):
        tmp = _sorted_by_keys(obj)
        obj.clear()
        obj.update(tmp)


def sorted_dicts_args(args: tuple[Any, ...]) -> tuple[Any, ...]:
    args_copy = copy.deepcopy(args)
    for arg in args_copy:
        _sort_dicts(arg)
    return args_copy


def sorted_dicts(dict_: dict[str, Any]) -> dict[str, Any]:
    sorted_dict = _sorted_by_keys(copy.deepcopy(dict_))
    for value in sorted_dict.values():
        _sort_dicts(value)
    return sorted_dict


def hash_key(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    sorted_args = sorted_dicts_args(args)
    sorted_kwargs = sorted_dicts(kwargs)

    s = f"{sorted_args}, {sorted_kwargs}"
    return hashlib.sha256(s.encode()).hexdigest()


class RedisCache:
    def __init__(
        self,
        redis_client: Redis,
        *,
        prefix: str = "rc",
    ) -> None:
        self.client = redis_client
        self.prefix = prefix

    def cache(
        self,
        *,
        ignore_positionals: list[int] | None = None,
        ignore_kw: list[str] | None = None,
        validation_func: ValidationFunction | None = None,
        ttl: float | None = None,
        serializer: Callable[[Any], bytes] = pickle.dumps,
        deserializer: Callable[[bytes], Any] = pickle.loads,
        key_serializer: KeySerializer = hash_key,
        namespace: str | None = None,
        ignore_validation_error: bool = True,
        concurrent_max_wait_time: float = 0,
        concurrent_check_interval: float = _DEFAULT_CONCURRENT_CHECK_INTERVAL,
    ) -> Callable[[FuncType], FuncType]:
        ignore_positionals_set = set(ignore_positionals or [])
        ignore_kw_set = set(ignore_kw or [])
        effective_check_interval = (
            concurrent_check_interval
            if concurrent_check_interval > 0
            else _DEFAULT_CONCURRENT_CHECK_INTERVAL
        )

        def decorator(func: FuncType) -> FuncType:
            if not inspect.iscoroutinefunction(func):
                raise TypeError("RedisCache only supports async callables.")

            resolved_namespace = namespace or f"{func.__module__}.{func.__qualname__}"
            base_components = [
                component for component in (self.prefix, resolved_namespace) if component
            ]
            key_prefix = ":".join(base_components)

            def _normalize_parameters(
                call_args: tuple[Any, ...], call_kwargs: dict[str, Any]
            ) -> tuple[tuple[Any, ...], dict[str, Any]]:
                filtered_args = tuple(
                    value
                    for index, value in enumerate(call_args)
                    if index not in ignore_positionals_set
                )
                filtered_kwargs = {
                    key: value for key, value in call_kwargs.items() if key not in ignore_kw_set
                }
                return filtered_args, filtered_kwargs

            def _build_cache_key(
                call_args: tuple[Any, ...],
                call_kwargs: dict[str, Any],
            ) -> tuple[str, tuple[Any, ...], dict[str, Any]]:
                filtered_args, filtered_kwargs = _normalize_parameters(call_args, call_kwargs)
                hashed = key_serializer(filtered_args, filtered_kwargs)
                cache_key = ":".join([key_prefix, hashed]) if hashed else key_prefix
                return cache_key, filtered_args, filtered_kwargs

            async def _load_cached_response(cache_key: str) -> CacheResponse | None:
                try:
                    raw_value = await self.client.get(cache_key)
                except Exception:
                    return None

                if raw_value is None:
                    return None

                if not isinstance(raw_value, (bytes, bytearray)):
                    return None

                try:
                    cached_value = deserializer(bytes(raw_value))
                except Exception:
                    if ignore_validation_error:
                        return None
                    raise

                if not isinstance(cached_value, dict):
                    return None

                if "value" not in cached_value:
                    return None

                return cast(CacheResponse, cached_value)

            async def _resolve_cached_value(
                call_args: tuple[Any, ...],
                call_kwargs: dict[str, Any],
                *,
                precomputed_cache_key: str | None = None,
            ) -> Any | None:
                cache_key_local = precomputed_cache_key
                if cache_key_local is None:
                    cache_key_local, _, _ = _build_cache_key(call_args, call_kwargs)

                cached_response = await _load_cached_response(cache_key_local)
                if cached_response is None:
                    return None

                try:
                    if validation_func is None or validation_func(
                        call_args, call_kwargs, cached_response
                    ):
                        return cached_response["value"]
                except Exception:
                    if not ignore_validation_error:
                        raise
                    return None

                return None

            async def _invalidate(call_args: tuple[Any, ...], call_kwargs: dict[str, Any]) -> int:
                cache_key_local, _, _ = _build_cache_key(call_args, call_kwargs)
                try:
                    deleted = await self.client.delete(cache_key_local)
                except Exception:
                    if ignore_validation_error:
                        return 0
                    raise
                return int(deleted or 0)

            async def _get_cached_timestamp(
                call_args: tuple[Any, ...], call_kwargs: dict[str, Any]
            ) -> float | int | None:
                cache_key_local, _, _ = _build_cache_key(call_args, call_kwargs)
                cached_response = await _load_cached_response(cache_key_local)
                if cached_response is None:
                    return None

                timestamp = cached_response.get("timestamp")
                if isinstance(timestamp, (int, float)):
                    return timestamp

                if ignore_validation_error:
                    return None

                raise TypeError(f"Invalid cache timestamp type: {type(timestamp)}")

            async def _invalidate_all() -> int:
                pattern = f"{key_prefix}:*"
                deleted = 0
                batch: list[Any] = []

                try:
                    async for cache_key in self.client.scan_iter(pattern):
                        batch.append(cache_key)
                        if len(batch) >= 128:
                            deleted += int(await self.client.delete(*batch) or 0)
                            batch.clear()
                    if batch:
                        deleted += int(await self.client.delete(*batch) or 0)
                except Exception:
                    if ignore_validation_error:
                        return deleted
                    raise

                return deleted

            async def _is_cached(call_args: tuple[Any, ...], call_kwargs: dict[str, Any]) -> bool:
                cache_key_local, _, _ = _build_cache_key(call_args, call_kwargs)
                try:
                    result = await self.client.exists(cache_key_local)
                except Exception:
                    if ignore_validation_error:
                        return False
                    raise
                return bool(result)

            async def _has_valid_value(
                call_args: tuple[Any, ...], call_kwargs: dict[str, Any]
            ) -> bool:
                cached = await _resolve_cached_value(call_args, call_kwargs)
                return cached is not None

            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key, key_args, key_kwargs = _build_cache_key(args, kwargs)
                lock_key = f"{cache_key}:lock"

                cached_result = await _resolve_cached_value(
                    args, kwargs, precomputed_cache_key=cache_key
                )
                if cached_result is not None:
                    return cached_result

                have_lock = False

                if concurrent_max_wait_time > 0:
                    deadline = time.monotonic() + concurrent_max_wait_time
                    lock_ttl = max(int(math.ceil(concurrent_max_wait_time)), 1)

                    while time.monotonic() < deadline:
                        cached_result = await _resolve_cached_value(
                            args, kwargs, precomputed_cache_key=cache_key
                        )
                        if cached_result is not None:
                            return cached_result

                        try:
                            acquired = await self.client.set(lock_key, b"1", nx=True, ex=lock_ttl)
                        except Exception:
                            acquired = False

                        if acquired:
                            have_lock = True
                            break

                        await asyncio.sleep(effective_check_interval)

                    if not have_lock:
                        cached_result = await _resolve_cached_value(
                            args, kwargs, precomputed_cache_key=cache_key
                        )
                        if cached_result is not None:
                            return cached_result

                try:
                    result = await func(*args, **kwargs)
                except Exception:
                    if have_lock:
                        try:
                            await self.client.delete(lock_key)
                        except Exception:
                            pass
                    raise

                ttl_kwargs: dict[str, Any] = {}
                if ttl is not None:
                    ttl_seconds = float(ttl)
                    if ttl_seconds <= 0:
                        if have_lock:
                            try:
                                await self.client.delete(lock_key)
                            except Exception:
                                pass
                        return result

                    if ttl_seconds.is_integer():
                        ttl_kwargs["ex"] = int(ttl_seconds)
                    else:
                        ttl_kwargs["px"] = max(int(ttl_seconds * 1000), 1)

                cache_payload: CacheResponse = {
                    "timestamp": time.time(),
                    "value": result,
                    "parameters": {"args": key_args, "kwargs": key_kwargs},
                }

                try:
                    serialized = serializer(cache_payload)
                    if isinstance(serialized, bytearray):
                        serialized = bytes(serialized)
                    if not isinstance(serialized, (bytes, bytearray)):
                        raise TypeError("Serializer must return bytes-like object.")

                    await self.client.set(cache_key, serialized, **ttl_kwargs)
                except Exception:
                    if not ignore_validation_error:
                        raise
                finally:
                    if have_lock:
                        try:
                            await self.client.delete(lock_key)
                        except Exception:
                            pass

                return result

            async def invalidate(*call_args: Any, **call_kwargs: Any) -> int:
                return await _invalidate(call_args, call_kwargs)

            async def invalidate_all() -> int:
                return await _invalidate_all()

            async def is_cached(*call_args: Any, **call_kwargs: Any) -> bool:
                return await _is_cached(call_args, call_kwargs)

            async def has_valid_value(*call_args: Any, **call_kwargs: Any) -> bool:
                return await _has_valid_value(call_args, call_kwargs)

            async def get_cached_timestamp(
                *call_args: Any, **call_kwargs: Any
            ) -> float | int | None:
                return await _get_cached_timestamp(call_args, call_kwargs)

            def cache_key_for(*call_args: Any, **call_kwargs: Any) -> str:
                return _build_cache_key(call_args, call_kwargs)[0]

            wrapper.invalidate = invalidate
            wrapper.invalidate_all = invalidate_all
            wrapper.is_cached = is_cached
            wrapper.has_valid_value = has_valid_value
            wrapper.get_cached_timestamp = get_cached_timestamp
            wrapper.cache_instance = self
            wrapper.cache_key_for = cache_key_for
            wrapper.cache_namespace = resolved_namespace

            return cast(FuncType, wrapper)

        return decorator


@lru_cache(1)
def get_local_redis_cache() -> RedisCache:
    return RedisCache(get_redis_client(), prefix=settings.CACHE_PREFIX)


def redis_cache_decorator(
    ignore_positionals: list[int] | None = None,
    ignore_kw: list[str] | None = None,
    validation_func: ValidationFunction | None = None,
    ttl: float | None = None,
    serializer: Callable[[Any], bytes] = pickle.dumps,
    deserializer: Callable[[bytes], Any] = pickle.loads,
    key_serializer: KeySerializer = hash_key,
    namespace: str | None = None,
    ignore_validation_error: bool = True,
    concurrent_max_wait_time: float = 0,
    concurrent_check_interval: float = _DEFAULT_CONCURRENT_CHECK_INTERVAL,
) -> Callable[[FuncType], FuncType]:
    def decorator(func: FuncType) -> FuncType:
        cache = get_local_redis_cache()
        cached_func = cache.cache(
            ignore_positionals=ignore_positionals,
            ignore_kw=ignore_kw,
            validation_func=validation_func,
            ttl=ttl,
            serializer=serializer,
            deserializer=deserializer,
            key_serializer=key_serializer,
            namespace=namespace,
            ignore_validation_error=ignore_validation_error,
            concurrent_max_wait_time=concurrent_max_wait_time,
            concurrent_check_interval=concurrent_check_interval,
        )(func)

        return cached_func

    return decorator
