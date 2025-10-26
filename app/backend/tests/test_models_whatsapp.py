"""Tests for WhatsApp models (Account, Message, Session)."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.architect import Architect
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.user import User
from src.db.models.whatsapp_account import WhatsAppAccount
from src.db.models.whatsapp_message import MessageDirection, MessageStatus, WhatsAppMessage
from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession


# WhatsAppAccount Tests
@pytest.mark.asyncio
async def test_create_whatsapp_account(db_session: AsyncSession):
    """Test creating a WhatsApp account."""
    org = Organization(name="Test Org", whatsapp_business_account_id="123456")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    account = WhatsAppAccount(
        organization_id=org.id,
        phone_number_id="phone123",
        phone_number="+5511999999999",
        access_token="token_secret",
        webhook_verify_token="verify_secret",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    assert account.id is not None
    assert account.organization_id == org.id
    assert account.phone_number_id == "phone123"
    assert account.phone_number == "+5511999999999"
    assert account.access_token == "token_secret"
    assert account.webhook_verify_token == "verify_secret"
    assert account.is_active is True
    assert account.created_at is not None


@pytest.mark.asyncio
async def test_whatsapp_account_relationship_with_organization(db_session: AsyncSession):
    """Test WhatsApp account relationship with organization."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    account = WhatsAppAccount(
        organization_id=org.id,
        phone_number_id="phone123",
        phone_number="+5511999999999",
        access_token="token",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account, ["organization"])

    assert account.organization.id == org.id
    assert account.organization.name == "Test Org"


@pytest.mark.asyncio
async def test_whatsapp_account_unique_phone_number_id(db_session: AsyncSession):
    """Test phone_number_id is unique across accounts."""
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add_all([org1, org2])
    await db_session.commit()
    await db_session.refresh(org1)
    await db_session.refresh(org2)

    account1 = WhatsAppAccount(
        organization_id=org1.id,
        phone_number_id="phone123",
        phone_number="+5511111111111",
        access_token="token1",
    )
    db_session.add(account1)
    await db_session.commit()

    # Try to create another account with same phone_number_id
    account2 = WhatsAppAccount(
        organization_id=org2.id,
        phone_number_id="phone123",  # Same phone_number_id
        phone_number="+5511222222222",
        access_token="token2",
    )
    db_session.add(account2)

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_whatsapp_account_cascade_on_organization_delete(db_session: AsyncSession):
    """Test WhatsApp account is deleted when organization is deleted."""
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    account = WhatsAppAccount(
        organization_id=org.id,
        phone_number_id="phone123",
        phone_number="+5511999999999",
        access_token="token",
    )
    db_session.add(account)
    await db_session.commit()

    account_id = account.id

    # Delete organization
    await db_session.delete(org)
    await db_session.commit()

    # Check account is deleted
    result = await db_session.execute(select(WhatsAppAccount).where(WhatsAppAccount.id == account_id))
    assert result.scalar_one_or_none() is None


# WhatsAppSession Tests
@pytest.mark.asyncio
async def test_create_whatsapp_session(db_session: AsyncSession):
    """Test creating a WhatsApp session."""
    # Create end client
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(
        architect_id=architect.id, name="Client", phone="+5511999999999", email="client@test.com"
    )
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    # Create session
    session = WhatsAppSession(
        end_client_id=end_client.id,
        phone_number="+5511999999999",
        status=SessionStatus.ACTIVE.value,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    assert session.id is not None
    assert session.end_client_id == end_client.id
    assert session.phone_number == "+5511999999999"
    assert session.status == SessionStatus.ACTIVE.value
    assert session.created_at is not None
    assert session.last_interaction_at is not None


@pytest.mark.asyncio
async def test_whatsapp_session_relationship_with_end_client(db_session: AsyncSession):
    """Test WhatsApp session relationship with end client."""
    # Create end client
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511999999999")
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    # Create session
    session = WhatsAppSession(
        end_client_id=end_client.id, phone_number="+5511999999999", status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session, ["end_client"])

    assert session.end_client.id == end_client.id
    assert session.end_client.name == "Client"


@pytest.mark.asyncio
async def test_whatsapp_session_status_enum(db_session: AsyncSession):
    """Test WhatsApp session status enum values."""
    # Verify enum values are strings
    assert SessionStatus.ACTIVE.value == "active"
    assert SessionStatus.CLOSED.value == "closed"
    assert SessionStatus.EXPIRED.value == "expired"


@pytest.mark.asyncio
async def test_whatsapp_session_cascade_on_end_client_delete(db_session: AsyncSession):
    """Test WhatsApp session is deleted when end client is deleted."""
    # Create end client
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511999999999")
    db_session.add(end_client)
    await db_session.commit()
    await db_session.refresh(end_client)

    # Create session
    session = WhatsAppSession(
        end_client_id=end_client.id, phone_number="+5511999999999", status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()

    session_id = session.id

    # Delete end client
    await db_session.delete(end_client)
    await db_session.commit()

    # Check session is deleted
    result = await db_session.execute(select(WhatsAppSession).where(WhatsAppSession.id == session_id))
    assert result.scalar_one_or_none() is None


# WhatsAppMessage Tests
@pytest.mark.asyncio
async def test_create_whatsapp_message(db_session: AsyncSession):
    """Test creating a WhatsApp message."""
    # Create session first
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511999999999")
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id, phone_number="+5511999999999", status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create message
    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.123456",
        direction=MessageDirection.INBOUND.value,
        status=MessageStatus.RECEIVED.value,
        content={"type": "text", "text": {"body": "Hello"}},
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)

    assert message.id is not None
    assert message.session_id == session.id
    assert message.wa_message_id == "wamid.123456"
    assert message.direction == MessageDirection.INBOUND.value
    assert message.status == MessageStatus.RECEIVED.value
    assert message.content["text"]["body"] == "Hello"
    assert message.created_at is not None


@pytest.mark.asyncio
async def test_whatsapp_message_relationship_with_session(db_session: AsyncSession):
    """Test WhatsApp message relationship with session."""
    # Create session
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511999999999")
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id, phone_number="+5511999999999", status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create message
    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.123",
        direction=MessageDirection.INBOUND.value,
        status=MessageStatus.RECEIVED.value,
        content={"type": "text", "text": {"body": "Hi"}},
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message, ["session"])

    assert message.session.id == session.id
    assert message.session.phone_number == "+5511999999999"


