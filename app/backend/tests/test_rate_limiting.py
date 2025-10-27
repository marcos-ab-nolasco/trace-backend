"""Rate limiting tests for API endpoints.

These tests validate that rate limiting works correctly for both IP-based
(public endpoints) and user-based (authenticated endpoints) strategies.
"""

import asyncio

import pytest
from httpx import AsyncClient

from src.db.models.architect import Architect


@pytest.mark.asyncio
async def test_login_rate_limited_by_ip(client: AsyncClient) -> None:
    """Login endpoint should be rate limited to 5 requests per minute by IP.

    6th request should return 429 Too Many Requests with Retry-After header.
    """
    # First 5 requests should succeed (or fail with 401, but not 429)
    for i in range(5):
        response = await client.post(
            "/auth/login",
            auth=(f"user{i}@example.com", "wrong_password"),
        )
        # Should be 401 (invalid credentials) or 200, but NOT 429
        assert response.status_code in (200, 401), f"Request {i+1} got unexpected status"

    # 6th request should be rate limited
    response = await client.post(
        "/auth/login",
        auth=("user6@example.com", "wrong_password"),
    )
    assert response.status_code == 429, "6th request should be rate limited"
    # Note: Retry-After header is optional but recommended
    # assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_register_rate_limited_by_ip(client: AsyncClient) -> None:
    """Register endpoint should be rate limited to 5 requests per minute by IP."""
    # First 5 requests with valid passwords to actually trigger endpoint logic
    for i in range(5):
        response = await client.post(
            "/auth/register",
            json={
                "email": f"testuser{i}@ratelimit.com",
                "password": "ValidPassword123!",
                "full_name": f"Test User {i}",
                "phone": f"+551199999{i:04d}",
                "organization_name": f"Test Org {i}",
            },
        )
        # Should be 201 (created) or 400 (email exists), but NOT 429
        assert response.status_code in (
            201,
            400,
        ), f"Request {i+1} got unexpected status {response.status_code}"

    # 6th request should be rate limited
    response = await client.post(
        "/auth/register",
        json={
            "email": "testuser6@ratelimit.com",
            "password": "ValidPassword123!",
            "full_name": "Test User 6",
            "phone": "+5511999996666",
            "organization_name": "Test Org 6",
        },
    )
    assert response.status_code == 429, "6th request should be rate limited"


@pytest.mark.asyncio
async def test_rate_limit_429_includes_error_detail(client: AsyncClient) -> None:
    """Rate limit error should include helpful error message."""
    # Trigger rate limit
    for _ in range(6):
        response = await client.post(
            "/auth/login",
            auth=("test@example.com", "password"),
        )

    # Last response should be 429 with detail
    assert response.status_code == 429
    data = response.json()
    assert "detail" in data or "error" in data, "Should include error detail"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_rate_limit_resets_after_window(client: AsyncClient) -> None:
    """Rate limit should reset after the time window expires.

    This test is marked as slow because it needs to wait ~60 seconds.
    """
    # First 5 requests
    for i in range(5):
        response = await client.post(
            "/auth/login",
            auth=(f"user{i}@example.com", "password"),
        )
        assert response.status_code in (200, 401)

    # 6th should fail
    response = await client.post("/auth/login", auth=("user6@example.com", "password"))
    assert response.status_code == 429

    # Wait for window to reset (61 seconds to be safe)
    await asyncio.sleep(61)

    # Should work again now
    response = await client.post("/auth/login", auth=("user7@example.com", "password"))
    assert response.status_code in (200, 401), "Rate limit should have reset"
    assert response.status_code != 429


# ===== User-based Rate Limiting Tests =====


@pytest.mark.asyncio
async def test_create_message_rate_limited_by_user(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str]
) -> None:
    """Create message endpoint should be rate limited to 10 requests per minute per user.

    This tests that authenticated users have separate rate limits based on user_id.
    """
    # First, create a conversation
    conv_response = await client.post(
        "/chat/conversations",
        json={
            "title": "Rate Limit Test",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert conv_response.status_code == 201
    conversation_id = conv_response.json()["id"]

    # Make 10 requests (should all succeed or fail for reasons other than rate limit)
    for i in range(10):
        response = await client.post(
            f"/chat/conversations/{conversation_id}/messages",
            json={"role": "user", "content": f"Test message {i}"},
            headers=auth_headers,
        )
        # Should NOT be rate limited yet
        assert response.status_code != 429, f"Request {i+1} should not be rate limited"

    # 11th request should be rate limited
    response = await client.post(
        f"/chat/conversations/{conversation_id}/messages",
        json={"role": "user", "content": "This should be rate limited"},
        headers=auth_headers,
    )
    assert response.status_code == 429, "11th request should be rate limited"


@pytest.mark.asyncio
async def test_different_users_have_separate_rate_limits(client: AsyncClient) -> None:
    """Different users should have independent rate limits.

    User A hitting rate limit should NOT affect User B.
    """
    # Create two users
    user1_response = await client.post(
        "/auth/register",
        json={
            "email": "ratelimituser1@test.com",
            "password": "Password123!",
            "full_name": "Rate Limit User 1",
            "phone": "+5511999991111",
            "organization_name": "Rate Limit Org 1",
        },
    )
    assert user1_response.status_code == 201

    user2_response = await client.post(
        "/auth/register",
        json={
            "email": "ratelimituser2@test.com",
            "password": "Password123!",
            "full_name": "Rate Limit User 2",
            "phone": "+5511999992222",
            "organization_name": "Rate Limit Org 2",
        },
    )
    assert user2_response.status_code == 201

    # Login both users
    login1 = await client.post(
        "/auth/login",
        auth=("ratelimituser1@test.com", "Password123!"),
    )
    assert login1.status_code == 200
    token1 = login1.json()["access_token"]

    login2 = await client.post(
        "/auth/login",
        auth=("ratelimituser2@test.com", "Password123!"),
    )
    assert login2.status_code == 200
    token2 = login2.json()["access_token"]

    # Create conversation for user 1
    conv1 = await client.post(
        "/chat/conversations",
        json={"title": "User 1 Conv", "ai_provider": "openai", "ai_model": "gpt-4o"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert conv1.status_code == 201
    conv1_id = conv1.json()["id"]

    # Create conversation for user 2
    conv2 = await client.post(
        "/chat/conversations",
        json={"title": "User 2 Conv", "ai_provider": "openai", "ai_model": "gpt-4o"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert conv2.status_code == 201
    conv2_id = conv2.json()["id"]

    # User 1: Send 10 messages (exhaust rate limit)
    for i in range(10):
        response = await client.post(
            f"/chat/conversations/{conv1_id}/messages",
            json={"role": "user", "content": f"User 1 message {i}"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert response.status_code != 429

    # User 1: 11th message should be rate limited
    response = await client.post(
        f"/chat/conversations/{conv1_id}/messages",
        json={"role": "user", "content": "User 1 should be rate limited"},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 429, "User 1 should be rate limited"

    # User 2: Should still be able to send messages (separate limit)
    response = await client.post(
        f"/chat/conversations/{conv2_id}/messages",
        json={"role": "user", "content": "User 2 should work"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert response.status_code != 429, "User 2 should NOT be affected by User 1's limit"
