"""Tests for AuthorizedPhone model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.db.models.architect import Architect
from src.db.models.authorized_phone import AuthorizedPhone
from src.db.models.organization import Organization


@pytest.mark.asyncio
async def test_create_authorized_phone(db_session):
    """Test creating an authorized phone."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        full_name="Test Architect",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    auth_phone = AuthorizedPhone(
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by_architect_id=architect.id,
        is_active=True,
    )
    db_session.add(auth_phone)
    await db_session.commit()
    await db_session.refresh(auth_phone)

    assert isinstance(auth_phone.id, UUID)
    assert auth_phone.organization_id == org.id
    assert auth_phone.phone_number == "+5511987654321"
    assert auth_phone.added_by_architect_id == architect.id
    assert auth_phone.is_active is True
    assert isinstance(auth_phone.created_at, datetime)


@pytest.mark.asyncio
async def test_authorized_phone_unique_constraint(db_session):
    """Test that (organization_id, phone_number) must be unique."""
    org = Organization(name="Test Org Unique")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@unique.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    db_session.add(architect)
    await db_session.commit()

    phone1 = AuthorizedPhone(
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by_architect_id=architect.id,
    )
    db_session.add(phone1)
    await db_session.commit()

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
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add_all([org1, org2])
    await db_session.commit()
    await db_session.refresh(org1)
    await db_session.refresh(org2)

    arch1 = Architect(
        organization_id=org1.id,
        email="arch1@test.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    arch2 = Architect(
        organization_id=org2.id,
        email="arch2@test.com",
        hashed_password="hashed",
        phone="+5511222222222",
    )
    db_session.add_all([arch1, arch2])
    await db_session.commit()

    phone1 = AuthorizedPhone(
        organization_id=org1.id,
        phone_number="+5511987654321",
        added_by_architect_id=arch1.id,
    )
    phone2 = AuthorizedPhone(
        organization_id=org2.id,
        phone_number="+5511987654321",
        added_by_architect_id=arch2.id,
    )
    db_session.add_all([phone1, phone2])
    await db_session.commit()

    result = await db_session.execute(
        select(AuthorizedPhone).where(AuthorizedPhone.phone_number == "+5511987654321")
    )
    phones = result.scalars().all()
    assert len(phones) == 2


@pytest.mark.asyncio
async def test_authorized_phone_cascade_delete_organization(db_session):
    """Test that deleting organization cascades to authorized phones."""
    org = Organization(name="Delete Cascade Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@cascade.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    auth_phone = AuthorizedPhone(
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by_architect_id=architect.id,
    )
    db_session.add(auth_phone)
    await db_session.commit()
    phone_id = auth_phone.id

    await db_session.delete(org)
    await db_session.commit()

    result = await db_session.execute(select(AuthorizedPhone).where(AuthorizedPhone.id == phone_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_authorized_phone_relationships(db_session):
    """Test authorized phone relationships with organization and architect."""
    org = Organization(name="Relationship Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@rel.com",
        hashed_password="hashed",
        full_name="Relationship Architect",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    auth_phone = AuthorizedPhone(
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by_architect_id=architect.id,
    )
    db_session.add(auth_phone)
    await db_session.commit()
    await db_session.refresh(auth_phone, ["organization", "added_by"])

    assert auth_phone.organization.id == org.id
    assert auth_phone.organization.name == "Relationship Org"
    assert auth_phone.added_by.id == architect.id
    assert auth_phone.added_by.full_name == "Relationship Architect"


@pytest.mark.asyncio
async def test_authorized_phone_default_is_active(db_session):
    """Test that is_active defaults to True."""
    org = Organization(name="Default Active Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@default.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    auth_phone = AuthorizedPhone(
        organization_id=org.id,
        phone_number="+5511987654321",
        added_by_architect_id=architect.id,
    )
    db_session.add(auth_phone)
    await db_session.commit()
    await db_session.refresh(auth_phone)

    assert auth_phone.is_active is True
