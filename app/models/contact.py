"""
Contact model - manages relationships between users.
"""

from sqlalchemy import Column, Enum as SQLEnum, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from datetime import datetime
import uuid
import enum

class ContactStatus(str, enum.Enum):
    """
    Contact relationship status.
    
    PENDING: Request sent, awaiting response
    ACCEPTED: Mutual contacts, can message/call
    BLOCKED: User blocked the contact
    """
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"

class Contact(Base):
    """
    Contact/Friend relationship model.
    
    Represents the relationship between two users.
    
    Examples:
        User A sends request to User B:
        - user_id = A, contact_user_id = B, status = pending
        
        User B accepts:
        - Status changes to accepted
        
        User A blocks User B:
        - user_id = A, contact_user_id = B, status = blocked
    
    Note: This is a unidirectional relationship from the database perspective,
    but queries handle bidirectional logic (both users can see each other as contacts).
    """
    __tablename__ = "contacts"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # User who initiated/owns this relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # The other user in the relationship
    contact_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Relationship status
    status: Mapped[ContactStatus] = mapped_column(
        SQLEnum(ContactStatus, name="contact_status"),
        nullable=False,
        default=ContactStatus.PENDING
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True
    )
    
    # Relationships to User model
    user = relationship("User", foreign_keys=[user_id], backref="initiated_contacts")
    contact_user = relationship("User", foreign_keys=[contact_user_id], backref="received_contacts")
    
    # Constraints
    __table_args__ = (
        # Prevent duplicate relationships
        UniqueConstraint('user_id', 'contact_user_id', name='unique_contact_pair'),
        
        # Prevent self-friending
        CheckConstraint('user_id != contact_user_id', name='no_self_contact'),
        
        # Composite index for efficient queries
        # Index for finding all contacts of a user (in either direction)
    )
    
    def __repr__(self):
        return f"<Contact(user_id={self.user_id}, contact_user_id={self.contact_user_id}, status={self.status})>"