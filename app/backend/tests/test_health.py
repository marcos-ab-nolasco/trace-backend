"""Test health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_basic(client: AsyncClient) -> None:
    """Test basic health check without database check."""
    response = await client.get("/health_check")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["environment"] == "test"
    assert "database" not in data


@pytest.mark.asyncio
async def test_health_check_with_db(client: AsyncClient) -> None:
    """Test health check with database connectivity check."""
    response = await client.get("/health_check?check_db=true")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
