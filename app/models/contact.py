from sqlalchemy import Column, Enum as SQLEnum, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from datetime import datetime
import uuid
import enum

class ContactStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid()
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    contact_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    status: Mapped[ContactStatus] = mapped_column(
        SQLEnum(ContactStatus, name="contact_status"),
        nullable=False,
        default=ContactStatus.PENDING,
        server_default="PENDING"
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    user = relationship("User", foreign_keys=[user_id], backref="initiated_contacts")
    contact_user = relationship("User", foreign_keys=[contact_user_id], backref="received_contacts")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'contact_user_id', name='unique_contact_pair'),
        CheckConstraint('user_id != contact_user_id', name='no_self_contact'),
    )