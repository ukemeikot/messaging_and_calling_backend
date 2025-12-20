"""
Service layer for messaging and conversation management.

This service handles all business logic for:
- Creating and managing conversations (1-on-1 and group chats)
- Sending, editing, and deleting messages
- Managing group chat participants and admins
- Tracking read receipts and unread counts
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload
from app.models.message import Conversation, ConversationParticipant, Message, MessageType
from app.models.contact import ContactStatus
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import uuid

class MessageService:
    """Service for managing conversations and messages."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    # ============================================
    # CONVERSATION MANAGEMENT
    # ============================================

    async def create_conversation(self, user_id: uuid.UUID, participant_id: uuid.UUID) -> Conversation:
        """
        Create or retrieve a 1-on-1 direct message conversation.
        
        Args:
            user_id: Current user's UUID
            participant_id: Other user's UUID
            
        Returns:
            The created or existing Conversation object
            
        Raises:
            ValueError: If users are the same or not accepted contacts
        """
        if user_id == participant_id: 
            raise ValueError("Cannot chat with yourself")
            
        # Verify contact relationship
        from app.services.contact_service import ContactService
        rel = await ContactService(self.db).get_relationship(user_id, participant_id)
        if not rel or rel.status != ContactStatus.ACCEPTED: 
            raise ValueError("Must be accepted contacts to start a conversation")
        
        # Check for existing conversation
        # FIX: We use a check that handles potential duplicates gracefully
        existing = await self.get_conversation_between_users(user_id, participant_id)
        if existing: 
            return await self.get_conversation_by_id(existing.id, user_id)
        
        # Create new conversation
        conv = Conversation(is_group=False)
        self.db.add(conv)
        await self.db.flush()
        
        # Add both participants
        self.db.add_all([
            ConversationParticipant(conversation_id=conv.id, user_id=user_id),
            ConversationParticipant(conversation_id=conv.id, user_id=participant_id)
        ])
        await self.db.commit()
        return await self.get_conversation_by_id(conv.id, user_id)

    async def create_group_chat(
        self, 
        creator_id: uuid.UUID, 
        name: str, 
        participant_ids: List[uuid.UUID],
        description: Optional[str] = None,
        admin_only_add_members: bool = False
    ) -> Conversation:
        """
        Create a new group chat with multiple participants.
        
        Args:
            creator_id: UUID of the user creating the group
            name: Group chat name
            participant_ids: List of user UUIDs to add as members
            description: Optional group description
            admin_only_add_members: If True, only admins can add members. If False, any member can add.
            
        Returns:
            The created Conversation object with all participants
        """
        group = Conversation(
            is_group=True, 
            name=name,
            description=description,
            admin_only_add_members=admin_only_add_members
        )
        self.db.add(group)
        await self.db.flush()
        
        # Add creator as admin
        self.db.add(
            ConversationParticipant(
                conversation_id=group.id, 
                user_id=creator_id, 
                is_admin=True
            )
        )
        
        # Add other participants
        for pid in participant_ids:
            if pid != creator_id:  # Avoid duplicate
                self.db.add(
                    ConversationParticipant(
                        conversation_id=group.id, 
                        user_id=pid
                    )
                )
                
        await self.db.commit()
        return await self.get_conversation_by_id(group.id, creator_id)

    # ============================================
    # GROUP CHAT PARTICIPANT MANAGEMENT
    # ============================================

    async def add_participants_to_group(
        self,
        conversation_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        participant_ids: List[uuid.UUID]
    ) -> Conversation:
        """
        Add new participants to an existing group chat.
        """
        conv = await self.db.get(Conversation, conversation_id)
        if not conv:
            raise ValueError("Conversation not found")
        if not conv.is_group:
            raise ValueError("Can only add participants to group chats")
        
        user_participant = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == admin_user_id
            )
        )
        user_part = user_participant.scalar_one_or_none()
        
        if not user_part:
            raise ValueError("You must be a member of this group to add participants")
        
        if conv.admin_only_add_members and not user_part.is_admin:
            raise ValueError("Only group admins can add participants to this group")
        
        existing = await self.db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id
            )
        )
        existing_ids = set(existing.scalars().all())
        new_participants = [pid for pid in participant_ids if pid not in existing_ids]
        
        if not new_participants:
            raise ValueError("All specified users are already participants")
        
        for pid in new_participants:
            self.db.add(ConversationParticipant(conversation_id=conversation_id, user_id=pid))
        
        await self.db.commit()
        return await self.get_conversation_by_id(conversation_id, admin_user_id)

    async def remove_participant_from_group(
        self,
        conversation_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        user_id_to_remove: uuid.UUID
    ) -> None:
        """
        Remove a participant from a group chat.
        """
        conv = await self.db.get(Conversation, conversation_id)
        if not conv or not conv.is_group:
            raise ValueError("Group conversation not found")
        
        is_self_removal = (admin_user_id == user_id_to_remove)
        
        if not is_self_removal:
            admin_check = await self.db.execute(
                select(ConversationParticipant).where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.user_id == admin_user_id,
                    ConversationParticipant.is_admin == True
                )
            )
            if not admin_check.scalar_one_or_none():
                raise ValueError("Only group admins can remove other participants")
        
        participant = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id_to_remove
            )
        )
        participant_obj = participant.scalar_one_or_none()
        
        if not participant_obj:
            raise ValueError("User is not a participant")
        
        if participant_obj.is_admin:
            admin_count = await self.db.execute(
                select(func.count(ConversationParticipant.id)).where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.is_admin == True
                )
            )
            if admin_count.scalar_one() <= 1:
                raise ValueError("Cannot remove the last admin")
        
        await self.db.delete(participant_obj)
        await self.db.commit()

    async def update_admin_status(
        self,
        conversation_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        is_admin: bool
    ) -> ConversationParticipant:
        """
        Promote or demote a group chat participant to/from admin.
        """
        admin_check = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == admin_user_id,
                ConversationParticipant.is_admin == True
            )
        )
        if not admin_check.scalar_one_or_none():
            raise ValueError("Only group admins can change admin status")
        
        target = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == target_user_id
            )
        )
        target_participant = target.scalar_one_or_none()
        
        if not target_participant:
            raise ValueError("Target user is not a participant")
        
        if not is_admin and target_participant.is_admin:
            admin_count = await self.db.execute(
                select(func.count(ConversationParticipant.id)).where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.is_admin == True
                )
            )
            if admin_count.scalar_one() <= 1:
                raise ValueError("Cannot demote the last admin")
        
        target_participant.is_admin = is_admin
        await self.db.commit()
        return target_participant

    async def update_group_settings(
        self,
        conversation_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        admin_only_add_members: bool
    ) -> Conversation:
        """
        Update group chat settings.
        """
        conv = await self.db.get(Conversation, conversation_id)
        if not conv or not conv.is_group:
            raise ValueError("Group chat not found")
        
        admin_check = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == admin_user_id,
                ConversationParticipant.is_admin == True
            )
        )
        if not admin_check.scalar_one_or_none():
            raise ValueError("Only group admins can update group settings")
        
        conv.admin_only_add_members = admin_only_add_members
        await self.db.commit()
        return await self.get_conversation_by_id(conversation_id, admin_user_id)

    # ============================================
    # MESSAGE MANAGEMENT
    # ============================================

    async def send_message(
        self, 
        conversation_id: uuid.UUID, 
        sender_id: uuid.UUID, 
        content: str, 
        **kwargs
    ) -> Message:
        """
        Send a new message in a conversation.
        """
        msg = Message(
            conversation_id=conversation_id, 
            sender_id=sender_id, 
            content=content, 
            **kwargs
        )
        self.db.add(msg)
        
        chat = await self.db.get(Conversation, conversation_id)
        # FIX: Guard clause to prevent "None" attribute access
        if chat is None:
            raise ValueError(f"Conversation with ID {conversation_id} not found")
            
        chat.last_message = content[:100]
        chat.last_message_at = func.now()
        chat.updated_at = func.now()
        
        await self.db.commit()
        
        res = await self.db.execute(
            select(Message).options(
                selectinload(Message.sender)
            ).where(Message.id == msg.id)
        )
        return res.scalar_one()

    async def edit_message(
        self, 
        message_id: uuid.UUID, 
        user_id: uuid.UUID, 
        new_content: str
    ) -> Message:
        """
        Edit an existing message's content.
        """
        res = await self.db.execute(
            select(Message).where(
                Message.id == message_id, 
                Message.sender_id == user_id, 
                Message.is_deleted == False
            )
        )
        msg = res.scalar_one_or_none()
        if not msg: 
            raise ValueError("Unauthorized or message not found")
            
        msg.content = new_content
        msg.is_edited = True
        msg.edited_at = func.now()
        await self.db.commit()
        return msg

    async def delete_message(
        self, 
        message_id: uuid.UUID, 
        user_id: uuid.UUID
    ) -> Message:
        """
        Soft-delete a message.
        """
        res = await self.db.execute(
            select(Message).where(
                Message.id == message_id, 
                Message.sender_id == user_id
            )
        )
        msg = res.scalar_one_or_none()
        if not msg: 
            raise ValueError("Unauthorized or message not found")
            
        msg.is_deleted = True
        msg.content = "This message was deleted"
        msg.deleted_at = func.now()
        await self.db.commit()
        return msg

    async def mark_messages_as_read(
        self, 
        conversation_id: uuid.UUID, 
        user_id: uuid.UUID, 
        last_read_message_id: uuid.UUID
    ) -> bool:
        """
        Mark all messages up to a specific message as read.
        """
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

    async def get_messages(
        self, 
        conversation_id: uuid.UUID, 
        user_id: uuid.UUID, 
        limit: int = 50, 
        offset: int = 0, 
        before_message_id: Optional[uuid.UUID] = None
    ) -> List[Message]:
        """
        Retrieve messages from a conversation with pagination.
        """
        query = select(Message).options(
            selectinload(Message.sender)
        ).where(
            Message.conversation_id == conversation_id, 
            Message.is_deleted == False
        )
        
        if before_message_id:
            ts_res = await self.db.execute(
                select(Message.created_at).where(Message.id == before_message_id)
            )
            ts = ts_res.scalar_one_or_none()
            if ts: 
                query = query.where(Message.created_at < ts)
                
        query = query.order_by(desc(Message.created_at)).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_all_participants(self, conversation_id: uuid.UUID) -> List[uuid.UUID]:
        """
        Get list of all user IDs participating in a conversation.
        """
        res = await self.db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id
            )
        )
        return list(res.scalars().all())

    async def get_conversation_by_id(
        self, 
        conv_id: uuid.UUID, 
        user_id: uuid.UUID
    ) -> Conversation:
        """
        Get a conversation by ID with all related data loaded.
        """
        res = await self.db.execute(
            select(Conversation).options(
                selectinload(Conversation.participants).selectinload(ConversationParticipant.user),
                selectinload(Conversation.messages).selectinload(Message.sender)
            ).where(Conversation.id == conv_id)
        )
        return res.scalar_one()

    async def get_user_conversations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Tuple[Conversation, int]]:
        """
        Get all conversations for a user with unread counts.
        """
        res = await self.db.execute(
            select(Conversation, ConversationParticipant)
            .join(ConversationParticipant)
            .where(ConversationParticipant.user_id == user_id)
            .options(
                selectinload(Conversation.participants).selectinload(ConversationParticipant.user)
            )
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        
        rows = res.all()
        conversations_with_unread = []
        for conv, participant in rows:
            unread_count = await self.get_unread_count(
                conv.id, 
                user_id, 
                participant.last_read_message_id
            )
            conversations_with_unread.append((conv, unread_count))
        return conversations_with_unread

    async def get_unread_count(
        self, 
        conversation_id: uuid.UUID, 
        user_id: uuid.UUID, 
        last_read_message_id: Optional[uuid.UUID]
    ) -> int:
        """
        Calculate number of unread messages for a user in a conversation.
        """
        query = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id, 
            Message.sender_id != user_id, 
            Message.is_deleted == False
        )
        
        if last_read_message_id:
            ts_res = await self.db.execute(
                select(Message.created_at).where(Message.id == last_read_message_id)
            )
            ts = ts_res.scalar_one_or_none()
            if ts: 
                query = query.where(Message.created_at > ts)
                
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_conversation_between_users(
        self, 
        u1: uuid.UUID, 
        u2: uuid.UUID
    ) -> Optional[Conversation]:
        """
        Find existing 1-on-1 conversation between two users.
        """
        res = await self.db.execute(
            select(Conversation)
            .join(ConversationParticipant)
            .where(
                Conversation.is_group == False, 
                ConversationParticipant.user_id.in_([u1, u2])
            )
            .group_by(Conversation.id)
            .having(func.count(ConversationParticipant.id) == 2)
        )
        # FIX: Using .first() ensures we find the chat and return it 
        # instead of throwing an error if duplicates exist.
        return res.scalars().first()