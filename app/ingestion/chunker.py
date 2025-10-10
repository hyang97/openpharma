"""
Document chunking service.
Implements token-based chunking with 512 tokens and 50-token overlap.
Chunks each section separately to preserve semantic boundaries.
"""
from typing import List, Dict
import tiktoken
import logging

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Chunks documents into overlapping segments for RAG."""

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 50,
        encoding_name: str = "cl100k_base"  # OpenAI's tokenizer
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoder = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoder.encode(text))

    def chunk_text(
        self,
        text: str,
        section: str = "body",
        doc_title: str = "",
        section_char_start: int = 0
    ) -> List[Dict]:
        """
        Chunk text into overlapping segments.

        Args:
            text: Text to chunk
            section: Section name (abstract, introduction, methods, etc.)
            doc_title: Document title for context
            section_char_start: Character offset where this section starts in full_text

        Returns:
            List of chunk dicts with keys: content, section, chunk_index,
            char_start, char_end, token_count, embedding_text
        """
        if not text or not text.strip():
            return []

        tokens = self.encoder.encode(text)
        chunks = []
        chunk_index = 0
        start_idx = 0

        while start_idx < len(tokens):
            # Get chunk of tokens
            end_idx = min(start_idx + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]

            # Decode back to text
            chunk_text = self.encoder.decode(chunk_tokens)

            # Calculate character offsets within the section text
            char_start_in_section = len(self.encoder.decode(tokens[:start_idx]))
            char_end_in_section = len(self.encoder.decode(tokens[:end_idx]))

            # Calculate absolute character offsets in full_text
            # section_char_start is where this section begins in the document's full_text
            abs_char_start = section_char_start + char_start_in_section
            abs_char_end = section_char_start + char_end_in_section

            # Create embedding text with context (title + section + content)
            # This is what gets embedded, not the content alone
            embedding_text = f"Document: {doc_title}\nSection: {section}\n\n{chunk_text}"

            chunks.append({
                "content": chunk_text,
                "section": section,
                "chunk_index": chunk_index,
                "char_start": abs_char_start,
                "char_end": abs_char_end,
                "token_count": len(chunk_tokens),
                "embedding_text": embedding_text  # Used for embedding, not stored in DB
            })

            chunk_index += 1

            # Move to next chunk with overlap
            start_idx = end_idx - self.overlap

            # Break if we're at the end
            if end_idx >= len(tokens):
                break

        return chunks

    def chunk_document(self, document: Dict) -> List[Dict]:
        """
        Chunk an entire document, processing each section separately.

        Args:
            document: Dict with keys:
                - title: Document title
                - full_text: Full article text, with all sections and headers
                - section_offsets: Contains section, char_start, and char_end

        Returns:
            List of chunk dicts ready for database insertion
        """
        all_chunks = []
        title = document.get("title", "")
        full_text = document.get("full_text", "")
        section_offsets = document.get("section_offsets", [])

        # Create sections: {"introduction": "text...", "methods": "text...", ...}, skip title
        sections = {}
        section_starts = {}
        for section in section_offsets:
            section_name = section["section"]
            if section_name in ["title"]:
                continue
            
            # Extract section text from full_text 
            char_start = section["char_start"]
            char_end = section["char_end"]
            section_text = full_text[char_start:char_end].strip()
            sections[section_name] = section_text
            section_starts[section_name] = char_start

        # Chunk each body section separately
        for section_name, section_text in sections.items():
            # Get the character offset for this section in full_text
            char_start = section_starts.get(section_name, 0)

            section_chunks = self.chunk_text(
                text=section_text,
                section=section_name,
                doc_title=title,
                section_char_start=char_start
            )
            all_chunks.extend(section_chunks)

        # Special case: title-only document
        if not all_chunks and title:
            section_chunks = self.chunk_text(
                text=title, 
                section="N/A",
                doc_title="Title-Only Article",
                section_char_start=0
            )
            all_chunks.extend(section_chunks)

        # Renumber chunk_index globally across all sections
        for global_index, chunk in enumerate(all_chunks):
            chunk["chunk_index"] = global_index

        logger.debug(
            f"Document '{title[:50]}...' chunked into "
            f"{len(all_chunks)} total chunks across "
            f"{len(sections)} sections"
        )
        return all_chunks
