"""Test authentication endpoints."""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.authorized_phone import AuthorizedPhone


@pytest.mark.asyncio
async def test_register_architect(client: AsyncClient, db_session: AsyncSession) -> None:
    """Architect registration should create tenant and architect record."""

    response = await client.post(
        "/auth/register",
        json={
            "email": "newarchitect@example.com",
            "password": "securepassword123",
            "full_name": "New Architect",
            "phone": "+5511988888888",
            "organization_name": "Nova Organização",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newarchitect@example.com"
    assert data["full_name"] == "New Architect"
    assert data["phone"] == "+5511988888888"
    assert data["is_authorized"] is True  # defaults to authorized after signup
    assert "organization_id" in data


@pytest.mark.asyncio
async def test_register_architect_auto_adds_phone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Architect registration should automatically add their phone as authorized."""

    response = await client.post(
        "/auth/register",
        json={
            "email": "architect@example.com",
            "password": "securepass123",
            "full_name": "Test Architect",
            "phone": "+5511987654321",
            "organization_name": "Test Org",
        },
    )

    assert response.status_code == 201
    data = response.json()
    organization_id = data["organization_id"]
    architect_id = data["id"]

    # Verify authorized phone was created
    result = await db_session.execute(
        select(AuthorizedPhone).where(
            AuthorizedPhone.organization_id == organization_id,
            AuthorizedPhone.phone_number == "+5511987654321",
        )
    )
    auth_phone = result.scalar_one_or_none()

    assert auth_phone is not None
    assert auth_phone.phone_number == "+5511987654321"
    assert auth_phone.is_active is True
    assert str(auth_phone.added_by_architect_id) == architect_id


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_architect: Architect) -> None:
    """Registration should fail when the email already exists."""

    response = await client.post(
        "/auth/register",
        json={
            "email": test_architect.email,
            "password": "password123",
            "full_name": "Duplicate",
            "phone": "+5511977777777",
            "organization_name": "Outra Organização",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_architect: Architect) -> None:
    """Architect should obtain tokens with correct credentials."""

    response = await client.post(
        "/auth/login",
        auth=(test_architect.email, "testpassword123"),
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_architect: Architect) -> None:
    """Wrong password should be rejected."""

    response = await client.post(
        "/auth/login",
        auth=(test_architect.email, "wrongpassword"),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_architect(client: AsyncClient) -> None:
    """Unknown email should fail authentication."""

    response = await client.post(
        "/auth/login",
        auth=("nonexistent@example.com", "password123"),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_architect(
    client: AsyncClient, test_architect: Architect, auth_headers: dict[str, str]
) -> None:
    """Authenticated architect info should be returned."""

    response = await client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_architect.email
    assert data["full_name"] == test_architect.full_name
    assert data["id"] == str(test_architect.id)


@pytest.mark.asyncio
async def test_get_current_architect_no_token(client: AsyncClient) -> None:
    """Request without token should be rejected."""

    response = await client.get("/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_current_architect_invalid_token(client: AsyncClient) -> None:
    """Invalid token should yield unauthorized."""

    response = await client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_success(client: AsyncClient, test_architect: Architect) -> None:
    """Refresh token flow should rotate refresh cookie and issue new access token."""

    login_response = await client.post(
        "/auth/login",
        auth=(test_architect.email, "testpassword123"),
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    original_cookie = login_response.cookies.get("refresh_token")
    assert original_cookie is not None

    await asyncio.sleep(1)

    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    rotated_cookie = refresh_response.cookies.get("refresh_token")
    assert rotated_cookie and rotated_cookie != original_cookie

    assert new_tokens["access_token"] != tokens["access_token"]

    me_response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_architect.email


@pytest.mark.asyncio
async def test_refresh_token_requires_cookie(client: AsyncClient) -> None:
    """Refresh endpoint should require cookie."""

    response = await client.post("/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_with_invalid_session(
    client: AsyncClient, test_architect: Architect
) -> None:
    """Invalid session id should invalidate refresh attempt."""

    client.cookies.set("refresh_token", "invalid-session", domain="testserver", path="/")

    response = await client.post("/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_invalidated_when_architect_deleted(
    client: AsyncClient, db_session: AsyncSession, test_architect: Architect
) -> None:
    """Deleting architect should invalidate refresh token."""

    login_response = await client.post(
        "/auth/login",
        auth=(test_architect.email, "testpassword123"),
    )
    assert login_response.status_code == 200

    await db_session.delete(test_architect)
    await db_session.commit()

    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 401
    assert refresh_response.cookies.get("refresh_token") is None
