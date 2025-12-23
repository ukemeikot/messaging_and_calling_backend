"""
Call models for WebRTC calling system with group call support.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Call(Base):
    """
    Call model - Represents a voice or video call (1-on-1 or group).
    
    Call Modes:
    - 1-on-1: Direct call between two users
    - group: Conference call with multiple participants
    
    Call States:
    - ringing: Call initiated, waiting for participants to join
    - active: Call in progress with at least one participant joined
    - ended: Call completed
    - missed: No one answered
    - declined: All participants declined
    - failed: Technical failure
    - cancelled: Initiator cancelled before anyone joined
    """
    
    __tablename__ = "calls"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    
    # Initiator (person who started the call)
    initiator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Call Configuration
    call_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )  # 'audio' or 'video'
    
    call_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # '1-on-1' or 'group'
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # 'ringing', 'active', 'ended', 'missed', 'declined', 'failed', 'cancelled'
    
    max_participants: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )  # For group calls (e.g., 10 max)
    
    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )
    
    # Duration (auto-calculated by trigger)
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    # End Information
    ended_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    end_reason: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )  # 'user_hangup', 'timeout', 'connection_error', 'all_left', etc.
    
    # Metadata (JSONB for flexibility)
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}"
    )
    # Example metadata:
    # {
    #   "ice_servers": [...],
    #   "recording_url": "...",
    #   "quality_metrics": {...}
    # }
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    initiator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[initiator_id],
        back_populates="calls_initiated"
    )
    
    ended_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[ended_by]
    )
    
    participants: Mapped[List["CallParticipant"]] = relationship(
        "CallParticipant",
        back_populates="call",
        cascade="all, delete-orphan"
    )
    
    invitations: Mapped[List["CallInvitation"]] = relationship(
        "CallInvitation",
        back_populates="call",
        cascade="all, delete-orphan"
    )
    
    # Table Constraints
    __table_args__ = (
        CheckConstraint(
            "call_type IN ('audio', 'video')",
            name="calls_call_type_check"
        ),
        CheckConstraint(
            "call_mode IN ('1-on-1', 'group')",
            name="calls_call_mode_check"
        ),
        CheckConstraint(
            "status IN ('ringing', 'active', 'ended', 'missed', 'declined', 'failed', 'cancelled')",
            name="calls_status_check"
        ),
        CheckConstraint(
            "max_participants IS NULL OR max_participants >= 2",
            name="calls_max_participants_check"
        ),
    )
    
    def __repr__(self) -> str:
        return f"<Call {self.id} - {self.call_type} - {self.call_mode} - {self.status}>"
    
    @property
    def is_active(self) -> bool:
        """Check if call is currently active"""
        return self.status in ["ringing", "active"]
    
    @property
    def is_group_call(self) -> bool:
        """Check if this is a group call"""
        return self.call_mode == "group"
    
    def get_joined_participant_count(self) -> int:
        """Get count of participants who joined"""
        return sum(1 for p in self.participants if p.status == "joined")
    
    def can_add_participant(self) -> bool:
        """Check if more participants can be added"""
        if not self.is_group_call:
            return False
        if self.max_participants is None:
            return True
        return len(self.participants) < self.max_participants


class CallParticipant(Base):
    """
    Call Participant model - Tracks user participation in calls.
    For both 1-on-1 and group calls.
    """
    
    __tablename__ = "call_participants"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    
    # Foreign Keys
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Participant Role
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )  # 'initiator' or 'participant'
    
    # Participant Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # 'ringing', 'joined', 'left', 'declined', 'missed'
    
    # Timestamps
    invited_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    joined_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True
    )
    
    left_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )
    
    # Media State
    is_muted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    is_video_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    is_screen_sharing: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    connection_quality: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )  # 'excellent', 'good', 'fair', 'poor'
    
    # Metadata
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    call: Mapped["Call"] = relationship(
        "Call",
        back_populates="participants"
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="call_participations"
    )
    
    # Table Constraints
    __table_args__ = (
        UniqueConstraint('call_id', 'user_id', name='uq_call_participants_call_user'),
        CheckConstraint(
            "role IN ('initiator', 'participant')",
            name="call_participants_role_check"
        ),
        CheckConstraint(
            "status IN ('ringing', 'joined', 'left', 'declined', 'missed')",
            name="call_participants_status_check"
        ),
    )
    
    def __repr__(self) -> str:
        return f"<CallParticipant {self.user_id} in Call {self.call_id} - {self.status}>"
    
    @property
    def is_active(self) -> bool:
        """Check if participant is currently in call"""
        return self.status == "joined" and self.left_at is None
    
    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate how long participant was in call"""
        if not self.joined_at:
            return None
        end_time = self.left_at or datetime.now(timezone.utc)
        return int((end_time - self.joined_at).total_seconds())


class CallInvitation(Base):
    """
    Call Invitation model - Tracks invitations sent during active group calls.
    Allows adding participants to ongoing calls.
    """
    
    __tablename__ = "call_invitations"
    
    # Primary Key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    
    # Foreign Keys
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    invited_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # 'pending', 'accepted', 'declined', 'expired'
    
    # Timestamps
    invited_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )
    
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    call: Mapped["Call"] = relationship(
        "Call",
        back_populates="invitations"
    )
    
    invited_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[invited_user_id],
        back_populates="call_invitations_received"
    )
    
    inviter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[invited_by],
        back_populates="call_invitations_sent"
    )
    
    # Table Constraints
    __table_args__ = (
        UniqueConstraint('call_id', 'invited_user_id', name='uq_call_invitations_call_user'),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired')",
            name="call_invitations_status_check"
        ),
    )
    
    def __repr__(self) -> str:
        return f"<CallInvitation {self.invited_user_id} to Call {self.call_id} - {self.status}>"
    
    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at