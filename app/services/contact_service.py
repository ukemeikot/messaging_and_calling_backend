"""
Contact service - handles contact/friend relationships.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, Row  # <--- Imported Row
from app.models.contact import Contact, ContactStatus
from app.models.user import User
from typing import Optional, List, Tuple, Sequence
import uuid

class ContactService:
    """
    Service for managing contact relationships.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def send_contact_request(
        self,
        user_id: uuid.UUID,
        contact_user_id: uuid.UUID
    ) -> Contact:
        """
        Send a contact request.
        """
        
        # Check if relationship already exists
        existing = await self.get_relationship(user_id, contact_user_id)
        
        if existing:
            if existing.status == ContactStatus.PENDING:
                # Check direction - who sent the original request
                if existing.user_id == user_id:
                    raise ValueError("Contact request already sent")
                else:
                    # They sent you a request - you're accepting it!
                    raise ValueError("This user already sent you a request. Accept it instead.")
            
            elif existing.status == ContactStatus.ACCEPTED:
                raise ValueError("Already contacts")
            
            elif existing.status == ContactStatus.BLOCKED:
                if existing.user_id == user_id:
                    raise ValueError("You have blocked this user. Unblock them first.")
                else:
                    raise ValueError("Cannot send request to this user")
        
        # Create new contact request
        contact = Contact(
            user_id=user_id,
            contact_user_id=contact_user_id,
            status=ContactStatus.PENDING
        )
        
        self.db.add(contact)
        await self.db.commit()
        await self.db.refresh(contact)
        
        return contact
    
    async def accept_contact_request(
        self,
        user_id: uuid.UUID,
        contact_id: uuid.UUID
    ) -> Contact:
        """
        Accept a contact request.
        """
        
        # Get the contact request
        result = await self.db.execute(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.contact_user_id == user_id,  # User must be the recipient
                Contact.status == ContactStatus.PENDING
            )
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            raise ValueError("Contact request not found or already processed")
        
        # Accept the request
        contact.status = ContactStatus.ACCEPTED
        
        await self.db.commit()
        await self.db.refresh(contact)
        
        return contact
    
    async def reject_contact_request(
        self,
        user_id: uuid.UUID,
        contact_id: uuid.UUID
    ) -> bool:
        """
        Reject (delete) a contact request.
        """
        
        # Get the contact request
        result = await self.db.execute(
            select(Contact).where(
                Contact.id == contact_id,
                Contact.contact_user_id == user_id,
                Contact.status == ContactStatus.PENDING
            )
        )
        contact = result.scalar_one_or_none()
        
        if not contact:
            raise ValueError("Contact request not found")
        
        # Delete the request
        await self.db.delete(contact)
        await self.db.commit()
        
        return True
    
    async def remove_contact(
        self,
        user_id: uuid.UUID,
        contact_user_id: uuid.UUID
    ) -> bool:
        """
        Remove a contact (unfriend).
        """
        
        # Find the relationship
        relationship = await self.get_relationship(user_id, contact_user_id)
        
        if not relationship or relationship.status != ContactStatus.ACCEPTED:
            raise ValueError("Not contacts")
        
        # Delete the relationship
        await self.db.delete(relationship)
        await self.db.commit()
        
        return True
    
    async def block_user(
        self,
        user_id: uuid.UUID,
        blocked_user_id: uuid.UUID
    ) -> Contact:
        """
        Block a user.
        """
        
        # Remove existing relationship if any
        existing = await self.get_relationship(user_id, blocked_user_id)
        if existing:
            await self.db.delete(existing)
        
        # Create blocked relationship
        block = Contact(
            user_id=user_id,
            contact_user_id=blocked_user_id,
            status=ContactStatus.BLOCKED
        )
        
        self.db.add(block)
        await self.db.commit()
        await self.db.refresh(block)
        
        return block
    
    async def unblock_user(
        self,
        user_id: uuid.UUID,
        blocked_user_id: uuid.UUID
    ) -> bool:
        """
        Unblock a user.
        """
        
        result = await self.db.execute(
            select(Contact).where(
                Contact.user_id == user_id,
                Contact.contact_user_id == blocked_user_id,
                Contact.status == ContactStatus.BLOCKED
            )
        )
        block = result.scalar_one_or_none()
        
        if block:
            await self.db.delete(block)
            await self.db.commit()
        
        return True
    
    async def get_relationship(
        self,
        user_id: uuid.UUID,
        other_user_id: uuid.UUID
    ) -> Optional[Contact]:
        """
        Get relationship between two users (bidirectional).
        """
        
        result = await self.db.execute(
            select(Contact).where(
                or_(
                    and_(
                        Contact.user_id == user_id,
                        Contact.contact_user_id == other_user_id
                    ),
                    and_(
                        Contact.user_id == other_user_id,
                        Contact.contact_user_id == user_id
                    )
                )
            )
        )
        
        return result.scalar_one_or_none()
    
    async def get_contacts(
        self,
        user_id: uuid.UUID,
        status: Optional[ContactStatus] = ContactStatus.ACCEPTED
    ) -> Sequence[Row[Tuple[Contact, User]]]:  # <--- UPDATED
        """
        Get user's contacts with user info.
        """
        
        query = select(Contact, User).where(
            or_(
                and_(
                    Contact.user_id == user_id,
                    Contact.contact_user_id == User.id
                ),
                and_(
                    Contact.contact_user_id == user_id,
                    Contact.user_id == User.id
                )
            )
        )
        
        if status:
            query = query.where(Contact.status == status)
        
        result = await self.db.execute(query)
        return result.all()
    
    async def get_pending_requests(
        self,
        user_id: uuid.UUID
    ) -> Sequence[Row[Tuple[Contact, User]]]:  # <--- UPDATED
        """
        Get pending contact requests sent TO this user.
        """
        
        result = await self.db.execute(
            select(Contact, User).where(
                Contact.contact_user_id == user_id,
                Contact.status == ContactStatus.PENDING,
                Contact.user_id == User.id
            )
        )
        
        return result.all()
    
    async def get_blocked_users(
        self,
        user_id: uuid.UUID
    ) -> Sequence[Row[Tuple[Contact, User]]]:  # <--- UPDATED
        """
        Get users blocked by this user.
        """
        
        result = await self.db.execute(
            select(Contact, User).where(
                Contact.user_id == user_id,
                Contact.status == ContactStatus.BLOCKED,
                Contact.contact_user_id == User.id
            )
        )
        
        return result.all()
    
    async def is_blocked(
        self,
        user_id: uuid.UUID,
        other_user_id: uuid.UUID
    ) -> bool:
        """
        Check if either user has blocked the other.
        """
        
        result = await self.db.execute(
            select(Contact).where(
                or_(
                    and_(
                        Contact.user_id == user_id,
                        Contact.contact_user_id == other_user_id,
                        Contact.status == ContactStatus.BLOCKED
                    ),
                    and_(
                        Contact.user_id == other_user_id,
                        Contact.contact_user_id == user_id,
                        Contact.status == ContactStatus.BLOCKED
                    )
                )
            )
        )
        
        return result.scalar_one_or_none() is not None