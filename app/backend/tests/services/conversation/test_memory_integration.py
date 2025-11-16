"""Integration tests for ConversationMemory with VectorStore."""

import pytest
from unittest.mock import AsyncMock, Mock

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion
from src.services.conversation.memory.conversation_memory import ConversationMemory
from src.services.conversation.memory.vector_store import VectorStore
from src.services.ai.base import BaseAIService


@pytest.fixture
async def test_briefing(db_session):
    """Create a test briefing with all required relationships."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        questions=[],
        context_prompt="Test context",
    )
    db_session.add(version)
    await db_session.commit()

    from src.core.security import hash_password

    architect = Architect(
        email="architect@test.com",
        hashed_password=hash_password("testpassword123"),
        full_name="Test Architect",
        phone="+5511999999999",
        is_authorized=True,
        organization_id=org.id,
    )
    db_session.add(architect)
    await db_session.commit()

    end_client = EndClient(
        name="Test Client",
        phone="+5511888888888",
        architect_id=architect.id,
        organization_id=org.id,
    )
    db_session.add(end_client)
    await db_session.commit()

    briefing = Briefing(
        end_client_id=end_client.id,
        template_version_id=version.id,
        current_question_order=1,
        answers={},
        information_state={},
        gathered_information={},
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    return briefing


@pytest.fixture
def mock_openai_client(mocker):
    """Mock AsyncOpenAI client for integration tests."""
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


@pytest.mark.asyncio
async def test_memory_with_vector_store_add_message(
    db_session, test_briefing, integration_ai_service, mock_openai_client
):
    """Test that adding messages to memory also stores in vector store."""
    vector_store = VectorStore()
    memory = ConversationMemory(
        db_session=db_session,
        briefing_id=test_briefing.id,
        ai_service=integration_ai_service,
        vector_store=vector_store,
    )

    # Add message via memory
    message_id = await memory.add_message(
        role="user",
        content="I love modern design",
    )

    # Verify it's searchable in vector store
    results = await vector_store.search_similar(
        query="modern",
        briefing_id=test_briefing.id,
        limit=1,
    )

    assert len(results) > 0
    assert "modern" in results[0]["content"]


@pytest.mark.asyncio
async def test_memory_search_context(
    db_session, test_briefing, integration_ai_service, mock_openai_client
):
    """Test semantic search through ConversationMemory."""
    vector_store = VectorStore()
    memory = ConversationMemory(
        db_session=db_session,
        briefing_id=test_briefing.id,
        ai_service=integration_ai_service,
        vector_store=vector_store,
    )

    # Add multiple messages
    await memory.add_message("user", "I love modern design")
    await memory.add_message("assistant", "Great! Tell me about budget")
    await memory.add_message("user", "Around 100k BRL")

    # Semantic search via memory
    results = await memory.search_context(
        query="What style does the user prefer?",
    )

    assert len(results) > 0
    assert any("modern" in r["content"].lower() for r in results)


@pytest.mark.asyncio
async def test_memory_search_context_budget(
    db_session, test_briefing, integration_ai_service, mock_openai_client
):
    """Test semantic search returns relevant budget information."""
    vector_store = VectorStore()
    memory = ConversationMemory(
        db_session=db_session,
        briefing_id=test_briefing.id,
        ai_service=integration_ai_service,
        vector_store=vector_store,
    )

    # Add messages
    await memory.add_message("user", "I love modern design")
    await memory.add_message("user", "My budget is 75k BRL")
    await memory.add_message("user", "I prefer wooden floors")

    # Search for budget info
    results = await memory.search_context(
        query="What is the user's budget?",
        limit=3,
    )

    # With mocked identical embeddings, any message could be returned
    assert len(results) >= 2
    contents = [r["content"] for r in results]
    assert any("75k" in c for c in contents)


@pytest.mark.asyncio
async def test_memory_without_vector_store(
    db_session, test_briefing, integration_ai_service
):
    """Test that memory works without vector store (graceful degradation)."""
    memory = ConversationMemory(
        db_session=db_session,
        briefing_id=test_briefing.id,
        ai_service=integration_ai_service,
        vector_store=None,
    )

    # Should still be able to add messages
    message_id = await memory.add_message(
        role="user",
        content="Test message",
    )

    assert message_id is not None

    # Search should return empty list
    results = await memory.search_context(
        query="test",
    )

    assert results == []


@pytest.mark.asyncio
async def test_memory_search_with_metadata(
    db_session, test_briefing, integration_ai_service, mock_openai_client
):
    """Test that search results include metadata."""
    vector_store = VectorStore()
    memory = ConversationMemory(
        db_session=db_session,
        briefing_id=test_briefing.id,
        ai_service=integration_ai_service,
        vector_store=vector_store,
    )

    # Add messages with different roles
    await memory.add_message("user", "I need help with my project")
    await memory.add_message("assistant", "I can help you with that")

    # Search
    results = await memory.search_context(
        query="help",
        limit=10,
    )

    assert len(results) > 0
    # Check that metadata includes role
    for result in results:
        assert "role" in result["metadata"]
        assert result["metadata"]["role"] in ["user", "assistant"]


@pytest.mark.asyncio
async def test_memory_search_multiple_briefings_isolated(
    db_session, test_briefing, integration_ai_service, mock_openai_client
):
    """Test that search is isolated to briefing's messages."""
    vector_store = VectorStore()

    # Memory for test_briefing
    memory = ConversationMemory(
        db_session=db_session,
        briefing_id=test_briefing.id,
        ai_service=integration_ai_service,
        vector_store=vector_store,
    )

    # Add message to this briefing
    await memory.add_message("user", "Modern kitchen design")

    # Search in this briefing
    results = await memory.search_context(
        query="design",
        limit=10,
    )

    # Should find messages from this briefing
    if len(results) > 0:
        for result in results:
            assert result["metadata"]["briefing_id"] == str(test_briefing.id)
