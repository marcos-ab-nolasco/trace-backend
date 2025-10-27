"""AuthorizedPhone model for phone number authorization."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base

if TYPE_CHECKING:
    from src.db.models.architect import Architect
    from src.db.models.organization import Organization


class AuthorizedPhone(Base):
    """AuthorizedPhone model - tracks phone numbers authorized to initiate briefings."""

    __tablename__ = "authorized_phones"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "phone_number", name="uq_organization_phone_number"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid(), index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    added_by_architect_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("architects.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="authorized_phones"
    )
    added_by: Mapped["Architect | None"] = relationship("Architect", foreign_keys=[added_by_architect_id])

    def __repr__(self) -> str:
        return f"<AuthorizedPhone(id={self.id}, phone={self.phone_number}, org={self.organization_id})>"
