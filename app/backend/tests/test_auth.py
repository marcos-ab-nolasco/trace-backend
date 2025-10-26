"""Test authentication endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient, db_session: AsyncSession) -> None:
    """Test user registration."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "securepassword123",
            "full_name": "New User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert "hashed_password" not in data
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user: User) -> None:
    """Test registration with duplicate email fails."""
    response = await client.post(
        "/auth/register",
        json={
            "email": test_user.email,
            "password": "password123",
            "full_name": "Duplicate User",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User) -> None:
    """Test successful login."""
    response = await client.post(
        "/auth/login",
        auth=("test@example.com", "testpassword123"),
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    cookies = response.cookies
    assert "refresh_token" in cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: User) -> None:
    """Test login with wrong password fails."""
    response = await client.post(
        "/auth/login",
        auth=("test@example.com", "wrongpassword"),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    """Test login with nonexistent user fails."""
    response = await client.post(
        "/auth/login",
        auth=("nonexistent@example.com", "password123"),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
) -> None:
    """Test getting current user with valid token."""
    response = await client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["full_name"] == test_user.full_name
    assert data["id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_get_current_user_no_token(client: AsyncClient) -> None:
    """Test getting current user without token fails."""
    response = await client.get("/auth/me")

    assert response.status_code == 403  # HTTPBearer returns 403 when no credentials


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(client: AsyncClient) -> None:
    """Test getting current user with invalid token fails."""
    response = await client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, test_user: User) -> None:
    """Test refresh token generates new access and refresh tokens.

    This test validates the complete refresh flow:
    1. Login to get initial tokens
    2. Use refresh token to get new tokens
    3. Verify new tokens are different from original
    4. Verify new access token works for authenticated requests
    """
    import asyncio

    # Step 1: Login to get initial tokens and cookie
    login_response = await client.post(
        "/auth/login",
        auth=("test@example.com", "testpassword123"),
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert "access_token" in tokens

    original_cookie = login_response.cookies.get("refresh_token")
    assert original_cookie is not None

    # Wait 1 second to ensure new tokens have different exp timestamp
    await asyncio.sleep(1)

    # Step 2: Use refresh token to get new tokens
    refresh_response = await client.post("/auth/refresh")

    # This should pass but currently FAILS with 401 due to UUID bug
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
    assert new_tokens["token_type"] == "bearer"

    rotated_cookie = refresh_response.cookies.get("refresh_token")
    assert rotated_cookie is not None
    assert rotated_cookie != original_cookie

    # Step 3: Verify new tokens are different (rotated)
    assert new_tokens["access_token"] != tokens["access_token"]

    # Step 4: Verify new access token works for authenticated requests
    me_response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert me_response.status_code == 200
    user_data = me_response.json()
    assert user_data["email"] == test_user.email


@pytest.mark.asyncio
async def test_refresh_token_requires_cookie(client: AsyncClient) -> None:
    """Refresh without cookie should fail."""
    response = await client.post("/auth/refresh")

    assert response.status_code == 401
    assert "Could not validate" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token_with_invalid_session(client: AsyncClient, test_user: User) -> None:
    """Refresh with unknown session id should fail."""
    # Seed cookie with random token
    client.cookies.set("refresh_token", "invalid-session", domain="testserver", path="/")

    response = await client.post("/auth/refresh")

    assert response.status_code == 401
    assert "Could not validate" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token_invalidated_when_user_deleted(
    client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    """If the user no longer exists, refresh should fail and clear cookie."""

    login_response = await client.post(
        "/auth/login",
        auth=("test@example.com", "testpassword123"),
    )
    assert login_response.status_code == 200

    # Delete user from DB
    await db_session.delete(test_user)
    await db_session.commit()

    response = await client.post("/auth/refresh")

    assert response.status_code == 401
    assert "Could not validate" in response.json()["detail"]
    assert "refresh_token" not in response.cookies


@pytest.mark.asyncio
async def test_logout_clears_session(
    client: AsyncClient, test_user: User, auth_headers: dict[str, str]
) -> None:
    """Logout should clear cookie and invalidate refresh session."""

    login_response = await client.post(
        "/auth/login",
        auth=("test@example.com", "testpassword123"),
    )
    assert login_response.status_code == 200
    cookie_before = login_response.cookies.get("refresh_token")
    assert cookie_before is not None

    logout_response = await client.post("/auth/logout", headers=auth_headers)
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Successfully logged out"

    cookie_after = logout_response.cookies.get("refresh_token")
    assert cookie_after is None

    # Attempt refresh with previous cookie should fail (not automatically sent, so set manually)
    client.cookies.set("refresh_token", cookie_before, domain="testserver", path="/")
    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 401
