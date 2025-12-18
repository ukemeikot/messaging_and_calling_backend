"""
OAuth service - handles OAuth authentication (Google, Apple, etc.)

Supports:
- Web OAuth flow (redirect-based)
- Mobile native OAuth (token exchange)
"""

import os
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from app.models.user import User
from app.services.user_service import UserService

load_dotenv()

# ======================================================
# OAUTH CLIENT REGISTRATION
# ======================================================

oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
    },
)

# ======================================================
# OAUTH SERVICE
# ======================================================

class OAuthService:
    """
    OAuth authentication service.

    Supports:
    - Web OAuth (redirect flows)
    - Mobile OAuth (Google Sign-In SDK token exchange)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    # --------------------------------------------------
    # GOOGLE AUTH
    # --------------------------------------------------

    async def authenticate_with_google(
        self,
        user_info: Dict[str, Any],
    ) -> tuple[User, bool]:
        """
        Authenticate or create a user using Google OAuth data.

        Args:
            user_info:
                {
                    "sub": "google-user-id",
                    "email": "user@gmail.com",
                    "name": "User Name",
                    "picture": "https://...",
                    "email_verified": True
                }

        Returns:
            (User, is_new_user)
        """

        email = user_info.get("email")
        if not email:
            raise ValueError("Email not provided by Google")

        # ----------------------------------------------
        # EXISTING USER
        # ----------------------------------------------

        user = await self.user_service.get_user_by_email(email)

        if user:
            # Update profile picture if missing
            if not user.profile_picture_url and user_info.get("picture"):
                user.profile_picture_url = user_info.get("picture")

            # Update last login
            user.last_login = datetime.now(timezone.utc)

            await self.db.commit()
            await self.db.refresh(user)

            return user, False

        # ----------------------------------------------
        # NEW USER
        # ----------------------------------------------

        username = self.generate_oauth_username(
            email=email,
            name=user_info.get("name"),
        )

        # Ensure username uniqueness
        original_username = username
        counter = 1
        while await self.user_service.get_user_by_username(username):
            username = f"{original_username}{counter}"
            counter += 1

        # Generate a secure random password
        random_password = secrets.token_urlsafe(32)

        user = await self.user_service.create_user(
            username=username,
            email=email,
            password=random_password,
            full_name=user_info.get("name"),
        )

        # Mark verified (Google already verified email)
        user.is_verified = user_info.get("email_verified", True)
        user.profile_picture_url = user_info.get("picture")
        user.last_login = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(user)

        return user, True

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------

    def generate_oauth_username(
        self,
        email: str,
        name: Optional[str] = None,
    ) -> str:
        """
        Generate a clean username from Google data.

        Examples:
            email="ukeme@gmail.com" → "ukeme"
            name="Ukeme Ikot" → "ukeme_ikot"
        """

        if name:
            username = name.lower().replace(" ", "_")
            username = "".join(
                c for c in username if c.isalnum() or c == "_"
            )
            return username[:50]

        return email.split("@")[0].lower()
