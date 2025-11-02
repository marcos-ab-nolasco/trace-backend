"""Organization-related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.organization import Organization


@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create a test organization."""
    organization = Organization(name="Test Organization")
    db_session.add(organization)
    await db_session.commit()
    await db_session.refresh(organization)
    return organization


@pytest.fixture
async def test_organization_with_whatsapp(db_session: AsyncSession) -> Organization:
    """Create a test organization with WhatsApp settings."""
    organization = Organization(
        name="Test Organization",
        whatsapp_business_account_id="123456789",
        settings={
            "phone_number_id": "test_phone_id",
            "access_token": "test_token",
        },
    )
    db_session.add(organization)
    await db_session.commit()
    await db_session.refresh(organization)
    return organization
