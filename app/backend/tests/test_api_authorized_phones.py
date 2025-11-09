"""Tests for authorized phones API endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.authorized_phone import AuthorizedPhone
from src.db.models.organization import Organization


@pytest.mark.asyncio
async def test_list_authorized_phones(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    auth_headers: dict[str, str],
):
    """Test listing authorized phones for the organization."""
    phone1 = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511111111111",
        added_by_architect_id=test_architect.id,
        is_active=True,
    )
    phone2 = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511222222222",
        added_by_architect_id=test_architect.id,
        is_active=True,
    )
    db_session.add_all([phone1, phone2])
    await db_session.commit()

    response = await client.get("/api/organizations/authorized-phones", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["phones"]) == 2
    phone_numbers = {p["phone_number"] for p in data["phones"]}
    assert "+5511111111111" in phone_numbers
    assert "+5511222222222" in phone_numbers


@pytest.mark.asyncio
async def test_list_authorized_phones_requires_auth(client: AsyncClient):
    """Test that listing phones requires authentication."""
    response = await client.get("/api/organizations/authorized-phones")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_add_authorized_phone(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    auth_headers: dict[str, str],
):
    """Test adding a new authorized phone."""
    response = await client.post(
        "/api/organizations/authorized-phones",
        headers=auth_headers,
        json={"phone_number": "+5511987654321"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["phone_number"] == "+5511987654321"
    assert data["is_active"] is True
    assert data["organization_id"] == str(test_organization.id)

    result = await db_session.execute(
        select(AuthorizedPhone).where(
            AuthorizedPhone.organization_id == test_organization.id,
            AuthorizedPhone.phone_number == "+5511987654321",
        )
    )
    db_phone = result.scalar_one_or_none()
    assert db_phone is not None


@pytest.mark.asyncio
async def test_add_authorized_phone_duplicate_fails(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    auth_headers: dict[str, str],
):
    """Test that adding duplicate phone returns error."""
    phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )
    db_session.add(phone)
    await db_session.commit()

    response = await client.post(
        "/api/organizations/authorized-phones",
        headers=auth_headers,
        json={"phone_number": "+5511987654321"},
    )

    assert response.status_code == 400
    assert "already authorized" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_add_authorized_phone_requires_auth(client: AsyncClient):
    """Test that adding phone requires authentication."""
    response = await client.post(
        "/api/organizations/authorized-phones",
        json={"phone_number": "+5511987654321"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_authorized_phone(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    auth_headers: dict[str, str],
):
    """Test deleting an authorized phone."""
    phone1 = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511111111111",
        added_by_architect_id=test_architect.id,
    )
    phone2 = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511222222222",
        added_by_architect_id=test_architect.id,
    )
    db_session.add_all([phone1, phone2])
    await db_session.commit()
    await db_session.refresh(phone1)

    response = await client.delete(
        f"/api/organizations/authorized-phones/{phone1.id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    result = await db_session.execute(
        select(AuthorizedPhone).where(AuthorizedPhone.id == phone1.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_last_phone_fails(
    client: AsyncClient,
    db_session: AsyncSession,
    test_organization: Organization,
    test_architect: Architect,
    auth_headers: dict[str, str],
):
    """Test that deleting the last phone returns error."""
    phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )
    db_session.add(phone)
    await db_session.commit()
    await db_session.refresh(phone)

    response = await client.delete(
        f"/api/organizations/authorized-phones/{phone.id}",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "at least 1" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_authorized_phone_not_found(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    """Test deleting non-existent phone returns 404."""
    fake_id = uuid4()
    response = await client.delete(
        f"/api/organizations/authorized-phones/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_authorized_phone_requires_auth(client: AsyncClient):
    """Test that deleting phone requires authentication."""
    fake_id = uuid4()
    response = await client.delete(f"/api/organizations/authorized-phones/{fake_id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cannot_delete_phone_from_another_org(
    client: AsyncClient,
    db_session: AsyncSession,
    test_architect: Architect,
    auth_headers: dict[str, str],
):
    """Test that architect cannot delete phone from another organization."""
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    await db_session.commit()
    await db_session.refresh(other_org)

    other_phone = AuthorizedPhone(
        organization_id=other_org.id,
        phone_number="+5511999999999",
        added_by_architect_id=test_architect.id,
    )
    db_session.add(other_phone)
    await db_session.commit()
    await db_session.refresh(other_phone)

    response = await client.delete(
        f"/api/organizations/authorized-phones/{other_phone.id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
