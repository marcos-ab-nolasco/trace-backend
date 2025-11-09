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

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    """Enum for message status (WhatsApp delivery status)."""

    RECEIVED = "received"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class WhatsAppMessage(Base):
    """WhatsApp message in a conversation session."""

    __tablename__ = "whatsapp_messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=func.gen_random_uuid())
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("whatsapp_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    wa_message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    direction: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["WhatsAppSession"] = relationship("WhatsAppSession", back_populates="messages")

    def __repr__(self) -> str:
        """String representation of WhatsAppMessage."""
        return f"<WhatsAppMessage(id={self.id}, wa_message_id={self.wa_message_id}, direction={self.direction})>"
