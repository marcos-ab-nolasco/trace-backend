"""Tests for EndClient model."""

import pytest
from uuid import UUID
from datetime import datetime
from sqlalchemy import select

from src.db.models.end_client import EndClient
from src.db.models.architect import Architect
from src.db.models.organization import Organization
from src.db.models.user import User


@pytest.mark.asyncio
async def test_create_end_client(db_session):
    """Test creating an end client."""
    # Setup architect
    user = User(email="arch@test.com", hashed_password="hashed")
    org = Organization(name="Test Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511111111111")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    # Create end client
    end_client = EndClient(
        architect_id=architect.id,
        name="Maria Silva",
        phone="+5511987654321",
        email="maria@example.com",
        meta={"project_type": "reforma", "budget_range": "100k-200k"},
    )
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    assert isinstance(end_client.id, UUID)
    assert end_client.architect_id == architect.id
    assert end_client.name == "Maria Silva"
    assert end_client.phone == "+5511987654321"
    assert end_client.email == "maria@example.com"
    assert end_client.meta == {"project_type": "reforma", "budget_range": "100k-200k"}
    assert isinstance(end_client.created_at, datetime)
    assert isinstance(end_client.updated_at, datetime)


@pytest.mark.asyncio
async def test_end_client_relationship_with_architect(db_session):
    """Test end client relationship with architect."""
    user = User(email="rel@test.com", hashed_password="hashed")
    org = Organization(name="Rel Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511222222222")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(architect_id=architect.id, name="João Santos", phone="+5511333333333")
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    # Test relationships
    assert end_client.architect.id == architect.id

    # Refresh architect to load end_clients relationship
    await db_session.refresh(architect, ["end_clients"])
    assert architect.end_clients[0].id == end_client.id


@pytest.mark.asyncio
async def test_end_client_unique_phone_per_architect(db_session):
    """Test that phone number must be unique per architect."""
    user = User(email="unique@test.com", hashed_password="hashed")
    org = Organization(name="Unique Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511444444444")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    client1 = EndClient(architect_id=architect.id, name="Client 1", phone="+5511999999999")
    db_session.add(client1)
    await db_session.commit()

    # Try to add another client with same phone for same architect
    client2 = EndClient(architect_id=architect.id, name="Client 2", phone="+5511999999999")
    db_session.add(client2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_end_client_cascade_on_architect_delete(db_session):
    """Test that end clients are deleted when architect is deleted."""
    user = User(email="cascade@test.com", hashed_password="hashed")
    org = Organization(name="Cascade Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511555555555")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(architect_id=architect.id, name="Test Client", phone="+5511666666666")
    db_session.add(end_client)
    await db_session.commit()
    client_id = end_client.id

    # Delete architect
    await db_session.delete(architect)
    await db_session.commit()

    # Verify end client is deleted
    result = await db_session.execute(select(EndClient).where(EndClient.id == client_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_end_client_optional_fields(db_session):
    """Test end client with minimal required fields."""
    user = User(email="minimal@test.com", hashed_password="hashed")
    org = Organization(name="Minimal Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511777777777")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(architect_id=architect.id, name="Minimal Client", phone="+5511888888888")
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    assert end_client.email is None
    assert end_client.meta is None
