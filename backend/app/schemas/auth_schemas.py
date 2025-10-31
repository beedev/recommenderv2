"""
Pydantic schemas for authentication API endpoints.

Request and response models for user authentication, registration,
token management, and profile operations.
"""

from typing import Optional
from pydantic import BaseModel, Field, EmailStr, validator


# =============================================================================
# REQUEST MODELS
# =============================================================================

class LoginRequest(BaseModel):
    """User login request model."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")
    rememberMe: bool = Field(False, description="Remember user login")


class RegisterRequest(BaseModel):
    """User registration request model."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    confirmPassword: str = Field(..., min_length=8, description="Confirm password")
    firstName: str = Field(..., min_length=1, max_length=100, description="First name")
    lastName: str = Field(..., min_length=1, max_length=100, description="Last name")

    @validator('confirmPassword')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class RefreshTokenRequest(BaseModel):
    """Refresh token request model."""
    refreshToken: str = Field(..., description="Refresh token")


class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    currentPassword: str = Field(..., description="Current password")
    newPassword: str = Field(..., min_length=8, description="New password")
    confirmPassword: str = Field(..., min_length=8, description="Confirm new password")

    @validator('confirmPassword')
    def passwords_match(cls, v, values):
        if 'newPassword' in values and v != values['newPassword']:
            raise ValueError('Passwords do not match')
        return v


class ForgotPasswordRequest(BaseModel):
    """Forgot password request model."""
    email: EmailStr = Field(..., description="User email address")


class ResetPasswordRequest(BaseModel):
    """Reset password request model."""
    token: str = Field(..., description="Reset token")
    password: str = Field(..., min_length=8, description="New password")
    confirmPassword: str = Field(..., min_length=8, description="Confirm password")

    @validator('confirmPassword')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class UpdateProfileRequest(BaseModel):
    """Update profile request model."""
    firstName: Optional[str] = Field(None, min_length=1, max_length=100)
    lastName: Optional[str] = Field(None, min_length=1, max_length=100)
    preferences: Optional[dict] = Field(None, description="User preferences")
    avatarUrl: Optional[str] = Field(None, description="Avatar URL")


# =============================================================================
# RESPONSE MODELS
# =============================================================================

class AuthResponse(BaseModel):
    """Authentication response model."""
    user: dict = Field(..., description="User information")
    token: str = Field(..., description="JWT access token")
    refreshToken: str = Field(..., description="Refresh token")
    expiresIn: int = Field(..., description="Token expiration in seconds")
    tokenType: str = Field(default="Bearer", description="Token type")


class RefreshResponse(BaseModel):
    """Token refresh response model."""
    user: dict = Field(..., description="User information")
    token: str = Field(..., description="New JWT access token")
    expiresIn: int = Field(..., description="Token expiration in seconds")


class MessageResponse(BaseModel):
    """Generic message response model."""
    message: str = Field(..., description="Response message")
