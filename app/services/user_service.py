"""
User service - handles all user-related business logic.

This layer sits between API routes and database.
Why separate this?
- Reusability: Same logic can be used by different routes
- Testing: Easy to test without HTTP requests
- Clean code: Routes stay thin, logic is here
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.core.security import hash_password
from typing import Optional
import uuid
class UserService:
    """
    Service class for user operations.
    
    Why use a class?
    - Encapsulation: All user logic in one place
    - State management: Can hold db session
    - Testability: Easy to mock
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Find user by email address.
        
        Args:
            email: User's email address
            
        Returns:
            User object if found, None otherwise
            
        Why async?
            Database queries are I/O operations (waiting for response)
            Async allows handling other requests while waiting
        """
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Find user by username.
        
        Args:
            username: User's username
            
        Returns:
            User object if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """
        Find user by UUID.
        
        Args:
            user_id: User's UUID
            
        Returns:
            User object if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None
    ) -> User:
        """
        Create a new user account.
        
        Args:
            username: Desired username (must be unique)
            email: Email address (must be unique)
            password: Plain text password (will be hashed)
            full_name: Optional full name
            
        Returns:
            Created User object
            
        Security:
            - Password is hashed before storage (never store plain text!)
            - Username is lowercase (case-insensitive usernames)
            - is_verified defaults to False (hybrid approach)
            - is_active defaults to True (user can log in immediately)
            
        Process:
            1. Hash password (expensive operation, ~100ms)
            2. Create User object (defaults from model)
            3. Add to database session
            4. Commit transaction
            5. Refresh to get auto-generated fields (id, created_at)
        """
        # Hash the password (slow by design - prevents brute force)
        hashed_password = hash_password(password)
        
        # Create new user object
        # Note: is_active and is_verified use defaults from User model
        # is_active = True (can log in)
        # is_verified = False (needs email verification)
        new_user = User(
            username=username.lower(),  # Store lowercase for consistency
            email=email.lower(),  # Store lowercase for consistency
            hashed_password=hashed_password,
            full_name=full_name
        )
        
        # Add to database session
        self.db.add(new_user)
        
        # Commit transaction (save to database)
        await self.db.commit()
        
        # Refresh to get auto-generated values (id, created_at, etc.)
        await self.db.refresh(new_user)
        
        return new_user
    
    async def user_exists(self, username: str, email: str) -> dict:
        """
        Check if username or email already exists.
        
        Args:
            username: Username to check
            email: Email to check
            
        Returns:
            Dictionary with existence status:
            {
                "username_exists": True/False,
                "email_exists": True/False
            }
            
        Why this method?
            - Returns detailed info (which field is duplicate)
            - Allows better error messages to user
            - Efficient (two separate queries, but fast with indexes)
            
        Example:
            exists = await user_service.user_exists("ukeme", "ukeme@example.com")
            if exists["username_exists"]:
                raise HTTPException(400, "Username taken")
        """
        # Check username (case-insensitive)
        username_user = await self.get_user_by_username(username)
        
        # Check email (case-insensitive)
        email_user = await self.get_user_by_email(email)
        
        return {
            "username_exists": username_user is not None,
            "email_exists": email_user is not None
        }
    
    async def authenticate_user(self, username_or_email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by username/email and password.
        
        Args:
            username_or_email: Username or email address
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
            
        Security:
            - Accepts both username and email for login flexibility
            - Uses constant-time password comparison (prevents timing attacks)
            - Returns None on failure (don't reveal which part failed)
            
        Process:
            1. Find user by username or email
            2. If not found, return None
            3. Verify password against hash
            4. If password wrong, return None
            5. If success, return User object
            
        Note: We'll implement this in the next step for login endpoint
        """
        # Try to find user by email first
        user = await self.get_user_by_email(username_or_email)
        
        # If not found by email, try username
        if not user:
            user = await self.get_user_by_username(username_or_email)
        
        # If still not found, authentication failed
        if not user:
            return None
        
        # Verify password
        from app.core.security import verify_password
        if not verify_password(password, str(user.hashed_password)):
            return None
        
        # Authentication successful
        return user