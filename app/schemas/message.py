"""
Pydantic schemas for messaging system.
"""

from pydantic import BaseModel, Field, ConfigDict
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

# ============================================
# MESSAGE SCHEMAS
# ============================================

class MessageCreate(BaseModel):
    """Schema for creating a message."""
    conversation_id: uuid.UUID
    content: str = Field(..., min_length=1, max_length=5000)
    message_type: str = Field(default="text")
    media_url: Optional[str] = None
    reply_to_message_id: Optional[uuid.UUID] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "content": "Hello! How are you?",
                    "message_type": "text"
                }
            ]
        }
    )

class MessageUpdate(BaseModel):
    """Schema for editing a message."""
    content: str = Field(..., min_length=1, max_length=5000)
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "content": "Hello! How are you doing?"
                }
            ]
        }
    )

class MessageSender(BaseModel):
    """Basic sender info for message display."""
    id: uuid.UUID
    username: str
    full_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    """Schema for message in responses."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    message_type: str
    media_url: Optional[str] = None
    is_edited: bool
    is_deleted: bool
    reply_to_message_id: Optional[uuid.UUID] = None
    created_at: datetime
    edited_at: Optional[datetime] = None
    
    # Populated sender info
    sender: MessageSender
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "sender_id": "660e8400-e29b-41d4-a716-446655440001",
                    "content": "Hello! How are you?",
                    "message_type": "text",
                    "created_at": "2024-12-15T10:00:00Z",
                    "is_edited": False,
                    "is_deleted": False,
                    "sender": {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "username": "john_doe"
                    }
                }
            ]
        }
    )

# ============================================
# CONVERSATION SCHEMAS
# ============================================

class ConversationCreate(BaseModel):
    """Schema for creating a conversation."""
    participant_id: uuid.UUID = Field(
        ...,
        description="User ID to start conversation with"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "participant_id": "660e8400-e29b-41d4-a716-446655440001"
                }
            ]
        }
    )

class CreateGroupChat(BaseModel):
    """Schema for creating a group chat."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    participant_ids: List[uuid.UUID]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Project Team",
                    "description": "Official chat for the Q1 project",
                    "participant_ids": ["550e8400-e29b-41d4-a716-446655440001"]
                }
            ]
        }
    )

class ConversationParticipantInfo(BaseModel):
    """Participant info for conversation display."""
    id: uuid.UUID
    username: str
    full_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_verified: bool
    
    model_config = ConfigDict(from_attributes=True)

class ConversationResponse(BaseModel):
    """Schema for conversation in responses."""
    id: uuid.UUID
    is_group: bool
    name: Optional[str] = None
    last_message: Optional[str] = None
    # Fix: Allow None to prevent validation crashes on new conversations
    last_message_at: Optional[datetime] = None
    created_at: datetime
    # Fix: Allow None to prevent 500 error on new records
    updated_at: Optional[datetime] = None
    unread_count: int = 0
    
    other_participant: Optional[ConversationParticipantInfo] = None
    participants: List[ConversationParticipantInfo] = []
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "is_group": False,
                    "last_message": "Hello! How are you?",
                    "created_at": "2024-12-15T09:00:00Z",
                    "unread_count": 3
                }
            ]
        }
    )

class MessageListResponse(BaseModel):
    """Schema for list of messages."""
    messages: List[MessageResponse]
    total: int
    conversation_id: uuid.UUID
    has_more: bool = False
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "messages": [],
                    "total": 50,
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "has_more": True
                }
            ]
        }
    )

# ============================================
# WEBSOCKET SCHEMAS
# ============================================

class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""
    type: str  # send_message, typing_start, typing_stop, message_read, etc.
    data: dict
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "send_message",
                    "data": {
                        "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                        "content": "Hello!"
                    }
                }
            ]
        }
    )