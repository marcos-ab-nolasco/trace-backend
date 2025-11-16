"""Tests for Organization model."""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.architect import Architect
from src.db.models.organization import Organization
from tests.factories import ArchitectFactory, BriefingTemplateFactory, OrganizationFactory


@pytest.mark.asyncio
async def test_create_organization(db_session):
    """Test creating an organization."""
    org = await OrganizationFactory.create_async(
        name="Arquitetura Studio",
        whatsapp_business_account_id="1234567890",
        settings={"timezone": "America/Sao_Paulo", "language": "pt-BR"},
    )

    assert isinstance(org.id, UUID)
    assert org.name == "Arquitetura Studio"
    assert org.whatsapp_business_account_id == "1234567890"
    assert org.settings == {"timezone": "America/Sao_Paulo", "language": "pt-BR"}
    assert isinstance(org.created_at, datetime)
    assert isinstance(org.updated_at, datetime)


@pytest.mark.asyncio
async def test_organization_unique_name(db_session):
    """Test that organization names must be unique."""
    await OrganizationFactory.create_async(name="Studio A", whatsapp_business_account_id="123")

    org2 = Organization(name="Studio A", whatsapp_business_account_id="456")
    db_session.add(org2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_organization_cascade_delete(db_session):
    """Test that deleting organization cascades to architects."""
    org = await OrganizationFactory.create_async(name="Studio Delete Test")

    architect = await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch@test.com",
        full_name="Test Architect",
    )
    architect_id = architect.id

    await db_session.delete(org)
    await db_session.commit()

    result = await db_session.execute(select(Architect).where(Architect.id == architect_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_organization_optional_fields(db_session):
    """Test organization with minimal required fields."""
    org = await OrganizationFactory.create_async(name="Minimal Org")

    assert org.whatsapp_business_account_id is None
    assert org.settings is None or org.settings == {}


@pytest.mark.asyncio
async def test_organization_architects_relationship(db_session):
    """Test organization's relationship with architects."""
    org = await OrganizationFactory.create_async(name="Multi Architect Org")

    await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch1@test.com",
    )
    await ArchitectFactory.create_async(
        organization=org,
        organization_id=org.id,
        email="arch2@test.com",
    )

    await db_session.refresh(org, ["architects"])
    assert len(org.architects) == 2
    assert {a.email for a in org.architects} == {"arch1@test.com", "arch2@test.com"}


@pytest.mark.asyncio
async def test_organization_templates_relationship(db_session, test_project_type):
    """Test organization's relationship with templates."""
    org = await OrganizationFactory.create_async(name="Template Owner Org")

    await BriefingTemplateFactory.create_async(
        organization=org,
        organization_id=org.id,
        name="Org Template",
        is_global=False,
        description="Template owned by organization",
        project_type=test_project_type,
    )

    await db_session.refresh(org, ["templates"])
    assert len(org.templates) == 1
    assert org.templates[0].name == "Org Template"
