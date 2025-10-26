"""Abstract base class for AI service providers."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


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

    @abstractmethod
    async def generate_structured_response(
        self,
        prompt: str,
        response_model: type[T],
        model: str,
        system_prompt: str | None = None,
    ) -> T:
        """Generate a structured response that conforms to a Pydantic model.

        Args:
            prompt: The user prompt/query
            response_model: Pydantic model class defining the expected response structure
            model: Model identifier (e.g., "gpt-4", "claude-3-5-sonnet-20241022")
            system_prompt: Optional system instruction

        Returns:
            Instance of response_model populated with AI-extracted data

        Raises:
            HTTPException: If AI service fails or returns invalid structured data
        """
        raise NotImplementedError
