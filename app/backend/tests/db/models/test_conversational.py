"""Tests for conversational AI database models.

This module tests the new models and modifications required for the
information-based conversational briefing system.
"""

from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from src.db.models.architect import Architect
from src.db.models.briefing import Briefing
from src.db.models.briefing_template import BriefingTemplate
from src.db.models.conversation_message import ConversationMessage
from src.db.models.end_client import EndClient
from src.db.models.information_requirement import InformationRequirement
from src.db.models.organization import Organization
from src.db.models.template_version import TemplateVersion

# ==================== InformationRequirement Model Tests ====================


@pytest.mark.asyncio
async def test_create_information_requirement(db_session):
    """Test creating an information requirement."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    requirement = InformationRequirement(
        template_id=version.id,
        field_name="budget",
        field_type="number",
        required=True,
        priority=8,
        description="Total project budget in BRL",
        validation_rules={"min": 0, "unit": "BRL"},
        suggested_questions=["What is your budget?", "How much can you invest?"],
    )
    db_session.add(requirement)
    await db_session.commit()
    await db_session.refresh(requirement)

    assert isinstance(requirement.id, UUID)
    assert requirement.field_name == "budget"
    assert requirement.field_type == "number"
    assert requirement.required is True
    assert requirement.priority == 8
    assert requirement.description == "Total project budget in BRL"
    assert requirement.validation_rules == {"min": 0, "unit": "BRL"}
    assert len(requirement.suggested_questions) == 2
    assert isinstance(requirement.created_at, datetime)


@pytest.mark.asyncio
async def test_information_requirement_template_relationship(db_session):
    """Test InformationRequirement relationship with TemplateVersion."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    # Create multiple requirements
    req1 = InformationRequirement(
        template_id=version.id,
        field_name="budget",
        field_type="number",
        description="Budget",
    )
    req2 = InformationRequirement(
        template_id=version.id,
        field_name="timeline",
        field_type="text",
        description="Timeline",
    )
    db_session.add_all([req1, req2])
    await db_session.commit()

    # Reload version with requirements relationship
    await db_session.refresh(version, ["requirements"])

    # Test relationship
    assert len(version.requirements) == 2
    assert version.requirements[0].field_name in ["budget", "timeline"]
    assert version.requirements[1].field_name in ["budget", "timeline"]
    assert version.requirements[0].template_id == version.id


@pytest.mark.asyncio
async def test_information_requirement_optional_fields(db_session):
    """Test InformationRequirement with minimal fields (optional fields)."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()

    # Create with minimal fields
    requirement = InformationRequirement(
        template_id=version.id,
        field_name="optional_field",
        field_type="text",
    )
    db_session.add(requirement)
    await db_session.commit()
    await db_session.refresh(requirement)

    assert requirement.required is True  # Default value
    assert requirement.priority == 5  # Default value
    assert requirement.validation_rules == {}  # Default empty dict
    assert requirement.suggested_questions == []  # Default empty list


# ==================== ConversationMessage Model Tests ====================


@pytest.mark.asyncio
async def test_create_conversation_message(db_session):
    """Test creating a conversation message."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        phone="+5511888888888",
        name="Test Client",
    )
    db_session.add(client)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()

    briefing = Briefing(
        end_client_id=client.id,
        template_version_id=version.id,
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    # Create conversation message
    message = ConversationMessage(
        briefing_id=briefing.id,
        role="user",
        content="I need help with my project",
        extracted_info={"topic": "project_help"},
        ai_metadata={"confidence": 0.95, "intent": "request_assistance"},
        embedding_id="emb_12345",
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)

    assert isinstance(message.id, UUID)
    assert message.briefing_id == briefing.id
    assert message.role == "user"
    assert message.content == "I need help with my project"
    assert message.extracted_info == {"topic": "project_help"}
    assert message.ai_metadata["confidence"] == 0.95
    assert message.embedding_id == "emb_12345"
    assert isinstance(message.timestamp, datetime)


@pytest.mark.asyncio
async def test_conversation_message_briefing_relationship(db_session):
    """Test ConversationMessage relationship with Briefing."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        phone="+5511888888888",
        name="Test Client",
    )
    db_session.add(client)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()

    briefing = Briefing(
        end_client_id=client.id,
        template_version_id=version.id,
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    # Create multiple messages
    msg1 = ConversationMessage(briefing_id=briefing.id, role="user", content="Hello")
    msg2 = ConversationMessage(
        briefing_id=briefing.id, role="assistant", content="Hi! How can I help?"
    )
    msg3 = ConversationMessage(briefing_id=briefing.id, role="user", content="I need information")
    db_session.add_all([msg1, msg2, msg3])
    await db_session.commit()

    # Reload briefing with conversation_messages relationship
    await db_session.refresh(briefing, ["conversation_messages"])

    # Test relationship
    assert len(briefing.conversation_messages) == 3
    assert briefing.conversation_messages[0].role == "user"
    assert briefing.conversation_messages[1].role == "assistant"
    assert briefing.conversation_messages[2].role == "user"


@pytest.mark.asyncio
async def test_conversation_message_cascade_delete(db_session):
    """Test that conversation messages are deleted when briefing is deleted."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        phone="+5511888888888",
        name="Test Client",
    )
    db_session.add(client)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()

    briefing = Briefing(
        end_client_id=client.id,
        template_version_id=version.id,
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    # Create messages
    msg1 = ConversationMessage(briefing_id=briefing.id, role="user", content="Test 1")
    msg2 = ConversationMessage(briefing_id=briefing.id, role="assistant", content="Test 2")
    db_session.add_all([msg1, msg2])
    await db_session.commit()

    briefing_id = briefing.id

    # Delete briefing
    await db_session.delete(briefing)
    await db_session.commit()

    # Verify messages are deleted (cascade)
    result = await db_session.execute(
        select(ConversationMessage).where(ConversationMessage.briefing_id == briefing_id)
    )
    messages = result.scalars().all()
    assert len(messages) == 0


# ==================== Modified Briefing Model Tests ====================


@pytest.mark.asyncio
async def test_briefing_with_information_state(db_session):
    """Test Briefing model with new information_state field."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        phone="+5511888888888",
        name="Test Client",
    )
    db_session.add(client)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()

    # Create briefing with information_state
    briefing = Briefing(
        end_client_id=client.id,
        template_version_id=version.id,
        information_state={
            "budget": "collected",
            "timeline": "pending",
            "style": "inferred",
        },
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    assert briefing.information_state == {
        "budget": "collected",
        "timeline": "pending",
        "style": "inferred",
    }


@pytest.mark.asyncio
async def test_briefing_with_gathered_information(db_session):
    """Test Briefing model with new gathered_information field."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        phone="+5511888888888",
        name="Test Client",
    )
    db_session.add(client)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()

    # Create briefing with gathered_information
    briefing = Briefing(
        end_client_id=client.id,
        template_version_id=version.id,
        gathered_information={
            "budget": {
                "value": "100000",
                "confidence": 0.95,
                "source_message_id": "msg_123",
            },
            "timeline": {
                "value": "3 months",
                "confidence": 0.80,
                "source_message_id": "msg_456",
            },
        },
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    assert briefing.gathered_information["budget"]["value"] == "100000"
    assert briefing.gathered_information["budget"]["confidence"] == 0.95
    assert briefing.gathered_information["timeline"]["value"] == "3 months"


@pytest.mark.asyncio
async def test_briefing_with_conversation_summary(db_session):
    """Test Briefing model with new conversation_summary field."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        phone="+5511888888888",
        name="Test Client",
    )
    db_session.add(client)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(template_id=template.id, version_number=1)
    db_session.add(version)
    await db_session.commit()

    # Create briefing with conversation_summary
    briefing = Briefing(
        end_client_id=client.id,
        template_version_id=version.id,
        conversation_summary="Client wants a modern residential project with a budget of 100k.",
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    assert (
        briefing.conversation_summary
        == "Client wants a modern residential project with a budget of 100k."
    )


# ==================== Modified TemplateVersion Model Tests ====================


@pytest.mark.asyncio
async def test_template_version_with_context_prompt(db_session):
    """Test TemplateVersion with new context_prompt field."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    template = BriefingTemplate(name="Test Template", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        context_prompt="You are gathering information for a residential renovation project. Be friendly and professional.",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    assert (
        version.context_prompt
        == "You are gathering information for a residential renovation project. Be friendly and professional."
    )


