"""WhatsApp Session model for managing conversation sessions with end clients."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.briefing import Briefing


class SessionStatus(str, Enum):
    """Enum for WhatsApp session status."""

    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class WhatsAppSession(Base):
    """WhatsApp conversation session with an end client."""

    __tablename__ = "whatsapp_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=func.gen_random_uuid())
    end_client_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("end_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    briefing_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("briefings.id", ondelete="SET NULL"), nullable=True, index=True
    )

    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=SessionStatus.ACTIVE.value
    )

    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    end_client: Mapped["EndClient"] = relationship("EndClient", back_populates="whatsapp_sessions")
    briefing: Mapped["Briefing | None"] = relationship(
        "Briefing", back_populates="whatsapp_sessions"
    )
    messages: Mapped[list["WhatsAppMessage"]] = relationship(
        "WhatsAppMessage", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of WhatsAppSession."""
        return f"<WhatsAppSession(id={self.id}, phone_number={self.phone_number}, status={self.status})>"
