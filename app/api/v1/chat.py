"""
Chat API Routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
from jose import JWTError

from app.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import decode_token
from app.models.user import User
from app.schemas.message import MessageCreate, MessageResponse, ConversationResponse, CreateGroupChat
from app.services.chat_service import ChatService
from app.services.user_service import UserService
from app.websocket.manager import manager

router = APIRouter(prefix="/chat", tags=["Chat"])

# --- HTTP Endpoints (Protected with standard Dependency) ---

@router.post(
    "/conversations/group", 
    response_model=ConversationResponse,
    summary="Create group chat",
    description="Create a new group conversation with multiple participants."
)
async def create_group_chat(
    group_data: CreateGroupChat,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ChatService(db)
    
    # Ensure creator is in the participant list
    if current_user.id not in group_data.participant_ids:
        group_data.participant_ids.append(current_user.id)
        
    return await service.create_group_chat(current_user.id, group_data.name, group_data.participant_ids)

@router.get(
    "/conversations", 
    response_model=List[ConversationResponse],
    summary="Get conversations",
    description="Get all 1-on-1 and group conversations for the current user."
)
async def get_my_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ChatService(db)
    return await service.get_user_conversations(current_user.id)

# --- WebSocket Endpoint (Real-Time) ---

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Token passed in URL"), 
    db: AsyncSession = Depends(get_db)
):
    """
    Real-time chat connection.
    Usage: ws://domain.com/api/v1/chat/ws?token=<ACCESS_TOKEN>
    """
    try:
        # 1. Decode Token using your existing security utility
        payload = decode_token(token)
        
        # 2. Extract and Validate User ID
        user_id_str = payload.get("user_id")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        user_id = uuid.UUID(user_id_str)

        # 3. Verify user exists and is active (Database Check)
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
    except (JWTError, ValueError):
        # Invalid Token or Invalid UUID format
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # --- Connection Successful ---
    
    await manager.connect(websocket, user_id)
    service = ChatService(db)
    
    try:
        while True:
            # 1. Receive data
            data = await websocket.receive_json()
            
            # 2. Validate using schema
            try:
                message_data = MessageCreate(**data)
            except Exception:
                # Malformed data shouldn't crash the server, just notify client
                await websocket.send_json({"error": "Invalid message format"})
                continue
            
            # 3. Save to DB
            saved_msg = await service.save_message(user_id, message_data)
            
            # 4. Convert to Response Schema
            response = MessageResponse.model_validate(saved_msg).model_dump()
            
            # 5. Broadcast to participants
            participants = await service.get_conversation_participants(message_data.conversation_id)
            await manager.broadcast_to_conversation(response, participants)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)