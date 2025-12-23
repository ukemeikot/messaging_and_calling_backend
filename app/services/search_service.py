"""
Search service - Business logic for all search operations.
Uses PostgreSQL full-text search with trigram similarity.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple
from sqlalchemy import select, func, or_, and_, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import uuid

from app.models.user import User
from app.models.message import Message
from app.models.message import Conversation
from app.models.message import ConversationParticipant
from app.schemas.search import (
    UserSearchResult,
    MessageSearchResult,
    ConversationSearchResult,
    UserSearchResponse,
    MessageSearchResponse,
    ConversationSearchResponse,
    GlobalSearchResponse
)

logger = logging.getLogger(__name__)


class SearchService:
    """
    Comprehensive search service with:
    - Full-text search
    - Fuzzy matching (trigram similarity)
    - Relevance scoring
    - Privacy filtering
    """
    
    def __init__(self, db: AsyncSession, current_user_id: uuid.UUID):
        self.db = db
        self.current_user_id = current_user_id
    
    # ============================================
    # USER SEARCH
    # ============================================
    
    async def search_users(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        online_only: bool = False,
        verified_only: bool = False,
        exclude_blocked: bool = True,
        sort_by: str = "relevance"
    ) -> Tuple[List[UserSearchResult], int]:
        """
        Search for users using full-text search and trigram similarity.
        
        Args:
            query: Search query string
            limit: Max results to return
            offset: Results to skip (pagination)
            online_only: Only return online users
            verified_only: Only return verified users
            exclude_blocked: Exclude users blocked by current user
            sort_by: Sort order (relevance, username, created_at)
            
        Returns:
            Tuple of (results, total_count)
        """
        start_time = time.time()
        
        # Prepare search query for full-text search
        search_query = query.strip()
        ts_query = func.plainto_tsquery('english', search_query)
        
        # Build base query
        stmt = select(
            User,
            # Full-text search ranking
            func.ts_rank(User.search_vector, ts_query).label('fts_rank'),
            # Trigram similarity for fuzzy matching
            func.greatest(
                func.similarity(User.username, search_query),
                func.similarity(func.coalesce(User.full_name, ''), search_query),
                func.similarity(User.email, search_query)
            ).label('similarity_score'),
            # Determine which field matched best
            case(
                (func.similarity(User.username, search_query) >= 
                 func.greatest(
                     func.similarity(func.coalesce(User.full_name, ''), search_query),
                     func.similarity(User.email, search_query)
                 ), 'username'),
                (func.similarity(func.coalesce(User.full_name, ''), search_query) >= 
                 func.similarity(User.email, search_query), 'full_name'),
                else_='email'
            ).label('matched_field')
        ).where(
            # Exclude current user from results
            User.id != self.current_user_id,
            # User must be active
            User.is_active == True,
            # Match using full-text search OR trigram similarity
            or_(
                User.search_vector.match(search_query),
                func.similarity(User.username, search_query) > 0.1,
                func.similarity(func.coalesce(User.full_name, ''), search_query) > 0.1,
                func.similarity(User.email, search_query) > 0.1
            )
        )
        
        # Apply filters
        if online_only:
            stmt = stmt.where(User.is_online == True)
        
        if verified_only:
            stmt = stmt.where(User.is_verified == True)
        
        # TODO: Add blocked users filter when Block model exists
        # if exclude_blocked:
        #     stmt = stmt.where(~User.id.in_(blocked_user_ids_subquery))
        
        # Calculate combined relevance score
        combined_score = (
            func.ts_rank(User.search_vector, ts_query) * 0.6 +
            func.greatest(
                func.similarity(User.username, search_query),
                func.similarity(func.coalesce(User.full_name, ''), search_query),
                func.similarity(User.email, search_query)
            ) * 0.4
        ).label('match_score')
        
        stmt = stmt.add_columns(combined_score)
        
        # Apply sorting
        if sort_by == "relevance":
            stmt = stmt.order_by(combined_score.desc())
        elif sort_by == "username":
            stmt = stmt.order_by(User.username.asc())
        elif sort_by == "created_at":
            stmt = stmt.order_by(User.created_at.desc())
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)
        
        # Execute query
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # Convert to response models
        results = []
        for row in rows:
            user = row[0]
            match_score = float(row[-1]) if row[-1] else 0.0
            matched_field = row[3]
            
            results.append(UserSearchResult(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                avatar_url=user.avatar_url,
                is_online=user.is_online,
                is_verified=user.is_verified,
                last_seen=user.last_seen,
                match_score=min(match_score, 1.0),  # Cap at 1.0
                matched_field=matched_field
            ))
        
        search_time = (time.time() - start_time) * 1000  # Convert to ms
        logger.info(f"User search for '{query}' returned {len(results)} results in {search_time:.2f}ms")
        
        return results, total
    
    # ============================================
    # MESSAGE SEARCH
    # ============================================
    
    async def search_messages(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        conversation_id: Optional[uuid.UUID] = None,
        sender_id: Optional[uuid.UUID] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "relevance"
    ) -> Tuple[List[MessageSearchResult], int]:
        """
        Search messages using full-text search.
        
        Args:
            query: Search query
            limit: Max results
            offset: Pagination offset
            conversation_id: Search in specific conversation
            sender_id: Filter by sender
            date_from: Search from date
            date_to: Search to date
            sort_by: Sort order (relevance, date)
            
        Returns:
            Tuple of (results, total_count)
        """
        start_time = time.time()
        
        search_query = query.strip()
        ts_query = func.plainto_tsquery('english', search_query)
        
        # Build query
        stmt = select(
            Message,
            User.username.label('sender_username'),
            User.avatar_url.label('sender_avatar_url'),
            Conversation.name.label('conversation_name'),
            func.ts_rank(Message.search_vector, ts_query).label('rank'),
            func.ts_headline(
                'english',
                Message.content,
                ts_query,
                'StartSel=<mark>, StopSel=</mark>, MaxWords=50, MinWords=25'
            ).label('highlighted_content')
        ).join(
            User, Message.sender_id == User.id
        ).join(
            Conversation, Message.conversation_id == Conversation.id
        ).join(
            ConversationParticipant,
            and_(
                ConversationParticipant.conversation_id == Message.conversation_id,
                ConversationParticipant.user_id == self.current_user_id
            )
        ).where(
            Message.search_vector.match(search_query),
            Message.deleted_at.is_(None)
        )
        
        # Apply filters
        if conversation_id:
            stmt = stmt.where(Message.conversation_id == conversation_id)
        
        if sender_id:
            stmt = stmt.where(Message.sender_id == sender_id)
        
        if date_from:
            stmt = stmt.where(Message.created_at >= date_from)
        
        if date_to:
            stmt = stmt.where(Message.created_at <= date_to)
        
        # Sorting
        if sort_by == "relevance":
            stmt = stmt.order_by(literal_column('rank').desc())
        else:  # date
            stmt = stmt.order_by(Message.created_at.desc())
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Pagination
        stmt = stmt.limit(limit).offset(offset)
        
        # Execute
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # Convert to response
        results = []
        for row in rows:
            message = row[0]
            rank = float(row[4]) if row[4] else 0.0
            
            results.append(MessageSearchResult(
                id=message.id,
                content=message.content,
                conversation_id=message.conversation_id,
                conversation_name=row[3],
                sender_id=message.sender_id,
                sender_username=row[1],
                sender_avatar_url=row[2],
                created_at=message.created_at,
                match_score=min(rank, 1.0),
                highlighted_content=row[5]
            ))
        
        search_time = (time.time() - start_time) * 1000
        logger.info(f"Message search for '{query}' returned {len(results)} results in {search_time:.2f}ms")
        
        return results, total
    
    # ============================================
    # CONVERSATION SEARCH
    # ============================================
    
    async def search_conversations(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        conversation_type: Optional[str] = None,
        only_joined: bool = True
    ) -> Tuple[List[ConversationSearchResult], int]:
        """
        Search conversations.
        
        Args:
            query: Search query
            limit: Max results
            offset: Pagination offset
            conversation_type: Filter by type (direct, group, channel)
            only_joined: Only show conversations user is part of
            
        Returns:
            Tuple of (results, total_count)
        """
        start_time = time.time()
        
        search_query = query.strip()
        ts_query = func.plainto_tsquery('english', search_query)
        
        # Build query
        stmt = select(
            Conversation,
            func.count(ConversationParticipant.user_id).label('participant_count'),
            func.ts_rank(Conversation.search_vector, ts_query).label('rank'),
            func.exists(
                select(1).where(
                    and_(
                        ConversationParticipant.conversation_id == Conversation.id,
                        ConversationParticipant.user_id == self.current_user_id
                    )
                )
            ).label('is_joined')
        ).outerjoin(
            ConversationParticipant,
            ConversationParticipant.conversation_id == Conversation.id
        ).where(
            or_(
                Conversation.search_vector.match(search_query),
                func.similarity(Conversation.name, search_query) > 0.1
            )
        ).group_by(Conversation.id)
        
        # Apply filters
        if conversation_type:
            stmt = stmt.where(Conversation.conversation_type == conversation_type)
        
        if only_joined:
            stmt = stmt.where(
                func.exists(
                    select(1).where(
                        and_(
                            ConversationParticipant.conversation_id == Conversation.id,
                            ConversationParticipant.user_id == self.current_user_id
                        )
                    )
                )
            )
        
        # Sort by relevance
        stmt = stmt.order_by(literal_column('rank').desc())
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Pagination
        stmt = stmt.limit(limit).offset(offset)
        
        # Execute
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # Convert to response
        results = []
        for row in rows:
            conversation = row[0]
            participant_count = row[1]
            rank = float(row[2]) if row[2] else 0.0
            is_joined = row[3]
            
            results.append(ConversationSearchResult(
                id=conversation.id,
                name=conversation.name,
                conversation_type=conversation.conversation_type,
                avatar_url=conversation.avatar_url,
                participant_count=participant_count,
                last_message_at=conversation.last_message_at,
                match_score=min(rank, 1.0),
                is_joined=is_joined
            ))
        
        search_time = (time.time() - start_time) * 1000
        logger.info(f"Conversation search for '{query}' returned {len(results)} results in {search_time:.2f}ms")
        
        return results, total
    
    # ============================================
    # GLOBAL SEARCH
    # ============================================
    
    async def global_search(
        self,
        query: str,
        limit_per_type: int = 5,
        search_types: List[str] = ["users", "messages", "conversations"]
    ) -> Dict:
        """
        Search across all entity types.
        
        Args:
            query: Search query
            limit_per_type: Max results per entity type
            search_types: Which types to search
            
        Returns:
            Dictionary with results grouped by type
        """
        start_time = time.time()
        
        results = {}
        total_count = {}
        has_more = {}
        
        # Search users
        if "users" in search_types:
            user_results, user_total = await self.search_users(
                query=query,
                limit=limit_per_type,
                offset=0
            )
            results["users"] = user_results
            total_count["users"] = user_total
            has_more["users"] = user_total > limit_per_type
        
        # Search messages
        if "messages" in search_types:
            message_results, message_total = await self.search_messages(
                query=query,
                limit=limit_per_type,
                offset=0
            )
            results["messages"] = message_results
            total_count["messages"] = message_total
            has_more["messages"] = message_total > limit_per_type
        
        # Search conversations
        if "conversations" in search_types:
            conv_results, conv_total = await self.search_conversations(
                query=query,
                limit=limit_per_type,
                offset=0
            )
            results["conversations"] = conv_results
            total_count["conversations"] = conv_total
            has_more["conversations"] = conv_total > limit_per_type
        
        search_time = (time.time() - start_time) * 1000
        logger.info(f"Global search for '{query}' completed in {search_time:.2f}ms")
        
        return {
            "query": query,
            "results": results,
            "total_count": total_count,
            "has_more": has_more,
            "search_time_ms": search_time
        }