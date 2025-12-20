from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.models.message import Conversation, ConversationParticipant, Message, MessageType
from app.models.contact import ContactStatus
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
        """Create or get a 1-on-1 DM."""
        if user_id == participant_id: 
            raise ValueError("Cannot chat with yourself")
            
        from app.services.contact_service import ContactService
        rel = await ContactService(self.db).get_relationship(user_id, participant_id)
        if not rel or rel.status != ContactStatus.ACCEPTED: 
            raise ValueError("Must be accepted contacts to start a conversation")
        
        existing = await self.get_conversation_between_users(user_id, participant_id)
        if existing: 
            return existing
        
        conv = Conversation(is_group=False)
        self.db.add(conv)
        await self.db.flush()
        
        self.db.add_all([
            ConversationParticipant(conversation_id=conv.id, user_id=user_id),
            ConversationParticipant(conversation_id=conv.id, user_id=participant_id)
        ])
        await self.db.commit()
        return await self.get_conversation_by_id(conv.id, user_id)

    async def create_group_chat(self, creator_id: uuid.UUID, name: str, participant_ids: List[uuid.UUID]) -> Conversation:
        """Creates a multi-user group chat."""
        group = Conversation(is_group=True, name=name)
        self.db.add(group)
        await self.db.flush()
        
        # Add creator as admin
        self.db.add(ConversationParticipant(conversation_id=group.id, user_id=creator_id, is_admin=True))
        
        # Add other participants
        for pid in participant_ids:
            if pid != creator_id:
                self.db.add(ConversationParticipant(conversation_id=group.id, user_id=pid))
                
        await self.db.commit()
        return await self.get_conversation_by_id(group.id, creator_id)

    # ============================================
    # MESSAGE MANAGEMENT
    # ============================================

    async def send_message(self, conversation_id: uuid.UUID, sender_id: uuid.UUID, content: str, **kwargs) -> Message:
        """Saves message and updates conversation preview metadata."""
        msg = Message(conversation_id=conversation_id, sender_id=sender_id, content=content, **kwargs)
        self.db.add(msg)
        
        chat = await self.db.get(Conversation, conversation_id)
        if chat is None:
            raise ValueError(f"Conversation with ID {conversation_id} not found")
            
        chat.last_message = content[:100]
        chat.last_message_at = func.now()
        chat.updated_at = func.now()
        
        await self.db.commit()
        
        res = await self.db.execute(
            select(Message).options(selectinload(Message.sender)).where(Message.id == msg.id)
        )
        return res.scalar_one()

    async def edit_message(self, message_id: uuid.UUID, user_id: uuid.UUID, new_content: str) -> Message:
        res = await self.db.execute(select(Message).where(Message.id == message_id, Message.sender_id == user_id, Message.is_deleted == False))
        msg = res.scalar_one_or_none()
        if not msg: 
            raise ValueError("Unauthorized or message not found")
            
        msg.content = new_content
        msg.is_edited = True
        msg.edited_at = func.now()
        await self.db.commit()
        return msg

    async def delete_message(self, message_id: uuid.UUID, user_id: uuid.UUID) -> Message:
        res = await self.db.execute(select(Message).where(Message.id == message_id, Message.sender_id == user_id))
        msg = res.scalar_one_or_none()
        if not msg: 
            raise ValueError("Unauthorized or message not found")
            
        msg.is_deleted = True
        msg.content = "This message was deleted"
        msg.deleted_at = func.now()
        await self.db.commit()
        return msg

    async def mark_messages_as_read(self, conversation_id: uuid.UUID, user_id: uuid.UUID, last_read_message_id: uuid.UUID) -> bool:
        res = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id, 
                ConversationParticipant.user_id == user_id
            )
        )
        participant = res.scalar_one_or_none()
        if not participant: 
            return False
            
        participant.last_read_message_id = last_read_message_id
        participant.last_read_at = func.now()
        await self.db.commit()
        return True

    # ============================================
    # QUERIES & HELPERS
    # ============================================

    async def get_messages(self, conversation_id: uuid.UUID, user_id: uuid.UUID, limit: int = 50, offset: int = 0, before_message_id: Optional[uuid.UUID] = None) -> List[Message]:
        query = select(Message).options(selectinload(Message.sender)).where(
            Message.conversation_id == conversation_id, 
            Message.is_deleted == False
        )
        
        if before_message_id:
            ts_res = await self.db.execute(select(Message.created_at).where(Message.id == before_message_id))
            ts = ts_res.scalar_one_or_none()
            if ts: 
                query = query.where(Message.created_at < ts)
                
        query = query.order_by(desc(Message.created_at)).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_all_participants(self, conversation_id: uuid.UUID) -> List[uuid.UUID]:
        res = await self.db.execute(select(ConversationParticipant.user_id).where(ConversationParticipant.conversation_id == conversation_id))
        return list(res.scalars().all())

    async def get_conversation_by_id(self, conv_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        res = await self.db.execute(select(Conversation).options(
            selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
            selectinload(Conversation.messages).selectinload(Message.sender)
        ).where(Conversation.id == conv_id))
        return res.scalar_one()

    async def get_user_conversations(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> List[Tuple[Conversation, int]]:
        res = await self.db.execute(
            select(Conversation, ConversationParticipant)
            .join(ConversationParticipant)
            .where(ConversationParticipant.user_id == user_id)
            .options(selectinload(Conversation.participants).selectinload(ConversationParticipant.user))
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        
        rows = res.all()
        conversations_with_unread = []
        for conv, participant in rows:
            unread_count = await self.get_unread_count(conv.id, user_id, participant.last_read_message_id)
            conversations_with_unread.append((conv, unread_count))
        return conversations_with_unread

    async def get_unread_count(self, conversation_id: uuid.UUID, user_id: uuid.UUID, last_read_message_id: Optional[uuid.UUID]) -> int:
        query = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id, 
            Message.sender_id != user_id, 
            Message.is_deleted == False
        )
        if last_read_message_id:
            ts_res = await self.db.execute(select(Message.created_at).where(Message.id == last_read_message_id))
            ts = ts_res.scalar_one_or_none()
            if ts: 
                query = query.where(Message.created_at > ts)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_conversation_between_users(self, u1: uuid.UUID, u2: uuid.UUID):
        res = await self.db.execute(
            select(Conversation)
            .join(ConversationParticipant)
            .where(Conversation.is_group == False, ConversationParticipant.user_id.in_([u1, u2]))
            .group_by(Conversation.id)
            .having(func.count(ConversationParticipant.id) == 2)
        )
        return res.scalar_one_or_none()