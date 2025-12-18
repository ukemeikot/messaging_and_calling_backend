"""
User service - handles all user-related business logic.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.models.user import User
from app.core.security import hash_password
from typing import Optional, List, Sequence  # <--- Added Sequence here
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
        """
        await self.db.delete(user)
        await self.db.commit()

    async def search_users(
        self, 
        query: str, 
        current_user_id: uuid.UUID, 
        limit: int = 10
    ) -> Sequence[User]:  # <--- Changed List to Sequence
        """
        Search users by username, email, or full name.
        Excludes the current user.
        """
        search_term = f"%{query.lower()}%"
        
        result = await self.db.execute(
            select(User)
            .where(
                and_(
                    User.id != current_user_id,  # Don't show myself
                    User.is_active == True,      # Only active users
                    or_(
                        User.username.ilike(search_term),
                        User.email.ilike(search_term),
                        User.full_name.ilike(search_term)
                    )
                )
            )
            .limit(limit)
        )
        return result.scalars().all()