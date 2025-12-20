"""
Message and conversation API routes (REST + WebSocket).
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
    WebSocketMessage
)
from app.services.chat_service import MessageService
from app.services.user_service import UserService
from app.websocket.manager import manager

router = APIRouter(
    prefix="/messages",
    tags=["Messaging"]
)

# ============================================
# CONVERSATION ENDPOINTS
# ============================================

@router.post(
    "/conversations",
    # Note: Service now handles 1-on-1 logic
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create 1-on-1 Conversation"
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
    summary="Create Group Chat"
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
    summary="Get user's conversations"
)
async def get_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    # Returns List[Tuple[Conversation, unread_count]]
    results = await service.get_user_conversations(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )
    
    # Map to schema - Pydantic handles the Tuple -> Obj mapping via from_attributes
    return [conv for conv, unread in results]

# ============================================
# MESSAGE ENDPOINTS (REST)
# ============================================

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse
)
async def get_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    before_message_id: uuid.UUID = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = MessageService(db)
    try:
        messages = await service.get_messages(
            conversation_id=conversation_id,
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            before_message_id=before_message_id
        )
        # Assuming you want a total count as well
        total = await service.get_unread_count(conversation_id, current_user.id, None)
        
        return {
            "messages": messages,
            "total": total,
            "conversation_id": conversation_id,
            "has_more": (offset + limit) < total
        }
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post(
    "/conversations/{conversation_id}/read",
    status_code=status.HTTP_200_OK
)
async def mark_as_read(
    conversation_id: uuid.UUID,
    last_message_id: uuid.UUID = Query(...),
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
        raise HTTPException(status_code=400, detail="Failed to mark as read")
    return {"message": "Success"}

# ============================================
# REAL-TIME WEBSOCKET
# ============================================

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...), 
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket for real-time chat. 
    URL: ws://domain/api/v1/messages/ws?token=JWT
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
    service = MessageService(db)
    
    try:
        while True:
            data = await websocket.receive_json()
            # Wrap data in schema
            try:
                ws_msg = WebSocketMessage(**data)
                if ws_msg.type == "send_message":
                    msg_create = MessageCreate(**ws_msg.data)
                    saved_msg = await service.send_message(
                        sender_id=user_id,
                        **msg_create.model_dump()
                    )
                    
                    # Prepare broadcast response
                    resp = MessageResponse.model_validate(saved_msg).model_dump()
                    
                    # Broadcast to participants
                    participants = await service.get_all_participants(msg_create.conversation_id)
                    participant_ids = [p.id for p in participants]
                    await manager.broadcast_to_conversation(resp, participant_ids)
                    
            except Exception as e:
                await websocket.send_json({"error": f"Invalid data: {str(e)}"})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)