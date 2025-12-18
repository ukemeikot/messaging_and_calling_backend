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
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
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
        hashed_password = hash_password(password)
        
        new_user = User(
            username=username.lower(),
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name
        )
        
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        
        return new_user
    
    async def user_exists(self, username: str, email: str) -> dict:
        username_user = await self.get_user_by_username(username)
        email_user = await self.get_user_by_email(email)
        
        return {
            "username_exists": username_user is not None,
            "email_exists": email_user is not None
        }
    
    async def authenticate_user(self, username_or_email: str, password: str) -> Optional[User]:
        user = await self.get_user_by_email(username_or_email)
        
        if not user:
            user = await self.get_user_by_username(username_or_email)
        
        if not user:
            return None
        
        from app.core.security import verify_password
        if not verify_password(password, str(user.hashed_password)):
            return None
        
        return user

    async def delete_user(self, user: User) -> None:
        """
        Permanently delete a user account.
        
        Args:
            user: The user object to delete
        """
        # In the future, you might want to delete related data here first
        # (e.g., profile pictures, messages, etc.) if cascading isn't set up in DB.
        
        await self.db.delete(user)
        await self.db.commit()