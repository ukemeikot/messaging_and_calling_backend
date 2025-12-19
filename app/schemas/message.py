from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from enum import Enum

class MessageType(str, Enum):
    """Enum for validation."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    SYSTEM = "system"

# --- Requests ---

class MessageCreate(BaseModel):
    """Schema for creating a message."""
    conversation_id: uuid.UUID
    content: str = Field(..., min_length=1, max_length=5000)
    message_type: str = Field(default="text")
    media_url: Optional[str] = None
    reply_to_message_id: Optional[uuid.UUID] = None
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "content": "Hello! How are you?",
                    "message_type": "text"
                },
                {
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "content": "Check out this video",
                    "message_type": "video",
                    "media_url": "https://api.example.com/uploads/vid123.mp4"
                }
            ]
        }
    }

class CreateGroupChat(BaseModel):
    """Schema for creating a group chat."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    participant_ids: List[uuid.UUID]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Project Team",
                    "description": "Official chat for the Q1 project",
                    "participant_ids": [
                        "550e8400-e29b-41d4-a716-446655440001",
                        "550e8400-e29b-41d4-a716-446655440002"
                    ]
                }
            ]
        }
    }

# --- Responses ---

class SenderInfo(BaseModel):
    """Minimal user info for message display."""
    id: uuid.UUID
    username: str
    profile_picture_url: Optional[str] = None
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "660e8400-e29b-41d4-a716-446655440000",
                    "username": "jdoe",
                    "profile_picture_url": "https://api.example.com/uploads/avatar.jpg"
                }
            ]
        }
    }

class ChatParticipant(BaseModel):
    """Schema for a user inside a conversation."""
    user: SenderInfo  
    is_admin: bool = False
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "is_admin": True,
                    "user": {
                        "id": "660e8400-e29b-41d4-a716-446655440000",
                        "username": "jdoe",
                        "profile_picture_url": "https://api.example.com/uploads/avatar.jpg"
                    }
                }
            ]
        }
    }

class MessageResponse(BaseModel):
    """Schema for message response."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    message_type: str
    media_url: Optional[str] = None
    reply_to_message_id: Optional[uuid.UUID] = None
    created_at: datetime
    is_read: bool
    sender: SenderInfo

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "sender_id": "660e8400-e29b-41d4-a716-446655440000",
                    "content": "Hello world",
                    "message_type": "text",
                    "created_at": "2024-01-01T12:00:00Z",
                    "is_read": True,
                    "sender": {
                        "id": "660e8400-e29b-41d4-a716-446655440000",
                        "username": "jdoe"
                    }
                }
            ]
        }
    }

class ConversationResponse(BaseModel):
    """Schema for conversation list item."""
    id: uuid.UUID
    is_group: bool
    name: Optional[str] = None
    group_image_url: Optional[str] = None
    last_message: Optional[MessageResponse] = None
    # CRITICAL FIX: Made Optional to allow creation before first update
    updated_at: Optional[datetime] = None 
    participants: List[ChatParticipant]
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "is_group": True,
                    "name": "Family Group",
                    "updated_at": "2024-01-01T12:05:00Z",
                    "participants": [
                        {
                            "is_admin": True,
                            "user": {"id": "uuid...", "username": "mom"}
                        },
                        {
                            "is_admin": False,
                            "user": {"id": "uuid...", "username": "dad"}
                        }
                    ],
                    "last_message": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "content": "See you soon!",
                        "sender_id": "660e8400-e29b-41d4-a716-446655440000"
                    }
                }
            ]
        }
    }