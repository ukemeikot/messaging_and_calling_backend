"""
Call REST API endpoints.

Endpoints:
- POST /calls/initiate - Start a new call
- POST /calls/{call_id}/answer - Answer/join a call
- POST /calls/{call_id}/decline - Decline an incoming call
- POST /calls/{call_id}/end - End/leave a call
- POST /calls/{call_id}/invite - Invite participants to group call
- PATCH /calls/{call_id}/media - Update media state
- GET /calls/{call_id} - Get call details
- GET /calls/history - Get call history
- GET /calls/active - Get active calls
- GET /calls/config - Get WebRTC configuration
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.services.call_service import CallService
from app.schemas.call import (
    CallInitiateRequest,
    CallInitiateResponse,
    CallAnswerRequest,
    CallDeclineRequest,
    CallEndRequest,
    CallInviteParticipantRequest,
    UpdateMediaStateRequest,
    CallResponse,
    CallHistoryResponse,
    CallHistoryItem,
    ActiveCallsResponse,
    WebRTCConfig,
    ICEServer,
    CallParticipantResponse,
    UserCallInfo
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/calls",
    tags=["Calls"]
)


# ============================================
# Helper Functions
# ============================================

def get_ice_servers():
    """
    Get STUN/TURN server configuration.
    
    Returns list of ICE servers for WebRTC connection.
    """
    ice_servers = []
    
    # Google's free STUN servers
    ice_servers.append({
        "urls": [
            "stun:stun.l.google.com:19302",
            "stun:stun1.l.google.com:19302",
            "stun:stun2.l.google.com:19302",
        ]
    })
    
    # Custom TURN server (if configured)
    turn_url = os.getenv("TURN_SERVER_URL")
    turn_username = os.getenv("TURN_SERVER_USERNAME")
    turn_credential = os.getenv("TURN_SERVER_CREDENTIAL")
    
    if turn_url and turn_username and turn_credential:
        ice_servers.append({
            "urls": turn_url,
            "username": turn_username,
            "credential": turn_credential
        })
    
    return ice_servers


def call_to_response(call, current_user_id=None) -> CallResponse:
    """Convert Call model to CallResponse schema"""
    
    participants_response = []
    for p in call.participants:
        participants_response.append(CallParticipantResponse(
            id=p.id,
            user_id=p.user_id,
            user=UserCallInfo.model_validate(p.user),
            role=p.role,
            status=p.status,
            invited_at=p.invited_at,
            joined_at=p.joined_at,
            left_at=p.left_at,
            is_muted=p.is_muted,
            is_video_enabled=p.is_video_enabled,
            is_screen_sharing=p.is_screen_sharing,
            connection_quality=p.connection_quality,
            duration_seconds=p.duration_seconds
        ))
    
    active_count = sum(1 for p in call.participants if p.status == "joined")
    
    return CallResponse(
        id=call.id,
        initiator_id=call.initiator_id,
        initiator=UserCallInfo.model_validate(call.initiator),
        call_type=call.call_type,
        call_mode=call.call_mode,
        status=call.status,
        max_participants=call.max_participants,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds,
        ended_by=call.ended_by,
        end_reason=call.end_reason,
        metadata=call.metadata,
        participants=participants_response,
        created_at=call.created_at,
        updated_at=call.updated_at,
        active_participant_count=active_count
    )


# ============================================
# Call Endpoints
# ============================================

@router.post(
    "/initiate",
    response_model=CallInitiateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a call",
    description="""
    Start a new voice or video call.
    
    **Call Types:**
    - `audio` - Voice call only
    - `video` - Video call with optional audio
    
    **Call Modes (automatic):**
    - 1 participant → 1-on-1 call
    - 2+ participants → Group call
    
    **Flow:**
    1. Backend creates call record
    2. Backend notifies participants via WebSocket
    3. Participants receive "incoming-call" notification
    4. WebRTC signaling begins through WebSocket
    
    **Note:** Initiator auto-joins, others must answer.
    """
)
async def initiate_call(
    request: CallInitiateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate a new call.
    """
    
    call_service = CallService(db)
    
    try:
        call = await call_service.initiate_call(
            initiator_id=current_user.id,
            participant_ids=request.participant_ids,
            call_type=request.call_type,
            max_participants=request.max_participants,
            metadata=request.metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate call: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate call"
        )
    
    # Get ICE servers
    ice_servers = get_ice_servers()
    
    return CallInitiateResponse(
        message=f"Call initiated successfully ({'1-on-1' if len(request.participant_ids) == 1 else 'group'})",
        call=call_to_response(call, current_user.id),
        ice_servers=ice_servers
    )


