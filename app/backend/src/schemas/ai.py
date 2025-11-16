"""Schemas for AI provider configuration."""

from pydantic import BaseModel


class AIModelOption(BaseModel):
    """AI model option schema."""

    value: str
    label: str


class AIProvider(BaseModel):
    """AI provider schema."""

    id: str
    label: str
    models: list[AIModelOption]
    is_configured: bool
