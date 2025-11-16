"""
Pydantic schemas for JSONB fields in the conversational AI system.

These schemas provide type safety and validation for the flexible JSONB fields
used to track information gathering state and AI metadata.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class FieldState(BaseModel):
    """
    State tracking for a single information field in the briefing.

    Stored in Briefing.information_state JSONB as:
    {
        "budget": FieldState(...),
        "timeline": FieldState(...),
        ...
    }
    """

    status: Literal["pending", "collected", "inferred", "clarifying", "corrected"] = Field(
        description="Current state of this field in the gathering process"
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) for collected/inferred values",
    )
    source_message_id: UUID | None = Field(
        default=None, description="ID of ConversationMessage where this info was extracted"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this state was last updated"
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Priority for gathering this field (1=low, 10=high)",
    )
    needs_confirmation: bool = Field(
        default=False,
        description="Whether this field needs explicit confirmation from user",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "collected",
                "confidence": 0.95,
                "source_message_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-11-16T10:30:00Z",
                "priority": 8,
                "needs_confirmation": False,
            }
        }


class GatheredField(BaseModel):
    """
    Actual extracted value for an information field.

    Stored in Briefing.gathered_information JSONB as:
    {
        "budget": GatheredField(...),
        "timeline": GatheredField(...),
        ...
    }
    """

    value: Any = Field(description="The extracted value (can be any JSON-serializable type)")
    confidence: float = Field(
        ge=0.0, le=1.0, description="AI confidence in this extraction (0.0-1.0)"
    )
    source_message_id: UUID = Field(
        description="ID of ConversationMessage where this was extracted"
    )
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow, description="When this value was extracted"
    )
    corrected: bool = Field(
        default=False, description="Whether this value was corrected by the user"
    )
    previous_value: Any | None = Field(
        default=None, description="Previous value if this was a correction"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "value": "100000",
                "confidence": 0.92,
                "source_message_id": "550e8400-e29b-41d4-a716-446655440000",
                "extracted_at": "2025-11-16T10:30:00Z",
                "corrected": False,
                "previous_value": None,
            }
        }


class ExtractedInfo(BaseModel):
    """
    Information extracted from a single conversation message.

    Stored in ConversationMessage.extracted_info JSONB.
    Maps field names to their extracted values.
    """

    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Mapping of field_name -> extracted_value",
    )
    confidence_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of field_name -> confidence (0.0-1.0)",
    )
    extraction_method: Literal["gpt-4o-mini", "claude-sonnet", "manual", "inferred"] = Field(
        description="How this information was extracted"
    )

    @field_validator("confidence_scores")
    @classmethod
    def validate_confidence_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Ensure all confidence scores are between 0 and 1."""
        for field_name, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"Confidence score for '{field_name}' must be between 0.0 and 1.0")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "fields": {"budget": "100000", "timeline": "3 months"},
                "confidence_scores": {"budget": 0.95, "timeline": 0.88},
                "extraction_method": "gpt-4o-mini",
            }
        }


class AIMetadata(BaseModel):
    """
    AI processing metadata for a conversation message.

    Stored in ConversationMessage.ai_metadata JSONB.
    Tracks intent classification, reasoning, and API usage.
    """

    intent: str | None = Field(
        default=None,
        description="Classified intent (answer_question, request_skip, etc.)",
    )
    intent_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in intent classification",
    )
    reasoning: str | None = Field(
        default=None, description="AI chain-of-thought reasoning for decisions"
    )
    decision_type: (
        Literal["ask_question", "clarify_answer", "confirm_inference", "complete_briefing"] | None
    ) = Field(default=None, description="Decision made by DecisionAgent")
    provider: str = Field(description="AI provider (openai, anthropic)")
    model: str = Field(description="Specific model used (gpt-4o-mini, claude-sonnet-4, etc.)")
    tokens_used: int = Field(ge=0, description="Number of tokens consumed")
    processing_time_ms: int | None = Field(
        default=None, ge=0, description="Processing time in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intent": "answer_question",
                "intent_confidence": 0.94,
                "reasoning": "User provided budget and timeline in natural language",
                "decision_type": "ask_question",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "tokens_used": 245,
                "processing_time_ms": 850,
            }
        }


class InformationStateDict(BaseModel):
    """
    Complete information state for a briefing.

    Type-safe wrapper for Briefing.information_state JSONB field.
    """

    fields: dict[str, FieldState] = Field(
        default_factory=dict,
        description="Mapping of field_name -> FieldState",
    )

    def get_pending_fields(self) -> list[str]:
        """Return list of field names with status='pending'."""
        return [name for name, state in self.fields.items() if state.status == "pending"]

    def get_collected_fields(self) -> list[str]:
        """Return list of field names with status='collected'."""
        return [name for name, state in self.fields.items() if state.status == "collected"]

    def get_fields_needing_confirmation(self) -> list[str]:
        """Return list of field names that need confirmation."""
        return [name for name, state in self.fields.items() if state.needs_confirmation]

    def get_completion_percentage(self, required_fields: list[str]) -> float:
        """Calculate completion percentage based on required fields."""
        if not required_fields:
            return 100.0

        collected = sum(
            1
            for field in required_fields
            if field in self.fields and self.fields[field].status in ["collected", "inferred"]
        )
        return (collected / len(required_fields)) * 100.0


class GatheredInformationDict(BaseModel):
    """
    Complete gathered information for a briefing.

    Type-safe wrapper for Briefing.gathered_information JSONB field.
    """

    fields: dict[str, GatheredField] = Field(
        default_factory=dict,
        description="Mapping of field_name -> GatheredField",
    )

    def get_field_value(self, field_name: str) -> Any:
        """Get the value for a specific field, or None if not found."""
        field = self.fields.get(field_name)
        return field.value if field else None

    def get_all_values(self) -> dict[str, Any]:
        """Get a simple dict of field_name -> value for all fields."""
        return {name: field.value for name, field in self.fields.items()}
