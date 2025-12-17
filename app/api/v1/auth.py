"""
Authentication routes.

Endpoints:
- POST /register - Create new user account
- POST /login - Authenticate user
- POST /refresh - Get new access token (coming next)
- GET /me - Get current user details
- GET /google/login - Initiate Google OAuth
- GET /google/callback - Handle Google OAuth return
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.user import (
    UserRegister,
    RegisterResponse,
    UserResponse,
    TokenResponse,
    LoginResponse,
    UserLogin,
    VerificationStatus,
    OAuthCallbackResponse
)
from app.services.user_service import UserService
from app.core.security import create_access_token, create_refresh_token
import os
from app.core.dependencies import get_current_user
from app.models.user import User
from authlib.integrations.starlette_client import OAuthError
from app.services.oauth_service import oauth, OAuthService

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
    description="Register a new user account with email and password."
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
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
        "user_id": str(new_user.id),
        "username": new_user.username
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    tokens = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
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
    
    user_response = UserResponse.model_validate(new_user)
    
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
    description="Authenticate user and return tokens."
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    user_service = UserService(db)
    
    # Authenticate user
    user = await user_service.authenticate_user(
        username_or_email=login_data.username_or_email,
        password=login_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_credentials",
                "message": "Invalid username/email or password"
            }
        )
    
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
    
    token_data = {
        "user_id": str(user.id),
        "username": user.username
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    tokens = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    user_response = UserResponse.model_validate(user)
    
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
    description="Get the currently authenticated user's information."
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    return UserResponse.model_validate(current_user)

# ============================================
# OAUTH AUTHENTICATION
# ============================================

@router.get(
    "/google/login",
    summary="Initiate Google OAuth login",
    description="Redirect user to Google login page."
)
async def google_login(request: Request):
    """
    Initiate Google OAuth flow.
    """
    # 1. Safely get the client using create_client
    client = oauth.create_client('google')
    if not client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth client not configured"
        )
        
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI')
    return await client.authorize_redirect(request, redirect_uri)

@router.get(
    "/google/callback",
    response_model=OAuthCallbackResponse,
    summary="Google OAuth callback",
    description="Callback endpoint after Google authentication."
)
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Google OAuth callback.
    """
    # 1. Safely get the client
    client = oauth.create_client('google')
    if not client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth client not configured"
        )

    try:
        # 2. Use the client instance to get token
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "oauth_failed",
                "message": f"Google authentication failed: {str(e)}"
            }
        )
    
    # Get user info from Google
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_user_info",
                "message": "Could not get user information from Google"
            }
        )
    
    # Authenticate or create user
    oauth_service = OAuthService(db)
    
    try:
        user, is_new_user = await oauth_service.authenticate_with_google(user_info)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "authentication_failed",
                "message": f"Failed to authenticate user: {str(e)}"
            }
        )
    
    # Generate JWT tokens
    token_data = {
        "user_id": str(user.id),
        "username": user.username
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    tokens = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    # Convert to Pydantic model
    user_response = UserResponse.model_validate(user)
    
    # Return response
    return OAuthCallbackResponse(
        message="Authentication successful" if not is_new_user else "Account created successfully",
        user=user_response,
        tokens=tokens,
        is_new_user=is_new_user
    )