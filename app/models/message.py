from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from datetime import datetime
from typing import Optional, List
import uuid
import enum

class MessageType(str, enum.Enum):
    """Enum for supported message types."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    SYSTEM = "system"

class Conversation(Base):
    """
    Conversation/Chat thread model.
    """
    __tablename__ = "conversations"

    # Fix: Added server_default for portable UUID generation
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    is_group: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    group_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Fix: Added the description column we had to patch earlier
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Fix: Added server_default so it is never NULL on creation
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    participants = relationship("ConversationParticipant", back_populates="conversation", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class ConversationParticipant(Base):
    """
    Link table: Connects Users to Conversations.
    """
    __tablename__ = "conversation_participants"

    # Fix: Added a dedicated ID column with server_default to prevent the NotNull violation
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="participants")
    user = relationship("User")

class Message(Base):
    """
    Individual message model.
    """
    __tablename__ = "messages"

    # Fix: Added server_default
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(SQLEnum(MessageType, name="message_type"), default=MessageType.TEXT, nullable=False)
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    reply_to_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False) 
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")