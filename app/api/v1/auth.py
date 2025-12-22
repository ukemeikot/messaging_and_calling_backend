"""
Authentication routes.

Endpoints:
- POST /register - Create new user account
- POST /login - Authenticate user
- GET /me - Get current user details
- POST /resend-verification - Resend verification email
- GET /verify-email - Verify email with token
- POST /forgot-password - Request password reset
- POST /reset-password - Reset password with token
- GET /google/login - Google OAuth (Web)
- GET /google/login/mobile - Google OAuth (Mobile deep link)
- GET /google/callback - Google OAuth callback
- POST /google/token-exchange - Google native token exchange (mobile SDK)
"""

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuthError
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from jose import JWTError
import uuid

from app.database import get_db
from app.models.user import User
from app.services.user_service import UserService
from app.services.oauth_service import oauth, OAuthService
from app.services.email_service import EmailService
from app.core.security import (
    create_access_token, 
    create_refresh_token,
    create_verification_token,
    verify_verification_token,
    create_password_reset_token,
    verify_password_reset_token,
    hash_password
)
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
    EmailVerificationRequest,
    PasswordResetRequest,
    PasswordResetConfirm
)

# Setup logging
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Router
# -------------------------------------------------------------------

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

# -------------------------------------------------------------------
# Background Task for Email Sending
# -------------------------------------------------------------------

async def send_verification_email_task(
    email: str,
    username: str,
    user_id: uuid.UUID
):
    """
    Background task to send verification email.
    Handles errors gracefully without breaking the main flow.
    """
    try:
        email_service = EmailService()
        token = create_verification_token(user_id, email)
        await email_service.send_verification_email(
            to_email=email,
            username=username,
            verification_token=token
        )
        logger.info(f"Verification email sent successfully to {email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {str(e)}")
        # In production, you might want to:
        # 1. Queue this for retry
        # 2. Send to a dead letter queue
        # 3. Alert monitoring system


async def send_password_reset_email_task(
    email: str,
    username: str,
    user_id: uuid.UUID
):
    """
    Background task to send password reset email.
    Handles errors gracefully without breaking the main flow.
    """
    try:
        email_service = EmailService()
        token = create_password_reset_token(user_id, email)
        await email_service.send_password_reset_email(
            to_email=email,
            username=username,
            reset_token=token
        )
        logger.info(f"Password reset email sent successfully to {email}")
    except Exception as e:
        logger.error(f" Failed to send password reset email to {email}: {str(e)}")

# -------------------------------------------------------------------
# AUTH: REGISTER
# -------------------------------------------------------------------

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="""
    Register a new user account.
    
    **Process:**
    1. Validate input (username, email, password)
    2. Check for duplicates
    3. Hash password securely
    4. Create user in database
    5. Send verification email (background)
    6. Return tokens (user can login immediately)
    
    **Note:** User starts as unverified. They can use the app with limited features
    until they verify their email.
    """
)
async def register(
    user_data: UserRegister,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)

    # Check for existing username/email
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

    # Create user
    try:
        user = await user_service.create_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
        )
        logger.info(f"User created: {user.username} ({user.email})")
    except Exception as e:
        logger.error(f" Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "registration_failed",
                "message": "An error occurred during registration.",
            },
        )

    # Schedule verification email in background (non-blocking)
    background_tasks.add_task(
        send_verification_email_task,
        email=user.email,
        username=user.username,
        user_id=user.id
    )
    logger.info(f"📧 Verification email queued for {user.email}")

    # Generate JWT tokens
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
    description="""
    Authenticate user with username/email and password.
    
    **Process:**
    1. Validate credentials
    2. Check account status (active/disabled)
    3. Update last login timestamp
    4. Generate JWT tokens
    5. Return user data + tokens
    
    **Security:**
    - Password verified using Argon2
    - Failed attempts don't reveal which part failed
    - Inactive accounts cannot log in
    """
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

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    token_data = {"user_id": str(user.id), "username": user.username}

    tokens = TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    logger.info(f" User logged in: {user.username}")

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
    description="""
    Get the currently authenticated user's information.
    
    **Authentication Required:** Yes (Bearer token)
    
    **Use cases:**
    - Load user profile on app startup
    - Verify token is still valid
    - Refresh user data after updates
    """
)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

# ============================================
# EMAIL VERIFICATION
# ============================================

