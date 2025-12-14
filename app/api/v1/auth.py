"""
Authentication routes.

Endpoints:
- POST /register - Create new user account
- POST /login - Authenticate user (coming next)
- POST /refresh - Get new access token (coming next)
- POST /resend-verification - Resend verification email (coming later)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.user import (
    UserRegister,
    RegisterResponse,
    UserResponse,
    TokenResponse,
    LoginResponse,
    UserLogin,
    VerificationStatus
)
from app.services.user_service import UserService
from app.core.security import create_access_token, create_refresh_token
import os
from app.core.dependencies import get_current_user
from app.models.user import User

# Create router with prefix and tags
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# Get token expiration from environment
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="""
    Register a new user account.
    
    **Process:**
    1. Validate input data (Pydantic handles this)
    2. Check if username/email already exists
    3. Hash password securely (Argon2)
    4. Create user in database
    5. Generate authentication tokens
    6. Return user data + tokens
    
    **Security:**
    - Password is hashed (never stored in plain text)
    - Tokens are JWT signed (can't be tampered with)
    - User starts as unverified (hybrid approach)
    
    **Next Steps for User:**
    - User receives verification email (we'll add this later)
    - User can explore app with limited features
    - User verifies email to unlock all features
    """
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    Args:
        user_data: Registration data (validated by Pydantic)
        db: Database session (injected by FastAPI)
        
    Returns:
        RegisterResponse with user info, tokens, and verification status
        
    Raises:
        HTTPException 400: If username or email already exists
        HTTPException 500: If database error occurs
    """
    
    # Create user service instance
    user_service = UserService(db)
    
    # Check if user already exists
    exists = await user_service.user_exists(
        username=user_data.username,
        email=user_data.email
    )
    
    # If username taken, return error
    if exists["username_exists"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "username_taken",
                "message": f"Username '{user_data.username}' is already taken",
                "field": "username"
            }
        )
    
    # If email taken, return error
    if exists["email_exists"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "email_taken",
                "message": f"Email '{user_data.email}' is already registered",
                "field": "email"
            }
        )
    
    # Create the user
    try:
        new_user = await user_service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name
        )
    except Exception as e:
        # Log the error (we'll add proper logging later)
        print(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "registration_failed",
                "message": "An error occurred during registration. Please try again."
            }
        )
    
    # Generate authentication tokens
    token_data = {
        "user_id": new_user.id,
        "username": new_user.username
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Create token response
    tokens = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert minutes to seconds
    )
    
    # Create verification status
    verification_status = VerificationStatus(
        is_verified=new_user.is_verified,
        message=f"A verification email has been sent to {new_user.email}",
        verification_required_for=[
            "Send messages",
            "Make voice/video calls",
            "Upload profile picture",
            "Add contacts"
        ]
    )
    
    # Convert SQLAlchemy model to Pydantic model
    user_response = UserResponse.model_validate(new_user)
    
    # Return complete response
    return RegisterResponse(
        message="User registered successfully",
        user=user_response,
        tokens=tokens,
        verification_status=verification_status
    )

@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="""
    Authenticate user and return tokens.
    
    **Process:**
    1. Accept username OR email (flexible login)
    2. Find user in database
    3. Verify password (constant-time comparison)
    4. Check if account is active
    5. Generate new tokens
    6. Update last_login timestamp
    7. Return user data + tokens
    
    **Security:**
    - Password verified using Argon2
    - Failed attempts don't reveal which part failed (username or password)
    - Returns same error for missing user or wrong password (prevents enumeration)
    - Inactive accounts cannot log in
    
    **Error Responses:**
    - 401: Invalid credentials (wrong username/email or password)
    - 403: Account disabled/inactive
    """
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.
    
    Args:
        login_data: Login credentials (username/email + password)
        db: Database session
        
    Returns:
        LoginResponse with user info and tokens
        
    Raises:
        HTTPException 401: Invalid credentials
        HTTPException 403: Account inactive
    """
    
    # Create user service
    user_service = UserService(db)
    
    # Authenticate user
    user = await user_service.authenticate_user(
        username_or_email=login_data.username_or_email,
        password=login_data.password
    )
    
    # If authentication failed
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_credentials",
                "message": "Invalid username/email or password"
            }
        )
    
    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_disabled",
                "message": "Your account has been disabled. Please contact support."
            }
        )
    
    # Update last login timestamp
    from datetime import datetime, timezone
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    
    # Generate tokens
    token_data = {
        "user_id": user.id,
        "username": user.username
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Create token response
    tokens = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    # Convert to Pydantic model
    user_response = UserResponse.model_validate(user)
    
    # Return response
    return LoginResponse(
        message="Login successful",
        user=user_response,
        tokens=tokens
    )

@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="""
    Get the currently authenticated user's information.
    
    **Authentication Required:** Yes (Bearer token)
    
    **How to use:**
    1. Login to get access token
    2. Add token to Authorization header: `Bearer <token>`
    3. Call this endpoint
    4. Receive your user information
    
    **Use cases:**
    - Load user profile on app startup
    - Verify token is still valid
    - Refresh user data after updates
    
    **Error Responses:**
    - 401: Invalid/expired token
    - 403: Account disabled
    """
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user.
    
    Args:
        current_user: Injected by get_current_user dependency
        
    Returns:
        UserResponse with current user data
        
    Security:
        - Requires valid JWT token in Authorization header
        - Token must not be expired
        - User must exist and be active
    """
    
    # Convert to Pydantic model
    return UserResponse.model_validate(current_user)