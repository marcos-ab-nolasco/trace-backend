"""Redis-based state caching for briefing sessions."""

import json
import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class BriefingStateCache:
    """Manages briefing state in Redis for fast access."""

    def __init__(self, redis_client: Redis | None = None):
        """Initialize state cache.

        Args:
            redis_client: Optional Redis client. If None, caching is disabled.
        """
        self.redis = redis_client
        self.enabled = redis_client is not None

    def _get_key(self, briefing_id: UUID) -> str:
        """Generate Redis key for briefing state.

        Args:
            briefing_id: Briefing UUID

        Returns:
            Redis key string
        """
        return f"briefing:state:{briefing_id}"

    async def get_state(self, briefing_id: UUID) -> dict[str, Any] | None:
        """Get cached briefing state.

        Args:
            briefing_id: Briefing UUID

        Returns:
            Cached state dict or None if not cached
        """
        if not self.enabled:
            return None

        try:
            key = self._get_key(briefing_id)
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as exc:
            logger.warning(f"Failed to get briefing state from cache: {exc}")

        return None

    async def set_state(self, briefing_id: UUID, state: dict[str, Any], ttl: int = 3600) -> None:
        """Cache briefing state.

        Args:
            briefing_id: Briefing UUID
            state: State data to cache
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        if not self.enabled:
            return

        try:
            key = self._get_key(briefing_id)
            data = json.dumps(state, default=str)
            await self.redis.set(key, data, ex=ttl)
            logger.debug(f"Cached briefing state: {briefing_id}")
        except Exception as exc:
            logger.warning(f"Failed to cache briefing state: {exc}")

    async def invalidate_state(self, briefing_id: UUID) -> None:
        """Invalidate cached briefing state.

        Args:
            briefing_id: Briefing UUID
        """
        if not self.enabled:
            return

        try:
            key = self._get_key(briefing_id)
            await self.redis.delete(key)
            logger.debug(f"Invalidated cached state: {briefing_id}")
        except Exception as exc:
            logger.warning(f"Failed to invalidate briefing state: {exc}")

    async def set_current_question(
        self, briefing_id: UUID, question_order: int, ttl: int = 600
    ) -> None:
        """Cache the current question for quick lookup.

        Args:
            briefing_id: Briefing UUID
            question_order: Current question order
            ttl: Time-to-live in seconds (default: 10 minutes)
        """
        if not self.enabled:
            return

        try:
            key = f"briefing:question:{briefing_id}"
            await self.redis.set(key, str(question_order), ex=ttl)
        except Exception as exc:
            logger.warning(f"Failed to cache current question: {exc}")

    async def get_current_question(self, briefing_id: UUID) -> int | None:
        """Get cached current question order.

        Args:
            briefing_id: Briefing UUID

        Returns:
            Current question order or None if not cached
        """
        if not self.enabled:
            return None

        try:
            key = f"briefing:question:{briefing_id}"
            data = await self.redis.get(key)
            if data:
                return int(data)
        except Exception as exc:
            logger.warning(f"Failed to get current question from cache: {exc}")

        return None