@pytest.mark.asyncio
async def test_whatsapp_message_direction_enum(db_session: AsyncSession):
    """Test WhatsApp message direction enum values."""
    assert MessageDirection.INBOUND.value == "inbound"
    assert MessageDirection.OUTBOUND.value == "outbound"


@pytest.mark.asyncio
async def test_whatsapp_message_status_enum(db_session: AsyncSession):
    """Test WhatsApp message status enum values."""
    assert MessageStatus.RECEIVED.value == "received"
    assert MessageStatus.SENT.value == "sent"
    assert MessageStatus.DELIVERED.value == "delivered"
    assert MessageStatus.READ.value == "read"
    assert MessageStatus.FAILED.value == "failed"


@pytest.mark.asyncio
async def test_whatsapp_message_cascade_on_session_delete(db_session: AsyncSession):
    """Test WhatsApp message is deleted when session is deleted."""
    # Create session
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511999999999")
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id, phone_number="+5511999999999", status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create message
    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.123",
        direction=MessageDirection.INBOUND.value,
        status=MessageStatus.RECEIVED.value,
        content={"type": "text", "text": {"body": "Hi"}},
    )
    db_session.add(message)
    await db_session.commit()

    message_id = message.id

    # Delete session
    await db_session.delete(session)
    await db_session.commit()

    # Check message is deleted
    result = await db_session.execute(select(WhatsAppMessage).where(WhatsAppMessage.id == message_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_whatsapp_message_unique_wa_message_id(db_session: AsyncSession):
    """Test wa_message_id is unique."""
    # Create session
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511999999999")
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id, phone_number="+5511999999999", status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create first message
    message1 = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.123",
        direction=MessageDirection.INBOUND.value,
        status=MessageStatus.RECEIVED.value,
        content={"type": "text", "text": {"body": "First"}},
    )
    db_session.add(message1)
    await db_session.commit()

    # Try to create another message with same wa_message_id
    message2 = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.123",  # Same ID
        direction=MessageDirection.INBOUND.value,
        status=MessageStatus.RECEIVED.value,
        content={"type": "text", "text": {"body": "Second"}},
    )
    db_session.add(message2)

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_whatsapp_message_optional_error_details(db_session: AsyncSession):
    """Test WhatsApp message can store error details."""
    # Create session
    org = Organization(name="Test Org")
    db_session.add(org)
    await db_session.flush()

    user = User(email="architect@test.com", hashed_password="hashed")
    db_session.add(user)
    await db_session.flush()

    architect = Architect(
        user_id=user.id, organization_id=org.id, phone="+5511888888888", is_authorized=True
    )
    db_session.add(architect)
    await db_session.flush()

    end_client = EndClient(architect_id=architect.id, name="Client", phone="+5511999999999")
    db_session.add(end_client)
    await db_session.flush()

    session = WhatsAppSession(
        end_client_id=end_client.id, phone_number="+5511999999999", status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create message with error
    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.failed",
        direction=MessageDirection.OUTBOUND.value,
        status=MessageStatus.FAILED.value,
        content={"type": "text", "text": {"body": "Failed message"}},
        error_code="131047",
        error_message="Message failed to send because more than 24h have passed since the customer last replied to this number",
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)

    assert message.status == MessageStatus.FAILED.value
    assert message.error_code == "131047"
    assert "24h have passed" in message.error_message
