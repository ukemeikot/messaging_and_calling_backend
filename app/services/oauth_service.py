"""
OAuth service - handles OAuth authentication (Google, Apple, etc.)
"""

from authlib.integrations.starlette_client import OAuth
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.services.user_service import UserService
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize OAuth
oauth = OAuth()

# Configure Google OAuth
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

class OAuthService:
    """
    Service for OAuth authentication.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
    
    async def authenticate_with_google(
        self,
        user_info: Dict[str, Any]
    ) -> tuple[User, bool]:
        """
        Authenticate user with Google OAuth.
        
        Args:
            user_info: User information from Google
                {
                    "sub": "google-user-id",
                    "email": "user@gmail.com",
                    "name": "User Name",
                    "picture": "https://...",
                    "email_verified": True
                }
        
        Returns:
            Tuple of (User object, is_new_user boolean)
            
        Process:
            1. Check if user exists by email
            2. If exists, return existing user
            3. If not, create new user account
            4. Mark as verified (Google verified the email)
        """
        
        email = user_info.get('email')
        if not email:
            raise ValueError("Email not provided by Google")
        
        # Check if user exists
        user = await self.user_service.get_user_by_email(email)
        
        if user:
            # Existing user - update profile picture if they don't have one
            if not user.profile_picture_url and user_info.get('picture'):
                user.profile_picture_url = user_info.get('picture')
                await self.db.commit()
                await self.db.refresh(user)
            
            return user, False  # Not a new user
        
        # New user - create account
        # Generate username from email
        username = email.split('@')[0]
        
        # Make username unique if it already exists
        original_username = username
        counter = 1
        while await self.user_service.get_user_by_username(username):
            username = f"{original_username}{counter}"
            counter += 1
        
        # Create user (no password needed for OAuth)
        # We'll generate a random password they can change later
        import secrets
        random_password = secrets.token_urlsafe(32)
        
        user = await self.user_service.create_user(
            username=username,
            email=email,
            password=random_password,
            full_name=user_info.get('name')
        )
        
        # Update additional fields
        user.is_verified = user_info.get('email_verified', True)  # Google verified
        user.profile_picture_url = user_info.get('picture')
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user, True  # New user created
    
    def generate_oauth_username(self, email: str, name: Optional[str] = None) -> str:
        """
        Generate a username from email or name.
        
        Args:
            email: User's email
            name: User's full name (optional)
            
        Returns:
            Generated username
            
        Examples:
            email="ukeme@gmail.com" → "ukeme"
            name="Ukeme Ikot" → "ukeme_ikot"
        """
        
        if name:
            # Use name if available
            username = name.lower().replace(' ', '_')
            # Remove special characters
            username = ''.join(c for c in username if c.isalnum() or c == '_')
        else:
            # Use email prefix
            username = email.split('@')[0].lower()
        
        return username