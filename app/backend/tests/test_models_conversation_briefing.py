"""Tests for Conversation model extensions for briefing support."""

from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.architect import Architect
from src.db.models.conversation import Conversation, ConversationType
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization


@pytest.mark.asyncio
async def test_create_web_chat_conversation(db_session):
    """Test creating a web chat conversation (original functionality)."""
    org = Organization(name="Chat Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="chat@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    conversation = Conversation(
        architect_id=architect.id,
        title="Test Chat",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WEB_CHAT,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert isinstance(conversation.id, UUID)
    assert conversation.architect_id == architect.id
    assert conversation.conversation_type == ConversationType.WEB_CHAT.value
    assert conversation.end_client_id is None
    assert conversation.whatsapp_context is None


@pytest.mark.asyncio
async def test_create_whatsapp_briefing_conversation(db_session):
    """Test creating a WhatsApp briefing conversation."""
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

    end_client = EndClient(
        organization_id=org.id, architect_id=architect.id, name="Client", phone="+5511222222222"
    )
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    conversation = Conversation(
        architect_id=architect.id,
        title="Briefing: Client",
        ai_provider="anthropic",
        ai_model="claude-3",
        conversation_type=ConversationType.WHATSAPP_BRIEFING,
        end_client_id=end_client.id,
        whatsapp_context={
            "session_id": "wa_session_123",
            "phone_number": "+5511222222222",
            "status": "active",
        },
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert conversation.conversation_type == ConversationType.WHATSAPP_BRIEFING.value
    assert conversation.end_client_id == end_client.id
    assert conversation.whatsapp_context["session_id"] == "wa_session_123"


@pytest.mark.asyncio
async def test_conversation_relationship_with_end_client(db_session):
    """Test conversation relationship with end client."""
    org = Organization(name="Rel Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="rel@test.com",
        hashed_password="hashed",
        phone="+5511333333333",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(
        organization_id=org.id, architect_id=architect.id, name="Test", phone="+5511444444444"
    )
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    conversation = Conversation(
        architect_id=architect.id,
        title="Test Conversation",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WHATSAPP_BRIEFING,
        end_client_id=end_client.id,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert conversation.end_client.id == end_client.id
    assert conversation.end_client.name == "Test"


@pytest.mark.asyncio
async def test_conversation_relationship_with_architect(db_session):
    """Test conversation relationship with architect."""
    org = Organization(name="Architect Rel Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="archrel@test.com",
        hashed_password="hashed",
        phone="+5511555555555",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    conversation = Conversation(
        architect_id=architect.id,
        title="Architect Conversation",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WEB_CHAT,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert conversation.architect.id == architect.id
    assert conversation.architect.email == "archrel@test.com"


@pytest.mark.asyncio
async def test_conversation_type_enum(db_session):
    """Test that conversation_type uses enum correctly."""
    org = Organization(name="Enum Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="enum@test.com",
        hashed_password="hashed",
        phone="+5511666666666",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    conv1 = Conversation(
        architect_id=architect.id,
        title="Web Chat",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WEB_CHAT,
    )
    db_session.add(conv1)
    await db_session.commit()
    await db_session.refresh(conv1)

    assert conv1.conversation_type == ConversationType.WEB_CHAT.value
    assert conv1.conversation_type == "web_chat"


@pytest.mark.asyncio
async def test_conversation_default_type_is_web_chat(db_session):
    """Test that conversation_type defaults to WEB_CHAT."""
    org = Organization(name="Default Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="default@test.com",
        hashed_password="hashed",
        phone="+5511777777777",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    conversation = Conversation(
        architect_id=architect.id, title="Default Type", ai_provider="openai", ai_model="gpt-4"
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert conversation.conversation_type == ConversationType.WEB_CHAT.value


@pytest.mark.asyncio
async def test_conversation_cascade_on_architect_delete(db_session):
    """Test that conversation is deleted when architect is deleted (CASCADE)."""
    org = Organization(name="Cascade Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="cascade@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    conversation = Conversation(
        architect_id=architect.id,
        title="Will be deleted",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WEB_CHAT,
    )
    db_session.add(conversation)
    await db_session.commit()
    conversation_id = conversation.id

    await db_session.delete(architect)
    await db_session.commit()

    result = await db_session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_conversation_set_null_on_architect_delete_if_needed(db_session):
    """Test conversation.architect_id can be NULL (SET NULL behavior)."""
    org = Organization(name="Set Null Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    conversation = Conversation(
        architect_id=None,
        title="System Conversation",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WEB_CHAT,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert conversation.architect_id is None
    assert conversation.architect is None
