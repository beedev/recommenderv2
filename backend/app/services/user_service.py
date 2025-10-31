"""
User Management Service for comprehensive user operations.

Comprehensive user CRUD operations, profile management, and user administration features.

Features:
- User registration and profile management
- Role-based user administration
- Email verification and password management
- User search and filtering
- Data validation and security
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from ..models.user import User, UserRole
from .auth_service import auth_service, AuthenticationError

logger = logging.getLogger(__name__)


# =============================================================================
# EXCEPTIONS
# =============================================================================

class UserNotFoundError(Exception):
    """Exception raised when user is not found."""
    pass


class UserAlreadyExistsError(Exception):
    """Exception raised when user already exists."""
    pass


# =============================================================================
# USER SERVICE
# =============================================================================

class UserService:
    """
    Comprehensive User Management Service.

    Handles user registration, profile management, administration,
    and user-related business logic with security best practices.
    """

    def __init__(self):
        """Initialize user service."""
        self.auth_service = auth_service

    # =============================================================================
    # USER REGISTRATION AND CREATION
    # =============================================================================

    async def create_user(self, session: AsyncSession, **user_data) -> User:
        """
        Create a new user with validation.

        Args:
            session: Database session
            **user_data: User data fields

        Returns:
            Created user instance

        Raises:
            UserAlreadyExistsError: If email already exists
            ValueError: If validation fails
        """
        # Extract and validate required fields
        email = user_data.get('email', '').lower().strip()
        password = user_data.get('password', '')
        first_name = user_data.get('first_name', '').strip()
        last_name = user_data.get('last_name', '').strip()
        role = user_data.get('role', UserRole.USER.value)

        # Validate required fields
        if not email:
            raise ValueError("Email is required")
        if not password:
            raise ValueError("Password is required")
        if not first_name:
            raise ValueError("First name is required")
        if not last_name:
            raise ValueError("Last name is required")

        # Check if user already exists
        existing_user = await self.get_user_by_email(session, email)
        if existing_user:
            raise UserAlreadyExistsError(f"User with email {email} already exists")

        # Validate password strength
        is_valid, error_msg = self.auth_service.validate_password_strength(password)
        if not is_valid:
            raise ValueError(error_msg)

        # Hash password
        password_hash = self.auth_service.hash_password(password)

        # Generate username from email (part before @)
        username = email.split('@')[0]

        # Create user instance
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=role,
            preferences=user_data.get('preferences', {
                "language": "en",
                "theme": "light",
                "notifications": {
                    "email": True,
                    "push": True,
                    "sparky": True
                }
            }),
            is_active=user_data.get('is_active', True),
            avatar_url=user_data.get('avatar_url')
        )

        # Save to database
        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info(f"User created successfully: {email} (ID: {user.id})")
        return user

    async def register_user(self, session: AsyncSession, registration_data: Dict[str, Any]) -> User:
        """
        Register a new user (public registration).

        Args:
            session: Database session
            registration_data: Registration form data

        Returns:
            Created user instance
        """
        # Validate password confirmation
        password = registration_data.get('password', '')
        confirm_password = registration_data.get('confirmPassword', '')

        if password != confirm_password:
            raise ValueError("Passwords do not match")

        # Create user with default role
        user_data = {
            'email': registration_data.get('email'),
            'password': password,
            'first_name': registration_data.get('firstName'),
            'last_name': registration_data.get('lastName'),
            'role': UserRole.USER.value,  # Default role for public registration
            'is_active': True
        }

        return await self.create_user(session, **user_data)

    # =============================================================================
    # USER RETRIEVAL
    # =============================================================================

    async def get_user_by_id(self, session: AsyncSession, user_id: str) -> Optional[User]:
        """
        Get user by ID.

        Args:
            session: Database session
            user_id: User ID (string or integer)

        Returns:
            User instance or None
        """
        try:
            # Convert string ID to integer for database query
            user_id_int = int(user_id)
            stmt = select(User).where(User.id == user_id_int)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None

    async def get_user_by_email(self, session: AsyncSession, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            session: Database session
            email: User email

        Returns:
            User instance or None
        """
        try:
            stmt = select(User).where(User.email == email.lower().strip())
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None

    async def get_users(self, session: AsyncSession,
                       skip: int = 0,
                       limit: int = 50,
                       search: Optional[str] = None,
                       role: Optional[str] = None,
                       is_active: Optional[bool] = None) -> Tuple[List[User], int]:
        """
        Get users with filtering and pagination.

        Args:
            session: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search term for name or email
            role: Filter by role
            is_active: Filter by active status

        Returns:
            Tuple of (users list, total count)
        """
        try:
            # Build base query
            stmt = select(User)
            count_stmt = select(func.count(User.id))

            # Apply filters
            conditions = []

            if search:
                search_term = f"%{search.lower()}%"
                conditions.append(or_(
                    func.lower(User.email).like(search_term),
                    func.lower(User.first_name).like(search_term),
                    func.lower(User.last_name).like(search_term)
                ))

            if role:
                conditions.append(User.role == role)

            if is_active is not None:
                conditions.append(User.is_active == is_active)

            if conditions:
                stmt = stmt.where(and_(*conditions))
                count_stmt = count_stmt.where(and_(*conditions))

            # Get total count
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar()

            # Apply pagination and ordering
            stmt = stmt.order_by(desc(User.created_at)).offset(skip).limit(limit)

            # Execute query
            result = await session.execute(stmt)
            users = result.scalars().all()

            return list(users), total_count

        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return [], 0

    # =============================================================================
    # USER UPDATES
    # =============================================================================

    async def update_user(self, session: AsyncSession, user_id: str,
                         update_data: Dict[str, Any],
                         current_user: Optional[User] = None) -> User:
        """
        Update user profile.

        Args:
            session: Database session
            user_id: User ID to update
            update_data: Fields to update
            current_user: User making the update (for permission check)

        Returns:
            Updated user instance

        Raises:
            UserNotFoundError: If user not found
            ValueError: If validation fails
            PermissionError: If user lacks permission
        """
        # Get user to update
        user = await self.get_user_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        # Permission check
        if current_user:
            # Users can update their own profile, admins can update anyone
            if str(current_user.id) != user_id and current_user.role != UserRole.ADMIN.value:
                raise PermissionError("You don't have permission to update this user")

        # Update allowed fields
        updatable_fields = {
            'first_name', 'last_name', 'preferences', 'avatar_url'
        }

        # Admin-only fields
        admin_fields = {'role', 'is_active', 'is_email_verified'}

        for field, value in update_data.items():
            if field in updatable_fields:
                setattr(user, field, value)
            elif field in admin_fields and current_user and current_user.role == UserRole.ADMIN.value:
                setattr(user, field, value)
            elif field == 'email':
                # Email updates require special handling
                if value != user.email:
                    # Check if new email already exists
                    existing = await self.get_user_by_email(session, value)
                    if existing and existing.id != user.id:
                        raise ValueError(f"Email {value} is already in use")
                    user.email = value.lower().strip()
                    user.is_email_verified = False  # Reset verification
            elif field in ['password', 'newPassword']:
                # Password updates are handled separately
                continue
            else:
                logger.warning(f"Attempted to update non-updatable field: {field}")

        # Update timestamp
        user.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(user)

        logger.info(f"User updated successfully: {user.email} (ID: {user.id})")
        return user

    async def change_password(self, session: AsyncSession, user_id: str,
                            current_password: str, new_password: str) -> bool:
        """
        Change user password.

        Args:
            session: Database session
            user_id: User ID
            current_password: Current password for verification
            new_password: New password

        Returns:
            True if successful

        Raises:
            UserNotFoundError: If user not found
            AuthenticationError: If current password is wrong
            ValueError: If new password is invalid
        """
        # Get user
        user = await self.get_user_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        # Verify current password
        if not self.auth_service.verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        # Validate new password
        is_valid, error_msg = self.auth_service.validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_msg)

        # Hash and update password
        user.password_hash = self.auth_service.hash_password(new_password)
        user.updated_at = datetime.utcnow()

        # Revoke all existing refresh tokens for security
        await self.auth_service.revoke_all_user_tokens(user.id, session)

        await session.commit()

        logger.info(f"Password changed successfully for user: {user.email}")
        return True

    async def update_last_login(self, session: AsyncSession, user_id: str) -> bool:
        """
        Update user's last login timestamp.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            user = await self.get_user_by_id(session, user_id)
            if user:
                user.last_login_at = datetime.utcnow()
                await session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
            return False

    # =============================================================================
    # USER ADMINISTRATION
    # =============================================================================

    async def deactivate_user(self, session: AsyncSession, user_id: str,
                            admin_user: User) -> bool:
        """
        Deactivate user account.

        Args:
            session: Database session
            user_id: User ID to deactivate
            admin_user: Admin user performing the action

        Returns:
            True if successful

        Raises:
            PermissionError: If admin_user lacks permission
            UserNotFoundError: If user not found
        """
        # Check admin permissions
        if admin_user.role != UserRole.ADMIN.value:
            raise PermissionError("Only admins can deactivate users")

        # Get user
        user = await self.get_user_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        # Don't allow self-deactivation
        if str(admin_user.id) == user_id:
            raise ValueError("Cannot deactivate your own account")

        # Deactivate user and revoke tokens
        user.is_active = False
        user.updated_at = datetime.utcnow()

        await self.auth_service.revoke_all_user_tokens(int(user_id), session)
        await session.commit()

        logger.info(f"User deactivated by admin {admin_user.email}: {user.email}")
        return True

    async def delete_user(self, session: AsyncSession, user_id: str,
                         admin_user: User) -> bool:
        """
        Permanently delete user account.

        Args:
            session: Database session
            user_id: User ID to delete
            admin_user: Admin user performing the action

        Returns:
            True if successful

        Raises:
            PermissionError: If admin_user lacks permission
            UserNotFoundError: If user not found
        """
        # Check admin permissions
        if admin_user.role != UserRole.ADMIN.value:
            raise PermissionError("Only admins can delete users")

        # Get user
        user = await self.get_user_by_id(session, user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        # Don't allow self-deletion
        if str(admin_user.id) == user_id:
            raise ValueError("Cannot delete your own account")

        # Delete user (cascade will handle refresh tokens)
        await session.delete(user)
        await session.commit()

        logger.info(f"User deleted by admin {admin_user.email}: {user.email}")
        return True

    # =============================================================================
    # UTILITY METHODS
    # =============================================================================

    async def get_user_stats(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Get user statistics for admin dashboard.

        Args:
            session: Database session

        Returns:
            Dictionary with user statistics
        """
        try:
            # Total users
            total_stmt = select(func.count(User.id))
            total_result = await session.execute(total_stmt)
            total_users = total_result.scalar()

            # Active users
            active_stmt = select(func.count(User.id)).where(User.is_active == True)
            active_result = await session.execute(active_stmt)
            active_users = active_result.scalar()

            # Users by role
            role_stmt = select(User.role, func.count(User.id)).group_by(User.role)
            role_result = await session.execute(role_stmt)
            users_by_role = dict(role_result.all())

            # Recent users (last 30 days)
            recent_date = datetime.utcnow() - timedelta(days=30)
            recent_stmt = select(func.count(User.id)).where(User.created_at >= recent_date)
            recent_result = await session.execute(recent_stmt)
            recent_users = recent_result.scalar()

            return {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "users_by_role": users_by_role,
                "recent_registrations": recent_users
            }

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}


# Global user service instance
user_service = UserService()
