"""Tests for template CRUD API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.db.models.architect import Architect


@pytest.fixture
async def organization(db_session: AsyncSession) -> Organization:
    """Create test organization."""
    org = Organization(name="Test Architecture Firm", whatsapp_business_account_id="1234567890")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def architect_user(db_session: AsyncSession, organization: Organization) -> Architect:
    """Create architect with organization."""
    architect = Architect(
        organization_id=organization.id,
        email="architect@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    return architect


@pytest.fixture
async def global_template(db_session: AsyncSession, project_type_residencial) -> BriefingTemplate:
    """Create a global template with version."""
    template = BriefingTemplate(
        name="Template Residencial Global",
        category="residencial",
        description="Template global para projetos residenciais",
        is_global=True,
        organization_id=None,  # Global template has no organization
        created_by_architect_id=None,  # System template
        project_type_id=project_type_residencial.id,
    )
    db_session.add(template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=[
            {
                "order": 1,
                "question": "Qual o tipo de construção?",
                "type": "multiple_choice",
                "options": ["Casa", "Apartamento", "Sobrado"],
                "required": True,
            },
            {
                "order": 2,
                "question": "Qual a área desejada em m²?",
                "type": "number",
                "required": True,
                "validation": {"min": 20, "max": 5000},
            },
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
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
    from src.core.security import create_access_token

    token = create_access_token(data={"sub": str(architect_user.id)})
    return {"Authorization": f"Bearer {token}"}


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
    assert len(data["templates"][0]["current_version"]["questions"]) == 2


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
    # Create custom template for architect
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
        questions=[
            {
                "order": 1,
                "question": "Tipo de reforma?",
                "type": "text",
                "required": True,
            }
        ],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()
    custom_template.current_version_id = version.id
    await db_session.commit()

    response = await client.get("/api/templates", headers=architect_auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    template_names = {t["name"] for t in data["templates"]}
    assert "Template Residencial Global" in template_names
    assert "Meu Template Customizado" in template_names


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
        "initial_version": {"questions": [{"order": 1, "question": "Test?", "type": "text", "required": True}]},
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
            "questions": [
                {
                    "order": 1,
                    "question": "Qual o tipo de reforma?",
                    "type": "multiple_choice",
                    "options": ["Cozinha", "Banheiro", "Quarto"],
                    "required": True,
                },
                {
                    "order": 2,
                    "question": "Orçamento disponível?",
                    "type": "number",
                    "required": False,
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
    assert len(data["current_version"]["questions"]) == 2


@pytest.mark.asyncio
async def test_create_template_invalid_category(
    client: AsyncClient, architect_user: Architect, architect_auth_headers: dict[str, str]
):
    """Test creating template with invalid category returns 400."""
    payload = {
        "name": "Invalid Template",
        "category": "invalid_category",
        "initial_version": {"questions": [{"order": 1, "question": "Test?", "type": "text", "required": True}]},
    }

    response = await client.post("/api/templates", json=payload, headers=architect_auth_headers)

    # 400 because service validates ProjectType existence (not a schema validation error)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_template_invalid_question_type(
    client: AsyncClient,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_residencial,
):
    """Test creating template with invalid question type returns 422."""
    payload = {
        "name": "Invalid Questions",
        "category": "residencial",
        "initial_version": {
            "questions": [{"order": 1, "question": "Test?", "type": "invalid_type", "required": True}]
        },
    }

    response = await client.post("/api/templates", json=payload, headers=architect_auth_headers)

    assert response.status_code == 422


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
    from uuid import uuid4

    fake_id = uuid4()
    response = await client.get(f"/api/templates/{fake_id}", headers=architect_auth_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_template_creates_new_version(
    client: AsyncClient,
    db_session: AsyncSession,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_comercial,
):
    """Test updating template creates a new version."""
    # Create custom template
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
        questions=[{"order": 1, "question": "Original question?", "type": "text", "required": True}],
        is_active=True,
    )
    db_session.add(version1)
    await db_session.flush()
    template.current_version_id = version1.id
    await db_session.commit()
    await db_session.refresh(template)

    # Update template
    update_payload = {
        "questions": [
            {"order": 1, "question": "Updated question?", "type": "text", "required": True},
            {"order": 2, "question": "New question?", "type": "number", "required": False},
        ],
        "change_description": "Added new question",
    }

    response = await client.put(
        f"/api/templates/{template.id}", json=update_payload, headers=architect_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["current_version"]["version_number"] == 2
    assert len(data["current_version"]["questions"]) == 2
    assert data["current_version"]["change_description"] == "Added new question"


@pytest.mark.asyncio
async def test_update_template_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
    architect_user: Architect,
    architect_auth_headers: dict[str, str],
    project_type_residencial,
):
    """Test updating another architect's template returns 403."""
    # Create another organization and architect
    other_org = Organization(name="Other Firm")
    db_session.add(other_org)
    await db_session.flush()

    other_architect = Architect(
        organization_id=other_org.id,
        email="other@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(other_architect)
    await db_session.flush()

    # Create template owned by other architect
    other_template = BriefingTemplate(
        name="Other's Template",
        category="residencial",
        is_global=False,
        organization_id=other_org.id,
        created_by_architect_id=other_architect.id,
        project_type_id=project_type_residencial.id,
    )
    db_session.add(other_template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=other_template.id,
        version_number=1,
        questions=[{"order": 1, "question": "Test?", "type": "text", "required": True}],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()
    other_template.current_version_id = version.id
    await db_session.commit()

    # Try to update with current user
    update_payload = {"questions": [{"order": 1, "question": "Hacked?", "type": "text", "required": True}]}

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
    update_payload = {"questions": [{"order": 1, "question": "Try to update?", "type": "text", "required": True}]}

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
    # Create template with multiple versions
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

    # Create 3 versions
    for i in range(1, 4):
        version = TemplateVersion(
            template_id=template.id,
            version_number=i,
            questions=[{"order": 1, "question": f"Question v{i}?", "type": "text", "required": True}],
            is_active=(i == 3),
            change_description=f"Version {i}" if i > 1 else None,
        )
        db_session.add(version)
        if i == 3:
            await db_session.flush()
            template.current_version_id = version.id

    await db_session.commit()
    await db_session.refresh(template)

    response = await client.get(
        f"/api/templates/{template.id}/versions", headers=architect_auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["versions"]) == 3
    assert data["versions"][0]["version_number"] == 3  # Most recent first
    assert data["versions"][2]["version_number"] == 1
