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
        existing = await self.get_conversation_between_users(user_id, participant_id)
        if existing: 
            return existing
        
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
        
        Permission is based on the group's admin_only_add_members setting:
        - If True: Only admins can add members
        - If False: Any group member can add members
        
        Args:
            conversation_id: UUID of the group chat
            admin_user_id: UUID of the user performing the action
            participant_ids: List of user UUIDs to add
            
        Returns:
            Updated Conversation object with new participants
            
        Raises:
            ValueError: If not a group, user not authorized, or participants already exist
        """
        # Verify conversation is a group
        conv = await self.db.get(Conversation, conversation_id)
        if not conv:
            raise ValueError("Conversation not found")
        if not conv.is_group:
            raise ValueError("Can only add participants to group chats")
        
        # Check if user is a participant
        user_participant = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == admin_user_id
            )
        )
        user_part = user_participant.scalar_one_or_none()
        
        if not user_part:
            raise ValueError("You must be a member of this group to add participants")
        
        # Check permissions based on group settings
        if conv.admin_only_add_members:
            # Restricted mode: Only admins can add
            if not user_part.is_admin:
                raise ValueError("Only group admins can add participants to this group")
        # If admin_only_add_members is False, any member can add (no further check needed)
        
        # Get existing participant IDs
        existing = await self.db.execute(
            select(ConversationParticipant.user_id).where(
                ConversationParticipant.conversation_id == conversation_id
            )
        )
        existing_ids = set(existing.scalars().all())
        
        # Filter out participants already in group
        new_participants = [pid for pid in participant_ids if pid not in existing_ids]
        
        if not new_participants:
            raise ValueError("All specified users are already participants")
        
        # Add new participants
        for pid in new_participants:
            self.db.add(
                ConversationParticipant(
                    conversation_id=conversation_id,
                    user_id=pid
                )
            )
        
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
        
        Args:
            conversation_id: UUID of the group chat
            admin_user_id: UUID of the user performing the action
            user_id_to_remove: UUID of the user to remove
            
        Raises:
            ValueError: If not authorized or trying to remove last admin
        """
        # Verify conversation is a group
        conv = await self.db.get(Conversation, conversation_id)
        if not conv:
            raise ValueError("Conversation not found")
        if not conv.is_group:
            raise ValueError("Can only remove participants from group chats")
        
        # User can remove themselves OR must be admin to remove others
        is_self_removal = (admin_user_id == user_id_to_remove)
        
        if not is_self_removal:
            # Verify user is admin
            admin_check = await self.db.execute(
                select(ConversationParticipant).where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.user_id == admin_user_id,
                    ConversationParticipant.is_admin == True
                )
            )
            if not admin_check.scalar_one_or_none():
                raise ValueError("Only group admins can remove other participants")
        
        # Get participant to remove
        participant = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id_to_remove
            )
        )
        participant_obj = participant.scalar_one_or_none()
        
        if not participant_obj:
            raise ValueError("User is not a participant in this conversation")
        
        # Prevent removing last admin
        if participant_obj.is_admin:
            admin_count = await self.db.execute(
                select(func.count(ConversationParticipant.id)).where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.is_admin == True
                )
            )
            if admin_count.scalar_one() <= 1:
                raise ValueError("Cannot remove the last admin. Promote another user first.")
        
        # Remove participant
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
        
        Args:
            conversation_id: UUID of the group chat
            admin_user_id: UUID of the user performing the action (must be admin)
            target_user_id: UUID of the user to promote/demote
            is_admin: True to promote, False to demote
            
        Returns:
            Updated ConversationParticipant object
            
        Raises:
            ValueError: If not authorized or trying to demote last admin
        """
        # Verify conversation is a group
        conv = await self.db.get(Conversation, conversation_id)
        if not conv or not conv.is_group:
            raise ValueError("Can only manage admins in group chats")
        
        # Verify requesting user is admin
        admin_check = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == admin_user_id,
                ConversationParticipant.is_admin == True
            )
        )
        if not admin_check.scalar_one_or_none():
            raise ValueError("Only group admins can change admin status")
        
        # Get target participant
        target = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == target_user_id
            )
        )
        target_participant = target.scalar_one_or_none()
        
        if not target_participant:
            raise ValueError("Target user is not a participant")
        
        # If demoting, ensure not the last admin
        if not is_admin and target_participant.is_admin:
            admin_count = await self.db.execute(
                select(func.count(ConversationParticipant.id)).where(
                    ConversationParticipant.conversation_id == conversation_id,
                    ConversationParticipant.is_admin == True
                )
            )
            if admin_count.scalar_one() <= 1:
                raise ValueError("Cannot demote the last admin")
        
        # Update admin status
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
        
        Args:
            conversation_id: UUID of the group chat
            admin_user_id: UUID of the user performing the action (must be admin)
            admin_only_add_members: If True, only admins can add members. If False, any member can add.
            
        Returns:
            Updated Conversation object
            
        Raises:
            ValueError: If not authorized or not a group chat
        """
        # Verify conversation is a group
        conv = await self.db.get(Conversation, conversation_id)
        if not conv:
            raise ValueError("Conversation not found")
        if not conv.is_group:
            raise ValueError("Can only update settings for group chats")
        
        # Verify requesting user is admin
        admin_check = await self.db.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == admin_user_id,
                ConversationParticipant.is_admin == True
            )
        )
        if not admin_check.scalar_one_or_none():
            raise ValueError("Only group admins can update group settings")
        
        # Update setting
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
        
        Updates the conversation's last_message metadata for preview display.
        
        Args:
            conversation_id: UUID of the conversation
            sender_id: UUID of the user sending the message
            content: Message text content
            **kwargs: Additional message fields (message_type, media_url, etc.)
            
        Returns:
            The created Message object with sender details loaded
            
        Raises:
            ValueError: If conversation not found
        """
        msg = Message(
            conversation_id=conversation_id, 
            sender_id=sender_id, 
            content=content, 
            **kwargs
        )
        self.db.add(msg)
        
        # Update conversation metadata for list view
        chat = await self.db.get(Conversation, conversation_id)
        if chat is None:
            raise ValueError(f"Conversation with ID {conversation_id} not found")
            
        chat.last_message = content[:100]  # Truncate for preview
        chat.last_message_at = func.now()
        chat.updated_at = func.now()
        
        await self.db.commit()
        
        # Return message with sender details
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
        
        Args:
            message_id: UUID of the message to edit
            user_id: UUID of the user attempting to edit (must be sender)
            new_content: New message content
            
        Returns:
            The updated Message object
            
        Raises:
            ValueError: If message not found, deleted, or user not authorized
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
        Soft-delete a message (marks as deleted, doesn't remove from database).
        
        Args:
            message_id: UUID of the message to delete
            user_id: UUID of the user attempting to delete (must be sender)
            
        Returns:
            The deleted Message object
            
        Raises:
            ValueError: If message not found or user not authorized
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
        
        Updates the user's last_read_message_id and last_read_at timestamp.
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user marking as read
            last_read_message_id: UUID of the last message read
            
        Returns:
            True if successful, False if user not a participant
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
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the requesting user (for permission check)
            limit: Maximum number of messages to return
            offset: Number of messages to skip (offset-based pagination)
            before_message_id: Return messages before this ID (cursor-based pagination)
            
        Returns:
            List of Message objects ordered by newest first
        """
        query = select(Message).options(
            selectinload(Message.sender)
        ).where(
            Message.conversation_id == conversation_id, 
            Message.is_deleted == False
        )
        
        # Cursor-based pagination (preferred for chat)
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
        
        Used for broadcasting events via WebSocket.
        
        Args:
            conversation_id: UUID of the conversation
            
        Returns:
            List of participant user UUIDs
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
        
        Args:
            conv_id: UUID of the conversation
            user_id: UUID of the requesting user
            
        Returns:
            Conversation object with participants and messages loaded
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
        
        Args:
            user_id: UUID of the user
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            
        Returns:
            List of tuples: (Conversation object, unread_count)
            Ordered by most recent activity
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
        
        Args:
            conversation_id: UUID of the conversation
            user_id: UUID of the user
            last_read_message_id: UUID of last message the user read
            
        Returns:
            Count of unread messages
        """
        query = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id, 
            Message.sender_id != user_id,  # Don't count own messages
            Message.is_deleted == False
        )
        
        # Only count messages after last_read_message
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
        
        Args:
            u1: First user's UUID
            u2: Second user's UUID
            
        Returns:
            Conversation object if exists, None otherwise
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
        return res.scalar_one_or_none()