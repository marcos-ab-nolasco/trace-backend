from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ArchitectBase(BaseModel):
    """Base schema shared across architect operations."""

    email: EmailStr
    full_name: str | None = None
    phone: str = Field(..., min_length=8, max_length=20)


class ArchitectCreate(ArchitectBase):
    """Schema for signing up a new architect and organization."""

    password: str = Field(..., min_length=8, max_length=100)
    organization_name: str = Field(..., min_length=2, max_length=255)


class ArchitectRead(ArchitectBase):
    """Schema for returning architect information."""

    id: UUID
    organization_id: UUID
    is_authorized: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
