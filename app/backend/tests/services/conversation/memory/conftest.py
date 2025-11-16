"""Conversation memory domain-specific test fixtures."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.services.ai.base import BaseAIService
from tests.factories import (
    ArchitectFactory,
    BriefingFactory,
    BriefingTemplateFactory,
    EndClientFactory,
    OrganizationFactory,
    TemplateVersionFactory,
)


@pytest.fixture
async def test_briefing(db_session):
    """Create a test briefing with all required relationships for conversation tests."""
    from tests.factories import ProjectTypeFactory

    org = await OrganizationFactory.create_async(name="Test Org")
    project_type = await ProjectTypeFactory.create_async()

    template = await BriefingTemplateFactory.create_async(
        name="Test Template",
        is_global=False,
        organization_id=org.id,
        project_type=project_type,
    )

    version = await TemplateVersionFactory.create_async(
        template_id=template.id,
        version_number=1,
        context_prompt="Test context",
    )

    architect = await ArchitectFactory.create_async(
        email="architect@test.com",
        full_name="Test Architect",
        phone="+5511999999999",
        organization_id=org.id,
    )

    end_client = await EndClientFactory.create_async(
        name="Test Client",
        phone="+5511888888888",
        architect_id=architect.id,
        organization_id=org.id,
    )

    briefing = await BriefingFactory.create_async(
        end_client_id=end_client.id,
        template_version_id=version.id,
        information_state={},
        gathered_information={},
    )

    return briefing


@pytest.fixture
def mock_openai_client(mocker):
    """Mock AsyncOpenAI client for VectorStore tests."""
    mock_embedding = [0.1] * 1536
    mock_response = Mock()
    mock_response.data = [Mock(embedding=mock_embedding)]

    mock_client = Mock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    mocker.patch(
        "src.services.conversation.memory.vector_store.AsyncOpenAI",
        return_value=mock_client,
    )

    return mock_client


@pytest.fixture
def integration_ai_service() -> Mock:
    """Create a mock AI service for integration tests."""
    mock = Mock(spec=BaseAIService)
    mock.generate_response = AsyncMock(return_value="Test response")
    return mock
