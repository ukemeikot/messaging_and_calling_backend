"""
Message service - handles conversations and messaging logic.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload
from app.models.message import Conversation, ConversationParticipant, Message, MessageType
from app.models.user import User
from app.models.contact import Contact, ContactStatus
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import uuid

class MessageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================
    # CONVERSATION MANAGEMENT
    # ============================================
    
    async def create_conversation(self, user_id: uuid.UUID, participant_id: uuid.UUID) -> Conversation:
        """Create or get 1-on-1 DM."""
        if user_id == participant_id:
            raise ValueError("Cannot create conversation with yourself")
        
        from app.services.contact_service import ContactService
        contact_service = ContactService(self.db)
        relationship = await contact_service.get_relationship(user_id, participant_id)
        
        if not relationship or relationship.status != ContactStatus.ACCEPTED:
            raise ValueError("Can only message accepted contacts")
        
        existing = await self.get_conversation_between_users(user_id, participant_id)
        if existing:
            return existing
        
        conversation = Conversation(is_group=False)
        self.db.add(conversation)
        await self.db.flush()
        
        p1 = ConversationParticipant(conversation_id=conversation.id, user_id=user_id)
        p2 = ConversationParticipant(conversation_id=conversation.id, user_id=participant_id)
        self.db.add_all([p1, p2])
        
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def create_group_chat(self, creator_id: uuid.UUID, name: str, participant_ids: List[uuid.UUID]) -> Conversation:
        """Create a group chat."""
        group = Conversation(is_group=True, name=name)
        self.db.add(group)
        await self.db.flush()
        
        self.db.add(ConversationParticipant(conversation_id=group.id, user_id=creator_id, is_admin=True))
        for pid in participant_ids:
            if pid != creator_id:
                self.db.add(ConversationParticipant(conversation_id=group.id, user_id=pid))
                
        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def get_user_conversations(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> List[Tuple[Conversation, int]]:
        """Get list of conversations with unread counts."""
        result = await self.db.execute(
            select(Conversation, ConversationParticipant)
            .join(ConversationParticipant)
            .options(
                selectinload(Conversation.participants).selectinload(ConversationParticipant.user)
            )
            .where(ConversationParticipant.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        
        rows = result.all()
        conversations_with_unread = []
        for conv, participant in rows:
            unread_count = await self.get_unread_count(conv.id, user_id, participant.last_read_message_id)
            conversations_with_unread.append((conv, unread_count))
        return conversations_with_unread

    async def get_conversation_by_id(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Conversation]:
        """Verify membership and return conversation."""
        result = await self.db.execute(
            select(Conversation).join(ConversationParticipant)
            .where(Conversation.id == conversation_id, ConversationParticipant.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_participants(self, conversation_id: uuid.UUID) -> List[User]:
        """Used by WebSocket broadcast logic."""
        result = await self.db.execute(
            select(User).join(ConversationParticipant).where(ConversationParticipant.conversation_id == conversation_id)
        )
        return list(result.scalars().all())

    # ============================================
    # MESSAGE MANAGEMENT
    # ============================================
    
    async def send_message(self, conversation_id: uuid.UUID, sender_id: uuid.UUID, content: str, 
                           message_type: str = "text", media_url: Optional[str] = None, 
                           reply_to_message_id: Optional[uuid.UUID] = None) -> Message:
        """Saves message and updates preview."""
        message = Message(
            conversation_id=conversation_id, sender_id=sender_id, content=content,
            message_type=MessageType(message_type), media_url=media_url, reply_to_message_id=reply_to_message_id
        )
        self.db.add(message)
        
        chat_res = await self.db.execute(select(Conversation).where(Conversation.id == conversation_id))
        chat = chat_res.scalar_one()
        chat.last_message = content[:100]
        chat.last_message_at = func.now()
        chat.updated_at = func.now()
        
        await self.db.commit()
        res = await self.db.execute(select(Message).options(selectinload(Message.sender)).where(Message.id == message.id))
        return res.scalar_one()

    async def edit_message(self, message_id: uuid.UUID, user_id: uuid.UUID, new_content: str) -> Message:
        """Logic for PUT endpoint."""
        result = await self.db.execute(select(Message).where(Message.id == message_id, Message.sender_id == user_id, Message.is_deleted == False))
        message = result.scalar_one_or_none()
        if not message: raise ValueError("Message not found or cannot be edited")
        message.content = new_content
        message.is_edited = True
        message.edited_at = func.now()
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def delete_message(self, message_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Soft delete logic."""
        result = await self.db.execute(select(Message).where(Message.id == message_id, Message.sender_id == user_id))
        message = result.scalar_one_or_none()
        if not message: raise ValueError("Message not found")
        message.is_deleted = True
        message.deleted_at = func.now()
        message.content = "This message was deleted"
        await self.db.commit()
        return True

    async def mark_messages_as_read(self, conversation_id: uuid.UUID, user_id: uuid.UUID, last_read_message_id: uuid.UUID) -> bool:
        """Logic for the /read endpoint."""
        result = await self.db.execute(select(ConversationParticipant).where(ConversationParticipant.conversation_id == conversation_id, ConversationParticipant.user_id == user_id))
        participant = result.scalar_one_or_none()
        if not participant: return False
        participant.last_read_message_id = last_read_message_id
        participant.last_read_at = func.now()
        await self.db.commit()
        return True

    async def get_messages(self, conversation_id: uuid.UUID, user_id: uuid.UUID, limit: int = 50, offset: int = 0, before_message_id: Optional[uuid.UUID] = None) -> List[Message]:
        query = select(Message).options(selectinload(Message.sender)).where(Message.conversation_id == conversation_id, Message.is_deleted == False)
        if before_message_id:
            ts_res = await self.db.execute(select(Message.created_at).where(Message.id == before_message_id))
            ts = ts_res.scalar_one_or_none()
            if ts: query = query.where(Message.created_at < ts)
        query = query.order_by(desc(Message.created_at)).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_unread_count(self, conversation_id: uuid.UUID, user_id: uuid.UUID, last_read_message_id: Optional[uuid.UUID]) -> int:
        query = select(func.count(Message.id)).where(Message.conversation_id == conversation_id, Message.sender_id != user_id, Message.is_deleted == False)
        if last_read_message_id:
            ts_res = await self.db.execute(select(Message.created_at).where(Message.id == last_read_message_id))
            ts = ts_res.scalar_one_or_none()
            if ts: query = query.where(Message.created_at > ts)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_conversation_between_users(self, u1: uuid.UUID, u2: uuid.UUID) -> Optional[Conversation]:
        result = await self.db.execute(select(Conversation).join(ConversationParticipant).where(Conversation.is_group == False, ConversationParticipant.user_id.in_([u1, u2])).group_by(Conversation.id).having(func.count(ConversationParticipant.id) == 2))
        return result.scalar_one_or_none()