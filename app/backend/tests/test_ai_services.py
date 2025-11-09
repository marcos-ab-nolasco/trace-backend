"""Tests for AI service implementations and factory."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from pytest_mock import MockerFixture

from src.services.ai import get_ai_service
from src.services.ai.anthropic_service import AnthropicService
from src.services.ai.openai_service import OpenAIService


@pytest.mark.asyncio
async def test_openai_service_generate_response(mocker: MockerFixture) -> None:
    """OpenAI service should format payload and return the provider response."""
    mock_settings = mocker.Mock()
    mock_settings.OPENAI_API_KEY = SecretStr("test-key")
    mocker.patch("src.services.ai.openai_service.get_settings", return_value=mock_settings)

    mock_message = mocker.Mock()
    mock_message.content = "Hello from OpenAI"
    mock_choice = mocker.Mock()
    mock_choice.message = mock_message
    mock_response = mocker.Mock()
    mock_response.choices = [mock_choice]

    mock_create = mocker.AsyncMock(return_value=mock_response)
    mock_client = mocker.Mock()
    mock_client.chat = mocker.Mock()
    mock_client.chat.completions = mocker.Mock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("src.services.ai.openai_service.AsyncOpenAI", return_value=mock_client)

    service = OpenAIService()
    result = await service.generate_response(
        messages=[{"role": "user", "content": "Hi"}],
        model="gpt-4",
        system_prompt="You are helpful.",
    )

    assert result == "Hello from OpenAI"
    await_kwargs = mock_create.await_args.kwargs
    assert await_kwargs["model"] == "gpt-4"
    assert await_kwargs["messages"][0]["role"] == "system"
    assert await_kwargs["messages"][1]["role"] == "user"


@pytest.mark.asyncio
async def test_openai_service_returns_message_when_api_key_missing(mocker: MockerFixture) -> None:
    """Should return mensagem amigável quando OPENAI_API_KEY não está configurada."""
    mock_settings = mocker.Mock()
    mock_settings.OPENAI_API_KEY = None
    mocker.patch("src.services.ai.openai_service.get_settings", return_value=mock_settings)
    async_openai = mocker.patch("src.services.ai.openai_service.AsyncOpenAI")

    service = OpenAIService()
    response = await service.generate_response(messages=[], model="gpt-4")

    assert "OpenAI não está configurado" in response
    async_openai.assert_not_called()


@pytest.mark.asyncio
async def test_anthropic_service_generate_response(mocker: MockerFixture) -> None:
    """Anthropic service should format payload and return response content."""
    mock_settings = mocker.Mock()
    mock_settings.ANTHROPIC_API_KEY = SecretStr("test-key")
    mocker.patch("src.services.ai.anthropic_service.get_settings", return_value=mock_settings)

    mock_response = mocker.Mock()
    mock_response.content = [SimpleNamespace(type="text", text="Hello from Claude")]

    mock_create = mocker.AsyncMock(return_value=mock_response)
    mock_client = mocker.Mock()
    mock_client.messages = mocker.Mock()
    mock_client.messages.create = mock_create
    mocker.patch("src.services.ai.anthropic_service.AsyncAnthropic", return_value=mock_client)

    service = AnthropicService()
    result = await service.generate_response(
        messages=[{"role": "user", "content": "Hi"}],
        model="claude-3",
        system_prompt="You are helpful.",
    )

    assert result == "Hello from Claude"
    await_kwargs = mock_create.await_args.kwargs
    assert await_kwargs["model"] == "claude-3"
    assert await_kwargs["messages"][0]["role"] == "user"
    assert await_kwargs["system"] == "You are helpful."


@pytest.mark.asyncio
async def test_anthropic_service_returns_message_when_api_key_missing(
    mocker: MockerFixture,
) -> None:
    """Should return mensagem amigável quando ANTHROPIC_API_KEY não está configurada."""
    mock_settings = mocker.Mock()
    mock_settings.ANTHROPIC_API_KEY = None
    mocker.patch("src.services.ai.anthropic_service.get_settings", return_value=mock_settings)
    async_anthropic = mocker.patch("src.services.ai.anthropic_service.AsyncAnthropic")

    service = AnthropicService()
    response = await service.generate_response(messages=[], model="claude-3")

    assert "Anthropic não está configurado" in response
    async_anthropic.assert_not_called()


def test_factory_returns_correct_service(mocker: MockerFixture) -> None:
    """Factory should return the correct service type for known providers."""
    mock_openai_class = mocker.patch("src.services.ai.OpenAIService")
    mock_anthropic_class = mocker.patch("src.services.ai.AnthropicService")

    openai_instance = mocker.Mock()
    anthropic_instance = mocker.Mock()

    mock_openai_class.return_value = openai_instance
    mock_anthropic_class.return_value = anthropic_instance

    assert get_ai_service("openai") is openai_instance
    assert get_ai_service("anthropic") is anthropic_instance


def test_factory_raises_on_unknown_provider() -> None:
    """Unknown providers should raise a ValueError."""
    with pytest.raises(ValueError):
        get_ai_service("unknown")


@pytest.mark.asyncio
async def test_service_retries_on_failure(mocker: MockerFixture) -> None:
    """OpenAI service should retry up to three times before succeeding."""
    mock_settings = mocker.Mock()
    mock_settings.OPENAI_API_KEY = SecretStr("test-key")
    mocker.patch("src.services.ai.openai_service.get_settings", return_value=mock_settings)

    mock_message = mocker.Mock()
    mock_message.content = "Success"
    mock_choice = mocker.Mock()
    mock_choice.message = mock_message
    mock_response = mocker.Mock()
    mock_response.choices = [mock_choice]

    mock_create = mocker.AsyncMock(
        side_effect=[RuntimeError("fail"), RuntimeError("fail"), mock_response]
    )
    mock_client = mocker.Mock()
    mock_client.chat = mocker.Mock()
    mock_client.chat.completions = mocker.Mock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("src.services.ai.openai_service.AsyncOpenAI", return_value=mock_client)

    service = OpenAIService()
    result = await service.generate_response(
        messages=[{"role": "user", "content": "Hi"}], model="gpt-4"
    )

    assert result == "Success"
    assert mock_create.await_count == 3


@pytest.mark.asyncio
async def test_service_raises_502_on_persistent_failure(mocker: MockerFixture) -> None:
    """OpenAI service should surface an HTTPException after repeated failures."""
    mock_settings = mocker.Mock()
    mock_settings.OPENAI_API_KEY = SecretStr("test-key")
    mocker.patch("src.services.ai.openai_service.get_settings", return_value=mock_settings)

    mock_create = mocker.AsyncMock(side_effect=RuntimeError("fail"))
    mock_client = mocker.Mock()
    mock_client.chat = mocker.Mock()
    mock_client.chat.completions = mocker.Mock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("src.services.ai.openai_service.AsyncOpenAI", return_value=mock_client)

    service = OpenAIService()

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_response(messages=[{"role": "user", "content": "Hi"}], model="gpt-4")

    assert exc_info.value.status_code == 502
    assert mock_create.await_count == 3


@pytest.mark.asyncio
async def test_openai_service_raises_when_response_empty(mocker: MockerFixture) -> None:
    """OpenAI responde vazio -> gera 502 amigável."""
    mock_settings = mocker.Mock()
    mock_settings.OPENAI_API_KEY = SecretStr("test-key")
    mocker.patch("src.services.ai.openai_service.get_settings", return_value=mock_settings)

    mock_message = mocker.Mock()
    mock_message.content = ""
    mock_choice = mocker.Mock()
    mock_choice.message = mock_message
    mock_response = mocker.Mock()
    mock_response.choices = [mock_choice]

    mock_create = mocker.AsyncMock(return_value=mock_response)
    mock_client = mocker.Mock()
    mock_client.chat = mocker.Mock()
    mock_client.chat.completions = mocker.Mock()
    mock_client.chat.completions.create = mock_create
    mocker.patch("src.services.ai.openai_service.AsyncOpenAI", return_value=mock_client)

    service = OpenAIService()

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_response(messages=[{"role": "user", "content": "Hi"}], model="gpt-4")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_anthropic_service_raises_when_response_empty(mocker: MockerFixture) -> None:
    """Anthropic responde vazio -> gera 502 amigável."""
    mock_settings = mocker.Mock()
    mock_settings.ANTHROPIC_API_KEY = SecretStr("test-key")
    mocker.patch("src.services.ai.anthropic_service.get_settings", return_value=mock_settings)

    mock_response = mocker.Mock()
    mock_response.content = [
        SimpleNamespace(type="text", text=""),
        SimpleNamespace(type="text", text=None),
    ]

    mock_create = mocker.AsyncMock(return_value=mock_response)
    mock_client = mocker.Mock()
    mock_client.messages = mocker.Mock()
    mock_client.messages.create = mock_create
    mocker.patch("src.services.ai.anthropic_service.AsyncAnthropic", return_value=mock_client)

    service = AnthropicService()

    with pytest.raises(HTTPException) as exc_info:
        await service.generate_response(
            messages=[{"role": "user", "content": "Hi"}], model="claude-3"
        )

    assert exc_info.value.status_code == 502
