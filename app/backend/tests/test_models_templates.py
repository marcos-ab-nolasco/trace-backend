"""Tests for BriefingTemplate and TemplateVersion models."""

from datetime import datetime
from uuid import UUID

import pytest

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.organization import Organization
from src.db.models.project_type import ProjectType
from src.db.models.template_version import TemplateVersion


@pytest.mark.asyncio
async def test_create_global_template(db_session):
    """Test creating a global (system-wide) template."""
    template = BriefingTemplate(
        name="Reforma Residencial",
        category="reforma",
        is_global=True,
        organization_id=None,
        description="Template padrão para projetos de reforma residencial",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert isinstance(template.id, UUID)
    assert template.name == "Reforma Residencial"
    assert template.category == "reforma"
    assert template.is_global is True
    assert template.organization_id is None
    assert template.created_by_architect_id is None
    assert template.current_version_id is None
    assert isinstance(template.created_at, datetime)


@pytest.mark.asyncio
async def test_create_organization_template(db_session):
    """Test creating a template owned by an organization."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="architect@test.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    template = BriefingTemplate(
        name="Reforma Custom",
        category="reforma",
        is_global=False,
        organization_id=org.id,
        created_by_architect_id=architect.id,
        description="Template customizado pela organização",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert template.is_global is False
    assert template.organization_id == org.id
    assert template.created_by_architect_id == architect.id
    assert template.organization.name == "Test Org"
    assert template.created_by.email == "architect@test.com"


@pytest.mark.asyncio
async def test_template_with_project_type(db_session):
    """Test creating a template with project type (normalized category)."""
    project_type = ProjectType(
        slug="residencial", label="Residencial", description="Projetos residenciais", is_active=True
    )
    db_session.add(project_type)
    await db_session.commit()
    await db_session.refresh(project_type)

    template = BriefingTemplate(
        name="Template Residencial",
        is_global=True,
        project_type_id=project_type.id,
        description="Template para projetos residenciais",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert template.project_type_id == project_type.id
    assert template.project_type.slug == "residencial"
    assert template.project_type.label == "Residencial"


@pytest.mark.asyncio
async def test_create_template_version(db_session):
    """Test creating a template version."""
    template = BriefingTemplate(name="Test Template", category="construcao", is_global=True)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    questions = [
        {
            "order": 1,
            "question": "Qual o tipo de construção?",
            "type": "multiple_choice",
            "options": ["Casa", "Apartamento", "Comercial"],
            "required": True,
        },
        {
            "order": 2,
            "question": "Qual a área aproximada em m²?",
            "type": "number",
            "required": True,
        },
    ]

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=questions,
        change_description="Versão inicial",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    assert isinstance(version.id, UUID)
    assert version.template_id == template.id
    assert version.version_number == 1
    assert len(version.questions) == 2
    assert version.questions[0]["question"] == "Qual o tipo de construção?"
    assert version.is_active is True
    assert isinstance(version.created_at, datetime)


@pytest.mark.asyncio
async def test_template_current_version_relationship(db_session):
    """Test template current_version relationship."""
    template = BriefingTemplate(name="Versioned Template", category="paisagismo", is_global=True)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    version1 = TemplateVersion(
        template_id=template.id, version_number=1, questions=[{"order": 1, "question": "Q1"}]
    )
    db_session.add(version1)
    await db_session.commit()
    await db_session.refresh(version1)

    template.current_version_id = version1.id
    await db_session.commit()
    await db_session.refresh(template, ["current_version"])

    assert template.current_version.id == version1.id
    assert template.current_version.version_number == 1


@pytest.mark.asyncio
async def test_template_versions_relationship(db_session):
    """Test template has multiple versions."""
    template = BriefingTemplate(name="Multi-Version Template", category="reforma", is_global=True)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    version1 = TemplateVersion(
        template_id=template.id, version_number=1, questions=[{"order": 1, "question": "V1"}]
    )
    version2 = TemplateVersion(
        template_id=template.id, version_number=2, questions=[{"order": 1, "question": "V2"}]
    )
    db_session.add_all([version1, version2])
    await db_session.commit()

    await db_session.refresh(template, ["versions"])
    assert len(template.versions) == 2
    assert template.versions[0].version_number in [1, 2]
    assert template.versions[1].version_number in [1, 2]


@pytest.mark.asyncio
async def test_template_version_deactivation(db_session):
    """Test deactivating old versions when creating new one."""
    template = BriefingTemplate(name="Deactivation Test", category="reforma", is_global=True)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    version1 = TemplateVersion(
        template_id=template.id, version_number=1, questions=[{"order": 1, "question": "V1"}]
    )
    db_session.add(version1)
    await db_session.commit()
    await db_session.refresh(version1)

    assert version1.is_active is True

    version2 = TemplateVersion(
        template_id=template.id, version_number=2, questions=[{"order": 1, "question": "V2"}]
    )
    version1.is_active = False
    db_session.add(version2)
    await db_session.commit()
    await db_session.refresh(version1)
    await db_session.refresh(version2)

    assert version1.is_active is False
    assert version2.is_active is True


@pytest.mark.asyncio
async def test_template_unique_name_per_organization(db_session):
    """Test that template names must be unique per organization."""
    org = Organization(name="Unique Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="unique@test.com",
        hashed_password="hashed",
        phone="+5511222222222",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    template1 = BriefingTemplate(
        name="My Template",
        category="reforma",
        is_global=False,
        organization_id=org.id,
        created_by_architect_id=architect.id,
    )
    db_session.add(template1)
    await db_session.commit()

    template2 = BriefingTemplate(
        name="My Template",
        category="construcao",
        is_global=False,
        organization_id=org.id,
    )
    db_session.add(template2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_template_unique_name_different_organizations(db_session):
    """Test that different organizations can have templates with same name."""
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add_all([org1, org2])
    await db_session.commit()
    await db_session.refresh(org1)
    await db_session.refresh(org2)

    template1 = BriefingTemplate(
        name="My Template", is_global=False, organization_id=org1.id, category="reforma"
    )
    db_session.add(template1)
    await db_session.commit()

    template2 = BriefingTemplate(
        name="My Template", is_global=False, organization_id=org2.id, category="construcao"
    )
    db_session.add(template2)
    await db_session.commit()

    assert template1.name == template2.name
    assert template1.organization_id != template2.organization_id


@pytest.mark.asyncio
async def test_cascade_delete_template_versions(db_session):
    """Test that deleting template deletes all its versions."""
    template = BriefingTemplate(name="Delete Test", category="reforma", is_global=True)
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    version = TemplateVersion(
        template_id=template.id, version_number=1, questions=[{"order": 1, "question": "Q1"}]
    )
    db_session.add(version)
    await db_session.commit()
    version_id = version.id

    await db_session.delete(template)
    await db_session.commit()

    from sqlalchemy import select

    result = await db_session.execute(
        select(TemplateVersion).where(TemplateVersion.id == version_id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_template_creator_can_be_null(db_session):
    """Test that template can exist without creator (created_by_architect_id = NULL)."""
    org = Organization(name="No Creator Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    template = BriefingTemplate(
        name="No Creator Template",
        is_global=False,
        organization_id=org.id,
        created_by_architect_id=None,
        description="Template sem criador identificado",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert template.created_by_architect_id is None
    assert template.created_by is None


@pytest.mark.asyncio
async def test_architect_deletion_preserves_templates(db_session):
    """Test that deleting creator architect preserves templates (SET NULL)."""
    org = Organization(name="Template Preservation Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="creator@test.com",
        hashed_password="hashed",
        phone="+5511333333333",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    template = BriefingTemplate(
        name="Architect Template",
        is_global=False,
        organization_id=org.id,
        created_by_architect_id=architect.id,
    )
    db_session.add(template)
    await db_session.commit()
    template_id = template.id

    await db_session.delete(architect)
    await db_session.commit()

    from sqlalchemy import select

    result = await db_session.execute(
        select(BriefingTemplate).where(BriefingTemplate.id == template_id)
    )
    preserved_template = result.scalar_one()
    assert preserved_template is not None
    assert preserved_template.organization_id == org.id
    assert preserved_template.created_by_architect_id is None
