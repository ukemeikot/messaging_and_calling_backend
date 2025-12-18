"""
Chat Service - Handles messaging business logic.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from typing import List, Sequence
import uuid

# Import the Enum explicitly to fix type errors
from app.models.message import Conversation, ConversationParticipant, Message, MessageType
from app.schemas.message import MessageCreate

class ChatService:
    """
    Service for managing conversations and messages.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_direct_chat(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> Conversation:
        """
        Create or get existing 1-on-1 Direct Message (DM).
        """
        # Note: In a production app, you would first check if a DM 
        # already exists between these two users to prevent duplicates.
        
        new_chat = Conversation(is_group=False)
        self.db.add(new_chat)
        await self.db.flush() # Flush to generate the new_chat.id
        
        # Add both users as participants
        p1 = ConversationParticipant(conversation_id=new_chat.id, user_id=user_id)
        p2 = ConversationParticipant(conversation_id=new_chat.id, user_id=recipient_id)
        
        self.db.add_all([p1, p2])
        await self.db.commit()
        await self.db.refresh(new_chat)
        
        return new_chat

    async def create_group_chat(
        self, 
        creator_id: uuid.UUID, 
        name: str, 
        participant_ids: List[uuid.UUID]
    ) -> Conversation:
        """
        Create a new group chat.
        """
        group = Conversation(is_group=True, name=name)
        self.db.add(group)
        await self.db.flush()
        
        # Add creator as admin
        admin = ConversationParticipant(
            conversation_id=group.id, 
            user_id=creator_id, 
            is_admin=True
        )
        self.db.add(admin)
        
        # Add other participants
        for pid in participant_ids:
            # Prevent adding the creator twice if they selected themselves
            if pid != creator_id:
                member = ConversationParticipant(conversation_id=group.id, user_id=pid)
                self.db.add(member)
                
        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def save_message(self, sender_id: uuid.UUID, message_data: MessageCreate) -> Message:
        """
        Save a message to the database.
        
        Fixes Type Errors:
        - Converts message_data.message_type (str) -> MessageType (Enum)
        - Handles optional media_url
        """
        
        # 1. Convert Schema String to Database Enum
        # This fixes the "str is not assignable to MessageType" error
        try:
            msg_type_enum = MessageType(message_data.message_type)
        except ValueError:
            # Fallback to text if invalid type is passed
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
        
        # 2. Update conversation's "updated_at" timestamp
        # This moves the chat to the top of the user's list
        chat = await self.db.get(Conversation, message_data.conversation_id)
        if chat:
            chat.updated_at = func.now()
            
        await self.db.commit()
        await self.db.refresh(msg)
        
        # 3. Fetch the message again with the Sender loaded
        # This ensures the API response includes the sender's username/avatar
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.sender))
            .where(Message.id == msg.id)
        )
        return result.scalar_one()

    async def get_user_conversations(self, user_id: uuid.UUID) -> Sequence[Conversation]:
        """
        Get all conversations for a user, ordered by latest activity.
        """
        # Find all conversation IDs where the user is a participant
        subquery = select(ConversationParticipant.conversation_id).where(
            ConversationParticipant.user_id == user_id
        )
        
        # Select the full conversation objects
        query = select(Conversation).where(
            Conversation.id.in_(subquery)
        ).order_by(desc(Conversation.updated_at))
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_conversation_participants(self, conversation_id: uuid.UUID) -> List[uuid.UUID]:
        """
        Get list of user IDs in a conversation (for WebSocket broadcasting).
        """
        query = select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id == conversation_id
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())