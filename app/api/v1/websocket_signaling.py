"""
WebSocket endpoint for real-time call signaling.

WebSocket URL: /api/v1/ws/signaling?token=<jwt_token>

Message Types:
- offer: WebRTC SDP offer
- answer: WebRTC SDP answer
- ice-candidate: ICE candidate for NAT traversal
- media-state-update: Broadcast media state changes
"""

import logging
import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.exceptions import WebSocketException
from jose import JWTError
import uuid

from app.core.security import decode_token
from app.services.websocket_manager import manager
from app.database import get_db
from app.models.user import User
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_current_user_ws(token: str, db) -> Optional[User]:
    """
    Authenticate WebSocket connection via JWT token.
    
    Args:
        token: JWT access token
        db: Database session
        
    Returns:
        User object if authenticated, None otherwise
    """
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id")
        
        if not user_id:
            return None
        
        # Get user from database
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        return user
        
    except JWTError:
        return None
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}")
        return None


@router.websocket("/ws/signaling")
async def websocket_signaling_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token")
):
    """
    WebSocket endpoint for WebRTC signaling.
    
    **Authentication:**
    - Pass JWT token as query parameter: ?token=<your_token>
    
    **Message Format:**
    ```json
    {
        "type": "offer|answer|ice-candidate|media-state-update",
        "call_id": "uuid",
        "to_user_id": "uuid",  // null for broadcast
        "sdp": "...",  // for offer/answer
        "candidate": {...}  // for ice-candidate
    }
    ```
    
    **Flow:**
    1. Connect with authentication
    2. Send/receive signaling messages
    3. WebRTC connection established P2P
    4. Media flows directly between peers
    """
    
    # Authenticate
    async for db in get_db():
        user = await get_current_user_ws(token, db)
        
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Connect
        await manager.connect(websocket, user.id)
        
        try:
            # Send connection confirmation
            await websocket.send_json({
                "type": "connected",
                "user_id": str(user.id),
                "message": "WebSocket connected successfully"
            })
            
            # Message loop
            while True:
                # Receive message
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })
                    continue
                
                # Handle message based on type
                await handle_signaling_message(websocket, user.id, message, db)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: user={user.id}")
            manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            manager.disconnect(websocket)


async def handle_signaling_message(
    websocket: WebSocket,
    user_id: uuid.UUID,
    message: dict,
    db
):
    """
    Handle incoming signaling message.
    
    Args:
        websocket: WebSocket connection
        user_id: Sender user ID
        message: Message dict
        db: Database session
    """
    
    message_type = message.get("type")
    call_id_str = message.get("call_id")
    to_user_id_str = message.get("to_user_id")
    
    if not message_type or not call_id_str:
        await websocket.send_json({
            "type": "error",
            "message": "Missing required fields: type, call_id"
        })
        return
    
    try:
        call_id = uuid.UUID(call_id_str)
        to_user_id = uuid.UUID(to_user_id_str) if to_user_id_str else None
    except ValueError:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid UUID format"
        })
        return
    
    # Add user to call if not already added
    manager.add_to_call(call_id, user_id)
    
    # Handle different message types
    if message_type == "offer":
        await handle_offer(user_id, to_user_id, call_id, message)
    
    elif message_type == "answer":
        await handle_answer(user_id, to_user_id, call_id, message)
    
    elif message_type == "ice-candidate":
        await handle_ice_candidate(user_id, to_user_id, call_id, message)
    
    elif message_type == "media-state-update":
        await handle_media_state_update(user_id, call_id, message)
    
    elif message_type == "join-call":
        # User joined call
        manager.add_to_call(call_id, user_id)
        await broadcast_call_event(call_id, {
            "type": "participant-joined",
            "call_id": str(call_id),
            "user_id": str(user_id)
        }, exclude_user_id=user_id)
    
    elif message_type == "leave-call":
        # User left call
        manager.remove_from_call(call_id, user_id)
        await broadcast_call_event(call_id, {
            "type": "participant-left",
            "call_id": str(call_id),
            "user_id": str(user_id)
        }, exclude_user_id=user_id)
    
    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        })


