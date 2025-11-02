"""Tests for EndClient model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.architect import Architect
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization


@pytest.mark.asyncio
async def test_create_end_client(db_session):
    """Test creating an end client."""
    # Setup organization and architect
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    # Create end client
    end_client = EndClient(
        organization_id=org.id,
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
    assert end_client.organization_id == org.id
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
    org = Organization(name="Rel Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="rel@test.com",
        hashed_password="hashed",
        phone="+5511222222222",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="João Santos",
        phone="+5511333333333",
    )
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    # Test relationships
    assert end_client.architect.id == architect.id

    # Refresh architect to load end_clients relationship
    await db_session.refresh(architect, ["end_clients"])
    assert architect.end_clients[0].id == end_client.id


@pytest.mark.asyncio
async def test_end_client_unique_phone_per_organization(db_session):
    """Test that phone is unique per organization (not per architect)."""
    org = Organization(name="Unique Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # Create two architects in same organization
    architect1 = Architect(
        organization_id=org.id,
        email="arch1@test.com",
        hashed_password="hashed",
        phone="+5511444444444",
    )
    architect2 = Architect(
        organization_id=org.id,
        email="arch2@test.com",
        hashed_password="hashed",
        phone="+5511444444445",
    )
    db_session.add_all([architect1, architect2])
    await db_session.commit()
    await db_session.refresh(architect1)
    await db_session.refresh(architect2)

    # Create first client with architect1
    client1 = EndClient(
        organization_id=org.id,
        architect_id=architect1.id,
        name="Client 1",
        phone="+5511555555555",
    )
    db_session.add(client1)
    await db_session.commit()

    # Try to create another client with same phone in same org (different architect)
    # This should FAIL because phone must be unique per organization
    client2 = EndClient(
        organization_id=org.id,
        architect_id=architect2.id,
        name="Client 2",
        phone="+5511555555555",
    )
    db_session.add(client2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_end_client_same_phone_different_organizations(db_session):
    """Test that same phone can exist in different organizations."""
    # Create two different organizations
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add_all([org1, org2])
    await db_session.commit()
    await db_session.refresh(org1)
    await db_session.refresh(org2)

    # Create architects for each organization
    architect1 = Architect(
        organization_id=org1.id,
        email="arch1@org1.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    architect2 = Architect(
        organization_id=org2.id,
        email="arch2@org2.com",
        hashed_password="hashed",
        phone="+5511222222222",
    )
    db_session.add_all([architect1, architect2])
    await db_session.commit()
    await db_session.refresh(architect1)
    await db_session.refresh(architect2)

    # Same phone number in different organizations should be OK
    client1 = EndClient(
        organization_id=org1.id,
        architect_id=architect1.id,
        name="Client in Org 1",
        phone="+5511999999999",
    )
    client2 = EndClient(
        organization_id=org2.id,
        architect_id=architect2.id,
        name="Client in Org 2",
        phone="+5511999999999",
    )
    db_session.add_all([client1, client2])
    await db_session.commit()

    # Both should be created successfully
    result = await db_session.execute(select(EndClient).where(EndClient.phone == "+5511999999999"))
    clients = result.scalars().all()
    assert len(clients) == 2


@pytest.mark.asyncio
async def test_end_client_cascade_on_architect_delete(db_session):
    """Test that end clients are deleted when architect is deleted (CASCADE)."""
    org = Organization(name="Cascade Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="cascade@test.com",
        hashed_password="hashed",
        phone="+5511666666666",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Will be deleted",
        phone="+5511777777777",
    )
    db_session.add(end_client)
    await db_session.commit()
    client_id = end_client.id

    # Delete architect
    await db_session.delete(architect)
    await db_session.commit()

    # Verify end client is also deleted
    result = await db_session.execute(select(EndClient).where(EndClient.id == client_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_end_client_optional_fields(db_session):
    """Test end client with minimal required fields."""
    org = Organization(name="Minimal Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="minimal@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    # Create end client with only required fields
    end_client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Minimal Client",
        phone="+5511999999999",
    )
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    assert end_client.email is None
    assert end_client.meta is None or end_client.meta == {}
