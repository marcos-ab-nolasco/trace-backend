"""Pydantic schemas for AuthorizedPhone."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AuthorizedPhoneCreate(BaseModel):
    """Schema for creating an authorized phone."""

    phone_number: str = Field(..., description="Phone number in international format (e.g., +5511987654321)")


class AuthorizedPhoneRead(BaseModel):
    """Schema for reading an authorized phone."""

    id: UUID
    organization_id: UUID
    phone_number: str
    added_by_architect_id: UUID | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AuthorizedPhoneList(BaseModel):
    """Schema for listing authorized phones."""

    phones: list[AuthorizedPhoneRead]
    total: int
