"""
Hybrid Messaging API - REST for Actions, WebSockets for Notifications.
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

async def broadcast_event(service: MessageService, conv_id: uuid.UUID, event_type: str, data: dict):
    """Utility to notify all participants of a specific chat event."""
    participant_ids = await service.get_all_participants(conv_id)
    await manager.broadcast_to_conversation({"type": event_type, "data": data}, participant_ids)

# ============================================
# CONVERSATION ENDPOINTS
# ============================================

@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(conversation_data: ConversationCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = MessageService(db)
    try:
        return await service.create_conversation(user_id=current_user.id, participant_id=conversation_data.participant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/conversations/group", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_group_chat(group_data: CreateGroupChat, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = MessageService(db)
    return await service.create_group_chat(creator_id=current_user.id, name=group_data.name, participant_ids=group_data.participant_ids)

@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = MessageService(db)
    results = await service.get_user_conversations(current_user.id)
    return [conv for conv, unread in results]

# ============================================
# MESSAGE ENDPOINTS (REST)
# ============================================

@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message_rest(message_data: MessageCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Primary endpoint for sending messages."""
    service = MessageService(db)
    try:
        msg = await service.send_message(sender_id=current_user.id, **message_data.model_dump())
        resp = MessageResponse.model_validate(msg).model_dump()
        await broadcast_event(service, msg.conversation_id, "new_message", resp)
        return msg
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{message_id}", response_model=MessageResponse)
async def edit_message(message_id: uuid.UUID, data: MessageUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = MessageService(db)
    try:
        msg = await service.edit_message(message_id, current_user.id, data.content)
        await broadcast_event(service, msg.conversation_id, "message_edited", MessageResponse.model_validate(msg).model_dump())
        return msg
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    service = MessageService(db)
    try:
        msg = await service.delete_message(message_id, current_user.id)
        await broadcast_event(service, msg.conversation_id, "message_deleted", {"message_id": str(message_id)})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================
# REAL-TIME WEBSOCKET
# ============================================

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...), db: AsyncSession = Depends(get_db)):
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
                    "data": {"user_id": str(user_id), "conversation_id": data["conversation_id"]}
                }, p_ids)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)