@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Resend verification email",
    description="""
    Resend email verification link.
    
    **Use cases:**
    - User didn't receive original email
    - Verification link expired
    - Email went to spam
    
    **Security:**
    - Always returns success (don't reveal if email exists)
    - Rate limited to prevent abuse
    - Token expires in 24 hours
    """
)
async def resend_verification_email(
    request_data: EmailVerificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Resend email verification.
    
    Args:
        request_data: Contains email address
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        Success message (always, for security)
    """
    
    user_service = UserService(db)
    
    # Find user by email
    user = await user_service.get_user_by_email(request_data.email)
    
    # If user exists and not verified, send email
    if user and not user.is_verified:
        background_tasks.add_task(
            send_verification_email_task,
            email=user.email,
            username=user.username,
            user_id=user.id
        )
        logger.info(f"Verification email re-queued for {user.email}")
    elif user and user.is_verified:
        logger.info(f"ℹUser {user.email} already verified, skipping email")
    else:
        logger.info(f"ℹEmail {request_data.email} not found, skipping email (security)")
    
    # Always return success (security: don't reveal if email exists)
    return {
        "message": "Verification email sent",
        "note": "Please check your email and spam folder. Link expires in 24 hours."
    }

@router.get(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="""
    Verify user's email address with token.
    
    **This endpoint is called when user clicks link in email.**
    
    **Flow:**
    1. User clicks "Verify Email" in email
    2. Browser opens: /api/v1/auth/verify-email?token=xyz
    3. Token validated
    4. Email marked as verified
    5. User can now access all features
    
    **Token security:**
    - Expires in 24 hours
    - Single use recommended
    - Cryptographically signed
    """
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify email address.
    
    Args:
        token: Verification token from email
        db: Database session
        
    Returns:
        Success message with redirect URL
        
    Raises:
        HTTPException 400: Invalid or expired token
        HTTPException 404: User not found
    """
    
    # Verify token
    try:
        token_data = verify_verification_token(token)
        logger.info(f"Token verified for user_id: {token_data.get('user_id')}")
    except JWTError as e:
        logger.warning(f"Invalid verification token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_token",
                "message": "Invalid or expired verification token",
                "action": "Request a new verification email"
            }
        )
    
    # Get user
    user_service = UserService(db)
    
    try:
        user_id = uuid.UUID(token_data["user_id"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_token",
                "message": "Invalid token format"
            }
        )
    
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        logger.warning(f"User not found for id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "User not found"
            }
        )
    
    # Check if already verified
    if user.is_verified:
        logger.info(f"ℹ️ User {user.email} already verified")
        return {
            "message": "Email already verified",
            "note": "You can log in and use all features",
            "redirect_url": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/login"
        }
    
    # Verify the email matches (security check)
    if user.email != token_data["email"]:
        logger.warning(f"Email mismatch for user {user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "email_mismatch",
                "message": "Token email does not match user email"
            }
        )
    
    # Mark as verified
    user.is_verified = True
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"Email verified successfully for {user.email}")
    
    # Return success with redirect URL
    return {
        "message": "Email verified successfully!",
        "note": "You can now access all features",
        "redirect_url": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/login?verified=true",
        "features_unlocked": [
            "Send and receive messages",
            "Make voice and video calls",
            "Upload profile pictures",
            "Add and manage contacts"
        ]
    }

# ============================================
# PASSWORD RESET
# ============================================

