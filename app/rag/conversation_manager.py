"""
Conversation Manager for OpenPharma RAG system.

Manages multi-turn conversations with consistent citation numbering across turns.
"""
from typing import Dict, List, Optional
import uuid
import time

from app.models import Citation, Conversation, SearchResult


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


    def create_conversation(self, user_id: str, conversation_id: Optional[str] = None) -> str:
        """Create a new conversation and return its UUID. Optionally accept client-provided ID"""
        self._run_cleanup_if_needed()

        c_id = conversation_id or str(uuid.uuid4())

        # Check if already exists
        if c_id in self.conversations:
            raise ValueError(f"Conversation {c_id} already exists")

        c = Conversation(conversation_id=c_id, user_id=user_id)
        self.conversations[c_id] = c
        return c_id


    def get_conversation(self, conversation_id: str, user_id: Optional[str] = None) -> Optional[Conversation]:
        """Retrieve conversation by ID, updating last_accessed. Returns None if not found or unauthorized."""
        if conversation_id not in self.conversations:
            return None 
        
        c = self.conversations.get(conversation_id, None)

        # Ownership validation (if user_id provided)
        if user_id is not None and c.user_id != user_id:
            return None

        c.last_accessed = time.time()
        return c


    def get_messages(self, conversation_id: str) -> List[dict]:
        """Get message history. Returns empty list if conversation not found."""
        if conversation_id not in self.conversations:
            return []
        else:
            return self.conversations.get(conversation_id).messages


    def add_message(
            self, 
            conversation_id: str, 
            role: str, 
            content: str, 
            cited_source_ids: Optional[List[str]] = None, 
            cited_chunk_ids: Optional[List[int]] = None
            ) -> None:
        """Add message to conversation with optional citation tracking."""
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        c = self.conversations.get(conversation_id)

        message = {"role": role, "content": content}
        if cited_source_ids is not None:
            message["cited_source_ids"] = cited_source_ids
        
        if cited_chunk_ids is not None:
            message["cited_chunk_ids"] = cited_chunk_ids

        c.messages.append(message)
        c.last_accessed = time.time()
        self._run_cleanup_if_needed()


    def delete_last_message(self, conversation_id: str) -> Dict:
        """Delete the last message for rollback"""
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        c = self.conversations.get(conversation_id)

        if not c.messages:
            raise ValueError(f"Conversation {conversation_id} has no messages")
        
        c.last_accessed = time.time()
        return c.messages.pop()
        

    def get_or_create_citation(self, conversation_id: str, chunk: SearchResult) -> Citation:
        """
        Get existing citation or create new one from SearchResult with assigned number.
        """
        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        c = self.conversations.get(conversation_id)
        c.last_accessed = time.time()
        self._run_cleanup_if_needed()

        source_id = chunk.source_id

        # If already exists, return existing Citation
        if source_id in c.conversation_citations:
            return c.conversation_citations[source_id]

        # Create new citation with assigned number
        next_number = len(c.citation_mapping) + 1
        citation = Citation(
            number=next_number,
            source_id=source_id,
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            journal=chunk.journal or "",
            authors=chunk.authors,
            publication_date=chunk.publication_date
        )

        c.citation_mapping[source_id] = next_number
        c.conversation_citations[source_id] = citation

        return citation


    def get_citation_mapping(self, conversation_id: str) -> Dict[str, int]:
        """Get source_id -> number mapping."""
        if conversation_id not in self.conversations:
            return {}
        
        c = self.conversations.get(conversation_id)
        c.last_accessed = time.time()
        return c.citation_mapping
    

    def get_all_citations(self, conversation_id: str) -> List[Citation]:
        """Return all Citation objects sorted by number."""
        if conversation_id not in self.conversations:
            return []
        
        c = self.conversations.get(conversation_id)
        c.last_accessed = time.time()

        all_citations = list(c.conversation_citations.values())
        all_citations.sort(key=lambda x: x.number)
        
        return all_citations
    

    def get_conversation_summaries(self, user_id: str) -> List[dict]:
        """Get all conversation summaries for a specific user, sorted by most recent."""
        summaries = []
        for c_id, convo in self.conversations.items():
            # Filter by user_id
            if convo.user_id != user_id:
                continue
            
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
        """Remove stale conversations, return count removed."""
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
        