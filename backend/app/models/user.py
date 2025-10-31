"""
User authentication models compatible with existing database schema.

Updated models to work with existing integer-based user ID system.
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from ..database.database import Base
import re


class UserRole(str, Enum):
    """User roles with clear permissions hierarchy."""
    ADMIN = "admin"      # Full system access
    MANAGER = "manager"  # Department management access
    USER = "user"        # Standard user access


class User(Base):
    """
    User model compatible with existing database schema.

    Uses integer primary keys to match existing database structure.
    """

    __tablename__ = "users"

    # Primary key (integer to match existing schema)
    id = Column(Integer, primary_key=True, index=True)

    # Basic user information
    username = Column(String(100), nullable=False, unique=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profile information
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # User status and permissions
    role = Column(String(20), nullable=False, default=UserRole.USER.value)
    is_active = Column(Boolean, nullable=False, default=True)

    # Enhanced authentication fields (added by migration)
    is_email_verified = Column(Boolean, nullable=False, default=False)
    avatar_url = Column(String(500), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # User preferences (JSON field)
    preferences = Column(JSON, nullable=False, default={
        "language": "en",
        "theme": "light",
        "notifications": {
            "email": True,
            "push": True,
            "sparky": True
        }
    })

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    @validates('email')
    def validate_email(self, key, address):
        """Validate email format."""
        if not address:
            raise ValueError("Email address is required")

        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, address):
            raise ValueError("Invalid email format")

        return address.lower().strip()

    @validates('role')
    def validate_role(self, key, role):
        """Validate user role."""
        if role not in [r.value for r in UserRole]:
            raise ValueError(f"Invalid role: {role}")
        return role

    def to_dict(self, include_sensitive=False) -> Dict[str, Any]:
        """
        Convert user to dictionary.

        Args:
            include_sensitive: Whether to include sensitive fields

        Returns:
            User data as dictionary
        """
        user_data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "role": self.role,
            "isActive": self.is_active,
            "isEmailVerified": self.is_email_verified,
            "avatarUrl": self.avatar_url,
            "preferences": self.preferences,
            "lastLoginAt": self.last_login_at.isoformat() if self.last_login_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None
        }

        if include_sensitive:
            user_data["passwordHash"] = self.password_hash

        return user_data

    def update_last_login(self) -> None:
        """Update last login timestamp."""
        self.last_login_at = datetime.utcnow()

    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN.value

    def is_manager(self) -> bool:
        """Check if user has manager role or higher."""
        return self.role in [UserRole.ADMIN.value, UserRole.MANAGER.value]

    def __repr__(self) -> str:
        """String representation of user."""
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class RefreshToken(Base):
    """
    Refresh token model for JWT authentication.

    Stores refresh tokens with metadata for security tracking.
    """

    __tablename__ = "refresh_tokens"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # User relationship (integer FK to match existing users table)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Token data (hashed for security)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)

    # Expiration and status
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_revoked = Column(Boolean, nullable=False, default=False, index=True)

    # Security metadata
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(INET, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    @validates('token_hash')
    def validate_token_hash(self, key, token_hash):
        """Validate token hash."""
        if not token_hash:
            raise ValueError("Token hash is required")
        if len(token_hash) < 32:
            raise ValueError("Token hash too short")
        return token_hash

    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)."""
        return not self.is_revoked and not self.is_expired()

    def revoke(self) -> None:
        """Revoke the refresh token."""
        self.is_revoked = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert refresh token to dictionary."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "expires_at": self.expires_at.isoformat(),
            "is_revoked": self.is_revoked,
            "user_agent": self.user_agent,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "created_at": self.created_at.isoformat()
        }

    def __repr__(self) -> str:
        """String representation of refresh token."""
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, expired={self.is_expired()})>"