@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="""
    Request password reset email.
    
    **Flow:**
    1. User enters email
    2. If account exists, reset email sent
    3. User clicks link in email
    4. User enters new password
    
    **Security:**
    - Always returns success (don't reveal if email exists)
    - Token expires in 1 hour
    - Single use only
    - Rate limited to prevent abuse
    """
)
async def forgot_password(
    request_data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset.
    
    Args:
        request_data: Contains email address
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        Success message (always, for security)
    """
    
    user_service = UserService(db)
    
    # Find user by email
    user = await user_service.get_user_by_email(request_data.email)
    
    # If user exists, send reset email
    if user:
        background_tasks.add_task(
            send_password_reset_email_task,
            email=user.email,
            username=user.username,
            user_id=user.id
        )
        logger.info(f" Password reset email queued for {user.email}")
    else:
        logger.info(f"ℹ Email {request_data.email} not found, skipping email (security)")
    
    # Always return success (security: don't reveal if email exists)
    return {
        "message": "Password reset email sent",
        "note": "Please check your email. Link expires in 1 hour.",
        "expiry": "1 hour"
    }

@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="""
    Reset password with token.
    
    **Flow:**
    1. User clicks reset link in email
    2. Frontend shows password form
    3. User enters new password
    4. Frontend calls this endpoint with token + new password
    5. Password updated
    
    **Security:**
    - Token verified (expiry, signature)
    - Password strength validated (handled by schema)
    - Token should be invalidated after use
    """
)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password with token.
    
    Args:
        reset_data: Contains token and new password
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException 400: Invalid token or weak password
        HTTPException 404: User not found
    """
    
    # Verify token
    try:
        token_data = verify_password_reset_token(reset_data.token)
        logger.info(f"Reset token verified for user_id: {token_data.get('user_id')}")
    except JWTError as e:
        logger.warning(f"Invalid reset token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_token",
                "message": "Invalid or expired password reset token",
                "action": "Request a new password reset"
            }
        )
    
    # Get user
    user_service = UserService(db)
    
    try:
        user_id = uuid.UUID(token_data["user_id"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_token",
                "message": "Invalid token format"
            }
        )
    
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        logger.warning(f" User not found for id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": "User not found"
            }
        )
    
    # Verify email matches (security check)
    if user.email != token_data["email"]:
        logger.warning(f" Email mismatch for user {user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "email_mismatch",
                "message": "Token email does not match user email"
            }
        )
    
    # Update password
    user.hashed_password = hash_password(reset_data.new_password)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"✅ Password reset successfully for {user.email}")
    
    return {
        "message": "✅ Password reset successfully!",
        "note": "You can now log in with your new password",
        "action": "Please log in with your new password"
    }

# ===================================================================
# GOOGLE OAUTH — WEB & MOBILE REDIRECT FLOW
# ===================================================================

@router.get(
    "/google/login",
    summary="Google OAuth (Web)",
    description="""
    Initiate Google OAuth flow for web applications.
    
    **Flow:**
    1. User clicks "Login with Google"
    2. Redirects to Google login page
    3. User authenticates
    4. Google redirects to callback
    5. API creates/authenticates user
    6. Returns JSON with tokens
    """
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
    description="""
    Initiate Google OAuth for mobile apps using in-app browser.
    
    **Flow:**
    1. Mobile app opens in-app browser
    2. Redirects to Google login
    3. User authenticates
    4. Redirects to mobile app with tokens in URL
    """
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
    description="""
    Callback endpoint after Google authentication.
    
    **Handles both web and mobile flows based on state parameter.**
    """
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
        logger.error(f"Google OAuth error: {str(e)}")
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

    logger.info(f"Google OAuth successful for {user.email} (new_user={is_new_user})")

    # Check if mobile flow
    if "mobile=true" in request.query_params.get("state", ""):
        scheme = os.getenv("MOBILE_APP_SCHEME", "enterprisemessaging")
        return RedirectResponse(
            f"{scheme}://auth/callback"
            f"?access_token={access_token}"
            f"&refresh_token={refresh_token}"
            f"&is_new_user={str(is_new_user).lower()}"
        )

    # Web flow - return JSON
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
    description="""
    Exchange Google ID token for JWT tokens.
    
    **For mobile apps using Google Sign-In SDK.**
    
    **Flow:**
    1. Mobile app uses @react-native-google-signin
    2. User signs in with Google natively
    3. App receives Google ID token
    4. App sends token to this endpoint
    5. API verifies token with Google
    6. API returns JWT tokens
    
    **Recommended method for mobile apps!**
    """
)
async def google_token_exchange(
    payload: GoogleTokenExchange,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange Google ID token for JWT tokens.
    
    Args:
        payload: Contains Google ID token
        db: Database session
        
    Returns:
        User data and JWT tokens
        
    Raises:
        HTTPException 401: Invalid Google token
    """
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            os.getenv("GOOGLE_CLIENT_ID"),
        )
    except ValueError as e:
        logger.warning(f" Invalid Google token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_google_token",
                "message": f"Invalid or expired Google ID token: {str(e)}",
                "hint": "Make sure you're sending the ID token (not access token)"
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

    logger.info(f" Google token exchange successful for {user.email} (new_user={is_new_user})")

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