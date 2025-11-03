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


@pytest.fixture
def mock_extraction_service(mocker: MockerFixture) -> Any:
    """Mock ExtractionService for briefing tests.

    Returns a mock that can be configured per-test.
    Tests should configure the return value like:
        mock_extraction_service.return_value = ExtractedClientInfo(...)
    """
    from src.schemas.briefing import ExtractedClientInfo

    mock = mocker.AsyncMock(
        return_value=ExtractedClientInfo(
            name="Test Client",
            phone="11999999999",
            project_type="residencial",
            confidence=0.95,
            raw_text="Test message",
        )
    )
    mocker.patch("src.api.briefings.ExtractionService.extract_client_info", new=mock)
    return mock


@pytest.fixture
def mock_whatsapp_service(mocker: MockerFixture) -> Any:
    """Mock WhatsAppService for briefing tests.

    Returns a mock that simulates successful WhatsApp message sending.
    """
    mock = mocker.AsyncMock(return_value={"success": True, "message_id": "wamid.test123"})
    mocker.patch("src.api.briefings.WhatsAppService.send_text_message", new=mock)
    return mock


@pytest.fixture
def mock_template_service(mocker: MockerFixture) -> Any:
    """Mock TemplateService for briefing tests.

    Returns a mock that can be configured per-test to return specific template versions.
    """
    mock = mocker.AsyncMock()
    mocker.patch(
        "src.services.template_service.TemplateService.select_template_version_for_project",
        new=mock,
    )
    return mock


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
