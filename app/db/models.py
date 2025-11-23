"""
Database models for OpenPharma ingestion pipeline.

SCHEMA OVERVIEW
===============================================================================

TABLE: pubmed_papers - Tracks discovered PMC IDs and fetch status
-------------------------------------------------------------------------------
pmc_id            VARCHAR       PRIMARY KEY        "1234567" (numeric only)
pmid              BIGINT                           PubMed ID (NULL=not fetched, -1=no PMID found)
doi               TEXT                             DOI (from NCBI API)
nih_percentile    FLOAT                            NIH percentile (NULL=not queried, -1=no data, >=0=actual) [DEPRECATED]
publication_year  INTEGER                          Publication year (NULL=not queried, -1=no data, >0=actual) [DEPRECATED]
citation_count    INTEGER                          Total citations (NULL=not queried, -1=no data, >=0=actual) [DEPRECATED]
relative_citation_ratio FLOAT                      RCR: field-adjusted citation metric (NULL=not queried, -1=no data, >=0=actual) [DEPRECATED]
is_clinical       BOOLEAN                          Clinical article (NULL=not queried or no data, True/False=actual) [DEPRECATED]
is_research_article BOOLEAN                        Research article (NULL=not queried or no data, True/False=actual) [DEPRECATED]
discovered_at     TIMESTAMP     DEFAULT NOW()
fetch_status      VARCHAR       DEFAULT 'pending'  'pending' | 'wont_fetch' | 'fetched' | 'failed'
priority          INTEGER       DEFAULT 50         Priority level (0=exclude, 10=low, 50=normal, 100=high)

SENTINEL VALUES (numeric/float only): -1 = "queried but no data available", NULL = "not yet queried"
BOOLEAN FIELDS: NULL = "not queried or no data", True/False = "actual value"

INDEX: idx_pubmed_papers_fetch_status ON fetch_status
INDEX: idx_pubmed_papers_pmid ON pmid
INDEX: idx_pubmed_papers_percentile ON nih_percentile
INDEX: idx_pubmed_papers_year ON publication_year
INDEX: idx_pubmed_papers_citation_count ON citation_count
INDEX: idx_pubmed_papers_rcr ON relative_citation_ratio
INDEX: idx_pubmed_papers_priority ON priority


TABLE: documents - Research papers and regulatory documents
-------------------------------------------------------------------------------
document_id       SERIAL        PRIMARY KEY
source            VARCHAR       NOT NULL           "pubmed" | "clinicaltrials" | "fda"
source_id         VARCHAR       NOT NULL           External ID (PMC ID, NCT number, etc.)
title             TEXT          NOT NULL
abstract          TEXT
full_text         TEXT                             Concatenated sections with headers
doc_metadata      JSONB                            Authors, journal, section_offsets, etc.
priority          INTEGER       DEFAULT 50         Priority level (0=exclude, 10=low, 50=normal, 100=high)
ingestion_status  VARCHAR       DEFAULT 'fetched'  'fetched' | 'chunked' | 'batch_submitted' | 'embedded'
openai_batch_id   VARCHAR                          Reference to batch job (nullable)
created_at        TIMESTAMP     DEFAULT NOW()
updated_at        TIMESTAMP

UNIQUE: (source, source_id)
INDEX:  idx_documents_ingestion_status ON ingestion_status
INDEX:  idx_documents_openai_batch_id ON openai_batch_id
INDEX:  idx_documents_priority ON priority


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
embedding          VECTOR(768)                      Ollama nomic-embed-text (NULL until embedded)
openai_embedding   VECTOR(1536)                     Legacy OpenAI embeddings (backup)
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
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Float, Boolean, func, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from .database import Base


class PubMedPaper(Base):
    """Tracks discovered PMC IDs and whether they've been fetched.

    NOTE: Citation metric columns (nih_percentile, citation_count, etc.) are DEPRECATED.
    These columns exist for backward compatibility but are NOT maintained going forward.
    Always use JOIN with icite_metadata table for citation filtering.

    Sentinel values for ID mapping:
        - pmid = -1: Looked up via NCBI API but no PMID found (invalid/non-existent PMC ID)
        - pmid = NULL: Not yet queried

    Citation metric columns (DEPRECATED - do not use):
        - nih_percentile, citation_count, publication_year, relative_citation_ratio
        - is_clinical, is_research_article
        - These are partially populated but NOT maintained
        - Use JOIN with icite_metadata instead: filter_by_metrics() does this automatically
    """
    __tablename__ = "pubmed_papers"

    # Primary key
    pmc_id = Column(String, primary_key=True, index=True)

    # ID mapping (PMC <-> PMID conversion)
    pmid = Column(Integer)  # BIGINT in Postgres, NULL = not fetched, -1 = no PMID found
    doi = Column(Text)      # DOI from NCBI API

    # Citation metrics (DEPRECATED - use JOIN with icite_metadata instead)
    # These columns are partially populated but NOT maintained going forward
    nih_percentile = Column(Float)              # DEPRECATED: Use icite_metadata.nih_percentile
    publication_year = Column(Integer)           # DEPRECATED: Use icite_metadata.year
    citation_count = Column(Integer)             # DEPRECATED: Use icite_metadata.citation_count
    relative_citation_ratio = Column(Float)      # DEPRECATED: Use icite_metadata.relative_citation_ratio
    is_clinical = Column(Boolean)                # DEPRECATED: Use icite_metadata.is_clinical
    is_research_article = Column(Boolean)        # DEPRECATED: Use icite_metadata.is_research_article

    # Tracking fields
    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetch_status = Column(String, default='pending', nullable=False)  # 'pending', 'wont_fetch', 'fetched', 'failed'
    priority = Column(Integer, default=50, nullable=False)  # 0=exclude, 10=low, 50=normal, 100=high

    # Indexes
    __table_args__ = (
        Index('idx_pubmed_papers_fetch_status', 'fetch_status'),
        Index('idx_pubmed_papers_pmid', 'pmid'),
        Index('idx_pubmed_papers_percentile', 'nih_percentile'),
        Index('idx_pubmed_papers_year', 'publication_year'),
        Index('idx_pubmed_papers_citation_count', 'citation_count'),
        Index('idx_pubmed_papers_rcr', 'relative_citation_ratio'),
        Index('idx_pubmed_papers_priority', 'priority'),
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

    # Priority level for filtering in semantic search
    priority = Column(Integer, default=50, nullable=False)  # 0=exclude, 10=low, 50=normal, 100=high

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
        Index('idx_documents_priority', 'priority'),
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


class ICiteMetadata(Base):
    """NIH iCite citation metrics for PubMed papers (imported from NIH snapshot)."""
    __tablename__ = "icite_metadata"

    # Primary key
    pmid = Column(BigInteger, primary_key=True)  # PubMed ID

    # Basic metadata
    doi = Column(Text)                            # Digital Object Identifier
    title = Column(Text)                          # Article title
    authors = Column(Text)                        # Comma-separated author names
    year = Column(Integer)                        # Publication year
    journal = Column(Text)                        # Journal name (ISO abbreviation)
    is_research_article = Column(Boolean)         # True if primary research article

    # Citation metrics
    citation_count = Column(Integer)                    # Total number of citations
    field_citation_rate = Column(Float)                 # Intrinsic citation rate of paper's field
    expected_citations_per_year = Column(Float)         # Expected citations for NIH papers in same field
    citations_per_year = Column(Float)                  # Actual citations per year since publication
    relative_citation_ratio = Column(Float)             # RCR: field-adjusted citation metric (NIH median = 1.0)
    nih_percentile = Column(Float)                      # Percentile rank vs all NIH papers (99 = top 1%)

    # Translation metrics (Human/Animal/Molecular-Cellular classification)
    human = Column(Float)                         # Fraction of MeSH terms in Human category
    animal = Column(Float)                        # Fraction of MeSH terms in Animal category
    molecular_cellular = Column(Float)            # Fraction of MeSH terms in Molecular/Cellular category
    x_coord = Column(Float)                       # X coordinate on Triangle of Biomedicine
    y_coord = Column(Float)                       # Y coordinate on Triangle of Biomedicine
    apt = Column(Float)                           # Approximate Potential to Translate (ML-based score)

    # Clinical classification
    is_clinical = Column(Boolean)                 # True if clinical article
    cited_by_clin = Column(Text)                  # Comma-separated PMIDs of clinical articles citing this

    # Citation network
    cited_by = Column(Text)                       # Comma-separated PMIDs of all citing articles
    references = Column(Text)                     # Comma-separated PMIDs in reference list

    # Metadata tracking
    provisional = Column(Boolean)                 # True if RCR is provisional (paper < 2 years old)
    last_modified = Column(Text)                  # When iCite last updated this record (stored as text in CSV)

    # Indexes (created by migration script)
    __table_args__ = (
        Index('idx_icite_percentile', 'nih_percentile'),
        Index('idx_icite_year', 'year'),
        Index('idx_icite_citation_count', 'citation_count'),
    )

    def __repr__(self):
        return f"<ICiteMetadata(pmid={self.pmid}, percentile={self.nih_percentile}, year={self.year})>"


# CitationLink table dropped 2025-01-23 (81 GB, not used in Phase 1)
# Can be re-imported from NIH iCite snapshot if needed for Phase 2 citation graph features
