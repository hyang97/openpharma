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

        logger.info(
            f"Chunked {self.count_tokens(text)} tokens from section '{section}' into "
            f"{len(chunks)} chunks"
        )
        return chunks

    def chunk_document(self, document: Dict) -> List[Dict]:
        """
        Chunk an entire document, processing each section separately.

        Args:
            document: Dict with keys:
                - title: Document title
                - abstract: Abstract text (optional)
                - sections: Dict mapping section names to text (body sections only)
                - metadata: Must contain 'section_offsets' with char positions

        Returns:
            List of chunk dicts ready for database insertion
        """
        all_chunks = []
        doc_title = document.get("title", "")
        abstract = document.get("abstract", "")
        sections = document.get("sections", {})
        section_offsets = document.get("metadata", {}).get("section_offsets", [])

        # Create a lookup for section character offsets
        section_offset_map = {
            offset["section"]: offset["char_start"]
            for offset in section_offsets
        }

        # Skip title - it's already in full_text for completeness, but we don't chunk it
        # because it's short and included in every chunk's embedding_text anyway

        # Chunk abstract if it exists
        if abstract and "abstract" in section_offset_map:
            abstract_chunks = self.chunk_text(
                text=abstract,
                section="abstract",
                doc_title=doc_title,
                section_char_start=section_offset_map["abstract"]
            )
            all_chunks.extend(abstract_chunks)

        # Chunk each body section separately
        for section_name, section_text in sections.items():
            # Get the character offset for this section in full_text
            section_char_start = section_offset_map.get(section_name, 0)

            section_chunks = self.chunk_text(
                text=section_text,
                section=section_name,
                doc_title=doc_title,
                section_char_start=section_char_start
            )
            all_chunks.extend(section_chunks)

        # Renumber chunk_index globally across all sections
        for global_index, chunk in enumerate(all_chunks):
            chunk["chunk_index"] = global_index

        logger.info(
            f"Document '{doc_title[:50]}...' chunked into "
            f"{len(all_chunks)} total chunks across "
            f"{len(sections) + (1 if abstract else 0) + (1 if doc_title else 0)} sections"
        )
        return all_chunks
