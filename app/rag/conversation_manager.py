"""
Conversation Manager for OpenPharma RAG system.

Manages multi-turn conversations with consistent citation numbering across turns.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from app.rag.generation import Citation
import uuid
import time


@dataclass
class Conversation:
    """A single conversation with message history and citation tracking."""
    conversation_id: str
    messages: List[dict] = field(default_factory=list)  # [{"role": "user", "content": "..."}, ...]
    citation_mapping: Dict[str, int] = field(default_factory=dict)  # source_id -> citation_number
    conversation_citations: Dict[str, Citation] = field(default_factory=dict)  # source_id -> citation
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)


class ConversationManager:
    """
    Manages conversation state in-memory.

    Handles:
    - Conversation creation and retrieval
    - Message history tracking
    - Conversation-wide citation numbering (PMC ID → [1], [2], etc.)
    - Automatic cleanup of old conversations
    """

    def __init__(self, max_age_seconds: int = 3600):
        """Initialize conversation manager with max age for cleanup."""
        self.conversations: Dict[str, Conversation] = {}
        self.max_age_seconds = max_age_seconds

    def create_conversation(self) -> str:
        """Create a new conversation and return its UUID."""
        self._run_cleanup_if_needed()

        c_id = str(uuid.uuid4())
        c = Conversation(conversation_id=c_id)
        self.conversations[c_id] = c
        return c_id

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Retrieve conversation by ID, updating last_accessed. Returns None if not found."""
        if conversation_id not in self.conversations:
            return None 
        else:
            c = self.conversations.get(conversation_id, None)
            c.last_accessed = time.time()
            return c

    def get_messages(self, conversation_id: str) -> List[dict]:
        """Get message history. Returns empty list if conversation not found."""
        if conversation_id not in self.conversations:
            return []
        else:
            return self.conversations.get(conversation_id).messages

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """Add message to conversation. Raises ValueError if conversation not found."""

        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        c = self.conversations.get(conversation_id)
        c.messages.append({"role": role, "content": content})
        c.last_accessed = time.time()
        self._run_cleanup_if_needed()

    def get_or_store_citation(self, conversation_id: str, citation: Citation) -> int:
        """
        Get existing citation number or store new citation and assign next number.
        Returns 1-indexed citation number.
        Raises ValueError if conversation not found.
        """
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        c = self.conversations.get(conversation_id)
        c.last_accessed = time.time()

        self._run_cleanup_if_needed()

        source_id = citation.source_id

        if source_id in c.citation_mapping:
            return c.citation_mapping.get(source_id)
        else:
            next_number = len(c.citation_mapping) + 1
            c.citation_mapping[source_id] = next_number
            c.conversation_citations[source_id] = citation
            return next_number


    def get_citation_mapping(self, conversation_id: str) -> Dict[str, int]:
        """Get PMC ID to citation number mapping. Returns empty dict if not found."""
        if conversation_id not in self.conversations:
            return {}
        
        c = self.conversations.get(conversation_id)
        c.last_accessed = time.time()
        return c.citation_mapping
    
    def get_all_citations(self, conversation_id: str) -> List[Citation]:
        """Return all Citation objects. Returns empty dict if not found."""
        if conversation_id not in self.conversations:
            return []
        
        c = self.conversations.get(conversation_id)
        c.last_accessed = time.time()

        all_citations = list(c.conversation_citations.values())
        all_citations.sort(key=lambda x: x.number)
        
        return all_citations
    
    def get_conversation_summaries(self) -> List[dict]:
        """Get summaries of all conversations, sorted by last_updated (newest first)"""
        summaries = []
        for c_id, convo in self.conversations.items():
            # Extracts first user message, with empty string if does not exist
            first_message = next((m["content"] for m in convo.messages if m["role"] == "user"), "")

            summaries.append({
                "conversation_id": convo.conversation_id,
                "first_message": first_message[:100],
                "message_count": len(convo.messages),
                "last_updated": convo.last_accessed
            })

        # Sort by last_updated descending (newest first)
        summaries.sort(key=lambda x: x["last_updated"], reverse=True)
        return summaries

    def cleanup_old_conversations(self) -> int:
        """Remove conversations inactive beyond max_age_seconds. Returns count removed."""
        current_time = time.time()
        to_remove = []
        for c_id, conversation in self.conversations.items():
            if current_time - conversation.last_accessed > self.max_age_seconds:
                to_remove.append(c_id)
        
        for c_id in to_remove:
            del self.conversations[c_id]

        return len(to_remove)

    def _run_cleanup_if_needed(self) -> None:
        """Run cleanup if over 100 conversations stored."""
        # Run cleanup if we have over 100 conversations
        if len(self.conversations) > 100:
            self.cleanup_old_conversations()
        