"""Token counting utilities for conversation memory management."""

import tiktoken


class TokenCounter:
    """Counts tokens in messages using tiktoken for accurate token estimation."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        """Initialize TokenCounter with a specific model encoding.

        Args:
            model_name: The model name to use for token encoding (default: "gpt-4o-mini")
        """
        self.model_name = model_name
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding (used by GPT-4 and newer models)
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_message(self, message: dict[str, str]) -> int:
        """Count tokens in a single message.

        Args:
            message: Message dict with 'role' and 'content' keys

        Returns:
            Number of tokens in the message including role overhead
        """
        # Format: <role>: <content>
        # This adds some overhead for the role prefix
        role = message.get("role", "")
        content = message.get("content", "")

        # Count role tokens
        role_tokens = len(self.encoding.encode(role))
        # Count content tokens
        content_tokens = len(self.encoding.encode(content))

        # Add overhead for message structure (approximate)
        # OpenAI uses special tokens for message boundaries
        overhead = 4  # Approximate overhead per message

        return role_tokens + content_tokens + overhead

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: List of message dicts

        Returns:
            Total number of tokens across all messages
        """
        if not messages:
            return 0

        return sum(self.count_message(msg) for msg in messages)

    def truncate_to_limit(
        self, messages: list[dict[str, str]], token_limit: int
    ) -> list[dict[str, str]]:
        """Truncate messages to fit within token limit, keeping most recent.

        Args:
            messages: List of message dicts in chronological order
            token_limit: Maximum number of tokens allowed

        Returns:
            Truncated list of messages (most recent that fit within limit)
        """
        if token_limit <= 0:
            return []

        if not messages:
            return []

        # Start from the end and work backwards
        truncated: list[dict[str, str]] = []
        current_tokens = 0

        for message in reversed(messages):
            message_tokens = self.count_message(message)

            # Check if adding this message would exceed limit
            if current_tokens + message_tokens > token_limit:
                break

            # Add to front (since we're going backwards)
            truncated.insert(0, message)
            current_tokens += message_tokens

        return truncated
