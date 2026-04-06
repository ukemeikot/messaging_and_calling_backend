"""
Pydantic schemas for user data validation and serialization.

Schemas define:
- Required vs optional data
- Data types and formats
- Validation rules
- Secure response structures
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re
import uuid

# ============================================
# USER REGISTRATION
# ============================================

class UserRegister(BaseModel):
    """
    Schema for user registration request.
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username (3–50 characters, alphanumeric + underscore)",
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password (minimum 8 characters)",
    )
    full_name: Optional[str] = Field(
        None,
        max_length=100,
        description="User's full name",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", value):
            raise ValueError(
                "Username must contain only letters, numbers, and underscores"
            )
        return value.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain at least one number")
        return value

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "ukeme_ikot",
                    "email": "ukeme@example.com",
                    "password": "SecurePass123!",
                    "full_name": "Ukeme Ikot",
                }
            ]
        }
    }

# ============================================
# USER RESPONSE
# ============================================

class UserResponse(BaseModel):
    """
    Schema for user data returned to clients.
    """

    id: uuid.UUID
    username: str
    email: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "username": "ukeme_ikot",
                    "email": "ukeme@example.com",
                    "full_name": "Ukeme Ikot",
                    "bio": "Software Engineer",
                    "profile_picture_url": "https://example.com/avatar.jpg",
                    "is_active": True,
                    "is_verified": False,
                    "created_at": "2024-12-14T10:00:00Z",
                    "updated_at": "2024-12-14T10:00:00Z",
                }
            ]
        },
    }

# ============================================
# AUTH TOKENS
# ============================================

class TokenResponse(BaseModel):
    """
    Authentication token response.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

# ============================================
# VERIFICATION STATUS
# ============================================

class VerificationStatus(BaseModel):
    """
    Indicates verification requirements.
    """

    is_verified: bool
    message: str
    verification_required_for: list[str]

# ============================================
# AUTH RESPONSES
# ============================================

class RegisterResponse(BaseModel):
    """
    Registration success response.
    """

    message: str
    user: UserResponse
    tokens: TokenResponse
    verification_status: VerificationStatus


class UserLogin(BaseModel):
    """
    Login request schema.
    """

    username_or_email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    """
    Login success response.
    """

    message: str
    user: UserResponse
    tokens: TokenResponse

# ============================================
# GOOGLE OAUTH (MOBILE NATIVE)
# ============================================

class GoogleTokenExchange(BaseModel):
    """
    Mobile Google Sign-In ID token exchange.
    """

    id_token: str = Field(
        ...,
        description="Google ID token from mobile Google Sign-In SDK",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE5ZmUyYTdi..."
                }
            ]
        }
    }

# ============================================
# OAUTH RESPONSE
# ============================================

class OAuthCallbackResponse(BaseModel):
    """
    Response after OAuth authentication.
    """

    message: str
    user: UserResponse
    tokens: TokenResponse
    is_new_user: bool

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Authentication successful",
                    "user": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "username": "ukeme_ikot",
                        "email": "ukeme@gmail.com",
                        "full_name": "Ukeme Ikot",
                        "profile_picture_url": "https://lh3.googleusercontent.com/...",
                        "is_active": True,
                        "is_verified": True,
                        "created_at": "2024-12-15T10:00:00Z",
                    },
                    "tokens": {
                        "access_token": "eyJhbGci...",
                        "refresh_token": "eyJhbGci...",
                        "token_type": "bearer",
                        "expires_in": 900,
                    },
                    "is_new_user": True,
                }
            ]
        },
    }

# ============================================
# EMAIL VERIFICATION SCHEMAS
# ============================================

class EmailVerificationRequest(BaseModel):
    """Schema for requesting email verification resend."""
    email: EmailStr = Field(
        ...,
        description="Email address to send verification to"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "ukeme@example.com"
                }
            ]
        }
    }

class PasswordResetRequest(BaseModel):
    """Schema for requesting password reset."""
    email: EmailStr = Field(
        ...,
        description="Email address associated with account"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "ukeme@example.com"
                }
            ]
        }
    }

class PasswordResetConfirm(BaseModel):
    """Schema for confirming password reset."""
    token: str = Field(
        ...,
        description="Password reset token from email"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="New password"
    )
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "new_password": "NewSecurePass123!"
                }
            ]
        }
    }