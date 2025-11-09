"""Tests for Architect model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization


@pytest.mark.asyncio
async def test_create_architect(db_session):
    """Test creating an architect with authentication fields."""
    org = Organization(name="Test Studio", whatsapp_business_account_id="123")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="architect@test.com",
        hashed_password="hashed_password_123",
        full_name="John Architect",
        phone="+5511987654321",
        is_authorized=True,
        meta={"specialty": "residential", "years_experience": 5},
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

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
    org = Organization(name="Rel Studio", whatsapp_business_account_id="456")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="rel@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    assert architect.organization.name == "Rel Studio"

    await db_session.refresh(org, ["architects"])
    assert org.architects[0].id == architect.id


@pytest.mark.asyncio
async def test_architect_unique_email(db_session):
    """Test that architect email must be unique."""
    org = Organization(name="Unique Studio")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect1 = Architect(
        organization_id=org.id,
        email="unique@test.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    db_session.add(architect1)
    await db_session.commit()

    org2 = Organization(name="Another Studio")
    db_session.add(org2)
    await db_session.commit()
    await db_session.refresh(org2)

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
    org = Organization(name="Default Studio")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="default@test.com",
        hashed_password="hashed",
        phone="+5511333333333",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    assert architect.is_authorized is False


@pytest.mark.asyncio
async def test_architect_cascade_on_organization_delete(db_session):
    """Test that architect is deleted when organization is deleted (CASCADE)."""
    org = Organization(name="Cascade Studio")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="cascade@test.com",
        hashed_password="hashed",
        phone="+5511444444444",
    )
    db_session.add(architect)
    await db_session.commit()
    architect_id = architect.id

    await db_session.delete(org)
    await db_session.commit()

    result = await db_session.execute(select(Architect).where(Architect.id == architect_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_architect_end_clients_relationship(db_session):
    """Test architect's relationship with end clients."""
    org = Organization(name="Client Rel Studio")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="clients@test.com",
        hashed_password="hashed",
        phone="+5511555555555",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    client1 = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Client One",
        phone="+5511666666666",
        email="c1@test.com",
    )
    client2 = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Client Two",
        phone="+5511777777777",
        email="c2@test.com",
    )
    db_session.add_all([client1, client2])
    await db_session.commit()

    await db_session.refresh(architect, ["end_clients"])
    assert len(architect.end_clients) == 2
    assert {c.name for c in architect.end_clients} == {"Client One", "Client Two"}


@pytest.mark.asyncio
async def test_architect_created_templates_relationship(db_session):
    """Test architect's relationship with templates they created."""
    org = Organization(name="Template Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="creator@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    template = BriefingTemplate(
        organization_id=org.id,
        created_by_architect_id=architect.id,
        name="Custom Template",
        is_global=False,
        description="Created by architect",
    )
    db_session.add(template)
    await db_session.commit()

    await db_session.refresh(architect, ["created_templates"])
    assert len(architect.created_templates) == 1
    assert architect.created_templates[0].name == "Custom Template"


@pytest.mark.asyncio
async def test_architect_required_fields(db_session):
    """Test that required fields cannot be null."""
    org = Organization(name="Required Fields Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    with pytest.raises(Exception):
        await db_session.commit()
