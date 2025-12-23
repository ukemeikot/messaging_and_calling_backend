"""
Search API endpoints.

Endpoints:
- GET /search/users - Search for users
- GET /search/messages - Search messages
- GET /search/conversations - Search conversations
- GET /search/global - Search everything
- GET /search/suggestions - Get search suggestions (autocomplete)
"""

import logging
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.message import Conversation
from app.core.dependencies import get_current_user
from app.services.search_service import SearchService
from app.schemas.search import (
    UserSearchResponse,
    MessageSearchResponse,
    ConversationSearchResponse,
    GlobalSearchResponse,
    UserSearchResult,
    MessageSearchResult,
    ConversationSearchResult
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["Search"]
)


# ============================================
# USER SEARCH
# ============================================

@router.get(
    "/users",
    response_model=UserSearchResponse,
    summary="Search users",
    description="""
    Search for users by username, email, or full name.
    
    **Features:**
    - Fuzzy matching (handles typos)
    - Partial matching ("joh" finds "john_doe")
    - Case-insensitive
    - Relevance scoring
    - Privacy filtering (excludes blocked users)
    
    **Use cases:**
    - Find users to start a conversation
    - Add contacts
    - Mention users in messages (@username)
    - Invite to groups
    
    **Performance:**
    - Uses PostgreSQL GIN indexes
    - Typical response: <50ms
    """
)
async def search_users(
    q: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search query (username, email, or name)"
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Max results to return"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Results to skip (pagination)"
    ),
    online_only: bool = Query(
        False,
        description="Only return online users"
    ),
    verified_only: bool = Query(
        False,
        description="Only return verified users"
    ),
    sort_by: str = Query(
        "relevance",
        regex="^(relevance|username|created_at)$",
        description="Sort order"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for users.
    
    Returns users matching the search query with relevance scores.
    """
    
    # Create search service
    search_service = SearchService(db, current_user.id)
    
    # Perform search
    try:
        results, total = await search_service.search_users(
            query=q,
            limit=limit,
            offset=offset,
            online_only=online_only,
            verified_only=verified_only,
            sort_by=sort_by
        )
    except Exception as e:
        logger.error(f"User search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed. Please try again."
        )
    
    # Calculate pagination info
    page = (offset // limit) + 1
    has_more = (offset + limit) < total
    
    return UserSearchResponse(
        query=q,
        results=results,
        total=total,
        page=page,
        limit=limit,
        has_more=has_more
    )


# ============================================
# MESSAGE SEARCH
# ============================================

@router.get(
    "/messages",
    response_model=MessageSearchResponse,
    summary="Search messages",
    description="""
    Search messages across conversations or within a specific conversation.
    
    **Features:**
    - Full-text search
    - Highlight matched terms
    - Date range filtering
    - Sender filtering
    - Only searches conversations user is part of
    
    **Use cases:**
    - Find old messages
    - Search conversation history
    - Find shared files/links
    - Review important discussions
    
    **Privacy:**
    - Only returns messages from conversations user has access to
    - Respects conversation permissions
    """
)
async def search_messages(
    q: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search query"
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Max results"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Results to skip"
    ),
    # Fixed: Type changed to uuid.UUID to satisfy Pylance
    conversation_id: Optional[uuid.UUID] = Query(
        None,
        description="Search within specific conversation (UUID)"
    ),
    # Fixed: Type changed to uuid.UUID to satisfy Pylance
    sender_id: Optional[uuid.UUID] = Query(
        None,
        description="Filter by sender (UUID)"
    ),
    date_from: Optional[datetime] = Query(
        None,
        description="Search from this date"
    ),
    date_to: Optional[datetime] = Query(
        None,
        description="Search to this date"
    ),
    sort_by: str = Query(
        "relevance",
        regex="^(relevance|date)$",
        description="Sort order"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search messages with optional filters.
    
    Returns messages with highlighted search terms.
    """
    
    search_service = SearchService(db, current_user.id)
    
    try:
        # Fixed: Conversion of datetime to string to satisfy SearchService signature
        results, total = await search_service.search_messages(
            query=q,
            limit=limit,
            offset=offset,
            conversation_id=conversation_id,
            sender_id=sender_id,
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
            sort_by=sort_by
        )
    except Exception as e:
        logger.error(f"Message search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed. Please try again."
        )
    
    page = (offset // limit) + 1
    has_more = (offset + limit) < total
    
    # Get conversation name if searching within one conversation
    conversation_name = None
    if conversation_id and results:
        conversation_name = results[0].conversation_name
    
    return MessageSearchResponse(
        query=q,
        results=results,
        total=total,
        page=page,
        limit=limit,
        has_more=has_more,
        conversation_id=conversation_id, # Fixed: Removed str() conversion to match schema type
        conversation_name=conversation_name
    )


# ============================================
# CONVERSATION SEARCH
# ============================================

@router.get(
    "/conversations",
    response_model=ConversationSearchResponse,
    summary="Search conversations",
    description="""
    Search for conversations/channels by name.
    
    **Features:**
    - Search by conversation name
    - Filter by type (direct, group, channel)
    - Shows participant count
    - Indicates if user is already joined
    
    **Use cases:**
    - Find specific conversation
    - Discover public channels
    - Switch between conversations quickly
    """
)
async def search_conversations(
    q: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search query"
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Max results"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Results to skip"
    ),
    conversation_type: Optional[str] = Query(
        None,
        regex="^(direct|group|channel)$",
        description="Filter by conversation type"
    ),
    only_joined: bool = Query(
        True,
        description="Only show conversations user is part of"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search conversations.
    
    Returns conversations matching the query.
    """
    
    search_service = SearchService(db, current_user.id)
    
    try:
        results, total = await search_service.search_conversations(
            query=q,
            limit=limit,
            offset=offset,
            conversation_type=conversation_type,
            only_joined=only_joined
        )
    except Exception as e:
        logger.error(f"Conversation search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed. Please try again."
        )
    
    page = (offset // limit) + 1
    has_more = (offset + limit) < total
    
    return ConversationSearchResponse(
        query=q,
        results=results,
        total=total,
        page=page,
        limit=limit,
        has_more=has_more
    )


# ============================================
# GLOBAL SEARCH
# ============================================

@router.get(
    "/global",
    response_model=GlobalSearchResponse,
    summary="Global search",
    description="""
    Search across all entity types (users, messages, conversations).
    
    **Returns:**
    - Top 5 users (by default)
    - Top 5 messages
    - Top 5 conversations
    
    **Use cases:**
    - Universal search bar
    - Quick access to any content
    - Discover related content
    
    **Performance:**
    - Searches all types in parallel
    - Returns combined results
    - Typical response: <100ms
    """
)
async def global_search(
    q: str = Query(
        ...,
        min_length=1,
        max_length=100,
        description="Search query"
    ),
    limit_per_type: int = Query(
        5,
        ge=1,
        le=20,
        description="Max results per entity type"
    ),
    search_types: List[str] = Query(
        ["users", "messages", "conversations"],
        description="Which types to search"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search across all entity types.
    
    Returns grouped results with counts.
    """
    
    # Validate search_types
    valid_types = {"users", "messages", "conversations"}
    if not all(t in valid_types for t in search_types):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search_types. Must be one of: {valid_types}"
        )
    
    search_service = SearchService(db, current_user.id)
    
    try:
        result = await search_service.global_search(
            query=q,
            limit_per_type=limit_per_type,
            search_types=search_types
        )
    except Exception as e:
        logger.error(f"Global search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed. Please try again."
        )
    
    return GlobalSearchResponse(**result)


# ============================================
# SEARCH SUGGESTIONS (Autocomplete)
# ============================================

@router.get(
    "/suggestions",
    summary="Get search suggestions",
    description="""
    Get autocomplete suggestions as user types.
    
    **Features:**
    - Fast prefix matching
    - Returns top matches
    - Includes result counts
    
    **Use cases:**
    - Search bar autocomplete
    - Quick suggestions
    - Improved UX
    
    **Note:** This is a lightweight endpoint optimized for speed.
    It performs simpler queries than full search.
    """
)
async def get_search_suggestions(
    q: str = Query(
        ...,
        min_length=2,
        max_length=50,
        description="Partial search query"
    ),
    limit: int = Query(
        10,
        ge=1,
        le=20,
        description="Max suggestions"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get search suggestions for autocomplete.
    
    Returns quick suggestions based on partial input.
    """
    
    # Simple prefix matching for suggestions
    # This is faster than full-text search
    
    from sqlalchemy import select, func
    
    suggestions = []
    
    try:
        # Get user suggestions
        user_stmt = select(
            User.username,
            func.count().over().label('total')
        ).where(
            User.username.ilike(f"{q}%"),
            User.is_active == True,
            User.id != current_user.id
        ).limit(5)
        
        result = await db.execute(user_stmt)
        users = result.all()
        
        for user in users:
            suggestions.append({
                "suggestion": user[0],
                "type": "user",
                "count": None
            })
        
        # Get conversation suggestions
        conv_stmt = select(
            Conversation.name,
            func.count().over().label('total')
        ).where(
            Conversation.name.ilike(f"{q}%")
        ).limit(5)
        
        result = await db.execute(conv_stmt)
        conversations = result.all()
        
        for conv in conversations:
            suggestions.append({
                "suggestion": conv[0],
                "type": "conversation",
                "count": None
            })
        
        # Limit total suggestions
        suggestions = suggestions[:limit]
        
    except Exception as e:
        logger.error(f"Suggestions failed: {str(e)}")
        # Return empty suggestions on error (non-critical)
        suggestions = []
    
    return {
        "query": q,
        "suggestions": suggestions,
        "limit": limit
    }