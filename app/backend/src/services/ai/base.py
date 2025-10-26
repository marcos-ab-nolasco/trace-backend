"""Abstract base class for AI service providers."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAIService(ABC):
    """Defines the contract for AI providers used by the chat service."""

    @abstractmethod
    async def generate_response(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a response based on the conversation history."""
        raise NotImplementedError
