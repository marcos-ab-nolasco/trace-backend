"""Pydantic schemas for briefing templates."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Question Schema (embedded in template version)
class QuestionSchema(BaseModel):
    """Schema for a single question in a template."""

    order: int = Field(..., ge=1, description="Question order (1-indexed)")
    question: str = Field(..., min_length=1, description="Question text")
    type: str = Field(..., description="Question type: text, number, multiple_choice")
    options: list[str] | None = Field(None, description="Options for multiple_choice questions")
    required: bool = Field(True, description="Whether question is required")
    validation: dict[str, Any] | None = Field(
        None, description="Validation rules (e.g., min, max for numbers)"
    )

    @field_validator("type")
    @classmethod
    def validate_question_type(cls, v: str) -> str:
        """Validate question type is one of allowed types."""
        allowed_types = {"text", "number", "multiple_choice"}
        if v not in allowed_types:
            raise ValueError(f"Question type must be one of {allowed_types}")
        return v

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[str] | None, info) -> list[str] | None:
        """Validate options are provided for multiple_choice questions."""
        question_type = info.data.get("type")
        if question_type == "multiple_choice" and (not v or len(v) < 2):
            raise ValueError("multiple_choice questions must have at least 2 options")
        return v


# Template Version Schemas
class TemplateVersionBase(BaseModel):
    """Base schema for template version."""

    questions: list[QuestionSchema] = Field(..., min_length=1)
    change_description: str | None = Field(None, max_length=500)


class TemplateVersionCreate(TemplateVersionBase):
    """Schema for creating a new template version."""

    pass


class TemplateVersionRead(TemplateVersionBase):
    """Schema for reading a template version."""

    id: UUID
    template_id: UUID
    version_number: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Briefing Template Schemas
class BriefingTemplateBase(BaseModel):
    """Base schema for briefing template."""

    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., description="Category: residencial, reforma, comercial, incorporacao")
    description: str | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate category is one of allowed categories."""
        allowed_categories = {"residencial", "reforma", "comercial", "incorporacao"}
        if v not in allowed_categories:
            raise ValueError(f"Category must be one of {allowed_categories}")
        return v


class BriefingTemplateCreate(BriefingTemplateBase):
    """Schema for creating a new template."""

    initial_version: TemplateVersionCreate = Field(
        ..., description="Initial version of the template"
    )


class BriefingTemplateUpdate(BaseModel):
    """Schema for updating a template (creates new version)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    questions: list[QuestionSchema] | None = Field(None, min_length=1)
    change_description: str | None = Field(None, max_length=500)


class BriefingTemplateRead(BriefingTemplateBase):
    """Schema for reading a template."""

    id: UUID
    is_global: bool
    architect_id: UUID | None
    current_version_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BriefingTemplateWithVersion(BriefingTemplateRead):
    """Schema for template with current version details."""

    current_version: TemplateVersionRead | None = None

    model_config = ConfigDict(from_attributes=True)


class BriefingTemplateList(BaseModel):
    """Schema for listing templates."""

    templates: list[BriefingTemplateWithVersion]
    total: int
