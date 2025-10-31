"""
JWT Authentication Service for secure user authentication.

Comprehensive JWT token management, password security, and authentication workflows.

Features:
- Secure JWT token generation and validation
- Refresh token management with automatic cleanup
- Password hashing with bcrypt
- Rate limiting and security best practices
- Comprehensive error handling and logging
"""

# Standard library imports
import hashlib
import logging
import secrets
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

# Third-party imports
import bcrypt
import jwt
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Local imports
from ..models.user import RefreshToken, User, UserRole

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class AuthenticationError(Exception):
    """Authentication-related errors."""
    pass


# =============================================================================
# AUTH SERVICE
# =============================================================================

class AuthService:
    """
    Comprehensive JWT Authentication Service.

    Handles all authentication operations including login, registration,
    token management, and password operations with security best practices.
    """

    def __init__(self):
        """Initialize authentication service."""
        # Load JWT settings from environment
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY must be configured in .env")

        # Token settings (load from .env with defaults)
        self.access_token_expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "900")) // 60  # 15 min default
        self.refresh_token_expire_days = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", "604800")) // 86400  # 7 days default
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")

        # Password settings
        self.min_password_length = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))
        self.bcrypt_rounds = int(os.getenv("BCRYPT_ROUNDS", "12"))

        logger.info(f"AuthService initialized (access_token: {self.access_token_expire_minutes}m, refresh_token: {self.refresh_token_expire_days}d)")

    # =============================================================================
    # PASSWORD MANAGEMENT
    # =============================================================================

    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt with salt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        if len(password) < self.min_password_length:
            raise ValueError(f"Password must be at least {self.min_password_length} characters long")

        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=self.bcrypt_rounds)
        password_bytes = password.encode('utf-8')
        hashed = bcrypt.hashpw(password_bytes, salt)

        return hashed.decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password to verify
            hashed_password: Stored hashed password

        Returns:
            True if password matches, False otherwise
        """
        try:
            password_bytes = password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def validate_password_strength(self, password: str) -> Tuple[bool, str]:
        """
        Validate password strength.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < self.min_password_length:
            return False, f"Password must be at least {self.min_password_length} characters long"

        # Check for at least one uppercase, one lowercase, and one digit
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"

        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"

        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"

        return True, ""

    def _get_role_permissions(self, role: str) -> list:
        """
        Get permissions for a given role.

        Args:
            role: User role

        Returns:
            List of permissions for the role
        """
        role_permissions = {
            "admin": [
                "user:read", "user:write", "user:delete",
                "system:read", "system:write", "system:admin",
                "packages:read", "packages:write", "packages:delete",
                "recommendations:read", "recommendations:write"
            ],
            "manager": [
                "user:read", "user:write",
                "packages:read", "packages:write",
                "recommendations:read", "recommendations:write"
            ],
            "user": [
                "packages:read",
                "recommendations:read"
            ]
        }

        return role_permissions.get(role, [])

    # =============================================================================
    # JWT TOKEN MANAGEMENT
    # =============================================================================

    def create_access_token(self, user: User) -> str:
        """
        Create JWT access token for user.

        Args:
            user: User instance

        Returns:
            JWT access token string
        """
        # Token expiration
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)

        # Token payload
        payload = {
            "sub": str(user.id),          # Subject (user ID)
            "email": user.email,
            "role": user.role,
            "permissions": self._get_role_permissions(user.role),
            "exp": expire,                # Expiration time
            "iat": datetime.utcnow(),     # Issued at
            "type": "access"              # Token type
        }

        # Generate and return token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Access token created for user {user.email}")

        return token

    async def create_refresh_token(self, user: User, session: AsyncSession,
                                  user_agent: Optional[str] = None,
                                  ip_address: Optional[str] = None) -> str:
        """
        Create refresh token for user.

        Args:
            user: User instance
            session: Database session
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Refresh token string
        """
        # Generate secure random token
        token = secrets.token_urlsafe(32)

        # Hash token for storage
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Token expiration
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        # Create refresh token record
        refresh_token = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expire,
            user_agent=user_agent,
            ip_address=ip_address
        )

        session.add(refresh_token)
        await session.commit()

        logger.info(f"Refresh token created for user {user.email}")
        return token

    def decode_access_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT access token.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload

        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Validate token type
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")

            return payload

        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    async def validate_refresh_token(self, token: str, session: AsyncSession) -> Optional[User]:
        """
        Validate refresh token and return associated user.

        Args:
            token: Refresh token string
            session: Database session

        Returns:
            User instance if token is valid, None otherwise
        """
        try:
            # Hash the provided token
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            # Find refresh token in database
            stmt = (
                select(RefreshToken)
                .options(selectinload(RefreshToken.user))
                .where(and_(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.is_revoked == False,
                    RefreshToken.expires_at > datetime.utcnow()
                ))
            )

            result = await session.execute(stmt)
            refresh_token = result.scalar_one_or_none()

            if not refresh_token:
                return None

            # Return associated user
            return refresh_token.user

        except Exception as e:
            logger.error(f"Refresh token validation error: {e}")
            return None

    async def revoke_refresh_token(self, token: str, session: AsyncSession) -> bool:
        """
        Revoke a refresh token.

        Args:
            token: Refresh token string
            session: Database session

        Returns:
            True if token was revoked, False if not found
        """
        try:
            # Hash the provided token
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            # Find and revoke refresh token
            stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            result = await session.execute(stmt)
            refresh_token = result.scalar_one_or_none()

            if refresh_token:
                refresh_token.revoke()
                await session.commit()
                logger.info(f"Refresh token revoked: {refresh_token.id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error revoking refresh token: {e}")
            return False

    async def revoke_all_user_tokens(self, user_id: int, session: AsyncSession) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            user_id: User ID
            session: Database session

        Returns:
            Number of tokens revoked
        """
        try:
            # Find all active refresh tokens for user
            stmt = select(RefreshToken).where(and_(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False
            ))

            result = await session.execute(stmt)
            tokens = result.scalars().all()

            # Revoke all tokens
            count = 0
            for token in tokens:
                token.revoke()
                count += 1

            await session.commit()
            logger.info(f"Revoked {count} refresh tokens for user {user_id}")

            return count

        except Exception as e:
            logger.error(f"Error revoking user tokens: {e}")
            return 0

    # =============================================================================
    # AUTHENTICATION WORKFLOWS
    # =============================================================================

    async def authenticate_user(self, email: str, password: str, session: AsyncSession) -> Optional[User]:
        """
        Authenticate user with email and password.

        Args:
            email: User email
            password: User password
            session: Database session

        Returns:
            User instance if authentication successful, None otherwise
        """
        try:
            # Find user by email
            stmt = select(User).where(and_(
                User.email == email.lower().strip(),
                User.is_active == True
            ))

            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"Authentication failed: User not found for email {email}")
                return None

            # Verify password
            if not self.verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed: Invalid password for user {email}")
                return None

            # Update last login time
            user.last_login_at = datetime.utcnow()
            await session.commit()

            logger.info(f"User authenticated successfully: {email}")
            return user

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    async def create_auth_tokens(self, user: User, session: AsyncSession,
                                user_agent: Optional[str] = None,
                                ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Create authentication tokens for user.

        Args:
            user: User instance
            session: Database session
            user_agent: User agent string
            ip_address: Client IP address

        Returns:
            Dictionary containing tokens and user info
        """
        # Create access token
        access_token = self.create_access_token(user)

        # Create refresh token
        refresh_token = await self.create_refresh_token(
            user, session, user_agent, ip_address
        )

        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "role": user.role,
                "isActive": user.is_active,
                "isEmailVerified": user.is_email_verified,
                "preferences": user.preferences
            },
            "token": access_token,
            "refreshToken": refresh_token,
            "expiresIn": self.access_token_expire_minutes * 60,  # Convert to seconds
            "tokenType": "Bearer"
        }

    async def refresh_access_token(self, refresh_token: str, session: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token string
            session: Database session

        Returns:
            New token data if successful, None otherwise
        """
        # Validate refresh token and get user
        user = await self.validate_refresh_token(refresh_token, session)

        if not user or not user.is_active:
            return None

        # Create new access token
        access_token = self.create_access_token(user)

        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "firstName": user.first_name,
                "lastName": user.last_name,
                "role": user.role,
                "isActive": user.is_active,
                "isEmailVerified": user.is_email_verified,
                "preferences": user.preferences
            },
            "token": access_token,
            "expiresIn": self.access_token_expire_minutes * 60
        }

    # =============================================================================
    # CLEANUP OPERATIONS
    # =============================================================================

    async def cleanup_expired_tokens(self, session: AsyncSession) -> int:
        """
        Clean up expired refresh tokens from database.

        Args:
            session: Database session

        Returns:
            Number of tokens cleaned up
        """
        try:
            # Find expired tokens
            stmt = select(RefreshToken).where(
                RefreshToken.expires_at < datetime.utcnow()
            )

            result = await session.execute(stmt)
            expired_tokens = result.scalars().all()

            # Delete expired tokens
            count = len(expired_tokens)
            for token in expired_tokens:
                await session.delete(token)

            await session.commit()

            if count > 0:
                logger.info(f"Cleaned up {count} expired refresh tokens")

            return count

        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
            return 0


# Global authentication service instance
auth_service = AuthService()
