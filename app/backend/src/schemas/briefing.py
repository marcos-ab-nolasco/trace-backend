"""Pydantic schemas for briefing extraction and management."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractedClientInfo(BaseModel):
    """Schema for client information extracted from architect messages."""

    name: str | None = Field(None, description="Client's full name")
    phone: str | None = Field(None, description="Client's phone number")
    project_type: str | None = Field(
        None,
        description="Type of project (reforma, construcao, residencial, comercial, incorporacao)",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    raw_text: str = Field(..., description="Original message text")

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v: str | None) -> str | None:
        """Validate phone is not empty string."""
        if v is not None and v.strip() == "":
            return None
        return v

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v: str | None) -> str | None:
        """Validate name is not empty string."""
        if v is not None and v.strip() == "":
            return None
        return v


class TemplateRecommendation(BaseModel):
    """Schema for template recommendation based on project type."""

    template_id: UUID = Field(..., description="ID of the recommended template")
    category: str = Field(..., description="Template category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    reasoning: str = Field(..., description="Explanation for the recommendation")


class BriefingAnswerBase(BaseModel):
    """Base schema for briefing answer."""

    question_order: int = Field(..., ge=1, description="Question order number")
    answer: str = Field(..., min_length=1, description="Answer text")


class BriefingAnswerCreate(BriefingAnswerBase):
    """Schema for creating a briefing answer."""

    pass


class BriefingCreate(BaseModel):
    """Schema for creating a briefing."""

    end_client_id: UUID
    template_version_id: UUID
    status: Literal["in_progress", "completed", "cancelled"] = "in_progress"


class BriefingRead(BriefingCreate):
    """Schema for reading a briefing."""

    id: UUID
    answers: dict = Field(default_factory=dict, description="Question answers as JSONB")

    model_config = ConfigDict(from_attributes=True)


# WhatsApp Briefing Flow Schemas
class StartBriefingRequest(BaseModel):
    """Request schema for starting a briefing via WhatsApp."""

    architect_id: UUID = Field(..., description="ID of the architect initiating the briefing")
    architect_message: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Message from architect containing client information",
    )

    @field_validator("architect_message")
    @classmethod
    def validate_message_not_empty(cls, v: str) -> str:
        """Validate message is not just whitespace."""
        if v.strip() == "":
            raise ValueError("Message cannot be empty or only whitespace")
        return v.strip()


class StartBriefingResponse(BaseModel):
    """Response schema after starting a briefing via WhatsApp."""

    briefing_id: UUID = Field(..., description="ID of the created briefing")
    client_id: UUID = Field(..., description="ID of the end client")
    client_name: str = Field(..., description="Name of the end client")
    client_phone: str = Field(..., description="Phone number of the end client")
    first_question: str = Field(..., description="First question sent to the client")
    template_category: str = Field(..., description="Category of the template being used")
    whatsapp_message_id: str | None = Field(
        None, description="WhatsApp message ID if message was sent"
    )

    model_config = ConfigDict(from_attributes=True)
