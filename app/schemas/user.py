"""
Pydantic schemas for user data validation and serialization.

Schemas define:
- What data is required vs optional
- Data types (string, int, email, etc.)
- Validation rules (min length, format, etc.)
- What data to return to client (security!)
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re

# ============================================
# USER REGISTRATION
# ============================================

class UserRegister(BaseModel):
    """
    Schema for user registration request.
    
    This validates data when a new user signs up.
    """
    username: str = Field(
        ...,  # Required field
        min_length=3,
        max_length=50,
        description="Username (3-50 characters, alphanumeric + underscore)"
    )
    email: EmailStr = Field(
        ...,  # Required field
        description="Valid email address"
    )
    password: str = Field(
        ...,  # Required field
        min_length=8,
        max_length=100,
        description="Password (minimum 8 characters)"
    )
    full_name: Optional[str] = Field(
        None,  # Optional field
        max_length=100,
        description="User's full name"
    )
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, u_name: str) -> str:
        """
        Validate username format.
        
        Rules:
        - Only letters, numbers, and underscores
        - No spaces or special characters
        - Case insensitive
        
        Why this validation:
        - Prevents SQL injection attempts
        - Ensures usernames work in URLs (@ukeme_ikot)
        - Consistent format across the system
        """
        if not re.match(r'^[a-zA-Z0-9_]+$', u_name):
            raise ValueError(
                'Username must contain only letters, numbers, and underscores'
            )
        return u_name.lower()  # Convert to lowercase for consistency
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, u_password: str) -> str:
        """
        Validate password strength.
        
        Rules:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        
        Why these rules:
        - 8 chars = minimum for reasonable security
        - Mixed case + numbers = harder to crack
        - Industry standard (OWASP recommendation)
        
        Real-world impact:
        - Weak password (lowercase only): Cracked in seconds
        - Strong password (mixed): Cracked in years/never
        """
        if len(u_password) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', u_password):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', u_password):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', u_password):
            raise ValueError('Password must contain at least one number')
        
        return u_password
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "ukeme_ikot",
                    "email": "ukeme@example.com",
                    "password": "SecurePass123!",
                    "full_name": "Ukeme Ikot"
                }
            ]
        }
    }

# ============================================
# USER RESPONSE (What we send back to client)
# ============================================

class UserResponse(BaseModel):
    """
    Schema for user data in API responses.
    
    Security: This excludes sensitive data like hashed_password!
    
    Why we don't send hashed_password:
    - Even hashed passwords shouldn't be exposed
    - No legitimate reason for client to have it
    - Reduces attack surface
    """
    id: int
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
        "from_attributes": True,  # Allows conversion from SQLAlchemy models
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "username": "ukeme_ikot",
                    "email": "ukeme@example.com",
                    "full_name": "Ukeme Ikot",
                    "bio": "Software Engineer specializing in mobile and backend development",
                    "profile_picture_url": "https://example.com/avatars/ukeme.jpg",
                    "is_active": True,
                    "is_verified": False,
                    "created_at": "2024-12-14T10:00:00Z",
                    "updated_at": "2024-12-14T10:00:00Z"
                }
            ]
        }
    }

# ============================================
# AUTHENTICATION RESPONSES
# ============================================

class TokenResponse(BaseModel):
    """
    Schema for authentication token response.
    
    What each field means:
    - access_token: Short-lived token for API requests (15 min)
    - refresh_token: Long-lived token to get new access tokens (7 days)
    - token_type: Always "bearer" (OAuth 2.0 standard)
    - expires_in: Seconds until access token expires
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6InVrZW1lX2lrb3QiLCJleHAiOjE3MzQxODM2MDB9.abc123def456",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTczNDc4ODQwMH0.xyz789uvw012",
                    "token_type": "bearer",
                    "expires_in": 900
                }
            ]
        }
    }

class RegisterResponse(BaseModel):
    """
    Schema for registration success response.
    """
    message: str
    user: UserResponse
    tokens: TokenResponse
    verification_status: VerificationStatus  # NEW!
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "User registered successfully",
                    "user": {
                        "id": 1,
                        "username": "ukeme_ikot",
                        "email": "ukeme@example.com",
                        "full_name": "Ukeme Ikot",
                        "is_active": True,
                        "is_verified": False,  # Not verified yet!
                        "created_at": "2024-12-14T10:00:00Z"
                    },
                    "tokens": {
                        "access_token": "eyJhbGci...",
                        "refresh_token": "eyJhbGci...",
                        "token_type": "bearer",
                        "expires_in": 900
                    },
                    "verification_status": {
                        "is_verified": False,
                        "message": "A verification email has been sent to ukeme@example.com",
                        "verification_required_for": [
                            "Send messages",
                            "Make calls",
                            "Upload media"
                        ]
                    }
                }
            ]
        }
    }

# ============================================
# LOGIN REQUEST
# ============================================

class UserLogin(BaseModel):
    """
    Schema for user login request.
    
    Accepts either username or email + password.
    """
    username_or_email: str = Field(
        ...,
        min_length=3,
        description="Username or email address"
    )
    password: str = Field(
        ...,
        min_length=8,
        description="User password"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username_or_email": "ukeme_ikot",
                    "password": "SecurePass123!"
                },
                {
                    "username_or_email": "ukeme@example.com",
                    "password": "SecurePass123!"
                }
            ]
        }
    }

class LoginResponse(BaseModel):
    """
    Schema for successful login response.
    """
    message: str
    user: UserResponse
    tokens: TokenResponse
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Login successful",
                    "user": {
                        "id": 1,
                        "username": "ukeme_ikot",
                        "email": "ukeme@example.com",
                        "full_name": "Ukeme Ikot",
                        "is_active": True,
                        "is_verified": False,
                        "created_at": "2024-12-14T10:00:00Z"
                    },
                    "tokens": {
                        "access_token": "eyJhbGci...",
                        "refresh_token": "eyJhbGci...",
                        "token_type": "bearer",
                        "expires_in": 900
                    }
                }
            ]
        }
    }

class VerificationStatus(BaseModel):
    """
    Indicates what the user needs to do.
    """
    is_verified: bool
    message: str
    verification_required_for: list[str]  # Features that need verification
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "is_verified": False,
                    "message": "Please check your email to verify your account",
                    "verification_required_for": [
                        "Send messages",
                        "Make voice/video calls",
                        "Upload profile picture",
                        "Add contacts"
                    ]
                }
            ]
        }
    }

