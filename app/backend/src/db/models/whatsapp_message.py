"""WhatsApp Message model for storing message history."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


class MessageDirection(str, Enum):
    """Enum for message direction."""

    INBOUND = "inbound"  # Message from end client to system
    OUTBOUND = "outbound"  # Message from system to end client


class MessageStatus(str, Enum):
    """Enum for message status (WhatsApp delivery status)."""

    RECEIVED = "received"  # Inbound message received
    SENT = "sent"  # Outbound message sent to WhatsApp
    DELIVERED = "delivered"  # Message delivered to recipient
    READ = "read"  # Message read by recipient
    FAILED = "failed"  # Message failed to send


class WhatsAppMessage(Base):
    """WhatsApp message in a conversation session."""

    __tablename__ = "whatsapp_messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=func.gen_random_uuid())
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("whatsapp_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # WhatsApp message identifier (from API)
    wa_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    # Message metadata
    direction: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Message content (JSONB to support different message types: text, image, document, etc.)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Error handling (for failed messages)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True  # WhatsApp message timestamp
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True  # When message was delivered
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True  # When message was read
    )

    # Relationships
    session: Mapped["WhatsAppSession"] = relationship("WhatsAppSession", back_populates="messages")  # type: ignore

    def __repr__(self) -> str:
        """String representation of WhatsAppMessage."""
        return f"<WhatsAppMessage(id={self.id}, wa_message_id={self.wa_message_id}, direction={self.direction})>"
