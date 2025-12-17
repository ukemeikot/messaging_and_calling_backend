"""
Pydantic schemas for profile management.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

class ProfileUpdate(BaseModel):
    """
    Schema for updating user profile.
    
    All fields are optional - only send what you want to update.
    """
    full_name: Optional[str] = Field(
        None,
        max_length=100,
        description="User's full name"
    )
    bio: Optional[str] = Field(
        None,
        max_length=500,
        description="User bio (max 500 characters)"
    )
    
    @field_validator('bio')
    @classmethod
    def validate_bio(cls, user_bio: Optional[str]) -> Optional[str]:
        """
        Validate bio content.
        
        Rules:
        - Max 500 characters
        - No excessive newlines
        """
        if user_bio is None:
            return user_bio
        
        # Remove excessive whitespace
        user_bio = re.sub(r'\s+', ' ', user_bio).strip()
        
        if len(user_bio) > 500:
            raise ValueError('Bio cannot exceed 500 characters')
        
        return user_bio
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "full_name": "Ukeme Ikot",
                    "bio": "Software Engineer specializing in mobile and backend development. Passionate about building scalable systems."
                }
            ]
        }
    }

class PasswordChange(BaseModel):
    """
    Schema for changing password.
    """
    current_password: str = Field(
        ...,
        min_length=8,
        description="Current password for verification"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="New password (minimum 8 characters)"
    )
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, new_password: str) -> str:
        """
        Validate new password strength.
        """
        if len(new_password) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        if not re.search(r'[A-Z]', new_password):
            raise ValueError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', new_password):
            raise ValueError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', new_password):
            raise ValueError('Password must contain at least one number')
        
        return new_password
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "current_password": "OldPass123!",
                    "new_password": "NewSecurePass456!"
                }
            ]
        }
    }

class ProfilePictureResponse(BaseModel):
    """
    Response after uploading profile picture.
    """
    message: str
    profile_picture_url: str
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "Profile picture uploaded successfully",
                    "profile_picture_url": "https://storage.example.com/profiles/550e8400-e29b-41d4-a716-446655440000.jpg"
                }
            ]
        }
    }