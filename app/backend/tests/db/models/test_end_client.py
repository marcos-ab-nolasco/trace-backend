"""Tests for EndClient model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.end_client import EndClient
from tests.factories import ArchitectFactory, EndClientFactory, OrganizationFactory


@pytest.mark.asyncio
async def test_create_end_client(db_session):
    """Test creating an end client."""
    end_client = await EndClientFactory.create_async(
        name="Maria Silva",
        phone="+5511987654321",
        email="maria@example.com",
        meta={"project_type": "reforma", "budget_range": "100k-200k"},
    )

    assert isinstance(end_client.id, UUID)
    assert end_client.organization_id is not None
    assert end_client.architect_id is not None
    assert end_client.name == "Maria Silva"
    assert end_client.phone == "+5511987654321"
    assert end_client.email == "maria@example.com"
    assert end_client.meta == {"project_type": "reforma", "budget_range": "100k-200k"}
    assert isinstance(end_client.created_at, datetime)
    assert isinstance(end_client.updated_at, datetime)


@pytest.mark.asyncio
async def test_end_client_relationship_with_architect(db_session):
    """Test end client relationship with architect."""
    org = await OrganizationFactory.create_async(name="Rel Org")
    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="rel@test.com",
    )

    end_client = await EndClientFactory.create_async(
        organization=org,
        organization_id=org.id,
        architect=architect,
        architect_id=architect.id,
        name="João Santos",
    )

    assert end_client.architect.id == architect.id

    await db_session.refresh(architect, ["end_clients"])
    assert architect.end_clients[0].id == end_client.id


@pytest.mark.asyncio
async def test_end_client_unique_phone_per_organization(db_session):
    """Test that phone is unique per organization (not per architect)."""
    org = await OrganizationFactory.create_async(name="Unique Org")

    architect1 = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch1@test.com",
    )
    architect2 = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch2@test.com",
    )

    await EndClientFactory.create_async(
        organization=org,
        organization_id=org.id,
        architect=architect1,
        architect_id=architect1.id,
        name="Client 1",
        phone="+5511555555555",
    )

    client2 = EndClient(
        organization_id=org.id,
        architect_id=architect2.id,
        name="Client 2",
        phone="+5511555555555",
    )
    db_session.add(client2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_end_client_same_phone_different_organizations(db_session):
    """Test that same phone can exist in different organizations."""
    org1 = await OrganizationFactory.create_async(name="Org 1")
    org2 = await OrganizationFactory.create_async(name="Org 2")

    architect1 = await ArchitectFactory.create_async(
        organization=org1,
        organization_id=org1.id,
        email="arch1@org1.com",
    )
    architect2 = await ArchitectFactory.create_async(
        organization=org2,
        organization_id=org2.id,
        email="arch2@org2.com",
    )

    await EndClientFactory.create_async(
        organization=org1,
        organization_id=org1.id,
        architect=architect1,
        architect_id=architect1.id,
        name="Client in Org 1",
        phone="+5511999999999",
    )
    await EndClientFactory.create_async(
        organization=org2,
        organization_id=org2.id,
        architect=architect2,
        architect_id=architect2.id,
        name="Client in Org 2",
        phone="+5511999999999",
    )

    result = await db_session.execute(select(EndClient).where(EndClient.phone == "+5511999999999"))
    clients = result.scalars().all()
    assert len(clients) == 2


@pytest.mark.asyncio
async def test_end_client_cascade_on_architect_delete(db_session):
    """Test that end clients are deleted when architect is deleted (CASCADE)."""
    org = await OrganizationFactory.create_async(name="Cascade Org")
    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="cascade@test.com",
    )

    end_client = await EndClientFactory.create_async(
        organization=org,
        organization_id=org.id,
        architect=architect,
        architect_id=architect.id,
        name="Will be deleted",
    )
    client_id = end_client.id

    await db_session.delete(architect)
    await db_session.commit()

    result = await db_session.execute(select(EndClient).where(EndClient.id == client_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_end_client_optional_fields(db_session):
    """Test end client with minimal required fields."""
    end_client = await EndClientFactory.create_async(
        name="Minimal Client",
        email=None,
        meta=None,
    )

    assert end_client.email is None
    assert end_client.meta is None or end_client.meta == {}