# ==================== Integration Tests ====================


@pytest.mark.asyncio
async def test_full_conversational_workflow(db_session):
    """Test complete conversational briefing workflow with all new models."""
    # Setup organization and users
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511999999999",
    )
    db_session.add(architect)
    await db_session.commit()

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        phone="+5511888888888",
        name="Test Client",
    )
    db_session.add(client)
    await db_session.commit()

    # Setup template with requirements
    template = BriefingTemplate(name="Residential Project", is_global=False, organization_id=org.id)
    db_session.add(template)
    await db_session.commit()

    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        context_prompt="Gather information for residential projects.",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(version)

    # Create information requirements
    req1 = InformationRequirement(
        template_id=version.id,
        field_name="budget",
        field_type="number",
        priority=10,
        description="Project budget",
    )
    req2 = InformationRequirement(
        template_id=version.id,
        field_name="timeline",
        field_type="text",
        priority=8,
        description="Project timeline",
    )
    db_session.add_all([req1, req2])
    await db_session.commit()

    # Create briefing with new fields
    briefing = Briefing(
        end_client_id=client.id,
        template_version_id=version.id,
        information_state={"budget": "pending", "timeline": "pending"},
        gathered_information={},
    )
    db_session.add(briefing)
    await db_session.commit()
    await db_session.refresh(briefing)

    # Simulate conversation
    msg1 = ConversationMessage(
        briefing_id=briefing.id,
        role="assistant",
        content="Hi! What's your budget for this project?",
    )
    msg2 = ConversationMessage(
        briefing_id=briefing.id,
        role="user",
        content="I have around 150 thousand reais",
        extracted_info={"budget": "150000"},
        ai_metadata={"confidence": 0.92},
    )
    msg3 = ConversationMessage(
        briefing_id=briefing.id,
        role="assistant",
        content="Great! And what's your timeline?",
    )
    db_session.add_all([msg1, msg2, msg3])
    await db_session.commit()

    # Update briefing state
    briefing.information_state = {"budget": "collected", "timeline": "pending"}
    briefing.gathered_information = {
        "budget": {"value": "150000", "confidence": 0.92, "source_message_id": str(msg2.id)}
    }
    await db_session.commit()

    # Reload relationships
    await db_session.refresh(version, ["requirements"])
    await db_session.refresh(briefing, ["conversation_messages"])

    # Verify complete workflow
    assert len(version.requirements) == 2
    assert len(briefing.conversation_messages) == 3
    assert briefing.information_state["budget"] == "collected"
    assert briefing.gathered_information["budget"]["value"] == "150000"
    assert version.context_prompt == "Gather information for residential projects."
