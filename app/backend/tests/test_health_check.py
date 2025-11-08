"""Tests for health check endpoint (Issue #6)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_basic(client: AsyncClient):
    """Test basic health check without any checks."""
    response = await client.get("/health_check")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_check_with_db(client: AsyncClient):
    """Test health check with database connectivity check."""
    response = await client.get("/health_check?check_db=true")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_check_with_redis(client: AsyncClient):
    """Test health check with Redis connectivity check (Issue #6).

    Tests that health check can verify Redis is responsive via PING command.
    """
    response = await client.get("/health_check?check_redis=true")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_check_redis_failure(client: AsyncClient):
    """Test health check detects Redis connection failure."""
    with patch("src.core.cache.client.get_redis_client") as mock_redis:
        mock_redis.return_value.ping = AsyncMock(side_effect=Exception("Connection refused"))

        response = await client.get("/health_check?check_redis=true")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["redis"] == "disconnected"
        assert "error" in data


@pytest.mark.asyncio
async def test_health_check_with_ai(client: AsyncClient):
    """Test health check with AI provider connectivity check (Issue #6).

    Tests that health check can verify OpenAI/Anthropic APIs are responsive.
    """
    response = await client.get("/health_check?check_ai=true")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    # AI can be "connected" if any provider is available, or "not_configured"
    assert data["ai"] in ["connected", "not_configured"]


@pytest.mark.asyncio
async def test_health_check_all_checks(client: AsyncClient):
    """Test health check with all checks enabled."""
    response = await client.get(
        "/health_check?check_db=true&check_redis=true&check_whatsapp=true&check_ai=true"
    )

    assert response.status_code == 200
    data = response.json()
    # Status is "healthy" unless there's an actual error (not just "not_configured")
    assert data["status"] in ["healthy", "unhealthy"]
    assert "database" in data
    assert "redis" in data
    assert "ai" in data
    # If unhealthy, there should be an error
    if data["status"] == "unhealthy":
        assert "error" in data


@pytest.mark.asyncio
async def test_health_check_db_failure(client: AsyncClient):
    """Test health check detects database failure."""
    with patch("src.main.get_async_sessionmaker") as mock_session:
        mock_session.return_value.return_value.__aenter__.return_value.execute = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        response = await client.get("/health_check?check_db=true")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
