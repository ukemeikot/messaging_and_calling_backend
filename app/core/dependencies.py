"""
FastAPI dependencies for authentication and authorization.

Dependencies are reusable functions that FastAPI calls before route handlers.
They handle common tasks like authentication, validation, etc.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.security import decode_token
from app.services.user_service import UserService
from app.models.user import User
from jose import JWTError
import uuid

# Security scheme (extracts Bearer token from Authorization header)
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user.
    
    How it works:
    1. Extract token from Authorization header
    2. Decode and verify token
    3. Get user_id from token
    4. Load user from database
    5. Return user object
    
    Usage in routes:
        @app.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id, "username": user.username}
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        Current authenticated User object
        
    Raises:
        HTTPException 401: Invalid/expired token or user not found
        
    Security:
        - Verifies token signature (prevents tampering)
        - Checks token expiration
        - Validates user still exists in database
        - Validates user account is active
    """
    
    # Extract token from credentials
    token = credentials.credentials
    
    # Decode and verify token
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Invalid or expired token"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Get and validate user_id from token (it's stored as string)
    user_id_str = payload.get("user_id")
    if user_id_str is None or not isinstance(user_id_str, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Token missing or invalid user information"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Convert string to UUID
    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Invalid user ID format"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    # Get user from database
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)
    
    # Check if user exists
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "user_not_found",
                "message": "User not found"
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_disabled",
                "message": "Your account has been disabled"
            }
        )
    
    return user

async def get_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to require verified user (email verified).
    
    Use this on endpoints that need verified users only.
    
    Usage:
        @app.post("/messages/send")
        async def send_message(user: User = Depends(get_verified_user)):
            # Only verified users reach here
            ...
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Verified User object
        
    Raises:
        HTTPException 403: User email not verified
    """
    
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "email_verification_required",
                "message": "Please verify your email to access this feature",
                "verification_required_for": [
                    "Send messages",
                    "Make voice/video calls",
                    "Upload profile picture",
                    "Add contacts"
                ],
                "actions": [
                    {
                        "type": "resend_email",
                        "label": "Resend Verification Email",
                        "endpoint": "/api/v1/auth/resend-verification"
                    }
                ]
            }
        )
    
    return current_user