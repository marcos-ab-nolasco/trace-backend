"""Integration tests for chat functionality with cache behavior validation.

These tests validate end-to-end behavior through the API, including cache
invalidation and data consistency. They simulate real user workflows.
"""

import pytest
from httpx import AsyncClient

from src.db.models.architect import Architect


@pytest.mark.asyncio
async def test_conversation_list_reflects_create_operations(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """When a conversation is created, subsequent list calls must include it.

    This validates that cache invalidation works correctly on CREATE operations.
    """
    # Initially, user has no conversations
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["conversations"] == []

    # User creates first conversation
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "First Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    first_conv_id = response.json()["id"]

    # List should now include the new conversation
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["conversations"]) == 1
    assert data["conversations"][0]["id"] == first_conv_id
    assert data["conversations"][0]["title"] == "First Chat"

    # User creates second conversation
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Second Chat",
            "ai_provider": "anthropic",
            "ai_model": "claude-3-5-sonnet-20241022",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    second_conv_id = response.json()["id"]

    # List should now include BOTH conversations
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["conversations"]) == 2

    # Verify both are present
    conv_ids = {conv["id"] for conv in data["conversations"]}
    assert conv_ids == {first_conv_id, second_conv_id}


@pytest.mark.asyncio
async def test_conversation_list_reflects_update_operations(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """When a conversation is updated, subsequent list calls must show the changes.

    This validates that cache invalidation works correctly on UPDATE operations,
    and that ordering is preserved (updated_at changes affect sort order).
    """
    # Create two conversations
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Old Title",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    conv_id = response.json()["id"]

    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Another Chat",
            "ai_provider": "anthropic",
            "ai_model": "claude-3-haiku-20240307",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # List conversations (populate cache)
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    conversations = response.json()["conversations"]
    assert len(conversations) == 2

    # Find the conversation we want to update
    titles_before = {conv["title"] for conv in conversations}
    assert "Old Title" in titles_before

    # Update the conversation's title
    response = await client.patch(
        f"/chat/conversations/{conv_id}",
        json={"title": "New Title"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"

    # List again - must reflect the update
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    conversations = response.json()["conversations"]
    assert len(conversations) == 2

    titles_after = {conv["title"] for conv in conversations}
    assert "New Title" in titles_after
    assert "Old Title" not in titles_after

    # The updated conversation should be first (most recently updated)
    assert conversations[0]["title"] == "New Title"


@pytest.mark.asyncio
async def test_conversation_list_reflects_delete_operations(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """When a conversation is deleted, subsequent list calls must not include it.

    This validates that cache invalidation works correctly on DELETE operations.
    """
    # Create three conversations
    conv_ids = []
    for i in range(3):
        response = await client.post(
            "/chat/conversations",
            json={
                "title": f"Chat {i + 1}",
                "ai_provider": "openai",
                "ai_model": "gpt-4o-mini",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        conv_ids.append(response.json()["id"])

    # List should show all three
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 3

    # Delete the second conversation
    response = await client.delete(f"/chat/conversations/{conv_ids[1]}", headers=auth_headers)
    assert response.status_code == 204

    # List should now show only two conversations
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["conversations"]) == 2

    # Verify the deleted conversation is not present
    remaining_ids = {conv["id"] for conv in data["conversations"]}
    assert conv_ids[1] not in remaining_ids
    assert conv_ids[0] in remaining_ids
    assert conv_ids[2] in remaining_ids

    # Delete another one
    response = await client.delete(f"/chat/conversations/{conv_ids[0]}", headers=auth_headers)
    assert response.status_code == 204

    # List should now show only one conversation
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["conversations"][0]["id"] == conv_ids[2]


@pytest.mark.asyncio
async def test_conversation_list_ordering_by_updated_at(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """Conversations should be ordered by updated_at descending (most recent first).

    When a conversation is updated, it should move to the top of the list.
    """
    # Create three conversations in sequence
    conv_ids = []
    for i in range(3):
        response = await client.post(
            "/chat/conversations",
            json={
                "title": f"Chat {i + 1}",
                "ai_provider": "openai",
                "ai_model": "gpt-4o",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        conv_ids.append(response.json()["id"])

    # List should show them in reverse creation order (newest first)
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    conversations = response.json()["conversations"]
    assert len(conversations) == 3
    assert conversations[0]["title"] == "Chat 3"  # Most recently created
    assert conversations[1]["title"] == "Chat 2"
    assert conversations[2]["title"] == "Chat 1"  # Oldest

    # Update the oldest conversation (Chat 1)
    response = await client.patch(
        f"/chat/conversations/{conv_ids[0]}",
        json={"title": "Updated Chat 1"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    # List again - "Updated Chat 1" should now be first
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    conversations = response.json()["conversations"]
    assert conversations[0]["title"] == "Updated Chat 1"  # Now most recent
    assert conversations[1]["title"] == "Chat 3"
    assert conversations[2]["title"] == "Chat 2"


@pytest.mark.asyncio
async def test_conversation_list_isolation_between_users(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    """Each user should only see their own conversations.

    Cache should not leak data between different users.
    """
    from src.core.security import hash_password

    # Create a second user
    second_user = Architect(
        organization_id=test_user.organization_id,
        email="second@example.com",
        hashed_password=hash_password("password123"),
        full_name="Second User",
        phone="+5511777777777",
        is_authorized=True,
    )
    db_session.add(second_user)
    await db_session.commit()
    await db_session.refresh(second_user)

    # Create token for second user
    from src.core.security import create_access_token

    second_token = create_access_token(data={"sub": str(second_user.id)})
    second_headers = {"Authorization": f"Bearer {second_token}"}

    # First user creates a conversation
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "First User Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    first_user_conv_id = response.json()["id"]

    # Second user creates a conversation
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Second User Chat",
            "ai_provider": "anthropic",
            "ai_model": "claude-3-opus-20240229",
        },
        headers=second_headers,
    )
    assert response.status_code == 201
    second_user_conv_id = response.json()["id"]

    # First user lists conversations - should only see their own
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["conversations"][0]["id"] == first_user_conv_id
    assert data["conversations"][0]["title"] == "First User Chat"

    # Second user lists conversations - should only see their own
    response = await client.get("/chat/conversations", headers=second_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["conversations"][0]["id"] == second_user_conv_id
    assert data["conversations"][0]["title"] == "Second User Chat"

    # First user updates their conversation
    response = await client.patch(
        f"/chat/conversations/{first_user_conv_id}",
        json={"title": "Updated First User Chat"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    # Second user's list should remain unchanged
    response = await client.get("/chat/conversations", headers=second_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["conversations"][0]["title"] == "Second User Chat"  # Unchanged

    # First user deletes their conversation
    response = await client.delete(
        f"/chat/conversations/{first_user_conv_id}", headers=auth_headers
    )
    assert response.status_code == 204

    # First user should now have empty list
    response = await client.get("/chat/conversations", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0

    # Second user should still have their conversation
    response = await client.get("/chat/conversations", headers=second_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_multiple_rapid_list_calls_return_consistent_data(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """Multiple rapid list calls without mutations should return identical data.

    This validates that caching provides consistency and doesn't introduce
    race conditions or data corruption.
    """
    # Create a conversation
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Test Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    conv_id = response.json()["id"]

    # Make 5 rapid list calls
    responses = []
    for _ in range(5):
        response = await client.get("/chat/conversations", headers=auth_headers)
        assert response.status_code == 200
        responses.append(response.json())

    # All responses should be identical
    first_response = responses[0]
    for response in responses[1:]:
        assert response["total"] == first_response["total"]
        assert len(response["conversations"]) == len(first_response["conversations"])
        assert response["conversations"][0]["id"] == conv_id
        assert response["conversations"][0]["title"] == first_response["conversations"][0]["title"]


# ==================== MESSAGE CACHE INTEGRATION TESTS ====================


@pytest.mark.asyncio
async def test_message_list_reflects_create_operations(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """When messages are created, subsequent list calls must include them.

    This validates that cache invalidation works correctly when new messages
    are added to a conversation (both user and assistant messages).
    """
    # Create a conversation
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Test Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    conv_id = response.json()["id"]

    # Initially, conversation has no messages
    response = await client.get(f"/chat/conversations/{conv_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["messages"] == []

    # User sends first message (triggers AI response)
    response = await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={
            "role": "user",
            "content": "Hello, how are you?",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "user_message" in data
    assert "assistant_message" in data

    # List messages - should now show both user and assistant messages
    response = await client.get(f"/chat/conversations/{conv_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hello, how are you?"
    assert data["messages"][1]["role"] == "assistant"

    # User sends second message
    response = await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={
            "role": "user",
            "content": "Tell me a joke",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # List messages - should now show all 4 messages (2 user + 2 assistant)
    response = await client.get(f"/chat/conversations/{conv_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4
    assert len(data["messages"]) == 4


@pytest.mark.asyncio
async def test_message_list_ordering_by_created_at(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """Messages should be ordered by created_at ascending (oldest first).

    This ensures conversation flow makes sense (chronological order).
    """
    # Create a conversation
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Test Chat",
            "ai_provider": "anthropic",
            "ai_model": "claude-3-haiku-20240307",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    conv_id = response.json()["id"]

    # Send three messages in sequence
    messages_content = ["First message", "Second message", "Third message"]
    for content in messages_content:
        response = await client.post(
            f"/chat/conversations/{conv_id}/messages",
            json={
                "role": "user",
                "content": content,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

    # List messages - should be in chronological order
    response = await client.get(f"/chat/conversations/{conv_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    messages = data["messages"]

    # Should have 6 messages total (3 user + 3 assistant, interleaved)
    assert len(messages) == 6

    # Verify chronological order and interleaving
    user_messages = [msg for msg in messages if msg["role"] == "user"]
    assert len(user_messages) == 3
    assert user_messages[0]["content"] == "First message"
    assert user_messages[1]["content"] == "Second message"
    assert user_messages[2]["content"] == "Third message"

    # First message should be the first user message
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "First message"


@pytest.mark.asyncio
async def test_message_list_isolation_between_conversations(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """Each conversation should have isolated messages.

    Cache should not leak messages between different conversations.
    """
    # Create two conversations
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "First Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    conv1_id = response.json()["id"]

    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Second Chat",
            "ai_provider": "anthropic",
            "ai_model": "claude-3-opus-20240229",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    conv2_id = response.json()["id"]

    # Send message to first conversation
    response = await client.post(
        f"/chat/conversations/{conv1_id}/messages",
        json={
            "role": "user",
            "content": "Message for first chat",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # Send message to second conversation
    response = await client.post(
        f"/chat/conversations/{conv2_id}/messages",
        json={
            "role": "user",
            "content": "Message for second chat",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # List messages for first conversation
    response = await client.get(f"/chat/conversations/{conv1_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # user + assistant
    user_messages = [msg for msg in data["messages"] if msg["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "Message for first chat"

    # List messages for second conversation
    response = await client.get(f"/chat/conversations/{conv2_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # user + assistant
    user_messages = [msg for msg in data["messages"] if msg["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "Message for second chat"

    # Add more messages to first conversation
    response = await client.post(
        f"/chat/conversations/{conv1_id}/messages",
        json={
            "role": "user",
            "content": "Another message for first chat",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # First conversation should now have 4 messages
    response = await client.get(f"/chat/conversations/{conv1_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 4

    # Second conversation should still have only 2 messages
    response = await client.get(f"/chat/conversations/{conv2_id}/messages", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 2


@pytest.mark.asyncio
async def test_message_list_isolation_between_users(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
    db_session,
) -> None:
    """Users should only see messages from their own conversations.

    Cache should not leak messages between different users.
    """
    from src.core.security import create_access_token, hash_password

    # Create a second user
    second_user = Architect(
        organization_id=test_user.organization_id,
        email="second@example.com",
        hashed_password=hash_password("password123"),
        full_name="Second User",
        phone="+5511777777777",
        is_authorized=True,
    )
    db_session.add(second_user)
    await db_session.commit()
    await db_session.refresh(second_user)

    second_token = create_access_token(data={"sub": str(second_user.id)})
    second_headers = {"Authorization": f"Bearer {second_token}"}

    # First user creates conversation and sends message
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "First User Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    first_conv_id = response.json()["id"]

    response = await client.post(
        f"/chat/conversations/{first_conv_id}/messages",
        json={
            "role": "user",
            "content": "Message from first user",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # Second user creates conversation and sends message
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Second User Chat",
            "ai_provider": "anthropic",
            "ai_model": "claude-3-haiku-20240307",
        },
        headers=second_headers,
    )
    assert response.status_code == 201
    second_conv_id = response.json()["id"]

    response = await client.post(
        f"/chat/conversations/{second_conv_id}/messages",
        json={
            "role": "user",
            "content": "Message from second user",
        },
        headers=second_headers,
    )
    assert response.status_code == 201

    # First user should only see their own messages
    response = await client.get(
        f"/chat/conversations/{first_conv_id}/messages", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    user_messages = [msg for msg in data["messages"] if msg["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "Message from first user"

    # Second user should only see their own messages
    response = await client.get(
        f"/chat/conversations/{second_conv_id}/messages", headers=second_headers
    )
    assert response.status_code == 200
    data = response.json()
    user_messages = [msg for msg in data["messages"] if msg["role"] == "user"]
    assert len(user_messages) == 1
    assert user_messages[0]["content"] == "Message from second user"

    # Second user should NOT be able to access first user's conversation
    response = await client.get(
        f"/chat/conversations/{first_conv_id}/messages", headers=second_headers
    )
    assert response.status_code == 403  # Forbidden


@pytest.mark.asyncio
async def test_multiple_rapid_message_list_calls_return_consistent_data(
    client: AsyncClient,
    test_user: Architect,
    auth_headers: dict[str, str],
) -> None:
    """Multiple rapid list calls without new messages should return identical data.

    This validates that message caching provides consistency.
    """
    # Create conversation and send message
    response = await client.post(
        "/chat/conversations",
        json={
            "title": "Test Chat",
            "ai_provider": "openai",
            "ai_model": "gpt-4o",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    conv_id = response.json()["id"]

    response = await client.post(
        f"/chat/conversations/{conv_id}/messages",
        json={
            "role": "user",
            "content": "Test message",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # Make 5 rapid list calls
    responses = []
    for _ in range(5):
        response = await client.get(f"/chat/conversations/{conv_id}/messages", headers=auth_headers)
        assert response.status_code == 200
        responses.append(response.json())

    # All responses should be identical
    first_response = responses[0]
    for response in responses[1:]:
        assert response["total"] == first_response["total"]
        assert len(response["messages"]) == len(first_response["messages"])
        assert response["messages"][0]["content"] == first_response["messages"][0]["content"]
        assert response["messages"][1]["content"] == first_response["messages"][1]["content"]
