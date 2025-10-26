"""Tests for BriefingTemplate and TemplateVersion models."""

import pytest
from uuid import UUID
from datetime import datetime

from src.db.models.briefing_template import BriefingTemplate
from src.db.models.template_version import TemplateVersion
from src.db.models.architect import Architect
from src.db.models.organization import Organization
from src.db.models.user import User


@pytest.mark.asyncio
async def test_create_global_template(db_session):
    """Test creating a global (system-wide) template."""
    template = BriefingTemplate(
        name="Reforma Residencial",
        category="reforma",
        is_global=True,
        description="Template padrão para projetos de reforma residencial",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert isinstance(template.id, UUID)
    assert template.name == "Reforma Residencial"
    assert template.category == "reforma"
    assert template.is_global is True
    assert template.architect_id is None
    assert template.current_version_id is None
    assert isinstance(template.created_at, datetime)


@pytest.mark.asyncio
async def test_create_architect_custom_template(db_session):
    """Test creating a custom template for a specific architect."""
    user = User(email="architect@test.com", hashed_password="hashed")
    org = Organization(name="Test Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511111111111")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    template = BriefingTemplate(
        name="Reforma Custom",
        category="reforma",
        is_global=False,
        architect_id=architect.id,
        description="Template customizado pelo arquiteto",
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)

    assert template.is_global is False
    assert template.architect_id == architect.id
    assert template.architect.id == architect.id


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

    # Set current version
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

    # Create version 2 and deactivate version 1
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
async def test_template_unique_name_per_architect(db_session):
    """Test that template names must be unique per architect (or global)."""
    user = User(email="unique@test.com", hashed_password="hashed")
    org = Organization(name="Unique Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511222222222")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    template1 = BriefingTemplate(
        name="My Template", category="reforma", is_global=False, architect_id=architect.id
    )
    db_session.add(template1)
    await db_session.commit()

    # Try to create another template with same name for same architect
    template2 = BriefingTemplate(
        name="My Template", category="construcao", is_global=False, architect_id=architect.id
    )
    db_session.add(template2)
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


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

    # Delete template
    await db_session.delete(template)
    await db_session.commit()

    # Verify version is also deleted
    from sqlalchemy import select

    result = await db_session.execute(
        select(TemplateVersion).where(TemplateVersion.id == version_id)
    )
    assert result.scalar_one_or_none() is None
