"""Pydantic schemas for information requirements."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InformationRequirementBase(BaseModel):
    """Base schema for information requirement."""

    field_name: str = Field(
        ..., min_length=1, max_length=100, description="Field name (e.g., 'budget', 'timeline')"
    )
    field_type: str = Field(..., description="Field type: text, number, date, boolean")
    required: bool = Field(default=True, description="Whether this field is required")
    priority: int = Field(
        default=5, ge=1, le=10, description="Priority (1-10) for AI decision agent"
    )
    description: str | None = Field(None, description="What this field represents")
    validation_rules: dict = Field(
        default_factory=dict, description="Validation rules (e.g., {'min': 0, 'unit': 'BRL'})"
    )
    suggested_questions: list[str] = Field(
        default_factory=list, description="Example phrasings for AI"
    )


class InformationRequirementCreate(InformationRequirementBase):
    """Schema for creating a new information requirement."""

    pass


class InformationRequirementRead(InformationRequirementBase):
    """Schema for reading an information requirement."""

    id: UUID
    template_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InformationRequirementUpdate(BaseModel):
    """Schema for updating an information requirement."""

    field_name: str | None = Field(None, min_length=1, max_length=100)
    field_type: str | None = None
    required: bool | None = None
    priority: int | None = Field(None, ge=1, le=10)
    description: str | None = None
    validation_rules: dict | None = None
    suggested_questions: list[str] | None = None
