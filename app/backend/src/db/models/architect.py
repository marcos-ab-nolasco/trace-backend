"""Architect model - represents architects within organizations."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.end_client import EndClient
    from src.db.models.organization import Organization
    from src.db.models.user import User


class Architect(Base):
    """Architect model - links User to Organization with additional architect-specific data."""

    __tablename__ = "architects"

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    is_authorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Unique constraint: one user can only be an architect once per organization
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_organization"),)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="architects")
    organization: Mapped["Organization"] = relationship("Organization", back_populates="architects")
    end_clients: Mapped[list["EndClient"]] = relationship(
        "EndClient", back_populates="architect", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Architect(id={self.id}, user_id={self.user_id}, organization_id={self.organization_id})>"
