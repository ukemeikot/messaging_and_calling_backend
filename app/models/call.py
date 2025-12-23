"""
Call models for WebRTC calling system with group call support.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Any, Dict
from sqlalchemy import String, Integer, Boolean, ForeignKey, CheckConstraint, UniqueConstraint, text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User

class Call(Base):
    """
    Call model - Represents a voice or video call (1-on-1 or group).
    """
    __tablename__ = "calls"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    
    initiator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    call_type: Mapped[str] = mapped_column(String(20), nullable=False)
    call_mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    max_participants: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        index=True
    )
    
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    ended_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    end_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Aliased metadata to avoid reserved keyword conflict
    call_metadata: Mapped[Dict[str, Any]] = mapped_column(
        "metadata", 
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        index=True
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    initiator: Mapped["User"] = relationship("User", foreign_keys=[initiator_id], back_populates="calls_initiated")
    ended_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[ended_by])
    participants: Mapped[List["CallParticipant"]] = relationship("CallParticipant", back_populates="call", cascade="all, delete-orphan")
    invitations: Mapped[List["CallInvitation"]] = relationship("CallInvitation", back_populates="call", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("call_type IN ('audio', 'video')", name="calls_call_type_check"),
        CheckConstraint("call_mode IN ('1-on-1', 'group')", name="calls_call_mode_check"),
        CheckConstraint("status IN ('ringing', 'active', 'ended', 'missed', 'declined', 'failed', 'cancelled')", name="calls_status_check"),
        CheckConstraint("max_participants IS NULL OR max_participants >= 2", name="calls_max_participants_check"),
    )
    
    def __repr__(self) -> str:
        return f"<Call {self.id} - {self.call_type} - {self.status}>"
    
    @property
    def is_active(self) -> bool:
        return self.status in ["ringing", "active"]

    @property
    def is_group_call(self) -> bool:
        return self.call_mode == "group"

    def get_joined_participant_count(self) -> int:
        if "participants" not in self.__dict__:
            return 0
        return sum(1 for p in self.participants if p.status == "joined")


class CallParticipant(Base):
    __tablename__ = "call_participants"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True, index=True)
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    
    is_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_video_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_screen_sharing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connection_quality: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    participant_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now())
    
    call: Mapped["Call"] = relationship("Call", back_populates="participants")
    user: Mapped["User"] = relationship("User", back_populates="call_participations")
    
    __table_args__ = (
        UniqueConstraint('call_id', 'user_id', name='uq_call_participants_call_user'),
        CheckConstraint("role IN ('initiator', 'participant')", name="call_participants_role_check"),
        CheckConstraint("status IN ('ringing', 'joined', 'left', 'declined', 'missed')", name="call_participants_status_check"),
    )

    def __repr__(self) -> str:
        return f"<CallParticipant {self.user_id} in Call {self.call_id}>"

    @property
    def duration_seconds(self) -> Optional[int]:
        """Calculate call duration while ensuring naive datetime subtraction"""
        if not self.joined_at:
            return None
        
        # Use left_at if they left, otherwise current time
        end_time = self.left_at or datetime.utcnow()
        start_time = self.joined_at

        # FORCE BOTH TO NAIVE: Strips timezone info if present to avoid TypeError
        if start_time.tzinfo is not None:
            start_time = start_time.replace(tzinfo=None)
        if end_time.tzinfo is not None:
            end_time = end_time.replace(tzinfo=None)
            
        return int((end_time - start_time).total_seconds())

class CallInvitation(Base):
    __tablename__ = "call_invitations"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    
    call: Mapped["Call"] = relationship("Call", back_populates="invitations")
    invited_user: Mapped["User"] = relationship("User", foreign_keys=[invited_user_id], back_populates="call_invitations_received")
    inviter: Mapped["User"] = relationship("User", foreign_keys=[invited_by], back_populates="call_invitations_sent")
    
    __table_args__ = (
        UniqueConstraint('call_id', 'invited_user_id', name='uq_call_invitations_call_user'),
        CheckConstraint("status IN ('pending', 'accepted', 'declined', 'expired')", name="call_invitations_status_check"),
    )