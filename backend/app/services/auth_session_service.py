"""
Authentication Session Service using Redis.

Provides fast session management with Redis caching for:
- Active user session tracking
- Session validation and continuity
- Quick session revocation (logout)
- Multi-device session management
"""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class AuthSessionService:
    """
    Redis-backed authentication session service.

    Features:
    - Fast session validation (no DB query)
    - Active session tracking per user
    - Multi-device session management
    - Quick session revocation
    - Session activity monitoring
    """

    def __init__(self, redis_client: Redis, session_ttl: int = 604800):
        """
        Initialize auth session service.

        Args:
            redis_client: Redis async client
            session_ttl: Session time-to-live in seconds (default: 7 days = 604800s)
        """
        self.redis = redis_client
        self.session_ttl = session_ttl
        self.session_key_prefix = "auth:session:"
        self.user_sessions_prefix = "auth:user:sessions:"

        logger.info("Auth Session Service initialized")

    # =============================================================================
    # SESSION MANAGEMENT
    # =============================================================================

    async def create_session(
        self,
        user_id: int,
        token_jti: str,
        device_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create new auth session in Redis.

        Args:
            user_id: User ID
            token_jti: JWT token ID (jti claim)
            device_info: Optional device information (user_agent, ip_address)

        Returns:
            True if session created successfully
        """
        try:
            # Session data
            session_data = {
                "user_id": user_id,
                "token_jti": token_jti,
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "device_info": device_info or {}
            }

            # Store session by token ID
            session_key = f"{self.session_key_prefix}{token_jti}"
            await self.redis.setex(
                session_key,
                self.session_ttl,
                json.dumps(session_data)
            )

            # Add to user's active sessions set
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            await self.redis.sadd(user_sessions_key, token_jti)
            await self.redis.expire(user_sessions_key, self.session_ttl)

            logger.info(f"Created auth session for user {user_id} (token: {token_jti[:8]}...)")
            return True

        except Exception as e:
            logger.error(f"Failed to create session for user {user_id}: {e}")
            return False

    async def get_session(self, token_jti: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data from Redis.

        Args:
            token_jti: JWT token ID

        Returns:
            Session data or None if not found
        """
        try:
            session_key = f"{self.session_key_prefix}{token_jti}"
            session_json = await self.redis.get(session_key)

            if not session_json:
                return None

            session_data = json.loads(session_json)

            # Update last activity
            session_data["last_activity"] = datetime.utcnow().isoformat()
            await self.redis.setex(
                session_key,
                self.session_ttl,
                json.dumps(session_data)
            )

            return session_data

        except Exception as e:
            logger.error(f"Failed to get session {token_jti}: {e}")
            return None

    async def validate_session(self, token_jti: str) -> bool:
        """
        Validate if session exists and is active.

        Args:
            token_jti: JWT token ID

        Returns:
            True if session is valid
        """
        try:
            session_key = f"{self.session_key_prefix}{token_jti}"
            exists = await self.redis.exists(session_key)
            return bool(exists)

        except Exception as e:
            logger.error(f"Failed to validate session {token_jti}: {e}")
            return False

    async def revoke_session(self, token_jti: str) -> bool:
        """
        Revoke a specific session (logout from one device).

        Args:
            token_jti: JWT token ID to revoke

        Returns:
            True if session revoked successfully
        """
        try:
            # Get session to find user_id
            session_data = await self.get_session(token_jti)
            if not session_data:
                return False

            user_id = session_data["user_id"]

            # Delete session
            session_key = f"{self.session_key_prefix}{token_jti}"
            await self.redis.delete(session_key)

            # Remove from user's active sessions
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            await self.redis.srem(user_sessions_key, token_jti)

            logger.info(f"Revoked session for user {user_id} (token: {token_jti[:8]}...)")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke session {token_jti}: {e}")
            return False

    async def revoke_all_user_sessions(self, user_id: int) -> int:
        """
        Revoke all sessions for a user (logout from all devices).

        Args:
            user_id: User ID

        Returns:
            Number of sessions revoked
        """
        try:
            # Get all user sessions
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            token_jtis = await self.redis.smembers(user_sessions_key)

            if not token_jtis:
                return 0

            # Delete all session keys
            session_keys = [f"{self.session_key_prefix}{jti}" for jti in token_jtis]
            deleted_count = await self.redis.delete(*session_keys)

            # Clear user sessions set
            await self.redis.delete(user_sessions_key)

            logger.info(f"Revoked {deleted_count} sessions for user {user_id}")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to revoke all sessions for user {user_id}: {e}")
            return 0

    # =============================================================================
    # SESSION QUERIES
    # =============================================================================

    async def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all active sessions for a user.

        Args:
            user_id: User ID

        Returns:
            List of session data dictionaries
        """
        try:
            # Get all session token IDs for user
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            token_jtis = await self.redis.smembers(user_sessions_key)

            if not token_jtis:
                return []

            # Retrieve all session data
            sessions = []
            for jti in token_jtis:
                session_data = await self.get_session(jti)
                if session_data:
                    sessions.append(session_data)

            # Sort by last activity (most recent first)
            sessions.sort(key=lambda x: x["last_activity"], reverse=True)

            return sessions

        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {e}")
            return []

    async def get_active_session_count(self, user_id: int) -> int:
        """
        Get count of active sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Number of active sessions
        """
        try:
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            count = await self.redis.scard(user_sessions_key)
            return count

        except Exception as e:
            logger.error(f"Failed to get session count for user {user_id}: {e}")
            return 0

    async def extend_session(self, token_jti: str, ttl: Optional[int] = None) -> bool:
        """
        Extend session TTL (keep session alive).

        Args:
            token_jti: JWT token ID
            ttl: New TTL in seconds (default: use configured TTL)

        Returns:
            True if TTL extended successfully
        """
        try:
            session_key = f"{self.session_key_prefix}{token_jti}"
            new_ttl = ttl or self.session_ttl

            # Extend session TTL
            await self.redis.expire(session_key, new_ttl)

            logger.debug(f"Extended session TTL for {token_jti[:8]}... to {new_ttl}s")
            return True

        except Exception as e:
            logger.error(f"Failed to extend session TTL for {token_jti}: {e}")
            return False

    # =============================================================================
    # ADMIN & MONITORING
    # =============================================================================

    async def get_all_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all active sessions in the system (admin only).

        Returns:
            List of all session data
        """
        try:
            pattern = f"{self.session_key_prefix}*"
            session_keys = await self.redis.keys(pattern)

            sessions = []
            for key in session_keys:
                session_json = await self.redis.get(key)
                if session_json:
                    sessions.append(json.loads(session_json))

            return sessions

        except Exception as e:
            logger.error(f"Failed to get all active sessions: {e}")
            return []

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (Redis handles this automatically via TTL).

        Returns:
            Number of sessions cleaned up
        """
        # Redis automatically removes expired keys
        # This method can be used for manual cleanup if needed
        logger.info("Session cleanup triggered (Redis TTL handles automatic cleanup)")
        return 0


# Global service instance
_auth_session_service: Optional[AuthSessionService] = None


def get_auth_session_service() -> AuthSessionService:
    """Get singleton auth session service instance."""
    global _auth_session_service
    if _auth_session_service is None:
        raise RuntimeError("Auth session service not initialized")
    return _auth_session_service


def init_auth_session_service(redis_client: Redis, session_ttl: int = 604800):
    """
    Initialize global auth session service.

    Args:
        redis_client: Redis async client
        session_ttl: Session TTL in seconds (default: 7 days)
    """
    global _auth_session_service
    _auth_session_service = AuthSessionService(redis_client, session_ttl)
    logger.info(f"Auth session service initialized (TTL: {session_ttl}s)")
