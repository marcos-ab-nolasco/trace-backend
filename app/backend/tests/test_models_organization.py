"""Tests for Organization model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.architect import Architect
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
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_organization_cascade_delete(db_session):
    """Test that deleting organization cascades to architects."""
    org = Organization(name="Studio Delete Test", whatsapp_business_account_id="999")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        full_name="Test Architect",
        phone="+5511999999999",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    architect_id = architect.id

    await db_session.delete(org)
    await db_session.commit()

    result = await db_session.execute(select(Architect).where(Architect.id == architect_id))
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


@pytest.mark.asyncio
async def test_organization_architects_relationship(db_session):
    """Test organization's relationship with architects."""
    org = Organization(name="Multi Architect Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect1 = Architect(
        organization_id=org.id,
        email="arch1@test.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    architect2 = Architect(
        organization_id=org.id,
        email="arch2@test.com",
        hashed_password="hashed",
        phone="+5511222222222",
    )
    db_session.add_all([architect1, architect2])
    await db_session.commit()

    await db_session.refresh(org, ["architects"])
    assert len(org.architects) == 2
    assert {a.email for a in org.architects} == {"arch1@test.com", "arch2@test.com"}


@pytest.mark.asyncio
async def test_organization_templates_relationship(db_session):
    """Test organization's relationship with templates."""
    from src.db.models.briefing_template import BriefingTemplate

    org = Organization(name="Template Owner Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    template = BriefingTemplate(
        organization_id=org.id,
        name="Org Template",
        is_global=False,
        description="Template owned by organization",
    )
    db_session.add(template)
    await db_session.commit()

    await db_session.refresh(org, ["templates"])
    assert len(org.templates) == 1
    assert org.templates[0].name == "Org Template"
