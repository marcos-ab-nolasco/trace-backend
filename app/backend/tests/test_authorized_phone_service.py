"""Tests for AuthorizedPhoneService."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.authorized_phone import AuthorizedPhone
from src.db.models.organization import Organization
from src.services.authorized_phone_service import (
    AuthorizedPhoneService,
    MinimumPhonesError,
    PhoneAlreadyExistsError,
    PhoneNotFoundError,
)


@pytest.mark.asyncio
async def test_add_phone(db_session: AsyncSession, test_organization: Organization, test_architect: Architect):
    """Test adding a new authorized phone."""
    service = AuthorizedPhoneService(db_session)

    phone = await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )

    assert phone.organization_id == test_organization.id
    assert phone.phone_number == "+5511987654321"
    assert phone.added_by_architect_id == test_architect.id
    assert phone.is_active is True

    # Verify it's in database
    result = await db_session.execute(
        select(AuthorizedPhone).where(AuthorizedPhone.id == phone.id)
    )
    db_phone = result.scalar_one()
    assert db_phone.phone_number == "+5511987654321"


@pytest.mark.asyncio
async def test_add_phone_duplicate_raises_error(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test that adding duplicate phone raises PhoneAlreadyExistsError."""
    service = AuthorizedPhoneService(db_session)

    # Add phone first time
    await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )

    # Try to add same phone again
    with pytest.raises(PhoneAlreadyExistsError) as exc_info:
        await service.add_phone(
            organization_id=test_organization.id,
            phone_number="+5511987654321",
            added_by_architect_id=test_architect.id,
        )

    assert "+5511987654321" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_phone_different_orgs_same_phone(
    db_session: AsyncSession, test_architect: Architect
):
    """Test that same phone can be added to different organizations."""
    # Create two organizations
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add_all([org1, org2])
    await db_session.commit()
    await db_session.refresh(org1)
    await db_session.refresh(org2)

    service = AuthorizedPhoneService(db_session)

    # Add same phone to both orgs - should work
    phone1 = await service.add_phone(
        organization_id=org1.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )
    phone2 = await service.add_phone(
        organization_id=org2.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )

    assert phone1.organization_id != phone2.organization_id
    assert phone1.phone_number == phone2.phone_number


@pytest.mark.asyncio
async def test_remove_phone(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test removing an authorized phone."""
    service = AuthorizedPhoneService(db_session)

    # Add two phones
    phone1 = await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )
    await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511999999999",
        added_by_architect_id=test_architect.id,
    )

    # Remove first phone
    await service.remove_phone(phone_id=phone1.id, organization_id=test_organization.id)

    # Verify it's deleted
    result = await db_session.execute(
        select(AuthorizedPhone).where(AuthorizedPhone.id == phone1.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_remove_phone_not_found_raises_error(
    db_session: AsyncSession, test_organization: Organization
):
    """Test that removing non-existent phone raises PhoneNotFoundError."""
    service = AuthorizedPhoneService(db_session)

    from uuid import uuid4
    fake_id = uuid4()

    with pytest.raises(PhoneNotFoundError):
        await service.remove_phone(phone_id=fake_id, organization_id=test_organization.id)


@pytest.mark.asyncio
async def test_remove_last_phone_raises_error(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test that removing the last phone raises MinimumPhonesError."""
    service = AuthorizedPhoneService(db_session)

    # Add only one phone
    phone = await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )

    # Try to remove it (should fail - need minimum 1 phone)
    with pytest.raises(MinimumPhonesError) as exc_info:
        await service.remove_phone(phone_id=phone.id, organization_id=test_organization.id)

    assert "at least 1 authorized phone" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_list_phones(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test listing authorized phones for an organization."""
    service = AuthorizedPhoneService(db_session)

    # Add multiple phones
    await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511111111111",
        added_by_architect_id=test_architect.id,
    )
    await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511222222222",
        added_by_architect_id=test_architect.id,
    )

    # List phones
    phones = await service.list_phones(organization_id=test_organization.id)

    assert len(phones) == 2
    phone_numbers = {p.phone_number for p in phones}
    assert "+5511111111111" in phone_numbers
    assert "+5511222222222" in phone_numbers


@pytest.mark.asyncio
async def test_list_phones_only_active(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test that list_phones only returns active phones by default."""
    service = AuthorizedPhoneService(db_session)

    # Add active phone
    await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511111111111",
        added_by_architect_id=test_architect.id,
    )

    # Add inactive phone directly
    inactive_phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511222222222",
        added_by_architect_id=test_architect.id,
        is_active=False,
    )
    db_session.add(inactive_phone)
    await db_session.commit()

    # List phones (should only return active)
    phones = await service.list_phones(organization_id=test_organization.id)

    assert len(phones) == 1
    assert phones[0].phone_number == "+5511111111111"

    # List all phones including inactive
    all_phones = await service.list_phones(organization_id=test_organization.id, include_inactive=True)
    assert len(all_phones) == 2


@pytest.mark.asyncio
async def test_is_authorized_true(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test is_authorized returns True for authorized phone."""
    service = AuthorizedPhoneService(db_session)

    await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )

    is_auth = await service.is_authorized(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
    )

    assert is_auth is True


@pytest.mark.asyncio
async def test_is_authorized_false_not_found(
    db_session: AsyncSession, test_organization: Organization
):
    """Test is_authorized returns False for non-existent phone."""
    service = AuthorizedPhoneService(db_session)

    is_auth = await service.is_authorized(
        organization_id=test_organization.id,
        phone_number="+5511999999999",
    )

    assert is_auth is False


@pytest.mark.asyncio
async def test_is_authorized_false_inactive(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test is_authorized returns False for inactive phone."""
    # Add inactive phone directly
    inactive_phone = AuthorizedPhone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
        is_active=False,
    )
    db_session.add(inactive_phone)
    await db_session.commit()

    service = AuthorizedPhoneService(db_session)

    is_auth = await service.is_authorized(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
    )

    assert is_auth is False


@pytest.mark.asyncio
async def test_get_phone_by_id(
    db_session: AsyncSession, test_organization: Organization, test_architect: Architect
):
    """Test getting phone by ID."""
    service = AuthorizedPhoneService(db_session)

    phone = await service.add_phone(
        organization_id=test_organization.id,
        phone_number="+5511987654321",
        added_by_architect_id=test_architect.id,
    )

    retrieved = await service.get_phone_by_id(
        phone_id=phone.id,
        organization_id=test_organization.id,
    )

    assert retrieved.id == phone.id
    assert retrieved.phone_number == "+5511987654321"


@pytest.mark.asyncio
async def test_get_phone_by_id_not_found_raises_error(
    db_session: AsyncSession, test_organization: Organization
):
    """Test get_phone_by_id raises error for non-existent phone."""
    service = AuthorizedPhoneService(db_session)

    from uuid import uuid4
    fake_id = uuid4()

    with pytest.raises(PhoneNotFoundError):
        await service.get_phone_by_id(phone_id=fake_id, organization_id=test_organization.id)
