"""
Search schemas for request/response validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
import uuid


# ============================================
# Request Schemas
# ============================================

class SearchRequest(BaseModel):
    """Base search request parameters"""
    
    q: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Search query string"
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip"
    )
    
    @field_validator('q')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Sanitize search query"""
        # Strip whitespace
        v = v.strip()
        
        # Remove extra spaces
        v = ' '.join(v.split())
        
        if not v:
            raise ValueError("Search query cannot be empty")
        
        return v


class UserSearchRequest(SearchRequest):
    """User search with filters"""
    
    online_only: bool = Field(
        default=False,
        description="Only return online users"
    )
    verified_only: bool = Field(
        default=False,
        description="Only return verified users"
    )
    exclude_blocked: bool = Field(
        default=True,
        description="Exclude blocked users from results"
    )
    sort_by: Literal["relevance", "username", "created_at"] = Field(
        default="relevance",
        description="Sort order for results"
    )


class MessageSearchRequest(SearchRequest):
    """Message search within conversations"""
    
    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Search within specific conversation (optional)"
    )
    sender_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Filter by message sender"
    )
    date_from: Optional[datetime] = Field(
        default=None,
        description="Search messages from this date onwards"
    )
    date_to: Optional[datetime] = Field(
        default=None,
        description="Search messages up to this date"
    )
    sort_by: Literal["relevance", "date"] = Field(
        default="relevance",
        description="Sort order for results"
    )


class ConversationSearchRequest(SearchRequest):
    """Conversation search"""
    
    conversation_type: Optional[Literal["direct", "group", "channel"]] = Field(
        default=None,
        description="Filter by conversation type"
    )
    only_joined: bool = Field(
        default=True,
        description="Only search conversations user is part of"
    )


class GlobalSearchRequest(BaseModel):
    """Global search across all entities"""
    
    q: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Search query string"
    )
    limit_per_type: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max results per entity type"
    )
    search_types: List[Literal["users", "messages", "conversations"]] = Field(
        default=["users", "messages", "conversations"],
        description="Which entity types to search"
    )


# ============================================
# Response Schemas
# ============================================

class UserSearchResult(BaseModel):
    """Single user search result"""
    
    id: uuid.UUID
    username: str
    full_name: Optional[str] = None
    email: str
    avatar_url: Optional[str] = None
    is_online: bool
    is_verified: bool
    last_seen: Optional[datetime] = None
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0-1)"
    )
    matched_field: str = Field(
        ...,
        description="Which field matched (username, email, full_name)"
    )
    
    class Config:
        from_attributes = True


class MessageSearchResult(BaseModel):
    """Single message search result"""
    
    id: uuid.UUID
    content: str
    conversation_id: uuid.UUID
    conversation_name: Optional[str] = None
    sender_id: uuid.UUID
    sender_username: str
    sender_avatar_url: Optional[str] = None
    created_at: datetime
    match_score: float
    highlighted_content: str = Field(
        ...,
        description="Message content with search terms highlighted"
    )
    
    class Config:
        from_attributes = True


class ConversationSearchResult(BaseModel):
    """Single conversation search result"""
    
    id: uuid.UUID
    name: str
    conversation_type: str
    avatar_url: Optional[str] = None
    participant_count: int
    last_message_at: Optional[datetime] = None
    match_score: float
    is_joined: bool = Field(
        ...,
        description="Whether current user is a participant"
    )
    
    class Config:
        from_attributes = True


class UserSearchResponse(BaseModel):
    """User search response with pagination"""
    
    query: str
    results: List[UserSearchResult]
    total: int = Field(
        ...,
        description="Total number of matching users"
    )
    page: int
    limit: int
    has_more: bool = Field(
        ...,
        description="Whether more results are available"
    )
    search_time_ms: Optional[float] = Field(
        default=None,
        description="Search execution time in milliseconds"
    )


class MessageSearchResponse(BaseModel):
    """Message search response"""
    
    query: str
    results: List[MessageSearchResult]
    total: int
    page: int
    limit: int
    has_more: bool
    conversation_id: Optional[uuid.UUID] = None
    conversation_name: Optional[str] = None
    search_time_ms: Optional[float] = None


class ConversationSearchResponse(BaseModel):
    """Conversation search response"""
    
    query: str
    results: List[ConversationSearchResult]
    total: int
    page: int
    limit: int
    has_more: bool
    search_time_ms: Optional[float] = None


class GlobalSearchResponse(BaseModel):
    """Global search response with all entity types"""
    
    query: str
    results: dict = Field(
        ...,
        description="Search results grouped by entity type"
    )
    # results structure:
    # {
    #   "users": [UserSearchResult, ...],
    #   "messages": [MessageSearchResult, ...],
    #   "conversations": [ConversationSearchResult, ...]
    # }
    
    total_count: dict = Field(
        ...,
        description="Total count for each entity type"
    )
    # total_count structure:
    # {
    #   "users": 42,
    #   "messages": 128,
    #   "conversations": 8
    # }
    
    search_time_ms: Optional[float] = None
    has_more: dict = Field(
        default_factory=dict,
        description="Whether more results available per type"
    )


# ============================================
# Search Suggestions
# ============================================

class SearchSuggestion(BaseModel):
    """Search suggestion/autocomplete result"""
    
    suggestion: str
    type: Literal["user", "conversation", "recent"]
    count: Optional[int] = Field(
        default=None,
        description="Number of results for this suggestion"
    )


class SearchSuggestionsResponse(BaseModel):
    """Autocomplete suggestions response"""
    
    query: str
    suggestions: List[SearchSuggestion]
    limit: int = 10


# ============================================
# Search History
# ============================================

class SearchHistoryItem(BaseModel):
    """Single search history entry"""
    
    id: uuid.UUID
    query: str
    search_type: str
    results_count: int
    searched_at: datetime
    
    class Config:
        from_attributes = True


class SearchHistoryResponse(BaseModel):
    """User's recent searches"""
    
    history: List[SearchHistoryItem]
    total: int