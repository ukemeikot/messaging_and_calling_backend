"""
Pydantic schemas for contact management.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid

class ContactStatus(str, Enum):
    """Contact relationship status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"

class ContactRequest(BaseModel):
    """Schema for sending contact request."""
    contact_user_id: uuid.UUID = Field(
        ...,
        description="UUID of user to add as contact"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "contact_user_id": "550e8400-e29b-41d4-a716-446655440000"
                }
            ]
        }
    }

class ContactUserInfo(BaseModel):
    """Basic user info for contact display."""
    id: uuid.UUID
    username: str
    full_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    bio: Optional[str] = None
    is_verified: bool
    
    model_config = {
        "from_attributes": True
    }

class ContactResponse(BaseModel):
    """Schema for contact relationship."""
    id: uuid.UUID
    user_id: uuid.UUID
    contact_user_id: uuid.UUID
    status: ContactStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Populated contact user info
    contact_info: ContactUserInfo
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "contact_user_id": "660e8400-e29b-41d4-a716-446655440001",
                    "status": "accepted",
                    "created_at": "2024-12-15T10:00:00Z",
                    "updated_at": "2024-12-15T11:00:00Z",
                    "contact_info": {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "username": "john_doe",
                        "full_name": "John Doe",
                        "profile_picture_url": "https://...",
                        "bio": "Software developer",
                        "is_verified": True
                    }
                }
            ]
        }
    }

class ContactListResponse(BaseModel):
    """Schema for list of contacts."""
    contacts: List[ContactResponse]
    total: int
    pending_requests: int  # Number of pending incoming requests
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "contacts": [],
                    "total": 5,
                    "pending_requests": 2
                }
            ]
        }
    }

class PendingRequestResponse(BaseModel):
    """Schema for pending contact request."""
    id: uuid.UUID
    from_user: ContactUserInfo  # Person who sent the request
    created_at: datetime
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "from_user": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "username": "ukeme_ikot",
                        "full_name": "Ukeme Ikot",
                        "profile_picture_url": "https://...",
                        "is_verified": True
                    },
                    "created_at": "2024-12-15T10:00:00Z"
                }
            ]
        }
    }

class BlockedUserResponse(BaseModel):
    """Schema for blocked user."""
    id: uuid.UUID
    blocked_user: ContactUserInfo
    blocked_at: datetime
    
    model_config = {
        "from_attributes": True
    }