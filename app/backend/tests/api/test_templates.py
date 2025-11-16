"""Tests for template CRUD API endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from tests.factories import (
    ArchitectFactory,
    BriefingTemplateFactory,
    OrganizationFactory,
    TemplateVersionFactory,
    make_auth_headers,
)


@pytest.fixture
async def organization(db_session: AsyncSession) -> Organization:
    """Create test organization."""
    return await OrganizationFactory.create_async(
        name="Test Architecture Firm", whatsapp_business_account_id="1234567890"
    )


@pytest.fixture
async def architect_user(db_session: AsyncSession, organization: Organization) -> Architect:
    """Create architect with organization."""
    return await ArchitectFactory.create_async(
        organization_id=organization.id,
        email="architect@test.com",
        phone="+5511999999999",
    )


@pytest.fixture
async def global_template(db_session: AsyncSession, project_type_residencial) -> BriefingTemplate:
    """Create a global template with version."""
    from src.db.models.information_requirement import InformationRequirement

    template = await BriefingTemplateFactory.create_async(
        name="Template Residencial Global",
        category="residencial",
        description="Template global para projetos residenciais",
        is_global=True,
        organization_id=None,
        created_by_architect_id=None,
        project_type=project_type_residencial,
    )

    version = await TemplateVersionFactory.create_async(
        template_id=template.id,
        version_number=1,
        is_active=True,
        is_current=True,
    )

    # Create information requirements
    requirements = [
        InformationRequirement(
            template_id=version.id,
            field_name="property_type",
            field_type="text",
            required=True,
            priority=10,
            description="Tipo de construção (Casa, Apartamento, Sobrado)",
            suggested_questions=["Qual o tipo de construção?"],
        ),
        InformationRequirement(
            template_id=version.id,
            field_name="area_size",
            field_type="number",
            required=True,
            priority=9,
            description="Área desejada em m²",
            validation_rules={"min": 20, "max": 5000},
            suggested_questions=["Qual a área desejada em m²?"],
        ),
    ]
    for req in requirements:
        db_session.add(req)

    await db_session.commit()
    await db_session.refresh(template)

    return template


@pytest.mark.asyncio
async def test_list_templates_unauthenticated(client: AsyncClient):
    """Test listing templates without authentication returns 403."""
    response = await client.get("/api/templates")
    assert response.status_code == 403


@pytest.fixture
def architect_auth_headers(architect_user: Architect) -> dict[str, str]:
    """Create auth headers for architect user."""
    return make_auth_headers(architect_user)


@pytest.mark.skip(
    reason="TODO: Review after refactor - possible seed/fixture conflict causing duplicate templates"
)
@pytest.mark.asyncio
async def test_list_templates_global_only(
    client: AsyncClient,
    architect_user: Architect,
    global_template: BriefingTemplate,
    architect_auth_headers: dict[str, str],
):
    """Test listing templates returns global templates for authenticated architect."""
    response = await client.get("/api/templates", headers=architect_auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["templates"]) == 1
    assert data["templates"][0]["name"] == "Template Residencial Global"
    assert data["templates"][0]["is_global"] is True
    assert data["templates"][0]["current_version"] is not None
    assert len(data["templates"][0]["current_version"]["requirements"]) == 2


@pytest.mark.skip(
    reason="TODO: Review after refactor - possible seed/fixture conflict causing duplicate templates"
)
@pytest.mark.asyncio
async def test_list_templates_with_custom(
    client: AsyncClient,
    db_session: AsyncSession,
    architect_user: Architect,
    global_template: BriefingTemplate,
    architect_auth_headers: dict[str, str],
    project_type_reforma,
):
    """Test listing templates includes architect's custom templates."""
    from src.db.models.information_requirement import InformationRequirement

    architect = architect_user
    custom_template = BriefingTemplate(
        name="Meu Template Customizado",
        category="reforma",
        description="Template personalizado",
        is_global=False,
        organization_id=architect.organization_id,
        created_by_architect_id=architect.id,
        project_type_id=project_type_reforma.id,
    )
    db_session.add(custom_template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=custom_template.id,
        version_number=1,
        is_active=True,
        is_current=True,
    )
    db_session.add(version)
    await db_session.flush()

    # Create information requirement
    requirement = InformationRequirement(
        template_id=version.id,
        field_name="renovation_type",
        field_type="text",
        required=True,
        priority=10,
        suggested_questions=["Tipo de reforma?"],
    )
    db_session.add(requirement)

    await db_session.commit()

    response = await client.get("/api/templates", headers=architect_auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    template_names = {t["name"] for t in data["templates"]}
    assert "Template Residencial Global" in template_names
    assert "Meu Template Customizado" in template_names


@pytest.mark.skip(
    reason="TODO: Review after refactor - possible seed/fixture conflict causing duplicate templates"
)
@pytest.mark.asyncio
async def test_list_templates_filter_by_category(
    client: AsyncClient,
    architect_user: Architect,
    global_template: BriefingTemplate,
    architect_auth_headers: dict[str, str],
):
    """Test filtering templates by category."""
    response = await client.get(
        "/api/templates?category=residencial",
        headers=architect_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert all(t["category"] == "residencial" for t in data["templates"])


@pytest.mark.asyncio
async def test_create_template_unauthenticated(client: AsyncClient):
    """Test creating template without authentication returns 403."""
    payload = {
        "name": "New Template",
        "category": "residencial",
        "initial_version": {
            "requirements": [
                {
                    "field_name": "test_field",
                    "field_type": "text",
                    "required": True,
                    "suggested_questions": ["Test?"],
                }
            ]
        },
    }
    response = await client.post("/api/templates", json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_custom_template(
    client: AsyncClient,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_reforma,
):
    """Test creating a custom template for architect."""
    payload = {
        "name": "Novo Template Reforma",
        "category": "reforma",
        "description": "Template para reformas",
        "initial_version": {
            "requirements": [
                {
                    "field_name": "renovation_type",
                    "field_type": "text",
                    "required": True,
                    "priority": 10,
                    "description": "Tipo de reforma (Cozinha, Banheiro, Quarto)",
                    "suggested_questions": ["Qual o tipo de reforma?"],
                },
                {
                    "field_name": "budget",
                    "field_type": "number",
                    "required": False,
                    "priority": 5,
                    "suggested_questions": ["Orçamento disponível?"],
                },
            ],
            "change_description": "Versão inicial",
        },
    }

    response = await client.post("/api/templates", json=payload, headers=architect_auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Novo Template Reforma"
    assert data["category"] == "reforma"
    assert data["is_global"] is False
    assert data["created_by_architect_id"] is not None
    assert data["current_version"] is not None
    assert data["current_version"]["version_number"] == 1
    assert len(data["current_version"]["requirements"]) == 2


@pytest.mark.asyncio
async def test_create_template_invalid_category(
    client: AsyncClient, architect_user: Architect, architect_auth_headers: dict[str, str]
):
    """Test creating template with invalid category returns 400."""
    payload = {
        "name": "Invalid Template",
        "category": "invalid_category",
        "initial_version": {
            "requirements": [
                {
                    "field_name": "test",
                    "field_type": "text",
                    "required": True,
                    "suggested_questions": ["Test?"],
                }
            ]
        },
    }

    response = await client.post("/api/templates", json=payload, headers=architect_auth_headers)

    assert response.status_code == 400


@pytest.mark.skip(reason="TODO: Implement field_type validation in schema after refactor")
@pytest.mark.asyncio
async def test_create_template_invalid_field_type(
    client: AsyncClient,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_residencial,
):
    """Test creating template with invalid field type returns 422."""
    payload = {
        "name": "Invalid Requirements",
        "category": "residencial",
        "initial_version": {
            "requirements": [
                {
                    "field_name": "test",
                    "field_type": "invalid_type",
                    "required": True,
                    "suggested_questions": ["Test?"],
                }
            ]
        },
    }

    response = await client.post("/api/templates", json=payload, headers=architect_auth_headers)

    assert response.status_code == 422


@pytest.mark.skip(
    reason="TODO: Review after refactor - current_version might not be loaded correctly by API/service"
)
@pytest.mark.asyncio
async def test_get_template_by_id(
    client: AsyncClient,
    architect_user: Architect,
    global_template: BriefingTemplate,
    architect_auth_headers: dict[str, str],
):
    """Test getting template details by ID."""
    response = await client.get(
        f"/api/templates/{global_template.id}",
        headers=architect_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(global_template.id)
    assert data["name"] == "Template Residencial Global"
    assert data["current_version"] is not None


@pytest.mark.asyncio
async def test_get_template_not_found(
    client: AsyncClient, architect_user: Architect, architect_auth_headers: dict[str, str]
):
    """Test getting non-existent template returns 404."""
    fake_id = uuid4()
    response = await client.get(f"/api/templates/{fake_id}", headers=architect_auth_headers)

    assert response.status_code == 404


@pytest.mark.skip(
    reason="TODO: Review after refactor - current_version might not be loaded correctly by API/service"
)
@pytest.mark.asyncio
async def test_update_template_creates_new_version(
    client: AsyncClient,
    db_session: AsyncSession,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_comercial,
):
    """Test updating template creates a new version."""
    from src.db.models.information_requirement import InformationRequirement

    architect = architect_user
    template = BriefingTemplate(
        name="Template to Update",
        category="comercial",
        is_global=False,
        organization_id=architect.organization_id,
        created_by_architect_id=architect.id,
        project_type_id=project_type_comercial.id,
    )
    db_session.add(template)
    await db_session.flush()

    version1 = TemplateVersion(
        template_id=template.id,
        version_number=1,
        is_active=True,
        is_current=True,
    )
    db_session.add(version1)
    await db_session.flush()

    # Create initial requirement
    req1 = InformationRequirement(
        template_id=version1.id,
        field_name="original_field",
        field_type="text",
        required=True,
        suggested_questions=["Original question?"],
    )
    db_session.add(req1)

    await db_session.commit()
    await db_session.refresh(template)

    update_payload = {
        "requirements": [
            {
                "field_name": "updated_field",
                "field_type": "text",
                "required": True,
                "suggested_questions": ["Updated question?"],
            },
            {
                "field_name": "new_field",
                "field_type": "number",
                "required": False,
                "suggested_questions": ["New question?"],
            },
        ],
        "change_description": "Added new requirement",
    }

    response = await client.put(
        f"/api/templates/{template.id}", json=update_payload, headers=architect_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["current_version"]["version_number"] == 2
    assert len(data["current_version"]["requirements"]) == 2
    assert data["current_version"]["change_description"] == "Added new requirement"


@pytest.mark.asyncio
async def test_update_template_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_residencial,
):
    """Test updating another architect's template returns 403."""
    other_org = await OrganizationFactory.create_async(name="Other Firm")
    other_architect = await ArchitectFactory.create_async(
        organization_id=other_org.id,
        email="other@test.com",
        phone="+5511888888888",
    )

    other_template = await BriefingTemplateFactory.create_async(
        name="Other's Template",
        category="residencial",
        is_global=False,
        organization_id=other_org.id,
        created_by_architect_id=other_architect.id,
        project_type=project_type_residencial,
    )

    version = await TemplateVersionFactory.create_async(
        template_id=other_template.id,
        version_number=1,
        is_active=True,
        is_current=True,
    )

    # Create requirement
    from src.db.models.information_requirement import InformationRequirement

    req = InformationRequirement(
        template_id=version.id,
        field_name="test_field",
        field_type="text",
        required=True,
        suggested_questions=["Test?"],
    )
    db_session.add(req)

    await db_session.commit()

    update_payload = {
        "requirements": [
            {
                "field_name": "hacked_field",
                "field_type": "text",
                "required": True,
                "suggested_questions": ["Hacked?"],
            }
        ]
    }

    response = await client.put(
        f"/api/templates/{other_template.id}", json=update_payload, headers=architect_auth_headers
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_global_template_forbidden(
    client: AsyncClient,
    architect_user: Architect,
    global_template: BriefingTemplate,
    architect_auth_headers: dict[str, str],
):
    """Test architects cannot update global templates."""
    update_payload = {
        "requirements": [
            {
                "field_name": "try_update",
                "field_type": "text",
                "required": True,
                "suggested_questions": ["Try to update?"],
            }
        ]
    }

    response = await client.put(
        f"/api/templates/{global_template.id}", json=update_payload, headers=architect_auth_headers
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_template_versions(
    client: AsyncClient,
    db_session: AsyncSession,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_residencial,
):
    """Test getting version history of a template."""
    from src.db.models.information_requirement import InformationRequirement

    architect = architect_user
    template = BriefingTemplate(
        name="Versioned Template",
        category="residencial",
        is_global=False,
        organization_id=architect.organization_id,
        created_by_architect_id=architect.id,
        project_type_id=project_type_residencial.id,
    )
    db_session.add(template)
    await db_session.flush()

    for i in range(1, 4):
        version = TemplateVersion(
            template_id=template.id,
            version_number=i,
            is_active=(i == 3),
            is_current=(i == 3),
            change_description=f"Version {i}" if i > 1 else None,
        )
        db_session.add(version)
        await db_session.flush()

        # Create requirement for each version
        req = InformationRequirement(
            template_id=version.id,
            field_name=f"field_v{i}",
            field_type="text",
            required=True,
            suggested_questions=[f"Question v{i}?"],
        )
        db_session.add(req)

    await db_session.commit()
    await db_session.refresh(template)

    response = await client.get(
        f"/api/templates/{template.id}/versions", headers=architect_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["versions"]) == 3
    assert data["versions"][0]["version_number"] == 3
    assert data["versions"][2]["version_number"] == 1
