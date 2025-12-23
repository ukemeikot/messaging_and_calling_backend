"""
Call schemas for request/response validation with group call support.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, Dict, Any, List
from datetime import datetime
import uuid


# ============================================
# Request Schemas
# ============================================

class CallInitiateRequest(BaseModel):
    """Request to initiate a new call (1-on-1 or group)"""
    
    participant_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of user IDs to call (1 for 1-on-1, multiple for group)"
    )
    call_type: Literal["audio", "video"] = Field(
        ...,
        description="Type of call (audio or video)"
    )
    max_participants: Optional[int] = Field(
        default=None,
        ge=2,
        le=50,
        description="Max participants for group calls (optional)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional metadata"
    )
    
    @field_validator('participant_ids')
    @classmethod
    def validate_participants(cls, v: List[uuid.UUID]) -> List[uuid.UUID]:
        """Ensure no duplicate participants"""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate participant IDs not allowed")
        return v


class CallAnswerRequest(BaseModel):
    """Request to answer/join an incoming call"""
    
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional metadata (device info, etc.)"
    )


class CallEndRequest(BaseModel):
    """Request to end/leave a call"""
    
    reason: Optional[str] = Field(
        default="user_hangup",
        max_length=50,
        description="Reason for ending/leaving call"
    )


class CallDeclineRequest(BaseModel):
    """Request to decline an incoming call"""
    
    reason: Optional[str] = Field(
        default="declined",
        max_length=50,
        description="Reason for declining"
    )


class CallInviteParticipantRequest(BaseModel):
    """Request to invite additional participants to active group call"""
    
    user_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of user IDs to invite"
    )


class UpdateMediaStateRequest(BaseModel):
    """Request to update participant's media state"""
    
    is_muted: Optional[bool] = Field(
        default=None,
        description="Mute/unmute audio"
    )
    is_video_enabled: Optional[bool] = Field(
        default=None,
        description="Enable/disable video"
    )
    is_screen_sharing: Optional[bool] = Field(
        default=None,
        description="Enable/disable screen sharing"
    )


# ============================================
# Response Schemas
# ============================================

class UserCallInfo(BaseModel):
    """Minimal user info for call responses"""
    
    id: uuid.UUID
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_online: bool
    
    class Config:
        from_attributes = True


class CallParticipantResponse(BaseModel):
    """Call participant information"""
    
    id: uuid.UUID
    user_id: uuid.UUID
    user: UserCallInfo
    role: str  # 'initiator' or 'participant'
    status: str  # 'ringing', 'joined', 'left', 'declined', 'missed'
    invited_at: datetime
    joined_at: Optional[datetime] = None
    left_at: Optional[datetime] = None
    is_muted: bool
    is_video_enabled: bool
    is_screen_sharing: bool
    connection_quality: Optional[str] = None
    duration_seconds: Optional[int] = None
    
    class Config:
        from_attributes = True


class CallInvitationResponse(BaseModel):
    """Call invitation information"""
    
    id: uuid.UUID
    call_id: uuid.UUID
    invited_user_id: uuid.UUID
    invited_user: UserCallInfo
    invited_by: uuid.UUID
    inviter: UserCallInfo
    status: str
    invited_at: datetime
    responded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CallResponse(BaseModel):
    """Complete call information"""
    
    id: uuid.UUID
    initiator_id: uuid.UUID
    initiator: UserCallInfo
    call_type: str  # 'audio' or 'video'
    call_mode: str  # '1-on-1' or 'group'
    status: str
    max_participants: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    ended_by: Optional[uuid.UUID] = None
    end_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    participants: List[CallParticipantResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    active_participant_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class CallInitiateResponse(BaseModel):
    """Response when initiating a call"""
    
    message: str
    call: CallResponse
    ice_servers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="STUN/TURN server configuration"
    )


class CallHistoryItem(BaseModel):
    """Simplified call info for history list"""
    
    id: uuid.UUID
    call_type: str
    call_mode: str
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Initiator info
    initiator_id: uuid.UUID
    initiator_username: str
    initiator_avatar_url: Optional[str] = None
    
    # Participant info (for display)
    participant_count: int
    participant_names: List[str] = Field(
        default_factory=list,
        description="List of participant usernames"
    )
    
    # User's role in this call
    user_role: str = Field(
        ...,
        description="Current user's role (initiator/participant)"
    )
    
    class Config:
        from_attributes = True


