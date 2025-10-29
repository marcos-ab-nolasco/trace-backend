"""Tests for WhatsApp models (Account, Message, Session) with N:N organization relationship."""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.architect import Architect
from src.db.models.end_client import EndClient
from src.db.models.organization import Organization
from src.db.models.organization_whatsapp_account import OrganizationWhatsAppAccount
from src.db.models.whatsapp_account import WhatsAppAccount
from src.db.models.whatsapp_message import MessageDirection, MessageStatus, WhatsAppMessage
from src.db.models.whatsapp_session import SessionStatus, WhatsAppSession


# WhatsAppAccount Tests with N:N Organization Relationship
@pytest.mark.asyncio
async def test_create_whatsapp_account(db_session: AsyncSession):
    """Test creating a WhatsApp account without organization (standalone)."""
    account = WhatsAppAccount(
        phone_number_id="phone123",
        phone_number="+5511999999999",
        access_token="token_secret",
        webhook_verify_token="verify_secret",
        is_active=True,
        is_global=False,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    assert account.id is not None
    assert account.phone_number_id == "phone123"
    assert account.phone_number == "+5511999999999"
    assert account.access_token == "token_secret"
    assert account.webhook_verify_token == "verify_secret"
    assert account.is_active is True
    assert account.is_global is False
    assert account.created_at is not None


@pytest.mark.asyncio
async def test_whatsapp_account_n_to_n_with_organizations(db_session: AsyncSession):
    """Test N:N relationship between WhatsApp account and organizations."""
    # Create two organizations
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    db_session.add_all([org1, org2])
    await db_session.commit()
    await db_session.refresh(org1)
    await db_session.refresh(org2)

    # Create WhatsApp account
    account = WhatsAppAccount(
        phone_number_id="phone123",
        phone_number="+5511999999999",
        access_token="token",
        is_global=False,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    # Link account to both organizations
    link1 = OrganizationWhatsAppAccount(
        organization_id=org1.id, whatsapp_account_id=account.id, is_primary=True
    )
    link2 = OrganizationWhatsAppAccount(
        organization_id=org2.id, whatsapp_account_id=account.id, is_primary=False
    )
    db_session.add_all([link1, link2])
    await db_session.commit()

    # Refresh and verify relationships with eager loading
    result = await db_session.execute(
        select(WhatsAppAccount)
        .where(WhatsAppAccount.id == account.id)
        .options(selectinload(WhatsAppAccount.organization_links).selectinload(OrganizationWhatsAppAccount.organization))
    )
    account = result.scalar_one()

    await db_session.refresh(org1, ["whatsapp_account_links"])
    await db_session.refresh(org2, ["whatsapp_account_links"])

    # One account can be shared by multiple organizations
    assert len(account.organization_links) == 2
    assert {link.organization.name for link in account.organization_links} == {"Org 1", "Org 2"}

    # Each organization sees the shared account
    assert len(org1.whatsapp_account_links) == 1
    assert len(org2.whatsapp_account_links) == 1


@pytest.mark.asyncio
async def test_whatsapp_account_unique_phone_number_id(db_session: AsyncSession):
    """Test phone_number_id is unique across all accounts."""
    account1 = WhatsAppAccount(
        phone_number_id="phone123", phone_number="+5511111111111", access_token="token1"
    )
    db_session.add(account1)
    await db_session.commit()

    # Try to create another account with same phone_number_id
    account2 = WhatsAppAccount(
        phone_number_id="phone123",  # Same ID
        phone_number="+5511222222222",
        access_token="token2",
    )
    db_session.add(account2)
    with pytest.raises(Exception):  # IntegrityError - unique constraint violation
        await db_session.commit()


@pytest.mark.asyncio
async def test_whatsapp_account_is_primary_flag(db_session: AsyncSession):
    """Test is_primary flag in organization-account relationship."""
    org = Organization(name="Primary Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    # Create two accounts
    account1 = WhatsAppAccount(
        phone_number_id="phone1", phone_number="+5511111111111", access_token="token1"
    )
    account2 = WhatsAppAccount(
        phone_number_id="phone2", phone_number="+5511222222222", access_token="token2"
    )
    db_session.add_all([account1, account2])
    await db_session.commit()
    await db_session.refresh(account1)
    await db_session.refresh(account2)

    # Link both with different is_primary flags
    link1 = OrganizationWhatsAppAccount(
        organization_id=org.id, whatsapp_account_id=account1.id, is_primary=True
    )
    link2 = OrganizationWhatsAppAccount(
        organization_id=org.id, whatsapp_account_id=account2.id, is_primary=False
    )
    db_session.add_all([link1, link2])
    await db_session.commit()

    # Query the links
    result = await db_session.execute(
        select(OrganizationWhatsAppAccount).where(
            OrganizationWhatsAppAccount.organization_id == org.id
        )
    )
    links = result.scalars().all()

    assert len(links) == 2
    primary_link = next(l for l in links if l.is_primary)
    secondary_link = next(l for l in links if not l.is_primary)

    assert primary_link.whatsapp_account_id == account1.id
    assert secondary_link.whatsapp_account_id == account2.id


@pytest.mark.asyncio
async def test_whatsapp_account_global_flag(db_session: AsyncSession):
    """Test global WhatsApp accounts can be shared across all organizations."""
    # Create global account
    global_account = WhatsAppAccount(
        phone_number_id="global_phone",
        phone_number="+5511999999999",
        access_token="global_token",
        is_global=True,  # Marked as global
    )
    db_session.add(global_account)
    await db_session.commit()
    await db_session.refresh(global_account)

    assert global_account.is_global is True

    # Link to multiple organizations
    org1 = Organization(name="Org 1")
    org2 = Organization(name="Org 2")
    org3 = Organization(name="Org 3")
    db_session.add_all([org1, org2, org3])
    await db_session.commit()

    for org in [org1, org2, org3]:
        await db_session.refresh(org)
        link = OrganizationWhatsAppAccount(
            organization_id=org.id, whatsapp_account_id=global_account.id, is_primary=False
        )
        db_session.add(link)

    await db_session.commit()

    # Verify global account is linked to all 3 orgs (with eager loading)
    result = await db_session.execute(
        select(WhatsAppAccount)
        .where(WhatsAppAccount.id == global_account.id)
        .options(selectinload(WhatsAppAccount.organization_links))
    )
    global_account = result.scalar_one()
    assert len(global_account.organization_links) == 3


@pytest.mark.asyncio
async def test_organization_deletion_removes_links_not_account(db_session: AsyncSession):
    """Test that deleting organization removes links but preserves account."""
    org = Organization(name="Delete Test Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    account = WhatsAppAccount(
        phone_number_id="phone123", phone_number="+5511999999999", access_token="token"
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    link = OrganizationWhatsAppAccount(
        organization_id=org.id, whatsapp_account_id=account.id, is_primary=True
    )
    db_session.add(link)
    await db_session.commit()
    link_id = link.id
    account_id = account.id

    # Delete organization
    await db_session.delete(org)
    await db_session.commit()

    # Verify link is deleted (CASCADE)
    result = await db_session.execute(
        select(OrganizationWhatsAppAccount).where(OrganizationWhatsAppAccount.id == link_id)
    )
    assert result.scalar_one_or_none() is None

    # Verify account still exists
    result = await db_session.execute(select(WhatsAppAccount).where(WhatsAppAccount.id == account_id))
    preserved_account = result.scalar_one_or_none()
    assert preserved_account is not None
    assert preserved_account.phone_number_id == "phone123"


# WhatsAppSession Tests
@pytest.mark.asyncio
async def test_create_whatsapp_session(db_session: AsyncSession):
    """Test creating a WhatsApp session with end client."""
    # Setup: Create org, architect, and end client
    org = Organization(name="Session Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="arch@test.com",
        hashed_password="hashed",
        phone="+5511888888888",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    client = EndClient(
        organization_id=org.id, architect_id=architect.id, name="Client Name", phone="+5511999999999"
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    # Create session
    session = WhatsAppSession(
        end_client_id=client.id,
        phone_number=client.phone,
        status=SessionStatus.ACTIVE.value,
        meta={"context": "briefing"},
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    assert session.id is not None
    assert session.end_client_id == client.id
    assert session.phone_number == "+5511999999999"
    assert session.status == SessionStatus.ACTIVE.value
    assert session.meta == {"context": "briefing"}
    assert session.created_at is not None


@pytest.mark.asyncio
async def test_whatsapp_session_cascade_on_client_delete(db_session: AsyncSession):
    """Test that deleting end client cascades to sessions."""
    # Setup
    org = Organization(name="Cascade Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="cascade@test.com",
        hashed_password="hashed",
        phone="+5511777777777",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    client = EndClient(
        organization_id=org.id, architect_id=architect.id, name="Delete Me", phone="+5511666666666"
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    session = WhatsAppSession(
        end_client_id=client.id, phone_number=client.phone, status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    session_id = session.id

    # Delete client
    await db_session.delete(client)
    await db_session.commit()

    # Verify session is also deleted (CASCADE)
    result = await db_session.execute(select(WhatsAppSession).where(WhatsAppSession.id == session_id))
    assert result.scalar_one_or_none() is None


# WhatsAppMessage Tests
@pytest.mark.asyncio
async def test_create_whatsapp_message(db_session: AsyncSession):
    """Test creating WhatsApp messages in a session."""
    # Setup session
    org = Organization(name="Message Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="msg@test.com",
        hashed_password="hashed",
        phone="+5511555555555",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    client = EndClient(
        organization_id=org.id, architect_id=architect.id, name="Msg Client", phone="+5511444444444"
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    session = WhatsAppSession(
        end_client_id=client.id, phone_number=client.phone, status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create message
    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.123456",
        direction=MessageDirection.INBOUND.value,
        content={"type": "text", "text": "Hello, I need help", "from": client.phone},
        status=MessageStatus.DELIVERED.value,
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)

    assert message.id is not None
    assert message.session_id == session.id
    assert message.wa_message_id == "wamid.123456"
    assert message.direction == MessageDirection.INBOUND.value
    assert message.content["text"] == "Hello, I need help"
    assert message.status == MessageStatus.DELIVERED.value


@pytest.mark.asyncio
async def test_whatsapp_message_cascade_on_session_delete(db_session: AsyncSession):
    """Test that deleting session cascades to messages."""
    # Setup
    org = Organization(name="Msg Cascade Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="msgcascade@test.com",
        hashed_password="hashed",
        phone="+5511333333333",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    client = EndClient(
        organization_id=org.id,
        architect_id=architect.id,
        name="Cascade Client",
        phone="+5511222222222",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    session = WhatsAppSession(
        end_client_id=client.id, phone_number=client.phone, status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    message = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.delete",
        direction=MessageDirection.OUTBOUND.value,
        content={"type": "text", "text": "Test message", "to": client.phone},
        status=MessageStatus.SENT.value,
    )
    db_session.add(message)
    await db_session.commit()
    message_id = message.id

    # Delete session
    await db_session.delete(session)
    await db_session.commit()

    # Verify message is also deleted (CASCADE)
    result = await db_session.execute(select(WhatsAppMessage).where(WhatsAppMessage.id == message_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_whatsapp_session_relationship_with_messages(db_session: AsyncSession):
    """Test session relationship with multiple messages."""
    # Setup
    org = Organization(name="Rel Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    architect = Architect(
        organization_id=org.id,
        email="rel@test.com",
        hashed_password="hashed",
        phone="+5511111111111",
    )
    db_session.add(architect)
    await db_session.commit()
    await db_session.refresh(architect)

    client = EndClient(
        organization_id=org.id, architect_id=architect.id, name="Rel Client", phone="+5511000000000"
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    session = WhatsAppSession(
        end_client_id=client.id, phone_number=client.phone, status=SessionStatus.ACTIVE.value
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    # Create multiple messages
    msg1 = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.1",
        direction=MessageDirection.INBOUND.value,
        content={"type": "text", "text": "Message 1", "from": client.phone},
        status=MessageStatus.DELIVERED.value,
    )
    msg2 = WhatsAppMessage(
        session_id=session.id,
        wa_message_id="wamid.2",
        direction=MessageDirection.OUTBOUND.value,
        content={"type": "text", "text": "Message 2", "to": client.phone},
        status=MessageStatus.SENT.value,
    )
    db_session.add_all([msg1, msg2])
    await db_session.commit()

    # Refresh and verify relationship
    await db_session.refresh(session, ["messages"])
    assert len(session.messages) == 2
    assert {msg.wa_message_id for msg in session.messages} == {"wamid.1", "wamid.2"}


@pytest.mark.asyncio
async def test_unique_constraint_org_whatsapp_account(db_session: AsyncSession):
    """Test unique constraint on organization-account pair."""
    org = Organization(name="Unique Constraint Org")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    account = WhatsAppAccount(
        phone_number_id="phone_unique", phone_number="+5511999999999", access_token="token"
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    # Create first link
    link1 = OrganizationWhatsAppAccount(
        organization_id=org.id, whatsapp_account_id=account.id, is_primary=True
    )
    db_session.add(link1)
    await db_session.commit()

    # Try to create duplicate link (same org + same account)
    link2 = OrganizationWhatsAppAccount(
        organization_id=org.id, whatsapp_account_id=account.id, is_primary=False
    )
    db_session.add(link2)
    with pytest.raises(Exception):  # IntegrityError - unique constraint
        await db_session.commit()
