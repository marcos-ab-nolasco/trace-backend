"""Tests for organization isolation and multi-tenant security.

These tests verify that architects can only access resources from their own organization.
This is critical for GDPR compliance and preventing cross-tenant data leakage.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from tests.factories import (
    ArchitectFactory,
    BriefingTemplateFactory,
    EndClientFactory,
    OrganizationFactory,
    ProjectTypeFactory,
    make_auth_headers,
)


@pytest.fixture
async def org_a(db_session: AsyncSession) -> Organization:
    """Create Organization A."""
    return await OrganizationFactory.create_async(
        name="Organization A",
        settings={"access_token": "test_token_a", "phone_number_id": "123"},
    )


@pytest.fixture
async def org_b(db_session: AsyncSession) -> Organization:
    """Create Organization B."""
    return await OrganizationFactory.create_async(
        name="Organization B",
        settings={"access_token": "test_token_b", "phone_number_id": "456"},
    )


@pytest.fixture
async def architect_a(db_session: AsyncSession, org_a: Organization) -> Architect:
    """Create architect belonging to Organization A."""
    return await ArchitectFactory.create_async(
        organization=org_a,
        email="architect.a@example.com",
        phone="+5511999999999",
    )


@pytest.fixture
async def architect_b(db_session: AsyncSession, org_b: Organization) -> Architect:
    """Create architect belonging to Organization B."""
    return await ArchitectFactory.create_async(
        organization=org_b,
        email="architect.b@example.com",
        phone="+5511888888888",
    )


@pytest.fixture
async def client_a(
    db_session: AsyncSession, org_a: Organization, architect_a: Architect
) -> EndClient:
    """Create end client belonging to Organization A."""
    return await EndClientFactory.create_async(
        organization=org_a,
        architect=architect_a,
        name="Client A",
        phone="+5511777777777",
    )


@pytest.fixture
async def template_a(
    db_session: AsyncSession,
    org_a: Organization,
    architect_a: Architect,
) -> BriefingTemplate:
    """Create template for Organization A."""
    # Create a project type (using residencial trait)
    project_type = await ProjectTypeFactory.create_async(residencial=True)

    # Create template with custom questions
    return await BriefingTemplateFactory.create_with_version_async(
        organization_template=True,
        organization=org_a,
        created_by=architect_a,
        name="Template A",
        category="residencial",
        project_type=project_type,
        version_kwargs={
            "questions": [{"order": 1, "text": "What is your budget?", "type": "text"}]
        },
    )


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
        headers = make_auth_headers(architect_a)

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
