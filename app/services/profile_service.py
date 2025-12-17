"""
Profile service - handles profile-related business logic.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.core.security import hash_password, verify_password
from typing import Optional
import uuid

class ProfileService:
    """
    Service for profile management operations.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def update_profile(
        self,
        user: User,
        full_name: Optional[str] = None,
        bio: Optional[str] = None
    ) -> User:
        """
        Update user profile information.
        
        Args:
            user: Current user object
            full_name: New full name (optional)
            bio: New bio (optional)
            
        Returns:
            Updated User object
            
        Note:
            Only updates fields that are provided (not None).
            This allows partial updates.
        """
        
        # Update only provided fields
        if full_name is not None:
            user.full_name = full_name
        
        if bio is not None:
            user.bio = bio
        
        # Commit changes
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password.
        
        Args:
            user: Current user object
            current_password: Current password for verification
            new_password: New password to set
            
        Returns:
            True if password changed successfully
            
        Raises:
            ValueError: If current password is incorrect
            
        Security:
            - Verifies current password first
            - Hashes new password before storage
            - Never stores plain text passwords
        """
        
        # Verify current password
        if not verify_password(current_password, user.hashed_password):  # type: ignore[arg-type]
            raise ValueError("Current password is incorrect")
        
        # Hash new password
        user.hashed_password = hash_password(new_password)
        
        # Save changes
        await self.db.commit()
        await self.db.refresh(user)
        
        return True
    
    async def update_profile_picture(
        self,
        user: User,
        picture_url: str
    ) -> User:
        """
        Update user's profile picture URL.
        
        Args:
            user: Current user object
            picture_url: URL of uploaded profile picture
            
        Returns:
            Updated User object
            
        Note:
            The actual file upload happens separately.
            This method just updates the URL in the database.
        """
        
        user.profile_picture_url = picture_url
        
        await self.db.commit()
        await self.db.refresh(user)
        
        return user