"""Tests for Architect model."""

import pytest
from uuid import UUID
from datetime import datetime
from sqlalchemy import select

from src.db.models.architect import Architect
from src.db.models.organization import Organization
from src.db.models.user import User


@pytest.mark.asyncio
async def test_create_architect(db_session):
    """Test creating an architect."""
    # Create user first
    user = User(email="architect@test.com", hashed_password="hashed", full_name="John Architect")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create organization
    org = Organization(name="Test Studio", whatsapp_business_account_id="123")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # Create architect
    architect = Architect(
        user_id=user.id,
        organization_id=org.id,
        phone="+5511987654321",
        is_authorized=True,
        meta={"specialty": "residential", "years_experience": 5},
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    assert isinstance(architect.id, UUID)
    assert architect.user_id == user.id
    assert architect.organization_id == org.id
    assert architect.phone == "+5511987654321"
    assert architect.is_authorized is True
    assert architect.meta == {"specialty": "residential", "years_experience": 5}
    assert isinstance(architect.created_at, datetime)
    assert isinstance(architect.updated_at, datetime)


@pytest.mark.asyncio
async def test_architect_relationships(db_session):
    """Test architect relationships with user and organization."""
    # Setup
    user = User(email="rel@test.com", hashed_password="hashed", full_name="Rel Test")
    org = Organization(name="Rel Studio", whatsapp_business_account_id="456")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    # Create architect
    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511999999999")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    # Test relationships
    assert architect.user.email == "rel@test.com"
    assert architect.organization.name == "Rel Studio"

    # Refresh org to load architects relationship
    await db_session.refresh(org, ["architects"])
    assert org.architects[0].id == architect.id


@pytest.mark.asyncio
async def test_architect_unique_user_per_organization(db_session):
    """Test that a user can only be an architect once per organization."""
    user = User(email="unique@test.com", hashed_password="hashed")
    org = Organization(name="Unique Studio")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect1 = Architect(user_id=user.id, organization_id=org.id, phone="+5511111111111")
    db_session.add(architect1)
    await db_session.commit()

    # Try to add same user to same org again
    architect2 = Architect(user_id=user.id, organization_id=org.id, phone="+5511222222222")
    db_session.add(architect2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_architect_default_is_authorized_false(db_session):
    """Test that is_authorized defaults to False."""
    user = User(email="default@test.com", hashed_password="hashed")
    org = Organization(name="Default Studio")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511333333333")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    assert architect.is_authorized is False


@pytest.mark.asyncio
async def test_architect_cascade_on_user_delete(db_session):
    """Test that architect is deleted when user is deleted."""
    user = User(email="cascade@test.com", hashed_password="hashed")
    org = Organization(name="Cascade Studio")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511444444444")
    db_session.add(architect)
    await db_session.commit()
    architect_id = architect.id

    # Delete user
    await db_session.delete(user)
    await db_session.commit()

    # Verify architect is deleted
    result = await db_session.execute(select(Architect).where(Architect.id == architect_id))
    assert result.scalar_one_or_none() is None