async def handle_offer(
    from_user_id: uuid.UUID,
    to_user_id: Optional[uuid.UUID],
    call_id: uuid.UUID,
    message: dict
):
    """
    Handle WebRTC SDP offer.
    
    For 1-on-1: Send to specific peer
    For group: Send to all participants (mesh)
    """
    
    sdp = message.get("sdp")
    
    if not sdp:
        logger.warning("Offer missing SDP")
        return
    
    offer_message = {
        "type": "offer",
        "call_id": str(call_id),
        "from_user_id": str(from_user_id),
        "sdp": sdp
    }
    
    if to_user_id:
        # Send to specific user (1-on-1 or direct in group)
        await manager.send_to_peer(offer_message, from_user_id, to_user_id, call_id)
    else:
        # Broadcast to all (group call mesh)
        await manager.send_to_call(offer_message, call_id, exclude_user_id=from_user_id)
    
    logger.debug(f"Forwarded offer from {from_user_id} in call {call_id}")


async def handle_answer(
    from_user_id: uuid.UUID,
    to_user_id: Optional[uuid.UUID],
    call_id: uuid.UUID,
    message: dict
):
    """
    Handle WebRTC SDP answer.
    """
    
    sdp = message.get("sdp")
    
    if not sdp:
        logger.warning("Answer missing SDP")
        return
    
    answer_message = {
        "type": "answer",
        "call_id": str(call_id),
        "from_user_id": str(from_user_id),
        "sdp": sdp
    }
    
    if to_user_id:
        await manager.send_to_peer(answer_message, from_user_id, to_user_id, call_id)
    else:
        await manager.send_to_call(answer_message, call_id, exclude_user_id=from_user_id)
    
    logger.debug(f"Forwarded answer from {from_user_id} in call {call_id}")


async def handle_ice_candidate(
    from_user_id: uuid.UUID,
    to_user_id: Optional[uuid.UUID],
    call_id: uuid.UUID,
    message: dict
):
    """
    Handle ICE candidate for NAT traversal.
    """
    
    candidate = message.get("candidate")
    
    if not candidate:
        logger.warning("ICE candidate missing candidate data")
        return
    
    ice_message = {
        "type": "ice-candidate",
        "call_id": str(call_id),
        "from_user_id": str(from_user_id),
        "candidate": candidate
    }
    
    if to_user_id:
        await manager.send_to_peer(ice_message, from_user_id, to_user_id, call_id)
    else:
        await manager.send_to_call(ice_message, call_id, exclude_user_id=from_user_id)
    
    logger.debug(f"Forwarded ICE candidate from {from_user_id} in call {call_id}")


async def handle_media_state_update(
    from_user_id: uuid.UUID,
    call_id: uuid.UUID,
    message: dict
):
    """
    Broadcast media state changes to other participants.
    """
    
    state_message = {
        "type": "media-state-update",
        "call_id": str(call_id),
        "user_id": str(from_user_id),
        "is_muted": message.get("is_muted"),
        "is_video_enabled": message.get("is_video_enabled"),
        "is_screen_sharing": message.get("is_screen_sharing")
    }
    
    # Broadcast to all participants except sender
    await manager.send_to_call(state_message, call_id, exclude_user_id=from_user_id)
    
    logger.debug(f"Broadcast media state update from {from_user_id} in call {call_id}")


async def broadcast_call_event(
    call_id: uuid.UUID,
    event: dict,
    exclude_user_id: Optional[uuid.UUID] = None
):
    """
    Broadcast call event to all participants.
    
    Args:
        call_id: Call ID
        event: Event dict
        exclude_user_id: Optional user to exclude
    """
    await manager.send_to_call(event, call_id, exclude_user_id=exclude_user_id)


# Export for use in other modules
async def notify_incoming_call(call_id: uuid.UUID, user_id: uuid.UUID, call_data: dict):
    """
    Send incoming call notification to user.
    
    Args:
        call_id: Call ID
        user_id: User to notify
        call_data: Call information
    """
    message = {
        "type": "incoming-call",
        "call_id": str(call_id),
        "call": call_data
    }
    
    await manager.send_personal_message(message, user_id)


async def notify_call_ended(call_id: uuid.UUID, reason: str):
    """
    Notify all participants that call has ended.
    
    Args:
        call_id: Call ID
        reason: End reason
    """
    message = {
        "type": "call-ended",
        "call_id": str(call_id),
        "reason": reason
    }
    
    await manager.send_to_call(message, call_id)