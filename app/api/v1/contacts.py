"""
Contact API Routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.contact import ContactStatus
from app.schemas.contact import (
    ContactRequest,
    ContactResponse,
    ContactListResponse,
    PendingRequestResponse,
    BlockedUserResponse,
    ContactUserInfo
)
from app.services.contact_service import ContactService
from app.services.user_service import UserService

router = APIRouter(
    prefix="/contacts",
    tags=["Contacts"]
)

# Helper to format response
def format_contact_response(contact_row, current_user_id: uuid.UUID) -> ContactResponse:
    """
    Transforms (Contact, User) tuple into ContactResponse.
    User object in the tuple is the *other* person.
    """
    contact, other_user = contact_row
    
    return ContactResponse(
        id=contact.id,
        user_id=contact.user_id,
        contact_user_id=contact.contact_user_id,
        status=contact.status,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
        contact_info=ContactUserInfo.model_validate(other_user)
    )

@router.get(
    "/search",
    response_model=List[ContactUserInfo],
    summary="Search users",
    description="Search for users to add by username, email, or name."
)
async def search_users(
    q: str = Query(..., min_length=3, description="Search term"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_service = UserService(db)
    users = await user_service.search_users(q, current_user.id)
    return [ContactUserInfo.model_validate(u) for u in users]

@router.post(
    "/request",
    status_code=status.HTTP_201_CREATED,
    summary="Send contact request",
    description="Send a friend request to another user."
)
async def send_contact_request(
    request: ContactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if request.contact_user_id == current_user.id:
        raise HTTPException(400, "Cannot add yourself as a contact")
        
    contact_service = ContactService(db)
    
    try:
        await contact_service.send_contact_request(
            user_id=current_user.id,
            contact_user_id=request.contact_user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return {"message": "Contact request sent successfully"}

@router.get(
    "",
    response_model=ContactListResponse,
    summary="Get all contacts",
    description="Get list of accepted contacts."
)
async def get_contacts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    contact_service = ContactService(db)
    
    # Get accepted contacts
    contacts_data = await contact_service.get_contacts(current_user.id, ContactStatus.ACCEPTED)
    
    # Get count of pending requests for the badge
    pending_data = await contact_service.get_pending_requests(current_user.id)
    
    formatted_contacts = [
        format_contact_response(row, current_user.id) for row in contacts_data
    ]
    
    return ContactListResponse(
        contacts=formatted_contacts,
        total=len(formatted_contacts),
        pending_requests=len(pending_data)
    )

@router.get(
    "/pending",
    response_model=List[PendingRequestResponse],
    summary="Get pending requests",
    description="Get incoming contact requests awaiting your action."
)
async def get_pending_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    contact_service = ContactService(db)
    pending_data = await contact_service.get_pending_requests(current_user.id)
    
    # Transform to schema
    return [
        PendingRequestResponse(
            id=contact.id,
            from_user=ContactUserInfo.model_validate(sender_user),
            created_at=contact.created_at
        )
        for contact, sender_user in pending_data
    ]

@router.post(
    "/accept/{contact_id}",
    summary="Accept contact request",
    description="Accept an incoming contact request."
)
async def accept_request(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    contact_service = ContactService(db)
    try:
        await contact_service.accept_contact_request(current_user.id, contact_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"message": "Contact request accepted"}

@router.post(
    "/reject/{contact_id}",
    summary="Reject contact request",
    description="Reject/Delete an incoming contact request."
)
async def reject_request(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    contact_service = ContactService(db)
    try:
        await contact_service.reject_contact_request(current_user.id, contact_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"message": "Contact request rejected"}

@router.delete(
    "/{contact_user_id}",
    summary="Remove contact",
    description="Unfriend a user."
)
async def remove_contact(
    contact_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    contact_service = ContactService(db)
    try:
        await contact_service.remove_contact(current_user.id, contact_user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return {"message": "Contact removed successfully"}

@router.get(
    "/blocked",
    response_model=List[BlockedUserResponse],
    summary="Get blocked users"
)
async def get_blocked_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    contact_service = ContactService(db)
    blocked_data = await contact_service.get_blocked_users(current_user.id)
    
    return [
        BlockedUserResponse(
            id=contact.id,
            blocked_user=ContactUserInfo.model_validate(blocked_user),
            blocked_at=contact.updated_at or contact.created_at
        )
        for contact, blocked_user in blocked_data
    ]

@router.post(
    "/block/{contact_user_id}",
    summary="Block user",
    description="Block a user. This will also remove them from contacts."
)
async def block_user(
    contact_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if contact_user_id == current_user.id:
        raise HTTPException(400, "Cannot block yourself")
        
    contact_service = ContactService(db)
    await contact_service.block_user(current_user.id, contact_user_id)
    return {"message": "User blocked successfully"}

@router.post(
    "/unblock/{contact_user_id}",
    summary="Unblock user"
)
async def unblock_user(
    contact_user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    contact_service = ContactService(db)
    await contact_service.unblock_user(current_user.id, contact_user_id)
    return {"message": "User unblocked successfully"}