"""Architect model - represents authenticated architects within organizations."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.briefing_template import BriefingTemplate
    from src.db.models.conversation import Conversation
    from src.db.models.end_client import EndClient
    from src.db.models.organization import Organization


class Architect(Base):
    """Architect model - primary authenticated actor tied to an organization."""

    __tablename__ = "architects"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    is_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="architects")
    end_clients: Mapped[list["EndClient"]] = relationship(
        "EndClient", back_populates="architect", cascade="all, delete-orphan"
    )
    created_templates: Mapped[list["BriefingTemplate"]] = relationship(
        "BriefingTemplate",
        back_populates="created_by",
        foreign_keys="BriefingTemplate.created_by_architect_id",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="architect", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Architect(id={self.id}, email={self.email}, organization_id={self.organization_id})>"
        )
