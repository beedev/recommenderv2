"""
JWT Authentication Middleware for secure API access.

Comprehensive JWT validation, user context, and permission management.

Features:
- JWT token validation and decoding
- User context injection into requests
- Role-based permission checking
- Secure error handling
- Performance optimization
"""

import logging
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.auth_service import auth_service, AuthenticationError
from ..services.user_service import user_service
from ..models.user import User, UserRole
from ..database.database import get_postgres_session

logger = logging.getLogger(__name__)

# Security scheme for FastAPI docs
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """
    JWT Authentication Middleware.

    Provides token validation, user context, and permission checking
    for protected API endpoints.
    """

    def __init__(self):
        """Initialize authentication middleware."""
        self.auth_service = auth_service
        self.user_service = user_service

    async def get_current_user(self,
                             credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
                             session: AsyncSession = Depends(get_postgres_session)) -> User:
        """
        Get current authenticated user from JWT token.

        Args:
            credentials: Bearer token credentials
            session: Database session

        Returns:
            Current user instance

        Raises:
            HTTPException: If authentication fails
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Decode JWT token
            payload = self.auth_service.decode_access_token(credentials.credentials)
            user_id = payload.get("sub")

            if not user_id:
                raise AuthenticationError("Invalid token payload")

            # Get user from database
            user = await self.user_service.get_user_by_id(session, user_id)

            if not user:
                raise AuthenticationError("User not found")

            if not user.is_active:
                raise AuthenticationError("User account is deactivated")

            return user

        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def get_current_user_optional(self,
                                      credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
                                      session: AsyncSession = Depends(get_postgres_session)) -> Optional[User]:
        """
        Get current user if authenticated, return None if not.

        Args:
            credentials: Bearer token credentials
            session: Database session

        Returns:
            Current user instance or None
        """
        if not credentials:
            return None

        try:
            return await self.get_current_user(credentials, session)
        except HTTPException:
            return None

    def require_permission(self, permission: str):
        """
        Dependency for requiring specific permission.

        Args:
            permission: Required permission string

        Returns:
            Dependency function
        """
        def permission_dependency(current_user: User = Depends(self.get_current_user)) -> User:
            # Note: User model doesn't have has_permission method, using role-based check
            permissions = self.auth_service._get_role_permissions(current_user.role)
            if permission not in permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {permission}",
                )
            return current_user

        return permission_dependency

    def require_role(self, role: UserRole):
        """
        Dependency for requiring specific role.

        Args:
            role: Required user role

        Returns:
            Dependency function
        """
        def role_dependency(current_user: User = Depends(self.get_current_user)) -> User:
            if current_user.role != role.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {role.value}",
                )
            return current_user

        return role_dependency

    def require_admin(self, current_user: User) -> User:
        """
        Dependency for requiring admin role.

        Args:
            current_user: Current authenticated user

        Returns:
            Current user if admin

        Raises:
            HTTPException: If user is not admin
        """
        if current_user.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
        return current_user

    def require_roles(self, allowed_roles: List[UserRole]):
        """
        Dependency for requiring one of multiple roles.

        Args:
            allowed_roles: List of allowed roles

        Returns:
            Dependency function
        """
        def roles_dependency(current_user: User = Depends(self.get_current_user)) -> User:
            if not any(current_user.role == role.value for role in allowed_roles):
                role_names = [role.value for role in allowed_roles]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of these roles required: {', '.join(role_names)}",
                )
            return current_user

        return roles_dependency


# Global middleware instance
auth_middleware = AuthMiddleware()

# Convenience functions for dependency injection
async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
                          session: AsyncSession = Depends(get_postgres_session)) -> User:
    """Get current authenticated user."""
    return await auth_middleware.get_current_user(credentials, session)


async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
                                   session: AsyncSession = Depends(get_postgres_session)) -> Optional[User]:
    """Get current user if authenticated, None if not."""
    return await auth_middleware.get_current_user_optional(credentials, session)


def require_permission(permission: str):
    """Require specific permission."""
    return auth_middleware.require_permission(permission)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role."""
    return auth_middleware.require_admin(current_user)


def require_roles(allowed_roles: List[UserRole]):
    """Require one of multiple roles."""
    return auth_middleware.require_roles(allowed_roles)
