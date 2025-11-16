"""Tests for AuthorizedPhone model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.db.models.authorized_phone import AuthorizedPhone
from tests.factories import ArchitectFactory, AuthorizedPhoneFactory, OrganizationFactory


@pytest.mark.asyncio
async def test_create_authorized_phone(db_session):
    """Test creating an authorized phone."""
    auth_phone = await AuthorizedPhoneFactory.create_async(
        phone_number="+5511987654321",
        is_active=True,
    )

    assert isinstance(auth_phone.id, UUID)
    assert auth_phone.organization_id is not None
    assert auth_phone.phone_number == "+5511987654321"
    assert auth_phone.added_by_architect_id is not None
    assert auth_phone.is_active is True
    assert isinstance(auth_phone.created_at, datetime)


@pytest.mark.asyncio
async def test_authorized_phone_unique_constraint(db_session):
    """Test that (organization_id, phone_number) must be unique."""
    org = await OrganizationFactory.create_async(name="Test Org Unique")
    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch@unique.com",
    )

    await AuthorizedPhoneFactory.create_async(
        organization=org,
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by=architect,
        added_by_architect_id=architect.id,
    )

    phone2 = AuthorizedPhone(
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by_architect_id=architect.id,
    )
    db_session.add(phone2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_authorized_phone_different_orgs_same_phone(db_session):
    """Test that same phone can be authorized in different organizations."""
    org1 = await OrganizationFactory.create_async(name="Org 1")
    org2 = await OrganizationFactory.create_async(name="Org 2")

    arch1 = await ArchitectFactory.create_async(
        organization=org1,
        organization_id=org1.id,
        email="arch1@test.com",
    )
    arch2 = await ArchitectFactory.create_async(
        organization=org2,
        organization_id=org2.id,
        email="arch2@test.com",
    )

    await AuthorizedPhoneFactory.create_async(
        organization=org1,
        organization_id=org1.id,
        phone_number="+5511987654321",
        added_by=arch1,
        added_by_architect_id=arch1.id,
    )
    await AuthorizedPhoneFactory.create_async(
        organization=org2,
        organization_id=org2.id,
        phone_number="+5511987654321",
        added_by=arch2,
        added_by_architect_id=arch2.id,
    )

    result = await db_session.execute(
        select(AuthorizedPhone).where(AuthorizedPhone.phone_number == "+5511987654321")
    )
    phones = result.scalars().all()
    assert len(phones) == 2


@pytest.mark.asyncio
async def test_authorized_phone_cascade_delete_organization(db_session):
    """Test that deleting organization cascades to authorized phones."""
    org = await OrganizationFactory.create_async(name="Delete Cascade Org")
    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch@cascade.com",
    )

    auth_phone = await AuthorizedPhoneFactory.create_async(
        organization=org,
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by=architect,
        added_by_architect_id=architect.id,
    )
    phone_id = auth_phone.id

    await db_session.delete(org)
    await db_session.commit()

    result = await db_session.execute(select(AuthorizedPhone).where(AuthorizedPhone.id == phone_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_authorized_phone_relationships(db_session):
    """Test authorized phone relationships with organization and architect."""
    org = await OrganizationFactory.create_async(name="Relationship Org")
    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch@rel.com",
        full_name="Relationship Architect",
    )

    auth_phone = await AuthorizedPhoneFactory.create_async(
        organization=org,
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by=architect,
        added_by_architect_id=architect.id,
    )

    await db_session.refresh(auth_phone, ["organization", "added_by"])

    assert auth_phone.organization.id == org.id
    assert auth_phone.organization.name == "Relationship Org"
    assert auth_phone.added_by.id == architect.id
    assert auth_phone.added_by.full_name == "Relationship Architect"


@pytest.mark.asyncio
async def test_authorized_phone_default_is_active(db_session):
    """Test that is_active defaults to True."""
    auth_phone = await AuthorizedPhoneFactory.create_async(phone_number="+5511987654321")

    assert auth_phone.is_active is True
