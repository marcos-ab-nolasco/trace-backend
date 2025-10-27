"""Organization model for multitenant architecture."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.architect import Architect
    from src.db.models.authorized_phone import AuthorizedPhone
    from src.db.models.briefing_template import BriefingTemplate
    from src.db.models.organization_whatsapp_account import OrganizationWhatsAppAccount
    from src.db.models.whatsapp_account import WhatsAppAccount


class Organization(Base):
    """Organization model - top level tenant entity."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    whatsapp_business_account_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    architects: Mapped[list["Architect"]] = relationship(
        "Architect", back_populates="organization", cascade="all, delete-orphan"
    )
    authorized_phones: Mapped[list["AuthorizedPhone"]] = relationship(
        "AuthorizedPhone", back_populates="organization", cascade="all, delete-orphan"
    )
    whatsapp_account_links: Mapped[list["OrganizationWhatsAppAccount"]] = relationship(
        "OrganizationWhatsAppAccount",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    templates: Mapped[list["BriefingTemplate"]] = relationship(
        "BriefingTemplate", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"
