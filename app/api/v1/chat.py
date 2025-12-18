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
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/chat", tags=["Chat"])

# --- 1. CONVERSATION MANAGEMENT ---

@router.post(
    "/conversations/direct", 
    response_model=ConversationResponse,
    summary="Start Direct Message",
    description="Start a 1-on-1 chat with another user."
)
async def create_direct_chat(
    recipient_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates or retrieves an existing 1-on-1 chat.
    """
    if recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot chat with yourself")
        
    service = ChatService(db)
    return await service.create_direct_chat(current_user.id, recipient_id)

@router.post(
    "/conversations/group", 
    response_model=ConversationResponse,
    summary="Create Group Chat",
    description="Create a new group conversation."
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
    summary="List Conversations",
    description="Get all your active conversations (ordered by recent activity)."
)
async def get_my_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    service = ChatService(db)
    return await service.get_user_conversations(current_user.id)

# --- 2. MESSAGE HISTORY ---

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    summary="Get Chat History",
    description="Load previous messages for a specific conversation."
)
async def get_chat_history(
    conversation_id: uuid.UUID,
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches the history of a chat.
    """
    service = ChatService(db)
    
    # Security: Verify user is actually in this chat
    participants = await service.get_conversation_participants(conversation_id)
    if current_user.id not in participants:
        raise HTTPException(status_code=403, detail="You are not a participant in this chat")
        
    return await service.get_messages(conversation_id, limit, skip)

# --- DOCUMENTATION ONLY ---
@router.get(
    "/ws/docs",
    summary="WebSocket Documentation",
    description="""
    ## Real-Time Chat Protocol
    
    **Connection URL:** `ws://<domain>/api/v1/chat/ws?token=<ACCESS_TOKEN>`
    
    **Authentication:**
    Pass the JWT access token as a query parameter named `token`.
    
    ### 1. Sending a Message (Client -> Server)
    Send a JSON object with this structure:
    ```json
    {
      "conversation_id": "uuid-string",
      "content": "Hello World",
      "message_type": "text"  // "text", "image", "video"
    }
    ```
    
    ### 2. Receiving a Message (Server -> Client)
    You will receive JSON objects like this:
    ```json
    {
      "id": "message-uuid",
      "conversation_id": "conversation-uuid",
      "content": "Hello World",
      "sender": {
        "id": "user-uuid",
        "username": "john_doe",
        "profile_picture_url": "..."
      },
      "created_at": "2023-10-27T10:00:00Z"
    }
    ```
    """
)
async def get_websocket_info():
    """
    Returns connection information for the WebSocket.
    """
    return {
        "url": "/api/v1/chat/ws",
        "authentication": "Query Parameter 'token'",
        "supported_types": ["text", "image", "video", "audio", "file"]
    }

# --- 3. REAL-TIME WEBSOCKET ---

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
        # 1. Decode Token
        payload = decode_token(token)
        user_id_str = payload.get("user_id")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_id = uuid.UUID(user_id_str)
        
        # 2. Check DB
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_id)
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
    except (JWTError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. Connect
    await manager.connect(websocket, user_id)
    service = ChatService(db)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # 4. Validate & Save
            try:
                message_data = MessageCreate(**data)
            except Exception:
                await websocket.send_json({"error": "Invalid message format"})
                continue
            
            saved_msg = await service.save_message(user_id, message_data)
            response = MessageResponse.model_validate(saved_msg).model_dump()
            
            # 5. Broadcast
            participants = await service.get_conversation_participants(message_data.conversation_id)
            await manager.broadcast_to_conversation(response, participants)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)