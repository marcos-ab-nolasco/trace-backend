"""Factory and registry for AI service providers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from src.core.cache.decorator import redis_cache_decorator
from src.core.config import get_settings
from src.schemas.chat import AIModelOption, AIProvider

from .anthropic_service import AnthropicService
from .base import BaseAIService
from .openai_service import OpenAIService

AI_PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "openai": {
        "label": "OpenAI",
        "models": [
            {"value": "gpt-4o", "label": "GPT-4o"},
            {"value": "gpt-4o-mini", "label": "GPT-4o Mini"},
            {"value": "gpt-4-turbo", "label": "GPT-4 Turbo"},
            {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"},
        ],
        "is_configured": lambda settings: bool(settings.OPENAI_API_KEY),
    },
    "anthropic": {
        "label": "Anthropic",
        "models": [
            {"value": "claude-3-5-sonnet-20241022", "label": "Claude 3.5 Sonnet"},
            {"value": "claude-3-opus-20240229", "label": "Claude 3 Opus"},
            {"value": "claude-3-sonnet-20240229", "label": "Claude 3 Sonnet"},
            {"value": "claude-3-haiku-20240307", "label": "Claude 3 Haiku"},
        ],
        "is_configured": lambda settings: bool(settings.ANTHROPIC_API_KEY),
    },
}

__all__ = [
    "AI_PROVIDER_REGISTRY",
    "AnthropicService",
    "BaseAIService",
    "OpenAIService",
    "get_ai_service",
    "list_ai_providers",
]


def get_ai_service(provider: str) -> BaseAIService:
    """Return the AI service implementation for the given provider."""
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation does not define an AI provider",
        )

    normalized_provider = provider.lower()

    if normalized_provider == "openai":
        return OpenAIService()
    if normalized_provider == "anthropic":
        return AnthropicService()

    raise ValueError(f"Unknown provider: {provider}")


@redis_cache_decorator(ttl=3600, namespace="ai.providers")
async def list_ai_providers() -> list[AIProvider]:
    """Expose available AI providers with metadata."""

    settings = get_settings()
    providers: list[AIProvider] = []

    for provider_id, meta in AI_PROVIDER_REGISTRY.items():
        is_configured_callable = meta.get("is_configured")
        is_configured = (
            bool(is_configured_callable(settings)) if callable(is_configured_callable) else False
        )

        # Convert model dicts to AIModelOption objects
        models_data = meta.get("models", [])
        models = [AIModelOption(**model) for model in models_data]

        providers.append(
            AIProvider(
                id=provider_id,
                label=meta.get("label", provider_id.title()),
                models=models,
                is_configured=is_configured,
            )
        )

    return providers
