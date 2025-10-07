# Database Design

## Overview

OpenPharma uses PostgreSQL with the pgvector extension for storing research papers and their vector embeddings. The design prioritizes chunk-level semantic search for accurate RAG retrieval.

## Core Principles

1. **Chunk-level search only** - No document-level embeddings; all semantic search happens via chunks
2. **Batch embedding strategy** - Documents can be ingested without embeddings; embeddings generated later
3. **No versioning** - Document updates replace old data entirely (old chunks deleted)
4. **Context-enhanced embeddings** - Embeddings include document title + section for better retrieval
5. **Flexible metadata** - JSONB columns support source-specific fields

## Schema

### `documents` table

Stores metadata for research papers and regulatory documents. No embeddings at this level.

| Column | Type | Nullable | Constraints | Description |
|--------|------|----------|-------------|-------------|
| document_id | INTEGER | No | PRIMARY KEY | Auto-incrementing primary key |
| source | VARCHAR | No | Part of UNIQUE | Data source: "pubmed", "clinicaltrials", "fda" |
| source_id | VARCHAR | No | Part of UNIQUE | External ID (PMCID, NCT number, etc.) |
| title | TEXT | No | - | Document title |
| abstract | TEXT | Yes | - | Abstract/summary |
| full_text | TEXT | Yes | - | Full document text for chunking |
| doc_metadata | JSONB | Yes | - | Source-specific fields (authors, dates, journal, doi, etc.) |
| created_at | TIMESTAMP | No | DEFAULT now() | When document row was first inserted |
| updated_at | TIMESTAMP | Yes | - | When document content was replaced (NULL = never updated) |

**Constraints:**
- `UNIQUE(source, source_id)` - Prevents duplicate documents across data sources

**Example `doc_metadata` for PubMed:**
```json
{
  "authors": [
    {"name": "John Smith", "affiliation": "Harvard Medical School"},
    {"name": "Jane Doe", "affiliation": "MIT"}
  ],
  "publication_date": "2024-03-15",
  "journal": "Nature Medicine",
  "doi": "10.1038/s41591-024-12345",
  "keywords": ["cancer", "immunotherapy", "clinical trial"],
  "mesh_terms": ["Neoplasms", "Immunotherapy", "Humans"]
}
```

### `document_chunks` table

Stores chunked sections of documents with vector embeddings for semantic search.

| Column | Type | Nullable | Constraints | Description |
|--------|------|----------|-------------|-------------|
| document_chunk_id | INTEGER | No | PRIMARY KEY | Auto-incrementing primary key |
| document_id | INTEGER | No | INDEX | Foreign key to documents.document_id |
| section | VARCHAR | Yes | - | Section name: "abstract", "methods", "results", "discussion" |
| chunk_index | INTEGER | No | - | Order within document (0, 1, 2...) |
| content | TEXT | No | - | Raw chunk text (no context prepended) |
| char_start | INTEGER | No | - | Character offset where chunk starts in full_text |
| char_end | INTEGER | No | - | Character offset where chunk ends in full_text |
| token_count | INTEGER | No | - | Number of tokens in chunk (~512 with 50-token overlap) |
| embedding | VECTOR(1536) | Yes | HNSW INDEX | Vector embedding (NULL = needs generation) |
| created_at | TIMESTAMP | No | DEFAULT now() | When chunk row was inserted (independent of embedding status) |

**Indexes:**
- Primary key on `document_chunk_id`
- Index on `document_id` for JOINs to documents table
- HNSW index on `embedding` for fast vector similarity search

**Important notes:**
- `content` stores the raw text without any context prepended
- `embedding` is created from contextual text: `"Document: {title}\nSection: {section}\n\n{content}"`
- This separation allows flexible re-embedding strategies while preserving clean content for display

## Chunking Strategy

### Parameters
- **Chunk size**: 512 tokens
- **Overlap**: 50 tokens
- **Context prepending**: Document title + section name

### Example

For a paper titled "Immunotherapy in NSCLC: A Phase 2 Trial" with a Methods section:

**Chunk content (stored in DB):**
```
25 patients received pembrolizumab 200mg IV every 3 weeks for up to 2 years.
Inclusion criteria were age ≥18, histologically confirmed NSCLC...
```

**Text used for embedding (not stored):**
```
Document: Immunotherapy in NSCLC: A Phase 2 Trial
Section: Methods

25 patients received pembrolizumab 200mg IV every 3 weeks for up to 2 years.
Inclusion criteria were age ≥18, histologically confirmed NSCLC...
```

### Overlap visualization

For a 1500-token Methods section:

| chunk_index | char_start | char_end | tokens | Overlap |
|-------------|------------|----------|--------|---------|
| 0 | 0 | 1024 | 512 | - |
| 1 | 924 | 1948 | 512 | 50 tokens with chunk 0 |
| 2 | 1848 | 2500 | 512 | 50 tokens with chunk 1 |

The overlap prevents information loss at chunk boundaries.

## Vector Embeddings

### Model
- **OpenAI text-embedding-3-small**
- **Dimensions**: 1536
- **Rationale**: Fits under HNSW's 2000-dimension limit while maintaining good quality

### Index Type: HNSW
```sql
CREATE INDEX idx_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**Parameters:**
- `m = 16`: Number of connections per layer (higher = more accurate but slower)
- `ef_construction = 64`: Quality during index build (higher = better index but slower build)
- `vector_cosine_ops`: Use cosine distance for similarity (standard for embeddings)

**Why HNSW over IVFFlat:**
- Better accuracy (~99%+ vs ~95-98%)
- Faster query performance
- Insert speed not critical for batch ingestion
- Well-suited for our dataset size (<1M chunks)

### Embedding Workflow

**Initial ingestion (batch):**
```python
# Insert document
doc = Document(source="pubmed", source_id="PMC123456", title="...", full_text="...")
db.add(doc)

