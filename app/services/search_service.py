"""
Search service - Business logic for all search operations.
Uses PostgreSQL full-text search with trigram similarity.
"""

import logging
import time
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy import select, func, or_, and_, case, desc
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models.user import User
from app.models.message import Message, Conversation, ConversationParticipant
from app.schemas.search import (
    UserSearchResult,
    MessageSearchResult,
    ConversationSearchResult
)

logger = logging.getLogger(__name__)

class SearchService:
    """
    Comprehensive search service synchronized with GIN indexes and TSVECTOR triggers.
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
        sort_by: str = "relevance"
    ) -> Tuple[List[UserSearchResult], int]:
        start_time = time.time()
        search_query = query.strip()
        
        # 1. Handle empty queries immediately
        if not search_query:
            return [], 0

        ts_query = func.plainto_tsquery('english', search_query)
        
        # 2. Score and Match Logic
        sim_username = func.similarity(User.username, search_query)
        sim_fullname = func.similarity(func.coalesce(User.full_name, ''), search_query)
        sim_email = func.similarity(User.email, search_query)

        matched_field_logic = case(
            (sim_username >= func.greatest(sim_fullname, sim_email), 'username'),
            (sim_fullname >= sim_email, 'full_name'),
            else_='email'
        ).label('matched_field')

        combined_score = (
            func.ts_rank(User.search_vector, ts_query) * 0.6 +
            func.greatest(sim_username, sim_fullname, sim_email) * 0.4
        ).label('match_score')
        
        # 3. Build Statement
        stmt = select(User, combined_score, matched_field_logic).where(
            User.id != self.current_user_id,
            User.is_active == True,
            or_(
                User.search_vector.op("@@")(ts_query),
                User.username % search_query,
                User.full_name.ilike(f"%{search_query}%")
            )
        )
        
        if online_only:
            stmt = stmt.where(User.is_online == True)
        if verified_only:
            stmt = stmt.where(User.is_verified == True)
        
        # 4. Sorting
        if sort_by == "relevance":
            stmt = stmt.order_by(desc('match_score'))
        elif sort_by == "username":
            stmt = stmt.order_by(User.username.asc())
        else:
            stmt = stmt.order_by(User.created_at.desc())
        
        # 5. Execute
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        
        result = await self.db.execute(stmt.limit(limit).offset(offset))
        rows = result.all()
        
        results = []
        for row in rows:
            user_obj: User = row[0]
            score_val: Any = row[1]
            field_name: Any = row[2]
            
            results.append(UserSearchResult(
                id=user_obj.id,
                username=user_obj.username,
                full_name=user_obj.full_name,
                email=user_obj.email,
                avatar_url=user_obj.profile_picture_url,
                is_online=user_obj.is_online or False,
                is_verified=user_obj.is_verified or False,
                last_seen=user_obj.last_login,
                match_score=min(float(score_val or 0.0), 1.0),
                matched_field=str(field_name)
            ))
        
        search_time = (time.time() - start_time) * 1000
        logger.info(f"User search for '{query}' took {search_time:.2f}ms")
        return results, int(total)
    
    # ============================================
    # MESSAGE SEARCH
    # ============================================
    
    async def search_messages(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        conversation_id: Optional[uuid.UUID] = None,
        sort_by: str = "relevance"
    ) -> Tuple[List[MessageSearchResult], int]:
        start_time = time.time()
        search_query = query.strip()
        if not search_query:
            return [], 0

        ts_query = func.plainto_tsquery('english', search_query)
        rank = func.ts_rank(Message.search_vector, ts_query).label('rank')
        headline = func.ts_headline(
            'english', Message.content, ts_query, 
            'StartSel=<mark>, StopSel=</mark>, MaxWords=50'
        ).label('highlight')

        stmt = select(
            Message, 
            User.username.label('s_name'),
            User.profile_picture_url.label('s_avatar'),
            Conversation.name.label('c_name'),
            rank, 
            headline
        ).join(User, Message.sender_id == User.id)\
         .join(Conversation, Message.conversation_id == Conversation.id)\
         .join(ConversationParticipant, and_(
             ConversationParticipant.conversation_id == Message.conversation_id,
             ConversationParticipant.user_id == self.current_user_id
         )).where(
            Message.search_vector.op("@@")(ts_query),
            Message.is_deleted == False
        )
        
        if conversation_id:
            stmt = stmt.where(Message.conversation_id == conversation_id)
            
        stmt = stmt.order_by(desc('rank') if sort_by == "relevance" else desc(Message.created_at))
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        
        result = await self.db.execute(stmt.limit(limit).offset(offset))
        rows = result.all()
        
        results = []
        for row in rows:
            msg_obj, s_user, s_pfp, conv_n, r_val, hl_val = row
            results.append(MessageSearchResult(
                id=msg_obj.id,
                content=msg_obj.content,
                conversation_id=msg_obj.conversation_id,
                conversation_name=conv_n,
                sender_id=msg_obj.sender_id,
                sender_username=s_user,
                sender_avatar_url=s_pfp,
                created_at=msg_obj.created_at,
                match_score=min(float(r_val or 0.0), 1.0),
                highlighted_content=str(hl_val or "")
            ))
            
        return results, int(total)

    # ============================================
    # CONVERSATION SEARCH
    # ============================================

    async def search_conversations(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        only_joined: bool = True
    ) -> Tuple[List[ConversationSearchResult], int]:
        start_time = time.time()
        search_query = query.strip()
        if not search_query:
            return [], 0

        ts_query = func.plainto_tsquery('english', search_query)
        rank = func.ts_rank(Conversation.search_vector, ts_query).label('rank')
        
        stmt = select(Conversation, rank).where(
            or_(
                Conversation.search_vector.op("@@")(ts_query),
                Conversation.name % search_query
            )
        )
        
        if only_joined:
            stmt = stmt.join(ConversationParticipant, and_(
                ConversationParticipant.conversation_id == Conversation.id,
                ConversationParticipant.user_id == self.current_user_id
            ))

        stmt = stmt.order_by(desc('rank'))
        
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0
        
        result = await self.db.execute(stmt.limit(limit).offset(offset))
        rows = result.all()
        
        results = []
        for conv_obj, r_val in rows:
            results.append(ConversationSearchResult(
                id=conv_obj.id,
                name=conv_obj.name or "Unnamed Chat",
                conversation_type="group" if conv_obj.is_group else "direct",
                avatar_url=conv_obj.group_image_url,
                participant_count=0, 
                last_message_at=conv_obj.last_message_at,
                match_score=min(float(r_val or 0.0), 1.0),
                is_joined=True
            ))
            
        return results, int(total)

    # ============================================
    # GLOBAL SEARCH
    # ============================================
    
    async def global_search(
        self, 
        query: str, 
        limit_per_type: int = 5
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        user_res, user_total = await self.search_users(query, limit=limit_per_type)
        msg_res, msg_total = await self.search_messages(query, limit=limit_per_type)
        conv_res, conv_total = await self.search_conversations(query, limit=limit_per_type)
            
        search_time = (time.time() - start_time) * 1000
        return {
            "query": query,
            "results": {
                "users": user_res,
                "messages": msg_res,
                "conversations": conv_res
            },
            "total_count": {
                "users": user_total,
                "messages": msg_total,
                "conversations": conv_total
            },
            "has_more": {
                "users": user_total > limit_per_type,
                "messages": msg_total > limit_per_type,
                "conversations": conv_total > limit_per_type
            },
            "search_time_ms": search_time
        }