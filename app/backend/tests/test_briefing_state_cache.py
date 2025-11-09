"""Tests for BriefingStateCache - Redis-based state management."""

from uuid import uuid4

import pytest

from src.core.cache.client import get_redis_client
from src.services.briefing.state_cache import BriefingStateCache


@pytest.fixture
def state_cache() -> BriefingStateCache:
    """Create state cache with fakeredis."""
    return BriefingStateCache(redis_client=get_redis_client())


@pytest.fixture
def state_cache_disabled() -> BriefingStateCache:
    """Create state cache with caching disabled."""
    return BriefingStateCache(redis_client=None)


@pytest.mark.asyncio
async def test_set_and_get_state(state_cache: BriefingStateCache):
    """Test setting and getting cached state."""
    briefing_id = uuid4()
    state = {
        "status": "in_progress",
        "current_question": 2,
        "answers": {"1": "Apartamento"},
    }

    await state_cache.set_state(briefing_id, state)
    cached_state = await state_cache.get_state(briefing_id)

    assert cached_state is not None
    assert cached_state["status"] == "in_progress"
    assert cached_state["current_question"] == 2
    assert cached_state["answers"]["1"] == "Apartamento"


@pytest.mark.asyncio
async def test_get_state_not_cached(state_cache: BriefingStateCache):
    """Test getting state that was never cached."""
    briefing_id = uuid4()

    cached_state = await state_cache.get_state(briefing_id)

    assert cached_state is None


@pytest.mark.asyncio
async def test_invalidate_state(state_cache: BriefingStateCache):
    """Test invalidating cached state."""
    briefing_id = uuid4()
    state = {"status": "in_progress"}

    await state_cache.set_state(briefing_id, state)
    assert await state_cache.get_state(briefing_id) is not None

    await state_cache.invalidate_state(briefing_id)
    assert await state_cache.get_state(briefing_id) is None


@pytest.mark.asyncio
async def test_set_and_get_current_question(state_cache: BriefingStateCache):
    """Test caching current question order."""
    briefing_id = uuid4()

    await state_cache.set_current_question(briefing_id, question_order=3)
    cached_order = await state_cache.get_current_question(briefing_id)

    assert cached_order == 3


@pytest.mark.asyncio
async def test_get_current_question_not_cached(state_cache: BriefingStateCache):
    """Test getting current question that was never cached."""
    briefing_id = uuid4()

    cached_order = await state_cache.get_current_question(briefing_id)

    assert cached_order is None


@pytest.mark.asyncio
async def test_disabled_cache_set_state(state_cache_disabled: BriefingStateCache):
    """Test that disabled cache doesn't store state."""
    briefing_id = uuid4()
    state = {"status": "in_progress"}

    await state_cache_disabled.set_state(briefing_id, state)
    cached_state = await state_cache_disabled.get_state(briefing_id)

    assert cached_state is None


@pytest.mark.asyncio
async def test_disabled_cache_current_question(state_cache_disabled: BriefingStateCache):
    """Test that disabled cache doesn't store current question."""
    briefing_id = uuid4()

    await state_cache_disabled.set_current_question(briefing_id, 2)
    cached_order = await state_cache_disabled.get_current_question(briefing_id)

    assert cached_order is None


@pytest.mark.asyncio
async def test_disabled_cache_enabled_flag(state_cache_disabled: BriefingStateCache):
    """Test that disabled cache has enabled=False."""
    assert state_cache_disabled.enabled is False


@pytest.mark.asyncio
async def test_enabled_cache_enabled_flag(state_cache: BriefingStateCache):
    """Test that enabled cache has enabled=True."""
    assert state_cache.enabled is True


@pytest.mark.asyncio
async def test_cache_complex_state(state_cache: BriefingStateCache):
    """Test caching complex nested state data."""
    briefing_id = uuid4()
    state = {
        "status": "in_progress",
        "current_question": 5,
        "answers": {
            "1": "Apartamento",
            "2": "80",
            "3": "R$ 50.000",
            "4": "Cozinha, banheiro",
        },
        "metadata": {
            "started_at": "2025-10-26T10:00:00",
            "client_name": "João Silva",
        },
    }

    await state_cache.set_state(briefing_id, state)
    cached_state = await state_cache.get_state(briefing_id)

    assert cached_state is not None
    assert cached_state["answers"]["4"] == "Cozinha, banheiro"
    assert cached_state["metadata"]["client_name"] == "João Silva"


def test_get_key_format(state_cache: BriefingStateCache):
    """Test Redis key format."""
    briefing_id = uuid4()
    key = state_cache._get_key(briefing_id)

    assert key == f"briefing:state:{briefing_id}"
    assert key.startswith("briefing:state:")