@router.post(
    "/{call_id}/answer",
    response_model=CallResponse,
    summary="Answer/join a call",
    description="""
    Answer an incoming call or join an active group call.
    
    **Flow:**
    1. User receives "incoming-call" notification
    2. User clicks "Answer"
    3. Frontend calls this endpoint
    4. WebRTC peer connection established via WebSocket
    
    **Status Changes:**
    - Participant: ringing → joined
    - Call: ringing → active (when first person answers)
    """
)
async def answer_call(
    call_id: uuid.UUID,
    request: CallAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Answer/join a call.
    """
    
    call_service = CallService(db)
    
    try:
        call = await call_service.answer_call(
            call_id=call_id,
            user_id=current_user.id,
            metadata=request.metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to answer call: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to answer call"
        )
    
    return call_to_response(call, current_user.id)


@router.post(
    "/{call_id}/decline",
    response_model=CallResponse,
    summary="Decline an incoming call",
    description="""
    Decline an incoming call.
    
    **Behavior:**
    - 1-on-1: Call ends immediately
    - Group: Call continues if others remain
    
    **Status Changes:**
    - Participant: ringing → declined
    - Call (1-on-1): ringing → declined
    """
)
async def decline_call(
    call_id: uuid.UUID,
    request: CallDeclineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Decline an incoming call.
    """
    
    call_service = CallService(db)
    
    try:
        call = await call_service.decline_call(
            call_id=call_id,
            user_id=current_user.id,
            reason=request.reason or "declined"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to decline call: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decline call"
        )
    
    return call_to_response(call, current_user.id)


@router.post(
    "/{call_id}/end",
    response_model=CallResponse,
    summary="End/leave a call",
    description="""
    End or leave an active call.
    
    **Behavior:**
    - 1-on-1: Ends call for both participants
    - Group: User leaves, call continues if others remain
    
    **Status Changes:**
    - Participant: joined → left
    - Call (1-on-1): active → ended
    - Call (group): active → ended (if all leave)
    """
)
async def end_call(
    call_id: uuid.UUID,
    request: CallEndRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End/leave a call.
    """
    
    call_service = CallService(db)
    
    try:
        call = await call_service.end_call(
            call_id=call_id,
            user_id=current_user.id,
            reason=request.reason or "user_hangup"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to end call: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end call"
        )
    
    return call_to_response(call, current_user.id)


@router.post(
    "/{call_id}/invite",
    status_code=status.HTTP_200_OK,
    summary="Invite participants to group call",
    description="""
    Invite additional participants to an active group call.
    
    **Requirements:**
    - Call must be a group call
    - Call must be active
    - Caller must be an active participant
    - Cannot exceed max_participants (if set)
    
    **Flow:**
    1. Active participant invites others
    2. Invited users receive "incoming-call" notification
    3. They can join the active call
    """
)
async def invite_to_call(
    call_id: uuid.UUID,
    request: CallInviteParticipantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Invite participants to active group call.
    """
    
    call_service = CallService(db)
    
    try:
        participants = await call_service.invite_to_call(
            call_id=call_id,
            inviter_id=current_user.id,
            user_ids=request.user_ids
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to invite to call: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite participants"
        )
    
    return {
        "message": f"Invited {len(participants)} participants",
        "invited_count": len(participants)
    }


@router.patch(
    "/{call_id}/media",
    response_model=CallParticipantResponse,
    summary="Update media state",
    description="""
    Update participant's media state (mute, video, screen share).
    
    **Media States:**
    - `is_muted` - Mute/unmute microphone
    - `is_video_enabled` - Enable/disable camera
    - `is_screen_sharing` - Start/stop screen sharing
    
    **Note:** Other participants are notified via WebSocket.
    """
)
async def update_media_state(
    call_id: uuid.UUID,
    request: UpdateMediaStateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update participant's media state.
    """
    
    call_service = CallService(db)
    
    try:
        participant = await call_service.update_media_state(
            call_id=call_id,
            user_id=current_user.id,
            is_muted=request.is_muted,
            is_video_enabled=request.is_video_enabled,
            is_screen_sharing=request.is_screen_sharing
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update media state: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update media state"
        )
    
    return CallParticipantResponse(
        id=participant.id,
        user_id=participant.user_id,
        user=UserCallInfo.model_validate(participant.user),
        role=participant.role,
        status=participant.status,
        invited_at=participant.invited_at,
        joined_at=participant.joined_at,
        left_at=participant.left_at,
        is_muted=participant.is_muted,
        is_video_enabled=participant.is_video_enabled,
        is_screen_sharing=participant.is_screen_sharing,
        connection_quality=participant.connection_quality,
        duration_seconds=participant.duration_seconds
    )


@router.get(
    "/{call_id}",
    response_model=CallResponse,
    summary="Get call details",
    description="""
    Get detailed information about a specific call.
    
    **Includes:**
    - Call status and metadata
    - All participants and their states
    - Timestamps and duration
    
    **Permission:** Must be a participant in the call.
    """
)
async def get_call(
    call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get call details.
    """
    
    call_service = CallService(db)
    
    try:
        call = await call_service.get_call_by_id(
            call_id=call_id,
            user_id=current_user.id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get call: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get call"
        )
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    return call_to_response(call, current_user.id)


@router.get(
    "/history",
    response_model=CallHistoryResponse,
    summary="Get call history",
    description="""
    Get paginated call history for current user.
    
    **Includes:**
    - All calls (initiated and received)
    - Call type, duration, status
    - Participant information
    
    **Sorted:** Most recent first
    """
)
async def get_call_history(
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get call history.
    """
    
    call_service = CallService(db)
    
    try:
        calls, total = await call_service.get_call_history(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Failed to get call history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get call history"
        )
    
    # Convert to history items
    history_items = []
    for call in calls:
        # Get participant names
        participant_names = [
            p.user.username for p in call.participants 
            if p.user_id != current_user.id
        ]
        
        # Determine user's role
        user_participant = next(
            (p for p in call.participants if p.user_id == current_user.id),
            None
        )
        user_role = user_participant.role if user_participant else "unknown"
        
        history_items.append(CallHistoryItem(
            id=call.id,
            call_type=call.call_type,
            call_mode=call.call_mode,
            status=call.status,
            started_at=call.started_at,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds,
            initiator_id=call.initiator_id,
            initiator_username=call.initiator.username,
            initiator_avatar_url=call.initiator.avatar_url,
            participant_count=len(call.participants),
            participant_names=participant_names,
            user_role=user_role
        ))
    
    page = (offset // limit) + 1
    has_more = (offset + limit) < total
    
    return CallHistoryResponse(
        calls=history_items,
        total=total,
        page=page,
        limit=limit,
        has_more=has_more
    )


@router.get(
    "/active",
    response_model=ActiveCallsResponse,
    summary="Get active calls",
    description="""
    Get all currently active calls for current user.
    
    **Returns:**
    - Calls where user is actively joined
    - Ringing calls (incoming)
    
    **Use case:** Resume interrupted calls, show ongoing calls
    """
)
async def get_active_calls(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get active calls.
    """
    
    call_service = CallService(db)
    
    try:
        calls = await call_service.get_active_calls(
            user_id=current_user.id
        )
    except Exception as e:
        logger.error(f"Failed to get active calls: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get active calls"
        )
    
    call_responses = [call_to_response(call, current_user.id) for call in calls]
    
    return ActiveCallsResponse(
        calls=call_responses,
        total=len(call_responses)
    )


@router.get(
    "/config",
    response_model=WebRTCConfig,
    summary="Get WebRTC configuration",
    description="""
    Get WebRTC configuration (STUN/TURN servers).
    
    **Returns:**
    - ICE server list (STUN/TURN)
    - Transport policy
    
    **Use:** Configure WebRTC peer connection on client.
    """
)
async def get_webrtc_config(
    current_user: User = Depends(get_current_user)
):
    """
    Get WebRTC configuration.
    """
    
    ice_servers_raw = get_ice_servers()
    
    ice_servers = [
        ICEServer(**server) for server in ice_servers_raw
    ]
    
    return WebRTCConfig(
        ice_servers=ice_servers,
        ice_transport_policy="all"
    )