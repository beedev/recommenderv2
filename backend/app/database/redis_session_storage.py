"""
Redis Session Storage Service.

Provides session caching with:
- Automatic serialization/deserialization
- TTL management
- Session retrieval and storage
"""

import logging
import json
from typing import Optional
from redis.asyncio import Redis

from ..models.conversation import ConversationState

logger = logging.getLogger(__name__)


class RedisSessionStorage:
    """
    Redis-backed session storage service.

    Features:
    - Session caching with configurable TTL
    - Automatic serialization/deserialization
    - Session lifecycle management
    """

    def __init__(self, redis_client: Redis, ttl: int = 3600):
        """
        Initialize Redis session storage.

        Args:
            redis_client: Redis async client
            ttl: Time-to-live for sessions in seconds (default: 3600 = 1 hour)
        """
        self.redis = redis_client
        self.ttl = ttl
        self.key_prefix = "session:"

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session ID."""
        return f"{self.key_prefix}{session_id}"

    async def save_session(self, conversation_state: ConversationState):
        """
        Save conversation state to Redis with TTL.

        Args:
            conversation_state: Conversation state to save
        """
        try:
            session_key = self._session_key(conversation_state.session_id)

            # Serialize conversation state to JSON
            session_data = conversation_state.dict()
            session_json = json.dumps(session_data, default=str)  # default=str handles datetime

            # Store in Redis with TTL
            await self.redis.setex(
                session_key,
                self.ttl,
                session_json
            )

            logger.info(f"Saved session {conversation_state.session_id} to Redis (TTL: {self.ttl}s)")

        except Exception as e:
            logger.error(f"Failed to save session {conversation_state.session_id} to Redis: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        """
        Retrieve conversation state from Redis.

        Args:
            session_id: Session ID to retrieve

        Returns:
            ConversationState or None if not found
        """
        try:
            session_key = self._session_key(session_id)

            # Get from Redis
            session_json = await self.redis.get(session_key)

            if not session_json:
                logger.debug(f"Session {session_id} not found in Redis")
                return None

            # Deserialize JSON to ConversationState
            session_data = json.loads(session_json)
            conversation_state = ConversationState(**session_data)

            logger.info(f"Retrieved session {session_id} from Redis")
            return conversation_state

        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id} from Redis: {e}")
            return None

    async def delete_session(self, session_id: str):
        """
        Delete session from Redis.

        Args:
            session_id: Session ID to delete
        """
        try:
            session_key = self._session_key(session_id)
            await self.redis.delete(session_key)
            logger.info(f"Deleted session {session_id} from Redis")

        except Exception as e:
            logger.error(f"Failed to delete session {session_id} from Redis: {e}")

    async def extend_ttl(self, session_id: str, ttl: Optional[int] = None):
        """
        Extend TTL for an existing session.

        Args:
            session_id: Session ID to extend
            ttl: New TTL (default: use configured TTL)
        """
        try:
            session_key = self._session_key(session_id)
            new_ttl = ttl or self.ttl
            await self.redis.expire(session_key, new_ttl)
            logger.debug(f"Extended TTL for session {session_id} to {new_ttl}s")

        except Exception as e:
            logger.error(f"Failed to extend TTL for session {session_id}: {e}")

    async def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists in Redis.

        Args:
            session_id: Session ID to check

        Returns:
            True if session exists, False otherwise
        """
        try:
            session_key = self._session_key(session_id)
            exists = await self.redis.exists(session_key)
            return bool(exists)

        except Exception as e:
            logger.error(f"Failed to check if session {session_id} exists: {e}")
            return False

    async def get_all_session_ids(self) -> list[str]:
        """
        Get all active session IDs from Redis.

        Returns:
            List of session IDs
        """
        try:
            pattern = f"{self.key_prefix}*"
            keys = await self.redis.keys(pattern)

            # Extract session IDs from keys
            session_ids = [key.replace(self.key_prefix, "") for key in keys]

            return session_ids

        except Exception as e:
            logger.error(f"Failed to get all session IDs: {e}")
            return []


# Global service instance (will be initialized in main.py)
_redis_session_storage: Optional[RedisSessionStorage] = None


def get_redis_session_storage() -> RedisSessionStorage:
    """Get singleton Redis session storage instance."""
    global _redis_session_storage
    if _redis_session_storage is None:
        raise RuntimeError("Redis session storage not initialized")
    return _redis_session_storage


def init_redis_session_storage(redis_client: Redis, ttl: int = 3600):
    """Initialize global Redis session storage instance."""
    global _redis_session_storage
    _redis_session_storage = RedisSessionStorage(redis_client, ttl)
    logger.info("Redis session storage initialized")
