"""
Authentication endpoints for user login, registration, and token management.

Comprehensive authentication API endpoints with security best practices and validation.

Features:
- User registration and login
- JWT token management with refresh tokens
- Password management (change, reset)
- User profile management
- Comprehensive error handling and validation
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ...database.database import get_postgres_session
from ...services.auth_service import auth_service, AuthenticationError
from ...services.user_service import user_service, UserNotFoundError, UserAlreadyExistsError
from ...middleware.auth_middleware import get_current_user, get_current_user_optional
from ...models.user import User, UserRole
from ...schemas.auth_schemas import (
    LoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    AuthResponse,
    RefreshResponse,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """Extract client information from request."""
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    # Handle proxy headers
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()

    return user_agent, ip_address


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login(
    login_data: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Authenticate user and return JWT tokens.

    Args:
        login_data: Login credentials
        request: HTTP request for client info
        session: Database session

    Returns:
        Authentication response with tokens and user info
    """
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(
            login_data.email,
            login_data.password,
            session
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Get client information
        user_agent, ip_address = get_client_info(request)

        # Create authentication tokens
        auth_data = await auth_service.create_auth_tokens(
            user, session, user_agent, ip_address
        )

        logger.info(f"User logged in successfully: {user.email}")

        return AuthResponse(**auth_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    registration_data: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Register new user account.

    Args:
        registration_data: Registration form data
        request: HTTP request for client info
        session: Database session

    Returns:
        Authentication response with tokens and user info
    """
    try:
        # Register user
        user = await user_service.register_user(session, registration_data.dict())

        # Get client information
        user_agent, ip_address = get_client_info(request)

        # Create authentication tokens
        auth_data = await auth_service.create_auth_tokens(
            user, session, user_agent, ip_address
        )

        logger.info(f"User registered successfully: {user.email}")

        return AuthResponse(**auth_data)

    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Refresh JWT access token using refresh token.

    Args:
        refresh_data: Refresh token data
        session: Database session

    Returns:
        New access token and user info
    """
    try:
        # Refresh access token
        token_data = await auth_service.refresh_access_token(
            refresh_data.refreshToken,
            session
        )

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        return RefreshResponse(**token_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    refresh_data: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Logout user and revoke refresh token.

    Args:
        refresh_data: Refresh token to revoke
        current_user: Current authenticated user
        session: Database session

    Returns:
        Success message
    """
    try:
        # Revoke refresh token
        await auth_service.revoke_refresh_token(refresh_data.refreshToken, session)

        logger.info(f"User logged out successfully: {current_user.email}")

        return MessageResponse(message="Logged out successfully")

    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


# =============================================================================
# USER PROFILE ENDPOINTS
# =============================================================================

@router.get("/me", response_model=dict)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile.

    Args:
        current_user: Current authenticated user

    Returns:
        User profile information
    """
    return current_user.to_dict()


@router.put("/me", response_model=dict)
async def update_current_user_profile(
    profile_data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Update current user profile.

    Args:
        profile_data: Profile update data
        current_user: Current authenticated user
        session: Database session

    Returns:
        Updated user profile
    """
    try:
        # Update user profile
        updated_user = await user_service.update_user(
            session,
            str(current_user.id),
            profile_data.dict(exclude_unset=True),
            current_user
        )

        logger.info(f"User profile updated: {updated_user.email}")

        return updated_user.to_dict()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


# =============================================================================
# PASSWORD MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Change user password.

    Args:
        password_data: Password change data
        current_user: Current authenticated user
        session: Database session

    Returns:
        Success message
    """
    try:
        # Change password
        await user_service.change_password(
            session,
            str(current_user.id),
            password_data.currentPassword,
            password_data.newPassword
        )

        logger.info(f"Password changed for user: {current_user.email}")

        return MessageResponse(message="Password changed successfully")

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Request password reset email.

    Args:
        forgot_data: Forgot password request data
        session: Database session

    Returns:
        Success message
    """
    try:
        # Check if user exists
        user = await user_service.get_user_by_email(session, forgot_data.email)

        # Always return success for security (don't reveal if email exists)
        # In a real implementation, you would send a password reset email here
        logger.info(f"Password reset requested for email: {forgot_data.email}")

        return MessageResponse(
            message="If the email exists, a password reset link has been sent"
        )

    except Exception as e:
        logger.error(f"Forgot password error: {e}")
        # Still return success for security
        return MessageResponse(
            message="If the email exists, a password reset link has been sent"
        )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    reset_data: ResetPasswordRequest,
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Reset password using reset token.

    Args:
        reset_data: Password reset data
        session: Database session

    Returns:
        Success message
    """
    try:
        # In a real implementation, you would:
        # 1. Validate the reset token
        # 2. Find the user associated with the token
        # 3. Update their password
        # 4. Invalidate the reset token

        # For now, return a placeholder response
        return MessageResponse(message="Password reset functionality not yet implemented")

    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_postgres_session)
):
    """
    Verify email address using verification token.

    Args:
        token: Email verification token
        session: Database session

    Returns:
        Success message
    """
    try:
        # In a real implementation, you would:
        # 1. Validate the verification token
        # 2. Find the user associated with the token
        # 3. Mark their email as verified
        # 4. Invalidate the verification token

        # For now, return a placeholder response
        return MessageResponse(message="Email verification functionality not yet implemented")

    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )
