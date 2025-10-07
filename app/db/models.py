from sqlalchemy import Column, Integer, String, Text, DateTime, func, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from .database import Base


class Document(Base):
    """
    Research papers and regulatory documents with metadata.
    No embeddings at document level - all semantic search happens via chunks.
    """
    __tablename__ = "documents"

    # Primary key
    document_id = Column(Integer, primary_key=True, index=True)

    # Source identification
    source = Column(String, nullable=False)  # "pubmed", "clinicaltrials", "fda"
    source_id = Column(String, nullable=False)  # External ID (PMCID, NCT number, etc.)

    # Document content
    title = Column(Text, nullable=False)
    abstract = Column(Text)
    full_text = Column(Text)

    # Flexible metadata (authors, publication_date, journal, doi, etc.)
    # Named doc_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    doc_metadata = Column(JSONB)

    # Timestamps
    # created_at: When document row was first inserted
    # updated_at: When document content was replaced (NULL = never updated)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint('source', 'source_id', name='uq_source_sourceid'),
    )

    def __repr__(self):
        return f"<Document(id={self.document_id}, source={self.source}, title={self.title[:50]}...)>"


class DocumentChunk(Base):
    """
    Chunked sections of documents for granular RAG retrieval.
    Chunks are created with 512 tokens and 50-token overlap.
    Embeddings include context (document title + section) for better retrieval.
    """
    __tablename__ = "document_chunks"

    # Primary key
    document_chunk_id = Column(Integer, primary_key=True, index=True)

    # Foreign key to parent document
    document_id = Column(Integer, nullable=False, index=True)

    # Chunk metadata
    section = Column(String)  # "abstract", "methods", "results", "discussion"
    chunk_index = Column(Integer, nullable=False)  # Order within document (0, 1, 2...)

    # Content (raw text without context prepended)
    content = Column(Text, nullable=False)

    # Chunking details
    char_start = Column(Integer, nullable=False)  # Character offset in full_text
    char_end = Column(Integer, nullable=False)    # Character offset in full_text
    token_count = Column(Integer, nullable=False)  # Number of tokens (~512)

    # Vector embedding (1536 dimensions for OpenAI text-embedding-3-small)
    # NULL = embedding needs to be generated
    # Embedding is created from: "Document: {title}\nSection: {section}\n\n{content}"
    embedding = Column(Vector(1536))

    # Timestamps
    # created_at: When chunk row was inserted (independent of embedding status)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<DocumentChunk(id={self.document_chunk_id}, doc_id={self.document_id}, section={self.section})>"
