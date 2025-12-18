"""
Chat Service - Handles messaging business logic.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from typing import List, Sequence
import uuid

from app.models.message import Conversation, ConversationParticipant, Message, MessageType
from app.schemas.message import MessageCreate

class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_direct_chat(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> Conversation:
        """Create or get existing DM."""
        # 1. Check if DM already exists
        # We query for a conversation where both users are participants and is_group=False
        # (Simplified logic: creating new one for MVP reliability)
        new_chat = Conversation(is_group=False)
        self.db.add(new_chat)
        await self.db.flush()
        
        p1 = ConversationParticipant(conversation_id=new_chat.id, user_id=user_id)
        p2 = ConversationParticipant(conversation_id=new_chat.id, user_id=recipient_id)
        
        self.db.add_all([p1, p2])
        await self.db.commit()
        
        # Return with participants loaded
        return await self._get_conversation_by_id(new_chat.id)

    async def create_group_chat(self, creator_id: uuid.UUID, name: str, participant_ids: List[uuid.UUID]) -> Conversation:
        """Create a group chat."""
        group = Conversation(is_group=True, name=name)
        self.db.add(group)
        await self.db.flush()
        
        # Add admin
        self.db.add(ConversationParticipant(conversation_id=group.id, user_id=creator_id, is_admin=True))
        
        # Add members
        for pid in participant_ids:
            if pid != creator_id:
                self.db.add(ConversationParticipant(conversation_id=group.id, user_id=pid))
                
        await self.db.commit()
        return await self._get_conversation_by_id(group.id)

    async def save_message(self, sender_id: uuid.UUID, message_data: MessageCreate) -> Message:
        """Save message."""
        try:
            msg_type_enum = MessageType(message_data.message_type)
        except ValueError:
            msg_type_enum = MessageType.TEXT

        msg = Message(
            conversation_id=message_data.conversation_id,
            sender_id=sender_id,
            content=message_data.content,
            message_type=msg_type_enum,
            media_url=message_data.media_url, 
            reply_to_message_id=message_data.reply_to_message_id
        )
        self.db.add(msg)
        
        # Update timestamp
        chat = await self.db.get(Conversation, message_data.conversation_id)
        if chat:
            chat.updated_at = func.now()
            
        await self.db.commit()
        await self.db.refresh(msg)
        
        # Load sender for response
        result = await self.db.execute(
            select(Message).options(selectinload(Message.sender)).where(Message.id == msg.id)
        )
        return result.scalar_one()

    async def get_user_conversations(self, user_id: uuid.UUID) -> Sequence[Conversation]:
        """
        Get all conversations with Participants loaded.
        """
        # 1. Get IDs of chats user is in
        subquery = select(ConversationParticipant.conversation_id).where(
            ConversationParticipant.user_id == user_id
        )
        
        # 2. Fetch Chats + Participants + Users + Last Message
        query = select(Conversation)\
            .options(
                selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
                selectinload(Conversation.messages)  # Optional: Optimizing last_message loading is better done with a dedicated subquery in prod
            )\
            .where(Conversation.id.in_(subquery))\
            .order_by(desc(Conversation.updated_at))
        
        result = await self.db.execute(query)
        conversations = result.scalars().all()
        
        # Manual fix for 'last_message' if not using a complex hybrid_property
        # This is a simple way to populate the field for the schema
        for chat in conversations:
            if chat.messages:
                # Sort messages to find the last one (Python side sort)
                chat.last_message = sorted(chat.messages, key=lambda m: m.created_at)[-1]
        
        return conversations

    async def get_messages(self, conversation_id: uuid.UUID, limit: int = 50, skip: int = 0) -> Sequence[Message]:
        query = select(Message)\
            .options(selectinload(Message.sender))\
            .where(Message.conversation_id == conversation_id)\
            .order_by(desc(Message.created_at))\
            .offset(skip)\
            .limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_conversation_participants(self, conversation_id: uuid.UUID) -> List[uuid.UUID]:
        query = select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conversation_id
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # Helper to return a single conversation with all relations loaded
    async def _get_conversation_by_id(self, conversation_id: uuid.UUID) -> Conversation:
        query = select(Conversation)\
            .options(selectinload(Conversation.participants).selectinload(ConversationParticipant.user))\
            .where(Conversation.id == conversation_id)
        result = await self.db.execute(query)
        return result.scalar_one()