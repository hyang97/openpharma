"""
Database models for OpenPharma ingestion pipeline.

SCHEMA OVERVIEW
===============================================================================

TABLE: pubmed_papers - Tracks discovered PMC IDs and fetch status
-------------------------------------------------------------------------------
pmc_id            VARCHAR       PRIMARY KEY        "1234567" (numeric only)
discovered_at     TIMESTAMP     DEFAULT NOW()
fetch_status      VARCHAR       DEFAULT 'pending'  'pending' | 'fetched' | 'failed'

INDEX: idx_pubmed_papers_fetch_status ON fetch_status


TABLE: documents - Research papers and regulatory documents
-------------------------------------------------------------------------------
document_id       SERIAL        PRIMARY KEY
source            VARCHAR       NOT NULL           "pubmed" | "clinicaltrials" | "fda"
source_id         VARCHAR       NOT NULL           External ID (PMC ID, NCT number, etc.)
title             TEXT          NOT NULL
abstract          TEXT
full_text         TEXT                             Concatenated sections with headers
doc_metadata      JSONB                            Authors, journal, section_offsets, etc.
ingestion_status  VARCHAR       DEFAULT 'fetched'  'fetched' | 'chunked' | 'batch_submitted' | 'embedded'
openai_batch_id   VARCHAR                          Reference to batch job (nullable)
created_at        TIMESTAMP     DEFAULT NOW()
updated_at        TIMESTAMP

UNIQUE: (source, source_id)
INDEX:  idx_documents_ingestion_status ON ingestion_status
INDEX:  idx_documents_openai_batch_id ON openai_batch_id


TABLE: document_chunks - Chunked content with vector embeddings
-------------------------------------------------------------------------------
document_chunk_id  SERIAL        PRIMARY KEY
document_id        INTEGER       NOT NULL
section            VARCHAR                          "abstract" | "methods" | "results" | etc.
chunk_index        INTEGER       NOT NULL           Order within document (0, 1, 2...)
content            TEXT          NOT NULL           Raw chunk text
char_start         INTEGER       NOT NULL           Character offset in full_text
char_end           INTEGER       NOT NULL           Character offset in full_text
token_count        INTEGER       NOT NULL           ~512 tokens per chunk
embedding          VECTOR(1536)                     NULL until embedded
created_at         TIMESTAMP     DEFAULT NOW()

INDEX: idx_chunks_document ON document_id
INDEX: idx_chunks_embedding ON embedding USING hnsw (m=16, ef_construction=64)
INDEX: idx_chunks_needs_embedding ON document_chunk_id WHERE embedding IS NULL


TABLE: openai_batches - Tracks OpenAI Batch API embedding jobs
-------------------------------------------------------------------------------
openai_batch_id    VARCHAR       PRIMARY KEY        OpenAI batch ID (e.g., "batch_abc123")
status             VARCHAR       DEFAULT 'submitted' 'submitted' | 'validating' | 'in_progress' | etc.
submitted_at       TIMESTAMP     DEFAULT NOW()
completed_at       TIMESTAMP                        When batch finished
doc_count          INTEGER                          Number of documents in batch
chunk_count        INTEGER                          Number of chunks/requests in batch
token_count        BIGINT                           Total tokens in batch
input_file         VARCHAR                          Path to input JSONL file
output_file        VARCHAR                          Path to output JSONL file
error_message      TEXT                             Error details if failed

INDEX: idx_openai_batches_status ON status
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, func, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from .database import Base


class PubMedPaper(Base):
    """Tracks discovered PMC IDs and whether they've been fetched."""
    __tablename__ = "pubmed_papers"

    # Primary key
    pmc_id = Column(String, primary_key=True, index=True)

    # Tracking fields
    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetch_status = Column(String, default='pending', nullable=False)  # 'pending', 'fetched', 'failed'

    # Indexes
    __table_args__ = (
        Index('idx_pubmed_papers_fetch_status', 'fetch_status'),
    )

    def __repr__(self):
        return f"<PubMedPaper(pmc_id=PMC{self.pmc_id}, status={self.fetch_status})>"


class Document(Base):
    """
    Research papers and regulatory documents with full text and metadata.
    Sections are stored concatenated in full_text with character offsets in doc_metadata.
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
    full_text = Column(Text)  # Concatenated sections with headers (see design notes above)

    # Flexible metadata (authors, publication_date, journal, doi, section_offsets, etc.)
    # Named doc_metadata to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    # IMPORTANT: section_offsets must be stored here (see design notes above)
    doc_metadata = Column(JSONB)

    # Ingestion pipeline status tracking
    # Used by Stage 3 (chunking) and Stage 4 (embedding)
    ingestion_status = Column(String, default='fetched', nullable=False)  # 'fetched', 'chunked', 'batch_submitted', 'embedded'
    openai_batch_id = Column(String)  # Reference to OpenAI Batch API job (nullable)

    # Timestamps
    # created_at: When document row was first inserted
    # updated_at: When document content was replaced (NULL = never updated)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('source', 'source_id', name='uq_source_sourceid'),
        Index('idx_documents_ingestion_status', 'ingestion_status'),
    )

    def __repr__(self):
        return f"<Document(id={self.document_id}, source={self.source}, title={self.title[:50]}...)>"


class DocumentChunk(Base):
    """Token-based chunks (512 tokens, 50 overlap) with vector embeddings for RAG retrieval."""
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

    # Vector embeddings
    # Old OpenAI embeddings (backup, will be dropped after migration validated)
    openai_embedding = Column(Vector(1536))

    # New Ollama embeddings (768 dimensions for nomic-embed-text)
    # NULL = embedding needs to be generated
    # Embedding is created from: "Document: {title}\nSection: {section}\n\n{content}"
    embedding = Column(Vector(768))

    # Timestamps
    # created_at: When chunk row was inserted (independent of embedding status)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_chunks_document', 'document_id'),
        Index('idx_chunks_embedding', 'embedding', postgresql_using='hnsw',
              postgresql_with={'m': 16, 'ef_construction': 64},
              postgresql_ops={'embedding': 'vector_cosine_ops'}),
        Index('idx_chunks_needs_embedding', 'document_chunk_id', postgresql_where=Column('embedding').is_(None)),
    )

    def __repr__(self):
        return f"<DocumentChunk(id={self.document_chunk_id}, doc_id={self.document_id}, section={self.section})>"


class OpenAIBatch(Base):
    """Tracks OpenAI Batch API embedding jobs for monitoring and recovery."""
    __tablename__ = "openai_batches"

    # Primary key (OpenAI batch ID)
    openai_batch_id = Column(String, primary_key=True)

    # Batch status
    status = Column(String, default='submitted', nullable=False)

    # Timestamps
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))

    # Batch statistics
    doc_count = Column(Integer)
    chunk_count = Column(Integer)
    token_count = Column(Integer)

    # File paths
    input_file = Column(String)
    output_file = Column(String)

    # Error tracking
    error_message = Column(Text)

    # Indexes
    __table_args__ = (
        Index('idx_openai_batches_status', 'status'),
    )

    def __repr__(self):
        return f"<OpenAIBatch(id={self.openai_batch_id}, status={self.status}, chunks={self.chunk_count})>"
