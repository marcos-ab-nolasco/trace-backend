"""WhatsApp Account model for WhatsApp Business Cloud API integration."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.organization import Organization
    from src.db.models.organization_whatsapp_account import OrganizationWhatsAppAccount


class WhatsAppAccount(Base):
    """WhatsApp Business Account associated with an organization."""

    __tablename__ = "whatsapp_accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=func.gen_random_uuid())

    # WhatsApp Business API identifiers
    phone_number_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)

    # Authentication tokens
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    webhook_verify_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Optional metadata
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization_links: Mapped[list["OrganizationWhatsAppAccount"]] = relationship(
        "OrganizationWhatsAppAccount",
        back_populates="whatsapp_account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of WhatsAppAccount."""
        return f"<WhatsAppAccount(id={self.id}, phone_number={self.phone_number})>"
