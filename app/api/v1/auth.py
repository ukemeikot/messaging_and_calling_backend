"""
Authentication routes.

Endpoints:
- POST /register - Create new user account
- POST /login - Authenticate user
- GET /me - Get current user details
- GET /google/login - Google OAuth (Web)
- GET /google/login/mobile - Google OAuth (Mobile deep link)
- GET /google/callback - Google OAuth callback
- POST /google/token-exchange - Google native token exchange (mobile SDK)
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuthError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.database import get_db
from app.models.user import User
from app.services.user_service import UserService
from app.services.oauth_service import oauth, OAuthService
from app.core.security import create_access_token, create_refresh_token
from app.core.dependencies import get_current_user
from app.schemas.user import (
    UserRegister,
    RegisterResponse,
    UserResponse,
    TokenResponse,
    LoginResponse,
    UserLogin,
    VerificationStatus,
    OAuthCallbackResponse,
    GoogleTokenExchange,
)

# -------------------------------------------------------------------
# Router
# -------------------------------------------------------------------

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

# -------------------------------------------------------------------
# AUTH: REGISTER
# -------------------------------------------------------------------

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)

    exists = await user_service.user_exists(
        username=user_data.username,
        email=user_data.email,
    )

    if exists["username_exists"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "username_taken",
                "message": f"Username '{user_data.username}' is already taken",
                "field": "username",
            },
        )

    if exists["email_exists"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "email_taken",
                "message": f"Email '{user_data.email}' is already registered",
                "field": "email",
            },
        )

    try:
        user = await user_service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "registration_failed",
                "message": "An error occurred during registration.",
            },
        )

    token_data = {"user_id": str(user.id), "username": user.username}

    tokens = TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return RegisterResponse(
        message="User registered successfully",
        user=UserResponse.model_validate(user),
        tokens=tokens,
        verification_status=VerificationStatus(
            is_verified=user.is_verified,
            message=f"A verification email has been sent to {user.email}",
            verification_required_for=[
                "Send messages",
                "Make voice/video calls",
                "Upload profile picture",
                "Add contacts",
            ],
        ),
    )

# -------------------------------------------------------------------
# AUTH: LOGIN
# -------------------------------------------------------------------

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)

    user = await user_service.authenticate_user(
        username_or_email=login_data.username_or_email,
        password=login_data.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_credentials",
                "message": "Invalid username/email or password",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "account_disabled",
                "message": "Your account has been disabled.",
            },
        )

    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    token_data = {"user_id": str(user.id), "username": user.username}

    tokens = TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return LoginResponse(
        message="Login successful",
        user=UserResponse.model_validate(user),
        tokens=tokens,
    )

# -------------------------------------------------------------------
# AUTH: CURRENT USER
# -------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

# ===================================================================
# GOOGLE OAUTH — WEB & MOBILE REDIRECT FLOW
# ===================================================================

@router.get(
    "/google/login",
    summary="Google OAuth (Web)",
)
async def google_login(request: Request):
    client = oauth.create_client("google")
    if not client:
        raise HTTPException(500, "Google OAuth client not configured")

    return await client.authorize_redirect(
        request,
        os.getenv("GOOGLE_REDIRECT_URI"),
    )


@router.get(
    "/google/login/mobile",
    summary="Google OAuth (Mobile Deep Link)",
)
async def google_login_mobile(request: Request):
    client = oauth.create_client("google")
    if not client:
        raise HTTPException(500, "Google OAuth client not configured")

    return await client.authorize_redirect(
        request,
        os.getenv("GOOGLE_REDIRECT_URI"),
        state="mobile=true",
    )


@router.get(
    "/google/callback",
    summary="Google OAuth Callback",
)
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client = oauth.create_client("google")
    if not client:
        raise HTTPException(500, "Google OAuth client not configured")

    try:
        token = await client.authorize_access_token(request)
    except OAuthError as e:
        if "mobile=true" in request.query_params.get("state", ""):
            scheme = os.getenv("MOBILE_APP_SCHEME", "enterprisemessaging")
            return RedirectResponse(
                f"{scheme}://auth/callback?error=oauth_failed&message={str(e)}"
            )
        raise HTTPException(400, "Google authentication failed")

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(400, "Could not retrieve Google user info")

    oauth_service = OAuthService(db)
    user, is_new_user = await oauth_service.authenticate_with_google(user_info)

    token_data = {"user_id": str(user.id), "username": user.username}

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    if "mobile=true" in request.query_params.get("state", ""):
        scheme = os.getenv("MOBILE_APP_SCHEME", "enterprisemessaging")
        return RedirectResponse(
            f"{scheme}://auth/callback"
            f"?access_token={access_token}"
            f"&refresh_token={refresh_token}"
            f"&is_new_user={str(is_new_user).lower()}"
        )

    return OAuthCallbackResponse(
        message="Authentication successful"
        if not is_new_user
        else "Account created successfully",
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
        is_new_user=is_new_user,
    )

# ===================================================================
# GOOGLE OAUTH — MOBILE NATIVE TOKEN EXCHANGE (SDK)
# ===================================================================

@router.post(
    "/google/token-exchange",
    response_model=OAuthCallbackResponse,
    summary="Google Token Exchange (Mobile Native)",
)
async def google_token_exchange(
    payload: GoogleTokenExchange,
    db: AsyncSession = Depends(get_db),
):
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            os.getenv("GOOGLE_CLIENT_ID"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_google_token",
                "message": str(e),
            },
        )

    user_info = {
        "sub": idinfo["sub"],
        "email": idinfo["email"],
        "name": idinfo.get("name"),
        "picture": idinfo.get("picture"),
        "email_verified": idinfo.get("email_verified", True),
    }

    oauth_service = OAuthService(db)
    user, is_new_user = await oauth_service.authenticate_with_google(user_info)

    token_data = {"user_id": str(user.id), "username": user.username}

    return OAuthCallbackResponse(
        message="Authentication successful"
        if not is_new_user
        else "Account created and authenticated successfully",
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        ),
        is_new_user=is_new_user,
    )
