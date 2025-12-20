"""
Hybrid Messaging API - REST for Actions, WebSockets for Notifications.

This module provides endpoints for:
- Creating and managing conversations (1-on-1 and group chats)
- Sending, editing, and deleting messages
- Real-time message notifications via WebSockets
- Managing group chat participants
"""

from fastapi import (
    APIRouter, Depends, HTTPException, status, 
    Query, WebSocket, WebSocketDisconnect
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid
from jose import JWTError

from app.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_token
from app.models.user import User
from app.schemas.message import (
    ConversationCreate,
    ConversationResponse,
    CreateGroupChat,
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    MessageListResponse,
    WebSocketMessage,
    AddParticipantsRequest,
    RemoveParticipantRequest,
    ConversationParticipantInfo
)
from app.services.chat_service import MessageService
from app.services.user_service import UserService
from app.websocket.manager import manager

router = APIRouter(
    prefix="/messages",
    tags=["Messaging"]
)

async def broadcast_event(service: MessageService, conv_id: uuid.UUID, event_type: str, data: dict):
    """
    Broadcast an event to all participants in a conversation.
    
    Args:
        service: MessageService instance for DB operations
        conv_id: The conversation UUID
        event_type: Type of event (e.g., 'new_message', 'user_added')
        data: Event payload to broadcast
    """
    participant_ids = await service.get_all_participants(conv_id)
    await manager.broadcast_to_conversation({"type": event_type, "data": data}, participant_ids)

# ============================================
# CONVERSATION ENDPOINTS
# ============================================

@router.post(
    "/conversations", 
    response_model=ConversationResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a 1-on-1 conversation",
    description="""
    Create a new direct message conversation with another user.
    
    **Requirements:**
    - Both users must be accepted contacts
    - Cannot create conversation with yourself
    - Returns existing conversation if one already exists between the two users
    
    **Returns:**
    - The created or existing conversation with participant details
    """
)
async def create_conversation(
    conversation_data: ConversationCreate, 
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        return await service.create_conversation(
            user_id=current_user.id, 
            participant_id=conversation_data.participant_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/conversations/group", 
    response_model=ConversationResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a group chat",
    description="""
    Create a new group chat with multiple participants.
    
    **Requirements:**
    - Must provide a group name
    - Can optionally provide a description
    - Creator becomes an admin automatically
    - All specified participant_ids will be added as members
    
    **Returns:**
    - The created group conversation with all participant details
    """
)
async def create_group_chat(
    group_data: CreateGroupChat, 
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    return await service.create_group_chat(
        creator_id=current_user.id, 
        name=group_data.name, 
        participant_ids=group_data.participant_ids
    )

@router.get(
    "/conversations", 
    response_model=List[ConversationResponse],
    summary="Get user's conversations",
    description="""
    Retrieve all conversations for the current user, ordered by most recent activity.
    
    **Returns:**
    - List of conversations with:
        - Basic conversation info (name, type, last message)
        - Unread message count
        - Participant details
        - Sorted by last activity (most recent first)
    """
)
async def get_conversations(
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    results = await service.get_user_conversations(current_user.id)
    return [conv for conv, unread in results]

@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation details",
    description="""
    Retrieve detailed information about a specific conversation.
    
    **Returns:**
    - Complete conversation details including all participants
    """
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        return await service.get_conversation_by_id(conversation_id, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Conversation not found")

# ============================================
# GROUP CHAT MANAGEMENT
# ============================================

@router.post(
    "/conversations/{conversation_id}/participants",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Add participants to group chat",
    description="""
    Add one or more users to an existing group chat.
    
    **Requirements:**
    - Conversation must be a group chat (not 1-on-1)
    - Current user must be an admin of the group
    - Participant IDs must be valid user accounts
    
    **Notifications:**
    - All existing participants receive a 'participants_added' event via WebSocket
    - New participants receive a 'added_to_group' event
    
    **Returns:**
    - Updated conversation with new participants included
    """
)
async def add_participants_to_group(
    conversation_id: uuid.UUID,
    request: AddParticipantsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        conversation = await service.add_participants_to_group(
            conversation_id=conversation_id,
            admin_user_id=current_user.id,
            participant_ids=request.participant_ids
        )
        
        # Broadcast to existing members
        await broadcast_event(
            service, 
            conversation_id, 
            "participants_added", 
            {
                "conversation_id": str(conversation_id),
                "added_by": str(current_user.id),
                "new_participants": [str(pid) for pid in request.participant_ids]
            }
        )
        
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/conversations/{conversation_id}/participants/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove participant from group chat",
    description="""
    Remove a user from a group chat.
    
    **Requirements:**
    - Conversation must be a group chat
    - Current user must be an admin OR removing themselves
    - Cannot remove the last admin (must promote another user first)
    
    **Notifications:**
    - All participants receive a 'participant_removed' event via WebSocket
    
    **Use Cases:**
    - Admin removing a member
    - User leaving the group (user_id == current_user.id)
    """
)
async def remove_participant_from_group(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        await service.remove_participant_from_group(
            conversation_id=conversation_id,
            admin_user_id=current_user.id,
            user_id_to_remove=user_id
        )
        
        # Broadcast removal event
        await broadcast_event(
            service, 
            conversation_id, 
            "participant_removed", 
            {
                "conversation_id": str(conversation_id),
                "removed_user_id": str(user_id),
                "removed_by": str(current_user.id)
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch(
    "/conversations/{conversation_id}/participants/{user_id}/admin",
    response_model=ConversationParticipantInfo,
    summary="Promote/demote group admin",
    description="""
    Toggle admin status for a group chat participant.
    
    **Requirements:**
    - Current user must be an admin
    - Target user must be a participant in the group
    - Cannot demote yourself if you're the last admin
    
    **Returns:**
    - Updated participant info with new admin status
    """
)
async def toggle_admin_status(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    make_admin: bool = Query(..., description="True to promote, False to demote"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        participant = await service.update_admin_status(
            conversation_id=conversation_id,
            admin_user_id=current_user.id,
            target_user_id=user_id,
            is_admin=make_admin
        )
        
        # Broadcast admin change
        await broadcast_event(
            service,
            conversation_id,
            "admin_status_changed",
            {
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
                "is_admin": make_admin,
                "changed_by": str(current_user.id)
            }
        )
        
        return participant
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

# ============================================
# MESSAGE ENDPOINTS (REST)
# ============================================

@router.post(
    "", 
    response_model=MessageResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Send a message",
    description="""
    Send a new message in a conversation.
    
    **Supports:**
    - Text messages
    - Media messages (with media_url)
    - Reply-to functionality (with reply_to_message_id)
    - Multiple message types (text, image, video, audio, file)
    
    **Notifications:**
    - All conversation participants receive 'new_message' event via WebSocket
    
    **Returns:**
    - The created message with sender details
    """
)
async def send_message_rest(
    message_data: MessageCreate, 
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        msg = await service.send_message(
            sender_id=current_user.id, 
            **message_data.model_dump()
        )
        resp = MessageResponse.model_validate(msg).model_dump()
        await broadcast_event(service, msg.conversation_id, "new_message", resp)
        return msg
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="Get conversation messages",
    description="""
    Retrieve messages from a conversation with pagination support.
    
    **Pagination:**
    - Use `limit` and `offset` for offset-based pagination
    - Use `before_message_id` for cursor-based pagination (recommended)
    
    **Returns:**
    - List of messages ordered by newest first
    - Total message count
    - `has_more` flag indicating if more messages exist
    """
)
async def get_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    before_message_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    messages = await service.get_messages(
        conversation_id=conversation_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        before_message_id=before_message_id
    )
    
    # Get total count for pagination
    total = len(messages)  # Simplified; ideally query total separately
    
    return MessageListResponse(
        messages=messages,
        total=total,
        conversation_id=conversation_id,
        has_more=len(messages) == limit
    )

@router.put(
    "/{message_id}", 
    response_model=MessageResponse,
    summary="Edit a message",
    description="""
    Edit the content of a previously sent message.
    
    **Requirements:**
    - Must be the original sender
    - Message must not be deleted
    - Sets `is_edited` flag and `edited_at` timestamp
    
    **Notifications:**
    - All conversation participants receive 'message_edited' event via WebSocket
    
    **Returns:**
    - The updated message
    """
)
async def edit_message(
    message_id: uuid.UUID, 
    data: MessageUpdate, 
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        msg = await service.edit_message(message_id, current_user.id, data.content)
        await broadcast_event(
            service, 
            msg.conversation_id, 
            "message_edited", 
            MessageResponse.model_validate(msg).model_dump()
        )
        return msg
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/{message_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a message",
    description="""
    Soft-delete a message (marks as deleted, doesn't remove from database).
    
    **Requirements:**
    - Must be the original sender
    
    **Behavior:**
    - Sets `is_deleted` flag and `deleted_at` timestamp
    - Content changed to "This message was deleted"
    - Message still exists in database but hidden from normal queries
    
    **Notifications:**
    - All conversation participants receive 'message_deleted' event via WebSocket
    """
)
async def delete_message(
    message_id: uuid.UUID, 
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        msg = await service.delete_message(message_id, current_user.id)
        await broadcast_event(
            service, 
            msg.conversation_id, 
            "message_deleted", 
            {"message_id": str(message_id)}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/conversations/{conversation_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark messages as read",
    description="""
    Mark all messages up to a specific message as read.
    
    **Updates:**
    - Sets `last_read_message_id` for the user's participant record
    - Updates `last_read_at` timestamp
    - Affects unread count calculations
    
    **Use Case:**
    - Call when user views conversation
    - Pass the ID of the most recent message they've seen
    """
)
async def mark_as_read(
    conversation_id: uuid.UUID,
    last_message_id: uuid.UUID = Query(..., description="ID of last message user has read"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    success = await service.mark_messages_as_read(
        conversation_id=conversation_id,
        user_id=current_user.id,
        last_read_message_id=last_message_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found or not a participant")

# ============================================
# REAL-TIME WEBSOCKET
# ============================================

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    token: str = Query(..., description="JWT authentication token"), 
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time messaging features.
    
    **Authentication:**
    - Requires valid JWT token passed as query parameter
    - Connection closed with 1008 if authentication fails
    
    **Incoming Events:**
    - `typing`: Broadcast typing indicator to other participants
        ```json
        {
            "type": "typing",
            "conversation_id": "uuid-here"
        }
        ```
    
    **Outgoing Events:**
    - `new_message`: New message sent in a conversation
    - `message_edited`: Message content updated
    - `message_deleted`: Message removed
    - `user_typing`: Another user is typing
    - `participants_added`: Users added to group
    - `participant_removed`: User removed from group
    - `admin_status_changed`: Admin privileges changed
    
    **Connection Lifecycle:**
    - Authenticate on connect
    - Register connection with connection manager
    - Handle incoming typing events
    - Clean up on disconnect
    """
    try:
        payload = decode_token(token)
        user_id = uuid.UUID(payload.get("user_id"))
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except (JWTError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle Typing events (Too frequent for REST)
            if data.get("type") == "typing":
                service = MessageService(db)
                p_ids = await service.get_all_participants(uuid.UUID(data["conversation_id"]))
                await manager.broadcast_to_conversation({
                    "type": "user_typing", 
                    "data": {
                        "user_id": str(user_id), 
                        "conversation_id": data["conversation_id"]
                    }
                }, p_ids)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)