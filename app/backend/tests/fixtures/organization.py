"""Organization-related test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.organization import Organization

TEST_TOKEN = "gAAAAABpD5SBKMMw3egsVRJ7IWR3jtj5PzRnMyifxeXyWCJmg0gtErDSpZHZOH09gSgvalFlmre05W-8JcMdAswaN7E3zZvifw=="
GLOBAL_TEST_TOKEN_XYZ = "gAAAAABpD6LLnObMoYGi9Jq9XoxccZ5cdpBI0th_k7RKAnuQ8dIVVgTrzXMNsOtbD9IuK7jjfievpm-SeXHmC_4kTUyg2jUTNTETnMntOopbotCpdP0a2ms="


@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create a test organization."""
    organization = Organization(
        name="Test Organization",
        settings={
            "phone_number_id": "global_test_phone_123",
            "access_token": GLOBAL_TEST_TOKEN_XYZ,
        },
    )
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
            "access_token": TEST_TOKEN,
        },
    )
    db_session.add(organization)
    await db_session.commit()
    await db_session.refresh(organization)
    return organization
