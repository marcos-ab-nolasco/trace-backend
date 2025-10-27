"""Association table linking organizations to WhatsApp accounts."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.organization import Organization
    from src.db.models.whatsapp_account import WhatsAppAccount


class OrganizationWhatsAppAccount(Base):
    """Link between organizations and WhatsApp accounts."""

    __tablename__ = "organization_whatsapp_accounts"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    whatsapp_account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("whatsapp_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "whatsapp_account_id",
            name="uq_organization_whatsapp_account",
        ),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="whatsapp_account_links"
    )
    whatsapp_account: Mapped["WhatsAppAccount"] = relationship(
        "WhatsAppAccount", back_populates="organization_links"
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationWhatsAppAccount(organization_id={self.organization_id}, "
            f"whatsapp_account_id={self.whatsapp_account_id}, is_primary={self.is_primary})>"
        )
