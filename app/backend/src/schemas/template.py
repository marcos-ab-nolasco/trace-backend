"""Pydantic schemas for briefing templates."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.schemas.information_requirement import (
    InformationRequirementCreate,
    InformationRequirementRead,
)

if TYPE_CHECKING:
    from src.db.models.briefing_template import BriefingTemplate
    from src.db.models.template_version import TemplateVersion


class TemplateVersionBase(BaseModel):
    """Base schema for template version."""

    change_description: str | None = Field(None, max_length=500)


class TemplateVersionCreate(TemplateVersionBase):
    """Schema for creating a new template version."""

    requirements: list[InformationRequirementCreate] = Field(
        default_factory=list, description="Information requirements for this template"
    )


class TemplateVersionRead(TemplateVersionBase):
    """Schema for reading a template version."""

    id: UUID
    template_id: UUID
    version_number: int
    is_active: bool
    created_at: datetime
    requirements: list[InformationRequirementRead] = Field(
        default_factory=list, description="Information requirements for this template"
    )

    model_config = ConfigDict(from_attributes=True)


class BriefingTemplateBase(BaseModel):
    """Base schema for briefing template."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    project_type_slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("project_type_slug", "category"),
        serialization_alias="project_type_slug",
        description="Slug do tipo de projeto (ex.: reforma, residencial).",
    )
    description: str | None = None


class BriefingTemplateCreate(BriefingTemplateBase):
    """Schema for creating a new template."""

    initial_version: TemplateVersionCreate = Field(
        ..., description="Initial version of the template"
    )


class BriefingTemplateUpdate(BaseModel):
    """Schema for updating a template (creates new version)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    requirements: list[InformationRequirementCreate] | None = Field(
        None, description="Information requirements for this template"
    )
    change_description: str | None = Field(None, max_length=500)
    project_type_slug: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("project_type_slug", "category"),
        serialization_alias="project_type_slug",
    )


class BriefingTemplateRead(BriefingTemplateBase):
    """Schema for reading a template."""

    id: UUID
    is_global: bool
    category: str | None = Field(None, description="Legacy category field")
    organization_id: UUID | None
    created_by_architect_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BriefingTemplateWithVersion(BaseModel):
    """Schema for template with current version details.

    Note: current_version is computed from versions relationship by filtering for is_current=True.
    The TemplateService should ensure versions are loaded via selectinload.
    """

    id: UUID
    name: str
    project_type_slug: str | None
    description: str | None
    is_global: bool
    category: str | None
    organization_id: UUID | None
    created_by_architect_id: UUID | None
    created_at: datetime
    updated_at: datetime
    current_version: TemplateVersionRead | None = Field(
        None, description="Current version (computed from versions where is_current=True)"
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_model(cls, obj: "BriefingTemplate") -> "BriefingTemplateWithVersion":
        """Create instance from ORM model, computing current_version from versions."""
        project_type_slug = obj.project_type.slug if obj.project_type else None

        current_version_model: TemplateVersion | None = (
            next((v for v in obj.versions if v.is_current), None) if obj.versions else None
        )
        current_version = (
            TemplateVersionRead.model_validate(current_version_model)
            if current_version_model
            else None
        )

        return cls(
            id=obj.id,
            name=obj.name,
            project_type_slug=project_type_slug,
            description=obj.description,
            is_global=obj.is_global,
            category=obj.category,
            organization_id=obj.organization_id,
            created_by_architect_id=obj.created_by_architect_id,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            current_version=current_version,
        )


class BriefingTemplateList(BaseModel):
    """Schema for listing templates."""

    templates: list[BriefingTemplateWithVersion]
    total: int
