"""Tests for TokenCounter service."""

from src.services.conversation.memory.token_counter import TokenCounter


class TestTokenCounter:
    """Test suite for TokenCounter class."""

    def test_count_single_message_tokens(self) -> None:
        """Test counting tokens in a single message."""
        counter = TokenCounter()
        message = {"role": "user", "content": "Hello, how are you?"}

        token_count = counter.count_message(message)

        # Should be greater than 0
        assert token_count > 0
        # "Hello, how are you?" should be around 5-7 tokens + overhead
        assert 4 <= token_count <= 15

    def test_count_empty_message_tokens(self) -> None:
        """Test counting tokens in an empty message."""
        counter = TokenCounter()
        message = {"role": "user", "content": ""}

        token_count = counter.count_message(message)

        # Empty content should still have role overhead
        assert token_count >= 0

    def test_count_multiple_messages_tokens(self) -> None:
        """Test counting tokens in a list of messages."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there! How can I help you today?"},
            {"role": "user", "content": "I need help with my project."},
        ]

        total_tokens = counter.count_messages(messages)

        # Should be sum of all messages
        assert total_tokens > 0
        # Verify it's more than any single message
        assert total_tokens > counter.count_message(messages[0])

    def test_count_messages_empty_list(self) -> None:
        """Test counting tokens in an empty message list."""
        counter = TokenCounter()
        messages: list[dict[str, str]] = []

        total_tokens = counter.count_messages(messages)

        assert total_tokens == 0

    def test_truncate_messages_within_limit(self) -> None:
        """Test truncating messages when already within token limit."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi!"},
        ]

        # Set a high limit
        truncated = counter.truncate_to_limit(messages, token_limit=1000)

        # Should return all messages when within limit
        assert len(truncated) == 2
        assert truncated == messages

    def test_truncate_messages_exceeds_limit(self) -> None:
        """Test truncating messages when exceeding token limit."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Second message"},
            {"role": "user", "content": "Third message"},
            {"role": "assistant", "content": "Fourth message"},
            {"role": "user", "content": "Fifth message"},
        ]

        # Set a low limit that should only fit recent messages
        truncated = counter.truncate_to_limit(messages, token_limit=20)

        # Should keep only the most recent messages
        assert len(truncated) < len(messages)
        # Should keep the most recent messages (from the end)
        assert truncated[-1] == messages[-1]

    def test_truncate_messages_zero_limit(self) -> None:
        """Test truncating with zero token limit."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Hello!"},
        ]

        truncated = counter.truncate_to_limit(messages, token_limit=0)

        # Should return empty list
        assert len(truncated) == 0

    def test_count_message_with_long_content(self) -> None:
        """Test counting tokens in a message with long content."""
        counter = TokenCounter()
        long_content = "This is a much longer message. " * 50
        message = {"role": "user", "content": long_content}

        token_count = counter.count_message(message)

        # Long content should have many tokens
        assert token_count > 100

    def test_custom_model_initialization(self) -> None:
        """Test initializing TokenCounter with a custom model."""
        counter = TokenCounter(model_name="gpt-4")
        message = {"role": "user", "content": "Test message"}

        # Should not raise an error
        token_count = counter.count_message(message)
        assert token_count > 0

    def test_truncate_preserves_message_order(self) -> None:
        """Test that truncation preserves chronological order of kept messages."""
        counter = TokenCounter()
        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Message 2"},
            {"role": "user", "content": "Message 3"},
        ]

        truncated = counter.truncate_to_limit(messages, token_limit=30)

        # Verify order is preserved
        if len(truncated) >= 2:
            # Find indices in original
            for i in range(len(truncated) - 1):
                original_idx_current = messages.index(truncated[i])
                original_idx_next = messages.index(truncated[i + 1])
                assert original_idx_current < original_idx_next
