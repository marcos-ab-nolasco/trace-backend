import pytest
from httpx import AsyncClient
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Conversation
from src.db.models.architect import Architect


@pytest.mark.asyncio
async def test_create_conversation(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str]
) -> None:
    """Test creating a new conversation."""
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "My First Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4",
            "system_prompt": "You are a helpful assistant.",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My First Chat"
    assert data["ai_provider"] == "openai"
    assert data["ai_model"] == "gpt-4"
    assert data["system_prompt"] == "You are a helpful assistant."
    assert data["architect_id"] == str(test_user.id)
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_list_providers(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """Providers endpoint should return supported providers from backend registry."""

    response = await client.get("/chat/providers", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    provider_ids = {provider["id"] for provider in data["providers"]}
    assert {"openai", "anthropic"}.issubset(provider_ids)
    for provider in data["providers"]:
        assert "models" in provider
        assert isinstance(provider["models"], list)


@pytest.mark.asyncio
async def test_list_conversations(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str]
) -> None:
    """Test listing conversations for current user."""
    # Create two conversations
    await client.post(
        "/chat/conversations",
        json={"title": "Chat 1", "ai_provider": "openai", "ai_model": "gpt-4"},
        headers=auth_headers,
    )
    await client.post(
        "/chat/conversations",
        json={"title": "Chat 2", "ai_provider": "anthropic", "ai_model": "claude-3"},
        headers=auth_headers,
    )

    # List conversations
    response = await client.get("/chat/conversations", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["conversations"]) == 2
    # Should be ordered by updated_at desc (most recent first)
    assert data["conversations"][0]["title"] == "Chat 2"
    assert data["conversations"][1]["title"] == "Chat 1"


@pytest.mark.asyncio
async def test_get_conversation(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str]
) -> None:
    """Test getting a specific conversation."""
    # Create conversation
    create_response = await client.post(
        "/chat/conversations",
        json={"title": "Test Chat", "ai_provider": "openai", "ai_model": "gpt-4"},
        headers=auth_headers,
    )
    conversation_id = create_response.json()["id"]

    # Get conversation
    response = await client.get(f"/chat/conversations/{conversation_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == conversation_id
    assert data["title"] == "Test Chat"


@pytest.mark.asyncio
async def test_cannot_access_other_user_conversation(
    client: AsyncClient, test_user: Architect, db_session: AsyncSession
) -> None:
    """Test that users cannot access conversations from other users."""
    from src.core.security import create_access_token, hash_password

    # Create another user (same organization)
    other_user = Architect(
        organization_id=test_user.organization_id,
        email="other@example.com",
        hashed_password=hash_password("password123"),
        full_name="Other User",
        phone="+5511777777777",
        is_authorized=True,
    )
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)

    # Create conversation for other user
    other_conversation = Conversation(
        architect_id=other_user.id,
        title="Other User Chat",
        ai_provider="openai",
        ai_model="gpt-4",
    )
    db_session.add(other_conversation)
    await db_session.commit()
    await db_session.refresh(other_conversation)

    # Try to access with test_user's token
    test_user_token = create_access_token(data={"sub": str(test_user.id)})
    headers = {"Authorization": f"Bearer {test_user_token}"}

    response = await client.get(f"/chat/conversations/{other_conversation.id}", headers=headers)

    assert response.status_code == 403
    assert "Not authorized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_conversation(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str]
) -> None:
    """Test updating a conversation."""
    # Create conversation
    create_response = await client.post(
        "/chat/conversations",
        json={"title": "Original Title", "ai_provider": "openai", "ai_model": "gpt-4"},
        headers=auth_headers,
    )
    conversation_id = create_response.json()["id"]

    # Update conversation
    response = await client.patch(
        f"/chat/conversations/{conversation_id}",
        json={"title": "Updated Title", "system_prompt": "New system prompt"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["system_prompt"] == "New system prompt"


@pytest.mark.asyncio
async def test_delete_conversation(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str]
) -> None:
    """Test deleting a conversation."""
    # Create conversation
    create_response = await client.post(
        "/chat/conversations",
        json={"title": "To Be Deleted", "ai_provider": "openai", "ai_model": "gpt-4"},
        headers=auth_headers,
    )
    conversation_id = create_response.json()["id"]

    # Delete conversation
    delete_response = await client.delete(
        f"/chat/conversations/{conversation_id}", headers=auth_headers
    )
    assert delete_response.status_code == 204

    # Verify it's deleted (should return 404)
    get_response = await client.get(f"/chat/conversations/{conversation_id}", headers=auth_headers)
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_message_generates_ai_response(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
    mocker: MockerFixture,
) -> None:
    """Creating a message should persist user + assistant responses via the AI service."""
    mock_ai_service = mocker.Mock()
    mock_ai_service.generate_response = mocker.AsyncMock(return_value="AI response")
    mocker.patch("src.services.chat.get_ai_service", return_value=mock_ai_service)

    create_response = await client.post(
        "/chat/conversations",
        json={
            "title": "Chat with Messages",
            "ai_provider": "openai",
            "ai_model": "gpt-4",
            "system_prompt": "You are helpful.",
        },
        headers=auth_headers,
    )
    conversation_id = create_response.json()["id"]

    response = await client.post(
        f"/chat/conversations/{conversation_id}/messages",
        json={"role": "user", "content": "Hello, AI!", "tokens_used": 10, "meta": {"test": "data"}},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    user_payload = data["user_message"]
    assistant_payload = data["assistant_message"]

    assert user_payload["conversation_id"] == conversation_id
    assert user_payload["role"] == "user"
    assert user_payload["content"] == "Hello, AI!"
    assert user_payload["tokens_used"] == 10
    assert user_payload["meta"] == {"test": "data"}

    assert assistant_payload["conversation_id"] == conversation_id
    assert assistant_payload["role"] == "assistant"
    assert assistant_payload["content"] == "AI response"
    assert assistant_payload["tokens_used"] is None

    mock_ai_service.generate_response.assert_awaited_once()
    call_args = mock_ai_service.generate_response.await_args
    # Args are: (messages, model, system_prompt)
    assert call_args.args[1] == "gpt-4"
    assert call_args.args[2] == "You are helpful."

    messages_response = await client.get(
        f"/chat/conversations/{conversation_id}/messages", headers=auth_headers
    )

    assert messages_response.status_code == 200
    messages_data = messages_response.json()
    assert messages_data["total"] == 2
    roles = [message["role"] for message in messages_data["messages"]]
    assert roles == ["user", "assistant"]
    assert messages_data["messages"][1]["content"] == "AI response"


@pytest.mark.asyncio
async def test_list_messages(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str]
) -> None:
    """Test listing messages in a conversation."""
    # Create conversation
    create_response = await client.post(
        "/chat/conversations",
        json={"title": "Chat History", "ai_provider": "openai", "ai_model": "gpt-4"},
        headers=auth_headers,
    )
    conversation_id = create_response.json()["id"]

    # Create user messages (each will generate an assistant response)
    await client.post(
        f"/chat/conversations/{conversation_id}/messages",
        json={"role": "user", "content": "First message"},
        headers=auth_headers,
    )
    await client.post(
        f"/chat/conversations/{conversation_id}/messages",
        json={"role": "user", "content": "Second message"},
        headers=auth_headers,
    )

    # List messages
    response = await client.get(
        f"/chat/conversations/{conversation_id}/messages", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    # Each user message creates a user + assistant message pair (2 messages x 2 = 4 total)
    assert data["total"] == 4
    assert len(data["messages"]) == 4
    # Should be ordered by created_at asc (oldest first)
    assert data["messages"][0]["content"] == "First message"
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][2]["content"] == "Second message"
    assert data["messages"][2]["role"] == "user"
    assert data["messages"][3]["role"] == "assistant"


@pytest.mark.asyncio
async def test_delete_conversation_cascades_to_messages(
    client: AsyncClient, test_user: Architect, auth_headers: dict[str, str], db_session: AsyncSession
) -> None:
    """Test that deleting a conversation also deletes its messages."""
    from sqlalchemy import func, select

    from src.db.models import Message

    # Create conversation
    create_response = await client.post(
        "/chat/conversations",
        json={"title": "Cascade Test", "ai_provider": "openai", "ai_model": "gpt-4"},
        headers=auth_headers,
    )
    conversation_id = create_response.json()["id"]

    # Create messages
    await client.post(
        f"/chat/conversations/{conversation_id}/messages",
        json={"role": "user", "content": "Message 1"},
        headers=auth_headers,
    )
    await client.post(
        f"/chat/conversations/{conversation_id}/messages",
        json={"role": "assistant", "content": "Message 2"},
        headers=auth_headers,
    )

    # Delete conversation
    await client.delete(f"/chat/conversations/{conversation_id}", headers=auth_headers)

    # Verify messages are also deleted
    result = await db_session.execute(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
    )
    count = result.scalar()
    assert count == 0
