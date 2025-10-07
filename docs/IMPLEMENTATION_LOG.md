# Implementation Log

## Database Setup (2024-10-06)

### What We Built

Implemented a production-ready database schema for OpenPharma's RAG system with PostgreSQL + pgvector.

### Key Design Decisions

1. **Vector Embeddings: text-embedding-3-small (1536 dims)**
   - Why: HNSW index has 2000-dimension limit
   - Alternative considered: text-embedding-3-large (3072 dims) → would require IVFFlat
   - Trade-off: 50% cost savings, HNSW compatibility, negligible quality difference

2. **Chunk-level search only (no document embeddings)**
   - Why: Prevents context bloat, better retrieval accuracy
   - Documents table stores metadata only
   - All semantic search happens via document_chunks table

3. **HNSW vs. IVFFlat index**
   - Chose: HNSW (m=16, ef_construction=64)
   - Why: Better accuracy (~99%+ vs ~95%), faster queries
   - Trade-off: Slower inserts (acceptable for batch ingestion)

4. **Context-enhanced embeddings**
   - Embeddings created from: `"Document: {title}\nSection: {section}\n\n{content}"`
   - Raw content stored without context (clean for display)
   - Enables flexible re-embedding strategies

5. **Batch embedding workflow**
   - `embedding` column is nullable
   - Documents can be ingested without embeddings
   - Batch job generates embeddings later (cost-efficient)

6. **No versioning**
   - Document updates delete old chunks, create new ones
   - Simpler schema, no version tracking needed
   - Latest version is always what matters for research papers

7. **JSONB for metadata**
   - Column name: `doc_metadata` (avoiding SQLAlchemy reserved word)
   - Supports different source schemas (PubMed, ClinicalTrials, FDA)
   - Queryable with JSONB operators

8. **Chunking strategy**
   - 512 tokens per chunk
   - 50-token overlap between chunks
   - Section-based organization (abstract, methods, results, discussion)
   - Prevents information loss at boundaries

### Schema

#### `documents` table
- `document_id` (PK)
- `source`, `source_id` (UNIQUE constraint)
- `title`, `abstract`, `full_text`
- `doc_metadata` (JSONB)
- `created_at`, `updated_at`

#### `document_chunks` table
- `document_chunk_id` (PK)
- `document_id` (FK, indexed)
- `section`, `chunk_index`
- `content` (raw text)
- `char_start`, `char_end`, `token_count`
- `embedding` (VECTOR(1536), nullable, HNSW indexed)
- `created_at`

### Files Created

- `app/db/database.py` - SQLAlchemy engine and session management
- `app/db/models.py` - Document and DocumentChunk ORM models
- `app/db/init_db.py` - Database initialization script
- `docs/database_design.md` - Comprehensive design documentation

### Testing

```bash
# Start Postgres
docker-compose up -d postgres

# Initialize database
source venv/bin/activate
python -m app.db.init_db

# Verify schema
docker-compose exec postgres psql -U admin -d openpharma -c "\d documents"
docker-compose exec postgres psql -U admin -d openpharma -c "\d document_chunks"
```

### Next Steps

1. Implement PubMed data ingestion
2. Build chunking logic (512 tokens, 50 overlap)
3. Integrate OpenAI embedding API
4. Create RAG query endpoint
5. Add Streamlit UI

### Documentation Updated

- `CLAUDE.md` - Updated with actual implementation details
- `openpharma_spec_v1.md` - Reflected design decisions in spec
- `docs/database_design.md` - Comprehensive database documentation
