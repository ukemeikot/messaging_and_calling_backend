from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from app.database import Base
from typing import Optional, Any, List, TYPE_CHECKING
from datetime import datetime
import uuid

# Import call models for type checking only (avoid circular imports)
if TYPE_CHECKING:
    from app.models.call import Call, CallParticipant, CallInvitation

class User(Base):
    """
    User model for authentication and profile management.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # SOURCE OF TRUTH: Actual database column
    profile_picture_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Status fields
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Search vector for full-text search
    search_vector: Mapped[Optional[Any]] = mapped_column(TSVECTOR, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ============================================
    # COMPATIBILITY ALIAS (Python Only)
    # ============================================

    @property
    def avatar_url(self) -> Optional[str]:
        """Alias for profile_picture_url (for compatibility)"""
        return self.profile_picture_url

    @avatar_url.setter
    def avatar_url(self, value: Optional[str]):
        """Ensures that setting avatar_url updates profile_picture_url"""
        self.profile_picture_url = value

    # ============================================
    # CALL RELATIONSHIPS
    # ============================================
    
    # Calls initiated by this user
    calls_initiated: Mapped[List["Call"]] = relationship(
        "Call",
        foreign_keys="Call.initiator_id",
        back_populates="initiator",
        lazy="select"
    )
    
    # Call participations (all calls this user participated in)
    call_participations: Mapped[List["CallParticipant"]] = relationship(
        "CallParticipant",
        back_populates="user",
        lazy="select"
    )
    
    # Call invitations received by this user
    call_invitations_received: Mapped[List["CallInvitation"]] = relationship(
        "CallInvitation",
        foreign_keys="CallInvitation.invited_user_id",
        back_populates="invited_user",
        lazy="select"
    )
    
    # Call invitations sent by this user
    call_invitations_sent: Mapped[List["CallInvitation"]] = relationship(
        "CallInvitation",
        foreign_keys="CallInvitation.invited_by",
        back_populates="inviter",
        lazy="select"
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"