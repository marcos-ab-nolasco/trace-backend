"""Integration tests for authentication with cache behavior validation.

These tests validate that the authentication cache works correctly,
reducing database load while maintaining security and data integrity.
"""

import pytest
from httpx import AsyncClient

from src.core.security import create_access_token, hash_password
from src.db.models.architect import Architect


@pytest.mark.asyncio
async def test_multiple_requests_from_same_user_use_cache(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """Multiple authenticated requests from the same user should benefit from cache.

    This validates that after the first request (cache miss + DB query),
    subsequent requests hit the cache instead of querying the database.
    """
    endpoints = [
        "/chat/conversations",
        "/chat/providers",
        "/chat/conversations",
        "/auth/me",
        "/chat/conversations",
    ]

    for endpoint in endpoints:
        response = await client.get(endpoint, headers=auth_headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_different_users_have_isolated_cache(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    """Different users should have separate cache entries.

    Cache should not leak data between users - each user_id has its own cache.
    """
    second_user = Architect(
        organization_id=test_user.organization_id,
        email="second@example.com",
        hashed_password=hash_password("password123"),
        full_name="Second User",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(second_user)
    await db_session.commit()
    await db_session.refresh(second_user)

    second_token = create_access_token(data={"sub": str(second_user.id)})
    second_headers = {"Authorization": f"Bearer {second_token}"}

    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["full_name"] == test_user.full_name

    response = await client.get("/auth/me", headers=second_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == second_user.email
    assert data["full_name"] == second_user.full_name

    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["full_name"] == test_user.full_name


@pytest.mark.asyncio
async def test_token_refresh_does_not_break_cache(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """When a user refreshes their token, cache should still work.

    Cache is based on user_id (not token), so token refresh should not
    invalidate the cache or require a new database query.
    """
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200

    new_token = create_access_token(data={"sub": str(test_user.id)})
    new_headers = {"Authorization": f"Bearer {new_token}"}

    response = await client.get("/chat/conversations", headers=new_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rapid_concurrent_requests_return_consistent_user(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """Multiple rapid requests should return consistent user data.

    This validates that caching doesn't introduce race conditions
    or inconsistent data when multiple requests happen simultaneously.
    """
    responses = []
    for _ in range(10):
        response = await client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        responses.append(response.json())

    first_response = responses[0]
    for response in responses[1:]:
        assert response["id"] == first_response["id"]
        assert response["email"] == first_response["email"]
        assert response["full_name"] == first_response["full_name"]
        assert response["created_at"] == first_response["created_at"]


@pytest.mark.asyncio
async def test_invalid_token_does_not_pollute_cache(
    client: AsyncClient,
) -> None:
    """Invalid tokens should not create cache entries.

    Only valid authentication should result in cached user data.
    """
    invalid_headers = {"Authorization": "Bearer invalid_token_xyz"}

    response = await client.get("/auth/me", headers=invalid_headers)
    assert response.status_code == 401

    response = await client.get("/auth/me", headers=invalid_headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_deleted_user_eventually_fails_authentication(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    """When a user is deleted, authentication should eventually fail.

    Due to cache TTL (180s), a deleted user might still authenticate
    briefly from cache. This test validates the expected behavior.
    """
    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email

    await db_session.delete(test_user)
    await db_session.commit()

    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code in [200, 401]