class CallHistoryResponse(BaseModel):
    """Paginated call history"""
    
    calls: List[CallHistoryItem]
    total: int
    page: int
    limit: int
    has_more: bool


class ActiveCallsResponse(BaseModel):
    """List of currently active calls"""
    
    calls: List[CallResponse]
    total: int


# ============================================
# WebSocket Signaling Schemas
# ============================================

class SignalingMessage(BaseModel):
    """Base signaling message"""
    
    type: str = Field(
        ...,
        description="Message type"
    )
    call_id: uuid.UUID = Field(
        ...,
        description="Call ID"
    )
    from_user_id: uuid.UUID = Field(
        ...,
        description="Sender user ID"
    )
    to_user_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Recipient user ID (null for broadcast)"
    )


class SDPOfferMessage(SignalingMessage):
    """WebRTC SDP Offer message"""
    
    type: Literal["offer"] = "offer"
    sdp: str = Field(
        ...,
        description="Session Description Protocol offer"
    )


class SDPAnswerMessage(SignalingMessage):
    """WebRTC SDP Answer message"""
    
    type: Literal["answer"] = "answer"
    sdp: str = Field(
        ...,
        description="Session Description Protocol answer"
    )


class ICECandidateMessage(SignalingMessage):
    """WebRTC ICE Candidate message"""
    
    type: Literal["ice-candidate"] = "ice-candidate"
    candidate: Dict[str, Any] = Field(
        ...,
        description="ICE candidate information"
    )


class MediaStateUpdateMessage(SignalingMessage):
    """Broadcast media state changes to other participants"""
    
    type: Literal["media-state-update"] = "media-state-update"
    is_muted: Optional[bool] = None
    is_video_enabled: Optional[bool] = None
    is_screen_sharing: Optional[bool] = None


class CallEventMessage(BaseModel):
    """Call event notification"""
    
    type: Literal[
        "call-initiated",
        "call-ringing",
        "participant-joined",
        "participant-left",
        "participant-invited",
        "call-ended",
        "call-declined",
        "call-missed",
        "call-failed"
    ]
    call_id: uuid.UUID
    call: Optional[CallResponse] = None
    participant: Optional[CallParticipantResponse] = None
    message: str
    timestamp: datetime = Field(
        default_factory=datetime.utcnow
    )


class IncomingCallNotification(BaseModel):
    """Incoming call notification"""
    
    type: Literal["incoming-call"] = "incoming-call"
    call: CallResponse
    ice_servers: List[Dict[str, Any]] = Field(
        default_factory=list
    )


# ============================================
# Statistics & Analytics
# ============================================

class CallStatistics(BaseModel):
    """Call statistics for a user"""
    
    total_calls: int
    total_duration_seconds: int
    initiated_calls: int
    participated_calls: int
    missed_calls: int
    declined_calls: int
    average_duration_seconds: Optional[float] = None
    audio_calls: int
    video_calls: int
    one_on_one_calls: int
    group_calls: int
    total_group_call_participants: int


# ============================================
# STUN/TURN Configuration
# ============================================

class ICEServer(BaseModel):
    """ICE server configuration"""
    
    urls: str | List[str] = Field(
        ...,
        description="STUN/TURN server URL(s)"
    )
    username: Optional[str] = Field(
        default=None,
        description="Username for TURN server"
    )
    credential: Optional[str] = Field(
        default=None,
        description="Credential for TURN server"
    )


class WebRTCConfig(BaseModel):
    """Complete WebRTC configuration"""
    
    ice_servers: List[ICEServer] = Field(
        default_factory=list,
        description="List of STUN/TURN servers"
    )
    ice_transport_policy: Literal["all", "relay"] = Field(
        default="all",
        description="ICE transport policy"
    )


# ============================================
# Error Responses
# ============================================

class CallErrorResponse(BaseModel):
    """Error response for call operations"""
    
    error: str
    message: str
    call_id: Optional[uuid.UUID] = None
    details: Optional[Dict[str, Any]] = None