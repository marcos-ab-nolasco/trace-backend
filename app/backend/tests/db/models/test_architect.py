"""Tests for Architect model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.architect import Architect
from tests.factories import (
    ArchitectFactory,
    BriefingTemplateFactory,
    EndClientFactory,
    OrganizationFactory,
)


@pytest.mark.asyncio
async def test_create_architect(db_session):
    """Test creating an architect with authentication fields."""
    org = await OrganizationFactory.create_async(name="Test Studio")

    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="architect@test.com",
        hashed_password="hashed_password_123",
        full_name="John Architect",
        phone="+5511987654321",
        is_authorized=True,
        meta={"specialty": "residential", "years_experience": 5},
    )

    assert isinstance(architect.id, UUID)
    assert architect.organization_id == org.id
    assert architect.email == "architect@test.com"
    assert architect.hashed_password == "hashed_password_123"
    assert architect.full_name == "John Architect"
    assert architect.phone == "+5511987654321"
    assert architect.is_authorized is True
    assert architect.meta == {"specialty": "residential", "years_experience": 5}
    assert isinstance(architect.created_at, datetime)
    assert isinstance(architect.updated_at, datetime)


@pytest.mark.asyncio
async def test_architect_relationships(db_session):
    """Test architect relationships with organization."""
    org = await OrganizationFactory.create_async(name="Rel Studio")

    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="rel@test.com",
    )

    assert architect.organization.name == "Rel Studio"

    await db_session.refresh(org, ["architects"])
    assert org.architects[0].id == architect.id


@pytest.mark.asyncio
async def test_architect_unique_email(db_session):
    """Test that architect email must be unique."""
    await ArchitectFactory.create_async(email="unique@test.com")

    org2 = await OrganizationFactory.create_async(name="Another Studio")

    architect2 = Architect(
        organization_id=org2.id,
        email="unique@test.com",
        hashed_password="hashed",
        phone="+5511222222222",
    )
    db_session.add(architect2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_architect_default_is_authorized_false(db_session):
    """Test that is_authorized defaults to False."""
    architect = await ArchitectFactory.create_async(
        email="default@test.com",
        is_authorized=False,
    )

    assert architect.is_authorized is False


@pytest.mark.asyncio
async def test_architect_cascade_on_organization_delete(db_session):
    """Test that architect is deleted when organization is deleted (CASCADE)."""
    org = await OrganizationFactory.create_async(name="Cascade Studio")

    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="cascade@test.com",
    )
    architect_id = architect.id

    await db_session.delete(org)
    await db_session.commit()

    result = await db_session.execute(select(Architect).where(Architect.id == architect_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_architect_end_clients_relationship(db_session):
    """Test architect's relationship with end clients."""
    org = await OrganizationFactory.create_async(name="Client Rel Studio")
    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="clients@test.com",
    )

    await EndClientFactory.create_async(
        organization=org,
        organization_id=org.id,
        architect=architect,
        architect_id=architect.id,
        name="Client One",
        email="c1@test.com",
    )
    await EndClientFactory.create_async(
        organization=org,
        organization_id=org.id,
        architect=architect,
        architect_id=architect.id,
        name="Client Two",
        email="c2@test.com",
    )

    await db_session.refresh(architect, ["end_clients"])
    assert len(architect.end_clients) == 2
    assert {c.name for c in architect.end_clients} == {"Client One", "Client Two"}


@pytest.mark.asyncio
async def test_architect_created_templates_relationship(db_session, test_project_type):
    """Test architect's relationship with templates they created."""
    org = await OrganizationFactory.create_async(name="Template Org")
    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="creator@test.com",
    )

    await BriefingTemplateFactory.create_async(
        organization=org,
        organization_id=org.id,
        created_by=architect,
        created_by_architect_id=architect.id,
        name="Custom Template",
        is_global=False,
        description="Created by architect",
        project_type=test_project_type,
    )

    await db_session.refresh(architect, ["created_templates"])
    assert len(architect.created_templates) == 1
    assert architect.created_templates[0].name == "Custom Template"


@pytest.mark.asyncio
async def test_architect_required_fields(db_session):
    """Test that required fields cannot be null."""
    org = await OrganizationFactory.create_async(name="Required Fields Org")

    architect = Architect(
        organization_id=org.id,
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    with pytest.raises(Exception):
        await db_session.commit()
