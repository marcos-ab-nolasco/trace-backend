"""Vector store for semantic search over conversation history using ChromaDB."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import chromadb
from chromadb.config import Settings as ChromaSettings
from openai import AsyncOpenAI

from src.core.config import get_settings
from src.db.models.conversation_message import ConversationMessage


class VectorStore:
    """Manages vector embeddings for semantic search over conversations."""

    def __init__(self) -> None:
        """Initialize ChromaDB client and OpenAI for embeddings."""
        settings = get_settings()

        # Initialize ChromaDB in persistent mode
        self.client = chromadb.Client(
            ChromaSettings(
                persist_directory="./data/chromadb",
                anonymized_telemetry=False,
            )
        )

        # Create/get collection
        self.collection = self.client.get_or_create_collection(
            name="conversation_messages",
            metadata={"description": "Embeddings for conversation messages"},
        )

        # OpenAI client for embeddings
        if settings.OPENAI_API_KEY:
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
        else:
            raise ValueError("OPENAI_API_KEY not configured")

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding using OpenAI text-embedding-3-small model.

        Args:
            text: Text to generate embedding for

        Returns:
            List of floats representing the embedding vector
        """
        response = await self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-3-small",
        )
        return response.data[0].embedding

    async def add_message(
        self,
        message_id: str,
        content: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Add message embedding to vector store.

        Args:
            message_id: Unique identifier for the message
            content: Text content of the message
            metadata: Optional metadata to store with the embedding
        """
        embedding = await self.generate_embedding(content)

        self.collection.add(
            ids=[message_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata or {}],
        )

    async def add_messages_batch(
        self,
        messages: Sequence[ConversationMessage],
    ) -> None:
        """Add multiple messages in batch for better performance.

        Args:
            messages: Sequence of ConversationMessage objects to add
        """
        if not messages:
            return

        # Generate embeddings for all messages
        contents = [msg.content for msg in messages]
        embeddings = []

        for content in contents:
            embedding = await self.generate_embedding(content)
            embeddings.append(embedding)

        # Add to ChromaDB
        self.collection.add(
            ids=[str(msg.id) for msg in messages],
            embeddings=embeddings,
            documents=contents,
            metadatas=[
                {
                    "briefing_id": str(msg.briefing_id),
                    "role": msg.role,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in messages
            ],
        )

    async def search_similar(
        self,
        query: str,
        briefing_id: UUID,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for semantically similar messages within a briefing.

        Args:
            query: Search query text
            briefing_id: UUID of the briefing to search within
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing message id, content, metadata, and distance
        """
        query_embedding = await self.generate_embedding(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"briefing_id": str(briefing_id)},
        )

        # Format results
        if not results["ids"] or not results["ids"][0]:
            return []

        similar_messages: list[dict[str, Any]] = []
        for i, message_id in enumerate(results["ids"][0]):
            similar_messages.append(
                {
                    "id": message_id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None,
                }
            )

        return similar_messages

    async def delete_message(self, message_id: str) -> None:
        """Remove message from vector store.

        Args:
            message_id: ID of the message to delete
        """
        self.collection.delete(ids=[message_id])

    async def delete_briefing(self, briefing_id: UUID) -> None:
        """Remove all messages for a briefing.

        Args:
            briefing_id: UUID of the briefing to delete all messages for
        """
        self.collection.delete(where={"briefing_id": str(briefing_id)})

    def get_collection_stats(self) -> dict[str, int | str]:
        """Get statistics about the collection.

        Returns:
            Dictionary with total embeddings count and collection name
        """
        return {
            "total_embeddings": self.collection.count(),
            "collection_name": self.collection.name,
        }
