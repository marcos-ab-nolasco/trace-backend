"""Tests for Organization model."""

import pytest
from uuid import UUID
from datetime import datetime
from sqlalchemy import select

from src.db.models.organization import Organization


@pytest.mark.asyncio
async def test_create_organization(db_session):
    """Test creating an organization."""
    org = Organization(
        name="Arquitetura Studio",
        whatsapp_business_account_id="1234567890",
        settings={"timezone": "America/Sao_Paulo", "language": "pt-BR"},
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    assert isinstance(org.id, UUID)
    assert org.name == "Arquitetura Studio"
    assert org.whatsapp_business_account_id == "1234567890"
    assert org.settings == {"timezone": "America/Sao_Paulo", "language": "pt-BR"}
    assert isinstance(org.created_at, datetime)
    assert isinstance(org.updated_at, datetime)


@pytest.mark.asyncio
async def test_organization_unique_name(db_session):
    """Test that organization names must be unique."""
    org1 = Organization(name="Studio A", whatsapp_business_account_id="123")
    org2 = Organization(name="Studio A", whatsapp_business_account_id="456")

    db_session.add(org1)
    await db_session.commit()

    db_session.add(org2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_organization_cascade_delete(db_session):
    """Test that deleting organization cascades to architects."""
    from src.db.models.architect import Architect
    from src.db.models.user import User

    # Create user
    user = User(email="arch@test.com", hashed_password="hashed", full_name="Test Architect")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create organization
    org = Organization(name="Studio Delete Test", whatsapp_business_account_id="999")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # Create architect
    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511999999999", is_authorized=True
    )
    db_session.add(architect)
    await db_session.commit()

    # Delete organization
    await db_session.delete(org)
    await db_session.commit()

    # Verify architect is also deleted
    result = await db_session.execute(select(Architect).where(Architect.user_id == user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_organization_optional_fields(db_session):
    """Test organization with minimal required fields."""
    org = Organization(name="Minimal Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    assert org.whatsapp_business_account_id is None
    assert org.settings is None or org.settings == {}
