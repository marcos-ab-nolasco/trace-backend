"""Anthropic Claude chat service implementation."""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from anthropic import AsyncAnthropic
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import get_settings

from .base import BaseAIService

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AnthropicService(BaseAIService):
    """Implementation of the AI service using Anthropic's Messages API."""

    def __init__(self) -> None:
        settings = get_settings()
        api_key = (
            settings.ANTHROPIC_API_KEY.get_secret_value() if settings.ANTHROPIC_API_KEY else None
        )
        self._client = AsyncAnthropic(api_key=api_key) if api_key else None

    async def generate_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a completion using Anthropic with retry logic."""
        if self._client is None:
            logger.warning("Anthropic provider not configured: missing ANTHROPIC_API_KEY")
            return "Anthropic não está configurado. Defina ANTHROPIC_API_KEY para habilitar respostas automáticas."

        client = self._client
        payload = self._build_payload(messages)
        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": payload,
            "max_tokens": 1024,
        }

        if system_prompt:
            request_kwargs["system"] = system_prompt

        try:
            async for attempt in AsyncRetrying(
                reraise=True,
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                retry=retry_if_exception_type(Exception),
            ):
                with attempt:
                    if attempt.retry_state.attempt_number > 1:
                        logger.warning(
                            f"Anthropic retry attempt {attempt.retry_state.attempt_number}/3: model={model}"
                        )
                    response = await client.messages.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001 - upstream errors vary
            logger.error(
                f"Anthropic call failed after retries: model={model} error={type(exc).__name__}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to generate response from Anthropic: {exc}",
            ) from exc

        text_parts = [
            block.text
            for block in getattr(response, "content", [])
            if hasattr(block, "text") and block.text is not None
        ]

        content = "".join(text_parts)

        if not content:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Anthropic returned an empty response",
            )

        return content

    async def generate_structured_response(
        self,
        prompt: str,
        response_model: type[T],
        model: str,
        system_prompt: str | None = None,
    ) -> T:
        """Generate a structured response using Anthropic Claude with JSON output."""
        if self._client is None:
            logger.warning("Anthropic provider not configured: missing ANTHROPIC_API_KEY")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Anthropic não está configurado. Defina ANTHROPIC_API_KEY.",
            )

        client = self._client

        # Get JSON schema from Pydantic model
        schema = response_model.model_json_schema()
        schema_str = json.dumps(schema, indent=2)

        # Build enhanced system prompt with schema instructions
        structured_system = (
            f"{system_prompt}\n\n" if system_prompt else ""
        ) + f"""You must respond with valid JSON that matches this schema:

{schema_str}

IMPORTANT:
- Return ONLY the JSON object, no additional text
- Ensure all required fields are present
- Match the exact field names and types from the schema"""

        # Build messages
        messages = [{"role": "user", "content": prompt}]
        payload = self._build_payload(messages)

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": payload,
            "max_tokens": 2048,
            "system": structured_system,
        }

        try:
            async for attempt in AsyncRetrying(
                reraise=True,
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=4),
                retry=retry_if_exception_type(Exception),
            ):
                with attempt:
                    if attempt.retry_state.attempt_number > 1:
                        logger.warning(
                            f"Anthropic structured retry {attempt.retry_state.attempt_number}/3"
                        )
                    response = await client.messages.create(**request_kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"Anthropic structured call failed: model={model} error={type(exc).__name__}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to generate structured response from Anthropic: {exc}",
            ) from exc

        # Extract text content
        text_parts = [
            block.text
            for block in getattr(response, "content", [])
            if hasattr(block, "text") and block.text is not None
        ]
        content = "".join(text_parts).strip()

        if not content:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Anthropic returned empty structured response",
            )

        # Parse JSON and validate against Pydantic model
        try:
            # Try to extract JSON if wrapped in markdown code blocks
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error(f"Failed to parse Anthropic structured response: {exc}\nContent: {content}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Invalid structured response from Anthropic: {exc}",
            ) from exc

    @staticmethod
    def _build_payload(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform conversation history into Anthropic-compatible payload."""
        converted: list[dict[str, Any]] = []
        for message in messages:
            converted.append(
                {
                    "role": message["role"],
                    "content": [{"type": "text", "text": message["content"]}],
                }
            )
        return converted
