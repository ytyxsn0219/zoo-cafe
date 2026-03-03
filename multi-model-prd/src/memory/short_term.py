"""Short-term memory using Redis."""

import json
from typing import Any, Optional

import redis.asyncio as redis

from ..utils.config import get_memory_config
from ..utils.logger import get_logger

logger = get_logger("short_term_memory")


class ShortTermMemory:
    """Redis-based short-term memory for session state."""

    def __init__(self):
        """Initialize short-term memory."""
        self._config = get_memory_config()["redis"]
        self._client: Optional[redis.Redis] = None
        self._ttl = self._config.get("ttl", 86400)

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is not None:
            return

        try:
            redis_url = self._config.get("url", "redis://localhost:6379/0")
            self._client = redis.from_url(redis_url, decode_responses=True)
            await self._client.ping()
            logger.info("redis_connected", url=redis_url)
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            # Fallback to in-memory
            self._client = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set a value in memory.

        Args:
            key: Memory key
            value: Value to store
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        if self._client is None:
            logger.warning("redis_not_available, using_fallback")
            return False

        try:
            ttl = ttl or self._ttl
            serialized = json.dumps(value)
            await self._client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error("redis_set_failed", key=key, error=str(e))
            return False

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from memory.

        Args:
            key: Memory key

        Returns:
            Stored value or None
        """
        if self._client is None:
            return None

        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("redis_get_failed", key=key, error=str(e))
            return None

    async def delete(self, key: str) -> bool:
        """
        Delete a key from memory.

        Args:
            key: Memory key

        Returns:
            True if successful
        """
        if self._client is None:
            return False

        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.error("redis_delete_failed", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Memory key

        Returns:
            True if key exists
        """
        if self._client is None:
            return False

        try:
            return await self._client.exists(key) > 0
        except Exception as e:
            logger.error("redis_exists_check_failed", key=key, error=str(e))
            return False


# Global instance
_memory: Optional[ShortTermMemory] = None


async def get_short_term_memory() -> ShortTermMemory:
    """Get global short-term memory instance."""
    global _memory
    if _memory is None:
        _memory = ShortTermMemory()
        await _memory.connect()
    return _memory


async def store_session(session_id: str, data: dict[str, Any], ttl: int = 86400) -> bool:
    """Store session data."""
    memory = await get_short_term_memory()
    return await memory.set(f"session:{session_id}", data, ttl)


async def get_session(session_id: str) -> Optional[dict[str, Any]]:
    """Get session data."""
    memory = await get_short_term_memory()
    return await memory.get(f"session:{session_id}")


async def delete_session(session_id: str) -> bool:
    """Delete session data."""
    memory = await get_short_term_memory()
    return await memory.delete(f"session:{session_id}")
