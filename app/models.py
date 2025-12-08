"""
Core data models for OpenPharma RAG system.

These models represent the primary data structures used across
retrieval, generation, and conversation management.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import time


@dataclass
class SearchResult:
    """
    A single search result from semantic search.

    Represents a retrieved chunk from the database with its parent document metadata.
    Used in retrieval and passed to generation for building prompts.
    """
    chunk_id: int
    section: str
    content: str
    query: str
    similarity_score: Optional[float]
    document_id: int
    source_id: str  # PMC ID
    title: str
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None
    journal: Optional[str] = None
    doi: Optional[str] = None


@dataclass
class Citation:
    """
    A citation reference with conversation-wide numbering.

    Represents a cited source within a conversation. The number field
    is assigned by ConversationManager to ensure consistent numbering
    across multiple turns.
    """
    number: int
    source_id: str  # PMC ID
    chunk_id: int
    title: str
    journal: str
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None

@dataclass
class Conversation:
    """
    A single conversation with message history, citation tracking and user id.

    Messages format:
    - User: {"role": "user", "content": "..."}
    - Assistant: {"role": "assistant", "content": "...", "cited_source_ids": ["12345", ...], "cited_chunk_ids": ["5678", ...]}
    """
    conversation_id: str
    user_id: str
    messages: List[dict] = field(default_factory=list)
    citation_mapping: Dict[str, int] = field(default_factory=dict)  # source_id -> citation_number
    conversation_citations: Dict[str, Citation] = field(default_factory=dict)  # source_id -> Citation
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
