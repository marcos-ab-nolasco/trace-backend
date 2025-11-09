"""Tests for organization isolation and multi-tenant security.

These tests verify that architects can only access resources from their own organization.
This is critical for GDPR compliance and preventing cross-tenant data leakage.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.db.models.architect import Architect
from src.db.models.briefing import Briefing, BriefingStatus
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.project_type import ProjectType
from src.db.models.template_version import TemplateVersion


@pytest.fixture
async def org_a(db_session: AsyncSession) -> Organization:
    """Create Organization A."""
    org = Organization(
        name="Organization A",
        settings={"access_token": "test_token_a", "phone_number_id": "123"},
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def org_b(db_session: AsyncSession) -> Organization:
    """Create Organization B."""
    org = Organization(
        name="Organization B",
        settings={"access_token": "test_token_b", "phone_number_id": "456"},
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def architect_a(db_session: AsyncSession, org_a: Organization) -> Architect:
    """Create architect belonging to Organization A."""
    architect = Architect(
        organization_id=org_a.id,
        email="architect.a@example.com",
        hashed_password="hashed",
        phone="+5511999999999",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)
    return architect


@pytest.fixture
async def architect_b(db_session: AsyncSession, org_b: Organization) -> Architect:
    """Create architect belonging to Organization B."""
    architect = Architect(
        organization_id=org_b.id,
        email="architect.b@example.com",
        hashed_password="hashed",
        phone="+5511888888888",
        is_authorized=True,
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)
    return architect


@pytest.fixture
async def client_a(
    db_session: AsyncSession, org_a: Organization, architect_a: Architect
) -> EndClient:
    """Create end client belonging to Organization A."""
    client = EndClient(
        organization_id=org_a.id,
        architect_id=architect_a.id,
        name="Client A",
        phone="+5511777777777",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest.fixture
async def template_a(
    db_session: AsyncSession,
    org_a: Organization,
    architect_a: Architect,
    project_type_residencial: ProjectType,
) -> BriefingTemplate:
    """Create template for Organization A."""
    template = BriefingTemplate(
        organization_id=org_a.id,
        created_by_architect_id=architect_a.id,
        name="Template A",
        category="residencial",
        project_type_id=project_type_residencial.id,
    )
    db_session.add(template)
    await db_session.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=[{"order": 1, "text": "What is your budget?", "type": "text"}],
        is_active=True,
    )
    db_session.add(version)
    await db_session.flush()

    template.current_version_id = version.id
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def briefing_a(
    db_session: AsyncSession,
    client_a: EndClient,
    template_a: BriefingTemplate,
) -> Briefing:
    """Create briefing for Organization A's client."""
    version = template_a.versions[0]
    briefing = Briefing(
        end_client_id=client_a.id,
        template_version_id=version.id,
        status=BriefingStatus.IN_PROGRESS,
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)
    return briefing


def get_auth_headers(architect: Architect) -> dict:
    """Generate authentication headers for an architect."""
    access_token = create_access_token({"sub": str(architect.id)})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.mark.asyncio
class TestBriefingOrganizationIsolation:
    """Test that briefing endpoints enforce organization isolation."""

    async def test_cannot_start_briefing_with_other_org_architect_id(
        self,
        client: AsyncClient,
        architect_a: Architect,
        architect_b: Architect,
        mock_extraction_service,
        mock_template_service,
        mock_whatsapp_service,
    ):
        """Architect A cannot start a briefing using Architect B's ID."""
        headers = get_auth_headers(architect_a)

        response = await client.post(
            "/api/briefings/start-from-whatsapp",
            json={
                "architect_id": str(architect_b.id),
                "architect_message": "Client: John Doe, Phone: +5511555555555",
            },
            headers=headers,
        )

        assert response.status_code == 403
        assert "organization" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_architecture_has_organization_relationships():
    """Verify data model has necessary organization relationships.

    This test documents the expected data model structure for organization isolation.
    """
    assert hasattr(Architect, "organization_id")
    assert hasattr(EndClient, "organization_id")
    assert hasattr(BriefingTemplate, "organization_id")

    assert hasattr(Architect, "organization")
