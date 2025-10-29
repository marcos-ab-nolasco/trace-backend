"""EndClient model - represents final clients of architects."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.architect import Architect
    from src.db.models.briefing import Briefing
    from src.db.models.conversation import Conversation
    from src.db.models.organization import Organization
    from src.db.models.whatsapp_session import WhatsAppSession


class EndClient(Base):
    """EndClient model - final clients who receive briefing services."""

    __tablename__ = "end_clients"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    architect_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("architects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Unique constraint: phone number must be unique per organization (not per architect)
    __table_args__ = (UniqueConstraint("organization_id", "phone", name="uq_organization_phone"),)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="end_clients")
    architect: Mapped["Architect"] = relationship("Architect", back_populates="end_clients")
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="end_client", cascade="all, delete-orphan"
    )
    whatsapp_sessions: Mapped[list["WhatsAppSession"]] = relationship(
        "WhatsAppSession", back_populates="end_client", cascade="all, delete-orphan"
    )
    briefings: Mapped[list["Briefing"]] = relationship(
        "Briefing", back_populates="end_client", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EndClient(id={self.id}, name={self.name}, org={self.organization_id})>"