# Create chunks without embeddings
chunks = chunk_document(doc)
for chunk in chunks:
    chunk.embedding = None  # Will be generated later
    db.add(chunk)

# Later: Batch embedding job
pending_chunks = db.query(DocumentChunk).filter(DocumentChunk.embedding == None).all()
for chunk in pending_chunks:
    context_text = f"Document: {doc.title}\nSection: {chunk.section}\n\n{chunk.content}"
    chunk.embedding = get_embedding(context_text)  # OpenAI API call
```

**Document update:**
```python
# Delete old chunks
db.query(DocumentChunk).filter(document_id == doc.id).delete()

# Create new chunks and embed immediately (so search still works)
new_chunks = chunk_document(doc)
for chunk in new_chunks:
    context_text = f"Document: {doc.title}\nSection: {chunk.section}\n\n{chunk.content}"
    chunk.embedding = get_embedding(context_text)
    db.add(chunk)

doc.updated_at = now()
```

## Common Query Patterns

### 1. Vector similarity search with document metadata
```sql
SELECT
    c.content,
    c.section,
    d.title,
    d.abstract,
    d.doc_metadata,
    c.embedding <=> '[0.1, 0.2, ...]'::vector AS distance
FROM document_chunks c
JOIN documents d ON c.document_id = d.document_id
WHERE c.embedding IS NOT NULL
ORDER BY c.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

### 2. Check if document exists (during ingestion)
```sql
SELECT * FROM documents
WHERE source = 'pubmed' AND source_id = 'PMC123456';
```

### 3. Find chunks needing embeddings
```sql
SELECT * FROM document_chunks
WHERE embedding IS NULL;
```

### 4. Get all chunks for a document
```sql
SELECT * FROM document_chunks
WHERE document_id = 123
ORDER BY chunk_index;
```

### 5. Filter by section during search
```sql
SELECT c.*, d.title
FROM document_chunks c
JOIN documents d ON c.document_id = d.document_id
WHERE c.section = 'methods'
  AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

## Design Decisions & Rationale

### Why no document-level embeddings?

**Problem**: Embedding an entire 20-page paper into one vector loses semantic granularity.

**Better approach**: Search chunks, then join to parent document for metadata.

**Example**: Query "What were the inclusion criteria?" should match the specific Methods chunk, not the entire paper.

### Why store raw content separately from embedding context?

**Storage efficiency**: Don't duplicate title in every chunk's content field.

**Flexibility**: Can re-embed with different context strategies without changing stored content.

**Clean retrieval**: Show users raw content, not "Document: Title\nSection: Methods\n..."

### Why JSONB for metadata instead of separate columns?

**Different sources, different fields**:
- PubMed: `journal`, `doi`, `mesh_terms`
- ClinicalTrials: `phase`, `enrollment`, `sponsor`
- FDA: `approval_date`, `drug_class`

**Flexibility**: Add new sources without schema migrations.

**Queryable**: JSONB supports indexing and filtering: `WHERE doc_metadata->>'phase' = 'Phase 2'`

### Why compound UNIQUE constraint on (source, source_id)?

**Problem**: Different sources might use same IDs (e.g., "12345" could be both a PubMed ID and trial number).

**Solution**: Uniqueness scoped to source type.

**Benefit**: Prevents duplicates while supporting multiple data sources.

### Why nullable embedding column?

**Batch ingestion workflow**: Ingest 1000 papers quickly, then embed overnight (cheaper, more efficient).

**Re-embedding**: When switching models, set all embeddings to NULL and regenerate.

**Failed embeddings**: If API call fails, row still exists and can be retried.

### Why no versioning?

**Complexity**: Versioning requires tracking which version is "active" and filtering in all queries.

**Use case**: For research papers, the latest version is what matters. Historical versions rarely needed.

**Alternative**: If version history is needed, implement at application layer (soft delete + version column).

## Maintenance Operations

### Re-embedding with new model
```python
# Manual trigger when switching to better model
all_chunks = db.query(DocumentChunk).all()
for chunk in all_chunks:
    context_text = f"Document: {doc.title}\nSection: {chunk.section}\n\n{chunk.content}"
    chunk.embedding = get_embedding_v2(context_text)  # New model
db.commit()
```

### Updating a document
```python
# Fetch updated content from source
new_content = fetch_pubmed_paper("PMC123456")

# Find existing document
doc = db.query(Document).filter(
    Document.source == "pubmed",
    Document.source_id == "PMC123456"
).first()

# Update content
doc.full_text = new_content
doc.updated_at = now()

# Delete old chunks
db.query(DocumentChunk).filter(document_id == doc.document_id).delete()

# Create and embed new chunks
new_chunks = chunk_document(doc)
for chunk in new_chunks:
    context_text = f"Document: {doc.title}\nSection: {chunk.section}\n\n{chunk.content}"
    chunk.embedding = get_embedding(context_text)
    db.add(chunk)

db.commit()
```

## Future Considerations

### Phase 2 optimizations
- Add GIN index on `doc_metadata` for faster JSONB queries
- Partition `document_chunks` by `document_id` if dataset exceeds 10M chunks
- Consider materialized views for common aggregations

### Phase 3 optimizations
- Horizontal sharding by `source` if single-source queries dominate
- Dedicated read replicas for vector search
- Experiment with quantization to reduce embedding storage (1536 floats → int8)

## References

- [pgvector documentation](https://github.com/pgvector/pgvector)
- [HNSW algorithm paper](https://arxiv.org/abs/1603.09320)
- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings)
