"""Mock-related test fixtures."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from fakeredis.aioredis import FakeRedis
from pytest_mock import MockerFixture

from src.core.cache.client import get_redis_client


@pytest.fixture(autouse=True)
def avoid_external_requests(mocker: MockerFixture) -> None:
    """Block external HTTP requests during tests.

    Note: AsyncClient with ASGITransport doesn't make real HTTP requests,
    so we only block real network calls via HTTPTransport.
    """

    def fail(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("External HTTP communication disabled for tests")

    # Block real HTTP requests
    mocker.patch("httpx._transports.default.AsyncHTTPTransport.handle_async_request", new=fail)
    mocker.patch("httpx._transports.default.HTTPTransport.handle_request", new=fail)


@pytest.fixture(autouse=True)
def mock_ai_service(mocker: MockerFixture) -> Any:
    """Mock AI service globally to prevent slow external API calls during tests.

    Tests that need specific AI service behavior can override this by patching
    'src.services.chat.get_ai_service' again in the test.
    """
    mock_service = mocker.Mock()
    mock_service.generate_response = mocker.AsyncMock(return_value="Mocked AI response")
    mocker.patch("src.services.chat.get_ai_service", return_value=mock_service)
    return mock_service


@pytest.fixture(autouse=True)
def patch_redis() -> Generator[Any, Any, Any]:
    """Patch Redis with FakeRedis for testing."""
    with patch("src.core.cache.client.Redis.from_url", return_value=FakeRedis()):
        get_redis_client.cache_clear()
        yield


@pytest.fixture(autouse=True)
async def clear_redis(patch_redis: Any):
    """Clear Redis cache and rate limit storage before/after each test."""
    from src.core.rate_limit import limiter, limiter_authenticated

    client = get_redis_client()
    await client.flushdb()

    # Clear rate limit storage (memory storage for tests)
    limiter.reset()
    limiter_authenticated.reset()

    yield

    await client.flushdb()
    limiter.reset()
    limiter_authenticated.reset()
