"""
Pydantic schemas for messaging system.

This module defines all request/response schemas for:
- Messages (create, update, response)
- Conversations (create, response, participants)
- Group chat management (add/remove participants)
- WebSocket messages
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime
import uuid
from enum import Enum

class MessageType(str, Enum):
    """Enum for message type validation."""
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
    """
    Schema for creating a new message.
    
    Attributes:
        conversation_id: The conversation to send the message in
        content: Message text content (1-5000 characters)
        message_type: Type of message (default: "text")
        media_url: Optional URL for media attachments
        reply_to_message_id: Optional ID of message being replied to
    """
    conversation_id: uuid.UUID
    content: str = Field(..., min_length=1, max_length=5000)
    message_type: str = Field(default="text")
    media_url: Optional[str] = None
    reply_to_message_id: Optional[uuid.UUID] = None
    
    @field_validator('message_type')
    @classmethod
    def validate_message_type(cls, v):
        """Ensure message_type is valid."""
        valid_types = [mt.value for mt in MessageType]
        if v not in valid_types:
            raise ValueError(f"message_type must be one of: {', '.join(valid_types)}")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "content": "Hello! How are you?",
                    "message_type": "text"
                },
                {
                    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                    "content": "Check out this photo!",
                    "message_type": "image",
                    "media_url": "https://example.com/image.jpg"
                }
            ]
        }
    )

class MessageUpdate(BaseModel):
    """
    Schema for editing an existing message.
    
    Only the content can be updated after sending.
    
    Attributes:
        content: New message content (1-5000 characters)
    """
    content: str = Field(..., min_length=1, max_length=5000)
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "content": "Hello! How are you doing? (edited)"
                }
            ]
        }
    )

class MessageSender(BaseModel):
    """
    Basic sender information for message display.
    
    Attributes:
        id: User UUID
        username: User's unique username
        full_name: User's full name (if set)
        profile_picture_url: URL to user's profile picture
    """
    id: uuid.UUID
    username: str
    full_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    """
    Complete message response schema.
    
    Includes all message data plus populated sender information.
    
    Attributes:
        id: Message UUID
        conversation_id: Parent conversation UUID
        sender_id: Sender's user UUID
        content: Message text content
        message_type: Type of message
        media_url: URL for media attachments (if applicable)
        is_edited: Whether message has been edited
        is_deleted: Whether message has been deleted
        reply_to_message_id: ID of message being replied to (if applicable)
        created_at: When message was created
        edited_at: When message was last edited (if applicable)
        sender: Nested sender information
    """
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
                        "username": "john_doe",
                        "full_name": "John Doe"
                    }
                }
            ]
        }
    )

# ============================================
# CONVERSATION SCHEMAS
# ============================================

class ConversationCreate(BaseModel):
    """
    Schema for creating a 1-on-1 direct message conversation.
    
    Attributes:
        participant_id: UUID of the user to start conversation with
    """
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
    """
    Schema for creating a group chat.
    
    Attributes:
        name: Group chat name (1-100 characters)
        description: Optional group description (max 500 characters)
        participant_ids: List of user UUIDs to add as initial members
    """
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    participant_ids: List[uuid.UUID] = Field(
        ...,
        description="List of user IDs to add to the group"
    )

    @field_validator('participant_ids')
    @classmethod
    def validate_participants(cls, v):
        """Ensure at least one participant and no duplicates."""
        if not v:
            raise ValueError("At least one participant is required")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate participant IDs are not allowed")
        return v

    model_config = ConfigDict(
        json_schema_extra={
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
    )

class AddParticipantsRequest(BaseModel):
    """
    Schema for adding participants to an existing group chat.
    
    Attributes:
        participant_ids: List of user UUIDs to add to the group
    """
    participant_ids: List[uuid.UUID] = Field(
        ...,
        description="List of user IDs to add to the group chat"
    )
    
    @field_validator('participant_ids')
    @classmethod
    def validate_participants(cls, v):
        """Ensure at least one participant and no duplicates."""
        if not v:
            raise ValueError("At least one participant is required")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate participant IDs are not allowed")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "participant_ids": [
                        "550e8400-e29b-41d4-a716-446655440003",
                        "550e8400-e29b-41d4-a716-446655440004"
                    ]
                }
            ]
        }
    )

class RemoveParticipantRequest(BaseModel):
    """
    Schema for removing a participant from a group chat.
    
    Note: Typically used as path parameter, but included for completeness.
    
    Attributes:
        user_id: UUID of the user to remove
    """
    user_id: uuid.UUID = Field(
        ...,
        description="User ID to remove from the group chat"
    )

class ConversationParticipantInfo(BaseModel):
    """
    Participant information for conversation display.
    
    Attributes:
        id: User UUID
        username: User's unique username
        full_name: User's full name (if set)
        profile_picture_url: URL to user's profile picture
        is_verified: Whether user account is verified
        is_admin: Whether user is a group admin (only for groups)
    """
    id: uuid.UUID
    username: str
    full_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_verified: bool = False
    is_admin: Optional[bool] = None  # Only relevant for group chats
    
    model_config = ConfigDict(from_attributes=True)

class ConversationResponse(BaseModel):
    """
    Complete conversation response schema.
    
    Used for both 1-on-1 and group conversations.
    
    Attributes:
        id: Conversation UUID
        is_group: Whether this is a group chat
        name: Group name (only for groups)
        last_message: Preview of most recent message
        last_message_at: Timestamp of most recent message
        created_at: When conversation was created
        updated_at: When conversation was last updated
        unread_count: Number of unread messages for current user
        other_participant: Other user info (only for 1-on-1 chats)
        participants: List of all participants (includes all for groups, both for 1-on-1)
    """
    id: uuid.UUID
    is_group: bool
    name: Optional[str] = None
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    unread_count: int = 0
    
    # For 1-on-1: the other participant
    other_participant: Optional[ConversationParticipantInfo] = None
    # For groups: all participants
    participants: List[ConversationParticipantInfo] = []
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "is_group": False,
                    "last_message": "Hello! How are you?",
                    "last_message_at": "2024-12-15T10:00:00Z",
                    "created_at": "2024-12-15T09:00:00Z",
                    "unread_count": 3,
                    "other_participant": {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "username": "john_doe",
                        "is_verified": True
                    }
                },
                {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "is_group": True,
                    "name": "Project Team",
                    "last_message": "Great work everyone!",
                    "last_message_at": "2024-12-15T14:30:00Z",
                    "created_at": "2024-12-01T09:00:00Z",
                    "unread_count": 5,
                    "participants": [
                        {
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "username": "john_doe",
                            "is_admin": True
                        },
                        {
                            "id": "660e8400-e29b-41d4-a716-446655440002",
                            "username": "jane_smith",
                            "is_admin": False
                        }
                    ]
                }
            ]
        }
    )

class MessageListResponse(BaseModel):
    """
    Paginated list of messages response.
    
    Attributes:
        messages: List of message objects
        total: Total count of messages in conversation
        conversation_id: Parent conversation UUID
        has_more: Whether more messages exist (for pagination)
    """
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
    """
    Schema for WebSocket messages.
    
    Used for both incoming and outgoing WebSocket events.
    
    Supported event types:
    - Incoming: typing, stop_typing
    - Outgoing: new_message, message_edited, message_deleted, user_typing,
                participants_added, participant_removed, admin_status_changed
    
    Attributes:
        type: Event type identifier
        data: Event payload (structure varies by type)
    """
    type: str = Field(
        ...,
        description="Event type (e.g., 'typing', 'new_message', 'user_typing')"
    )
    data: dict = Field(
        ...,
        description="Event payload, structure depends on event type"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "typing",
                    "data": {
                        "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
                    }
                },
                {
                    "type": "new_message",
                    "data": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                        "content": "Hello!",
                        "sender": {
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "username": "john_doe"
                        }
                    }
                }
            ]
        }
    )