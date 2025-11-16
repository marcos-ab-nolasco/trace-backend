"""Validation tests for factory-boy factories."""

from tests.factories import (
    ArchitectFactory,
    BriefingFactory,
    BriefingTemplateFactory,
    EndClientFactory,
    OrganizationFactory,
    ProjectTypeFactory,
    WhatsAppSessionFactory,
    make_auth_headers,
)


class TestOrganizationFactory:
    """Test OrganizationFactory."""

    async def test_create_organization(self) -> None:
        """Test creating a basic organization."""
        org = await OrganizationFactory.create_async()
        assert org.id is not None
        assert org.name.startswith("Test Organization")
        assert org.whatsapp_business_account_id is None

    async def test_create_organization_with_whatsapp(self) -> None:
        """Test creating organization with WhatsApp enabled."""
        org = await OrganizationFactory.create_async(with_whatsapp=True)
        assert org.id is not None
        assert org.whatsapp_business_account_id is not None
        assert org.settings is not None
        assert org.settings["whatsapp_enabled"] is True


class TestArchitectFactory:
    """Test ArchitectFactory."""

    async def test_create_architect(self) -> None:
        """Test creating a basic architect."""
        architect = await ArchitectFactory.create_async()
        assert architect.id is not None
        assert architect.email.endswith("@example.com")
        assert architect.hashed_password is not None
        assert architect.organization_id is not None
        assert architect.is_authorized is True

    async def test_create_unauthorized_architect(self) -> None:
        """Test creating an unauthorized architect."""
        architect = await ArchitectFactory.create_async(unauthorized=True)
        assert architect.is_authorized is False

    async def test_make_auth_headers(self) -> None:
        """Test creating auth headers from architect."""
        architect = await ArchitectFactory.create_async()
        headers = make_auth_headers(architect)
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")


class TestEndClientFactory:
    """Test EndClientFactory."""

    async def test_create_end_client(self) -> None:
        """Test creating a basic end client."""
        client = await EndClientFactory.create_async()
        assert client.id is not None
        assert client.name is not None
        assert client.phone is not None
        assert client.organization_id is not None
        assert client.architect_id is not None

    async def test_end_client_hierarchy(self) -> None:
        """Test that end client has proper organization hierarchy."""
        client = await EndClientFactory.create_async()
        assert client.organization is not None
        assert client.architect is not None
        assert client.architect.organization_id == client.organization_id


class TestProjectTypeFactory:
    """Test ProjectTypeFactory."""

    async def test_create_project_type(self) -> None:
        """Test creating a generic project type."""
        project_type = await ProjectTypeFactory.create_async()
        assert project_type.id is not None
        assert project_type.slug is not None
        assert project_type.is_active is True

    async def test_create_residencial_project_type(self) -> None:
        """Test creating residencial project type."""
        project_type = await ProjectTypeFactory.create_async(residencial=True)
        assert project_type.slug == "residencial"
        assert project_type.label == "Residencial"

    async def test_create_reforma_project_type(self) -> None:
        """Test creating reforma project type."""
        project_type = await ProjectTypeFactory.create_async(reforma=True)
        assert project_type.slug == "reforma"


class TestBriefingTemplateFactory:
    """Test BriefingTemplateFactory."""

    async def test_create_template_with_version(self, test_project_type) -> None:
        """Test creating a template with automatic version."""
        template = await BriefingTemplateFactory.create_async(project_type=test_project_type)
        assert template.id is not None
        assert template.name.startswith("Test Template")
        assert template.is_global is True
        # Version is created in post_generation
        # We need to check differently since it's created synchronously

    async def test_create_organization_template(self, test_project_type) -> None:
        """Test creating an organization-specific template."""
        template = await BriefingTemplateFactory.create_async(
            organization_template=True, project_type=test_project_type
        )
        assert template.is_global is False
        assert template.organization_id is not None
        assert template.created_by_architect_id is not None


class TestBriefingFactory:
    """Test BriefingFactory."""

    async def test_create_briefing_in_progress(self) -> None:
        """Test creating an in-progress briefing."""
        briefing = await BriefingFactory.create_async()
        assert briefing.id is not None
        assert briefing.status.value == "in_progress"
        assert briefing.end_client_id is not None
        assert briefing.template_version_id is not None

    async def test_create_completed_briefing(self) -> None:
        """Test creating a completed briefing."""
        briefing = await BriefingFactory.create_async(completed=True)
        assert briefing.status.value == "completed"
        assert briefing.completed_at is not None
        assert len(briefing.answers) > 0

    async def test_create_cancelled_briefing(self) -> None:
        """Test creating a cancelled briefing."""
        briefing = await BriefingFactory.create_async(cancelled=True)
        assert briefing.status.value == "cancelled"


class TestWhatsAppSessionFactory:
    """Test WhatsAppSessionFactory."""

    async def test_create_active_session(self) -> None:
        """Test creating an active WhatsApp session."""
        session = await WhatsAppSessionFactory.create_async()
        assert session.id is not None
        assert session.status == "active"
        assert session.end_client_id is not None
        assert session.phone_number is not None

    async def test_create_closed_session(self) -> None:
        """Test creating a closed WhatsApp session."""
        session = await WhatsAppSessionFactory.create_async(closed=True)
        assert session.status == "closed"

    async def test_create_session_without_briefing(self) -> None:
        """Test creating a session without a briefing."""
        session = await WhatsAppSessionFactory.create_async(no_briefing=True)
        assert session.briefing_id is None


class TestFactoryBatchCreation:
    """Test batch creation with factories."""

    async def test_create_batch_organizations(self) -> None:
        """Test creating multiple organizations."""
        orgs = await OrganizationFactory.create_batch_async(3)
        assert len(orgs) == 3
        assert all(org.id is not None for org in orgs)

        # Check uniqueness
        names = [org.name for org in orgs]
        assert len(names) == len(set(names))

    async def test_create_batch_architects(self) -> None:
        """Test creating multiple architects."""
        architects = await ArchitectFactory.create_batch_async(3)
        assert len(architects) == 3
        assert all(arch.id is not None for arch in architects)

        # Check uniqueness of emails
        emails = [arch.email for arch in architects]
        assert len(emails) == len(set(emails))
