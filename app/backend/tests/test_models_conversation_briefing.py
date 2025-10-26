"""Tests for Conversation model extensions for briefing support."""

import pytest
from uuid import UUID
from datetime import datetime

from src.db.models.conversation import Conversation, ConversationType
from src.db.models.user import User
from src.db.models.organization import Organization
from src.db.models.architect import Architect
from src.db.models.end_client import EndClient


@pytest.mark.asyncio
async def test_create_web_chat_conversation(db_session):
    """Test creating a web chat conversation (original functionality)."""
    user = User(email="chat@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    conversation = Conversation(
        user_id=user.id,
        title="Test Chat",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WEB_CHAT,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert isinstance(conversation.id, UUID)
    assert conversation.user_id == user.id
    assert conversation.conversation_type == ConversationType.WEB_CHAT.value
    assert conversation.end_client_id is None
    assert conversation.briefing_id is None
    assert conversation.whatsapp_context is None


@pytest.mark.asyncio
async def test_create_whatsapp_briefing_conversation(db_session):
    """Test creating a WhatsApp briefing conversation."""
    # Setup user, org, architect, end_client
    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511111111111")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511222222222")
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    # Create WhatsApp briefing conversation
    conversation = Conversation(
        user_id=user.id,  # The architect user
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
    assert conversation.briefing_id is None  # Will be set when briefing starts
    assert conversation.whatsapp_context["session_id"] == "wa_session_123"


@pytest.mark.asyncio
async def test_conversation_relationship_with_end_client(db_session):
    """Test conversation relationship with end client."""
    user = User(email="rel@test.com", hashed_password="hashed")
    org = Organization(name="Rel Org")
    db_session.add_all([user, org])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(org)

    architect = Architect(user_id=user.id, organization_id=org.id, phone="+5511333333333")
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    end_client = EndClient(architect_id=architect.id, name="Test", phone="+5511444444444")
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    conversation = Conversation(
        user_id=user.id,
        title="Test Conversation",
        ai_provider="openai",
        ai_model="gpt-4",
        conversation_type=ConversationType.WHATSAPP_BRIEFING,
        end_client_id=end_client.id,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    # Test relationship
    assert conversation.end_client.id == end_client.id
    assert conversation.end_client.name == "Test"


@pytest.mark.asyncio
async def test_conversation_type_enum(db_session):
    """Test that conversation_type uses enum correctly."""
    user = User(email="enum@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Test WEB_CHAT type
    conv1 = Conversation(
        user_id=user.id,
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
    user = User(email="default@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    conversation = Conversation(
        user_id=user.id, title="Default Type", ai_provider="openai", ai_model="gpt-4"
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)

    assert conversation.conversation_type == ConversationType.WEB_CHAT.value
