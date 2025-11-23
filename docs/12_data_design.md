# Data Design Documentation

This document describes the data ingestion pipeline and storage design for OpenPharma.

## Table of Contents
- [Overview](#overview)
- [Ingestion Pipeline](#ingestion-pipeline)
- [Database Schema](#database-schema)
- [Section Storage Strategy](#section-storage-strategy)
- [Chunking Strategy](#chunking-strategy)
- [Embedding Strategy](#embedding-strategy)

---

## Overview

OpenPharma ingests research papers from PubMed Central and stores them in a normalized format optimized for RAG (Retrieval Augmented Generation). The pipeline extracts structured content, chunks it intelligently, generates embeddings, and stores everything in PostgreSQL with pgvector.

**Key Design Principles:**
1. **No data duplication** - Single source of truth for document content
2. **Section-aware chunking** - Preserve semantic boundaries from paper structure
3. **Metadata preservation** - Keep enough context to recover sections without duplication
4. **Efficient retrieval** - Optimize for semantic search via vector embeddings

---

## Ingestion Pipeline

**NOTE:** The ingestion pipeline uses a decoupled 4-phase architecture for resumability and cost efficiency. See `docs/ingestion_pipeline.md` for the complete design.

**4-Phase Architecture:**
```
Phase 1: Search PubMed → Store PMC IDs (pubmed_papers table)
Phase 2: Fetch Papers → Store Documents (documents table)
Phase 3: Chunk Documents → Create Chunks with NULL embeddings (document_chunks table)
Phase 4: Embed Chunks → Update Embeddings (document_chunks.embedding)
```

Each phase stores persistent state and can be run independently. The original monolithic approach is archived in `scripts/ingest_papers.py`.

**Core Processing Steps:**

```
1. Fetch → 2. Parse → 3. Chunk → 4. Embed → 5. Store
   ↓          ↓          ↓          ↓          ↓
 PubMed    Extract    Split     Generate   PostgreSQL
   API       XML      Tokens   Embeddings   + pgvector
```

### Stage 1: Fetch (PubMedFetcher)
**File:** `app/ingestion/pubmed_fetcher.py`

- Searches PubMed Central for diabetes research papers
- Uses NCBI Entrez API with query: `diabetes[Title/Abstract] AND open access[filter]`
- Returns list of PMC IDs (e.g., `['1234567', '2345678']`)
- Rate limited to 3 requests/second (NCBI requirement)

### Stage 2: Parse (PMCXMLParser)
**File:** `app/ingestion/xml_parser.py`

- Downloads full XML for each paper (JATS format)
- Extracts:
  - Title
  - Abstract
  - Body sections (Introduction, Methods, Results, Discussion, etc.)
- Builds `full_text` by concatenating sections with headers
- Tracks character offsets for each section

**Example Output:**
```python
{
  "title": "Diabetes Management Study",
  "abstract": "This study examines...",
  "full_text": "INTRODUCTION\\nBackground...\\n\\nMETHODS\\nWe studied...",
  "sections": {  # Temporary, for chunking only
    "introduction": "Background...",
    "methods": "We studied..."
  },
  "section_offsets": [  # Stored in metadata
    {"section": "introduction", "char_start": 13, "char_end": 500},
    {"section": "methods", "char_start": 510, "char_end": 1200}
  ]
}
```

### Stage 3: Chunk (DocumentChunker)
**File:** `app/ingestion/chunker.py`

- Splits text into 512-token chunks with 50-token overlap
- Chunks **each section separately** to preserve semantic boundaries
- Uses tiktoken tokenizer (cl100k_base encoding)
- Tracks character offsets within original document

**Example Chunk:**
```python
{
  "content": "We studied 100 patients with type 2 diabetes...",
  "section": "methods",
  "chunk_index": 0,
  "char_start": 510,
  "char_end": 750,
  "token_count": 512,
  "embedding_text": "Document: Diabetes Management Study\\nSection: methods\\n\\nWe studied..."
}
```

### Stage 4: Embed (Embedding Service)
**File:** `app/ingestion/embeddings.py`

- Generates embeddings using Ollama `nomic-embed-text` (768 dimensions, self-hosted, $0 cost)
- **CRITICAL**: Requires Ollama 0.11.x (NOT 0.12.5 - regression bug)
- Embeds the **embedding_text** field (title + section + content), not just content
- Processes sequentially to avoid overwhelming Ollama
- Embedding text format: `"Doc: {title}\\nSection: {section}\\n\\n{content}"`

### Stage 5: Store (Database)
**Tables:** `documents`, `document_chunks`

- Stores documents with metadata
- Stores chunks with embeddings
- Uses HNSW index for fast vector similarity search

---

## Database Schema

### Schema Overview

Four tables support the system:

| Table | Purpose | Size | Notes |
|-------|---------|------|-------|
| `pubmed_papers` | Track PMC IDs and fetch status | Small | Ingestion pipeline |
| `documents` | Store document content and metadata | ~3.6GB | Core data |
| `document_chunks` | Store chunks and embeddings | ~48GB | RAG retrieval |
| `icite_metadata` | Citation metrics for all PubMed papers | ~32GB | Landmark filtering, future KOL analysis |

---

### Table 1: `pubmed_papers`

Tracks PMC IDs discovered from searches and their fetch status. Includes PMID for linking to citation data.

```sql
CREATE TABLE pubmed_papers (
  pmc_id VARCHAR PRIMARY KEY,                    -- "1234567" (numeric only, no PMC prefix)
  discovered_at TIMESTAMP DEFAULT NOW(),
  fetch_status VARCHAR DEFAULT 'pending',        -- 'pending', 'wont_fetch', 'fetched', 'failed'
  pmid BIGINT,                                   -- PubMed ID for linking to icite_metadata
  doi TEXT                                       -- Digital Object Identifier
  -- Note: Citation metric columns exist but are NOT maintained (see Design Notes)
);

CREATE INDEX idx_pubmed_papers_fetch_status ON pubmed_papers(fetch_status);
CREATE INDEX idx_pubmed_papers_pmid ON pubmed_papers(pmid);
```

| Column | Type | Description |
|--------|------|-------------|
| `pmc_id` | VARCHAR (PK) | Numeric PMC ID (e.g., "1234567"), no "PMC" prefix |
| `discovered_at` | TIMESTAMP | When PMC ID was first discovered |
| `fetch_status` | VARCHAR | 'pending', 'wont_fetch', 'fetched', or 'failed' |
| `pmid` | BIGINT | PubMed ID (for joining with icite_metadata) |
| `doi` | TEXT | Digital Object Identifier |

**Indexes:**
- Primary key on `pmc_id`
- B-tree index on `fetch_status` (for `WHERE fetch_status='pending'` queries)
- B-tree index on `pmid` (for JOINs with `icite_metadata`)

**Design Notes:**
- No foreign key to `documents` (application-level enforcement)
- Relationship: `documents.source_id = pubmed_papers.pmc_id` when `source='pmc'`
- PMC prefix added only for display: `f"PMC{pmc_id}"`
- **Citation filtering:** Use JOIN with `icite_metadata` table (not denormalized columns)
- `pmid` populated via NCBI ID conversion API (Stage 1.1)
- Table includes citation metric columns (nih_percentile, citation_count, etc.) that are partially populated but NOT maintained going forward - always use `icite_metadata` for filtering

---

### Table 2: `documents`

Stores complete document content and metadata.

```sql
CREATE TABLE documents (
  document_id SERIAL PRIMARY KEY,
  source VARCHAR NOT NULL,                       -- "pmc", "clinicaltrials", "fda"
  source_id VARCHAR NOT NULL,                    -- "1234567" (PMC ID without prefix)
  title TEXT NOT NULL,
  abstract TEXT,
  full_text TEXT,                                -- Concatenated sections (see Section Storage)
  doc_metadata JSONB,                            -- Authors, journal, section_offsets, etc.
  priority INTEGER DEFAULT 50,                   -- 0=exclude, 10=low, 50=normal, 100=high
  ingestion_status VARCHAR DEFAULT 'fetched',    -- 'fetched', 'chunked', 'embedded'
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP,
  UNIQUE(source, source_id)
);

CREATE INDEX idx_documents_ingestion_status ON documents(ingestion_status);
CREATE INDEX idx_documents_priority ON documents(priority);
```

| Column | Type | Description |
|--------|------|-------------|
| `document_id` | SERIAL (PK) | Auto-incrementing primary key |
| `source` | VARCHAR | Data source: "pmc", "clinicaltrials", "fda" |
| `source_id` | VARCHAR | External ID (PMC ID, NCT number, etc.) |
| `title` | TEXT | Document title |
| `abstract` | TEXT | Abstract text (nullable) |
| `full_text` | TEXT | Concatenated sections with headers |
| `doc_metadata` | JSONB | Flexible metadata (authors, journal, section_offsets, etc.) |
| `priority` | INTEGER | Priority level: 0=exclude, 10=low, 50=normal, 100=high (default: 50) |
| `ingestion_status` | VARCHAR | 'fetched', 'chunked', or 'embedded' |
| `created_at` | TIMESTAMP | When row was first inserted |
| `updated_at` | TIMESTAMP | When content was last replaced (NULL = never updated) |

**Indexes:**
- Primary key on `document_id`
- Unique constraint on `(source, source_id)`
- B-tree index on `ingestion_status` (for `WHERE ingestion_status='fetched'` queries)
- B-tree index on `priority` (for filtering in semantic search)

**Design Notes:**
- `full_text` contains ALL sections concatenated (see Section Storage Strategy below)
- `doc_metadata['section_offsets']` stores character positions for section recovery
- `ingestion_status` tracks progress through Phase 2 → 3 → 4
- `priority` is used to filter documents in semantic search (chunks inherit priority via JOIN)
- UPSERT on `(source, source_id)` replaces old documents during updates

---

### Table 3: `document_chunks`

Stores chunked content and vector embeddings for RAG retrieval.

```sql
CREATE TABLE document_chunks (
  document_chunk_id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL,
  section VARCHAR,                               -- "abstract", "introduction", "methods", etc.
  chunk_index INTEGER NOT NULL,                  -- Order within document (0, 1, 2...)
  content TEXT NOT NULL,                         -- Raw chunk text (without context)
  char_start INTEGER NOT NULL,                   -- Character offset in full_text
  char_end INTEGER NOT NULL,                     -- Character offset in full_text
  token_count INTEGER NOT NULL,                  -- Number of tokens (~512)
  embedding VECTOR(768),                         -- Ollama nomic-embed-text embedding (NULL = needs embedding)
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_embedding ON document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_chunks_needs_embedding ON document_chunks(document_chunk_id)
  WHERE embedding IS NULL;
```

| Column | Type | Description |
|--------|------|-------------|
| `document_chunk_id` | SERIAL (PK) | Auto-incrementing primary key |
| `document_id` | INTEGER | Foreign key to parent document (not enforced) |
| `section` | VARCHAR | Section name: "abstract", "methods", "results", etc. |
| `chunk_index` | INTEGER | Order within document (0, 1, 2...) |
| `content` | TEXT | Raw chunk text (without title/section context) |
| `char_start` | INTEGER | Character offset in parent `full_text` |
| `char_end` | INTEGER | Character offset in parent `full_text` |
| `token_count` | INTEGER | Number of tokens in chunk (~512) |
| `embedding` | VECTOR(768) | Ollama nomic-embed-text embedding (NULL until Phase 4 completes) |
| `created_at` | TIMESTAMP | When chunk was created |

**Indexes:**
- Primary key on `document_chunk_id`
- B-tree index on `document_id` (for joining to documents)
- HNSW index on `embedding` (for vector similarity search, m=16, ef_construction=64)
- Partial index on `document_chunk_id WHERE embedding IS NULL` (for Phase 4 queries)

**Design Notes:**
- `embedding` is NULL when chunk is first created (Phase 3)
- Embedding generated from: `f"Document: {title}\nSection: {section}\n\n{content}"`
- Partial index shrinks as embeddings complete (efficient storage)
- `document_chunk_id` used for Batch API tracking (cleaner than denormalizing source/source_id)
- **Priority filtering:** Chunks do NOT store priority - they inherit it from their parent document via JOIN (see semantic_search.py). This avoids expensive UPDATE operations on the large chunks table when priorities change.

---

### Table 4: `icite_metadata`

Stores citation metrics from NIH iCite database for filtering and KOL analysis.

```sql
CREATE TABLE icite_metadata (
    pmid BIGINT PRIMARY KEY,
    year INTEGER,
    title TEXT,
    journal VARCHAR(255),
    authors TEXT,
    nih_percentile FLOAT,                    -- Percentile rank vs NIH papers (99 = top 1%)
    relative_citation_ratio FLOAT,           -- Field-normalized citation metric
    citation_count INTEGER,                  -- Total times cited
    citations_per_year FLOAT,
    is_research_article BOOLEAN,
    is_clinical BOOLEAN,
    apt FLOAT,                               -- Approximate Potential to Translate
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_icite_percentile ON icite_metadata(nih_percentile);
CREATE INDEX idx_icite_year ON icite_metadata(year);
CREATE INDEX idx_icite_citation_count ON icite_metadata(citation_count);
```

**Purpose**: Filter papers by citation metrics, identify most-cited authors, enrich RAG responses with citation counts

**Data Source**: NIH iCite Database Snapshot (https://nih.figshare.com/collections/iCite_Database_Snapshots_NIH_Open_Citation_Collection_/4586573)

**Size**: ~12GB for all PubMed papers with citation data

---

### Dropped Tables

**`citation_links` (dropped 2025-01-23)**
- Previously stored 870M citation network edges (81 GB)
- Purpose: Co-citation analysis, KOL identification, future Graph RAG
- Reason for dropping: Not used in Phase 1, consumed 49% of database storage
- Can be re-imported from NIH iCite snapshot if needed for Phase 2 features

---

## Section Storage Strategy

**Problem:** Research papers have sections (Introduction, Methods, Results, etc.). We need to:
1. Preserve section boundaries for intelligent chunking
2. Allow section recovery for re-chunking or analysis
3. Avoid storing the same content twice

**Solution:** Normalized storage with character offsets

### How It Works

1. **`full_text` column** contains ALL sections concatenated with headers:
   ```
   INTRODUCTION
   Type 2 diabetes affects millions...

   METHODS
   We conducted a randomized controlled trial...

   RESULTS
   Patient outcomes improved significantly...
   ```

2. **`doc_metadata['section_offsets']`** stores character positions:
   ```json
   {
     "authors": ["Smith J", "Jones A"],
     "journal": "Diabetes Care",
     "section_offsets": [
       {"section": "introduction", "char_start": 13, "char_end": 500},
       {"section": "methods", "char_start": 510, "char_end": 1200},
       {"section": "results", "char_start": 1210, "char_end": 2000}
     ]
   }
   ```

3. **During ingestion** (not stored in DB):
   The parser returns a temporary `sections` dict for chunking:
   ```python
   sections = {
     "introduction": "Type 2 diabetes affects...",
     "methods": "We conducted a randomized..."
   }
   ```
   This is used to chunk each section separately, then discarded.

4. **To recover a section later:**
   ```python
   offsets = doc.doc_metadata['section_offsets']
   methods_section = doc.full_text[offsets[1]['char_start']:offsets[1]['char_end']]
   ```

### Benefits

✅ **No duplication** - `full_text` is single source of truth
✅ **Easy recovery** - Simple string slicing to get sections
✅ **Proper chunk labels** - Chunks know their section during ingestion
✅ **Flexible** - Can add new section metadata without schema changes
✅ **Queryable** - Can use JSONB queries to find papers with specific sections

---

## Chunking Strategy

### Token-Based Chunking

- **Chunk size:** 512 tokens
- **Overlap:** 50 tokens
- **Tokenizer:** tiktoken `cl100k_base` encoding

### Section-Aware Chunking

Instead of chunking the entire `full_text` as one blob, we:

1. **Chunk each section separately**
   ```python
   for section_name, section_text in sections.items():
       chunks = chunker.chunk_text(section_text, section=section_name, ...)
   ```

2. **Preserve section boundaries**
   - A chunk from "Introduction" will never contain "Methods" content
   - Overlap happens within sections, not across them

3. **Track section in chunk metadata**
   ```python
   chunk = {
     "content": "...",
     "section": "methods",  # ← Stored in document_chunks table
     "chunk_index": 0
   }
   ```

### Why Section-Aware?

- **Better semantic coherence** - Methods chunks are about methods, not mixed with results
- **Improved retrieval** - User asks "How was the study conducted?" → retrieve from Methods chunks
- **Context preservation** - Each chunk's embedding includes section name for better matching

---

## Embedding Strategy

### Context-Enhanced Embeddings

Instead of embedding just the chunk content, we embed an **embedding_text** string:

```
Document: Diabetes Management in Primary Care
Section: methods

We conducted a randomized controlled trial with 100 patients...
```

This provides the embedding model with:
- **Document context** - What paper is this from?
- **Section context** - What part of the paper?
- **Content** - The actual chunk text

### Storage

- **Content column:** Stores raw chunk text - `"We conducted a randomized..."`
- **Embedding column:** Generated from `embedding_text` (not stored in DB)
- **Embedding text reconstruction:** Can rebuild anytime using title + section + content

### Why Not Store embedding_text?

- Embedding text is **redundant** - We can rebuild it from `title` + `section` + `content`
- Saves storage space
- Keeps chunks clean and reusable

---

## Data Flow Example

Here's a complete example of one paper flowing through the pipeline:

### 1. Fetch
```python
fetcher.search_diabetes_papers(max_results=10)
# Returns: ['1234567', '2345678', ...]
```

### 2. Parse
```python
paper = fetcher.fetch_paper_details('1234567')
# Returns:
{
  "source_id": "1234567",
  "title": "Diabetes Management Study",
  "abstract": "This study...",
  "full_text": "INTRODUCTION\\nType 2 diabetes...\\n\\nMETHODS\\nWe studied...",
  "sections": {"introduction": "...", "methods": "..."},  # Temporary
  "metadata": {
    "authors": ["Smith J"],
    "journal": "Diabetes Care",
    "section_offsets": [
      {"section": "introduction", "char_start": 13, "char_end": 500},
      {"section": "methods", "char_start": 510, "char_end": 1200}
    ]
  }
}
```

### 3. Chunk
```python
chunks = chunker.chunk_document(paper)
# Returns: [
#   {
#     "content": "Type 2 diabetes affects...",
#     "section": "introduction",
#     "chunk_index": 0,
#     "char_start": 13,
#     "char_end": 250,
#     "token_count": 512,
#     "context": "Document: Diabetes Management Study\\nSection: introduction\\n\\nType 2 diabetes..."
#   },
#   ...
# ]
```

### 4. Embed
```python
embedder = EmbeddingService()  # Uses Ollama
texts = [chunk["embedding_text"] for chunk in chunks]
embeddings, cost = embedder.embed_chunks(texts)
for chunk, emb in zip(chunks, embeddings):
    chunk["embedding"] = emb
```

### 5. Store
```python
# Insert document
doc = Document(
    source="pmc",
    source_id="1234567",
    title="Diabetes Management Study",
    abstract="This study...",
    full_text="INTRODUCTION\\nType 2 diabetes...",
    doc_metadata={
        "authors": ["Smith J"],
        "section_offsets": [...]
    }
)
db.add(doc)

# Insert chunks
for chunk in chunks:
    db_chunk = DocumentChunk(
        document_id=doc.document_id,
        section=chunk["section"],
        chunk_index=chunk["chunk_index"],
        content=chunk["content"],
        char_start=chunk["char_start"],
        char_end=chunk["char_end"],
        token_count=chunk["token_count"],
        embedding=chunk["embedding"]
    )
    db.add(db_chunk)
```

---

## Design Decisions & Rationale

### Why no document-level embeddings?
- Research papers are too long (>10K tokens) to embed as a whole
- Chunk-level embeddings provide more precise retrieval
- Can aggregate chunk scores if needed for document-level ranking

### Why store both abstract and full_text?
- Abstract is often queried separately (summaries, previews)
- Some papers only have abstracts available
- Keeps schema flexible for non-research sources (clinical trials, FDA docs)

### Why JSONB for metadata?
- Different sources have different metadata fields
- Avoid schema migrations when adding new sources
- Still queryable with PostgreSQL JSONB operators
- Example: `SELECT * FROM documents WHERE doc_metadata->'journal' = 'Diabetes Care'`

### Why character offsets instead of storing sections separately?
- Avoids data duplication
- Simpler schema (one `full_text` column vs many section columns)
- Flexible for papers with varying section structures
- Easy to reconstruct sections when needed

### Why not store source/source_id on chunks?
- **Previous design:** Denormalized `source` and `source_id` on chunks for Batch API tracking
- **Current design:** Use `document_chunk_id` as unique identifier
- **Rationale:**
  - Cleaner schema (no redundant data)
  - `document_chunk_id` is already unique and indexed
  - For Batch API: use `custom_id = f"chunk_{document_chunk_id}"`
  - Can still join to `documents` table when source info needed

### Why partial index on NULL embeddings?
- Query pattern: `SELECT * FROM document_chunks WHERE embedding IS NULL LIMIT 1000`
- Initially 10M chunks with NULL embeddings (full table scan is expensive)
- Partial index only stores rows matching `WHERE embedding IS NULL`
- Index shrinks as embeddings complete (efficient storage)
- Perfect for Phase 4 queries that repeatedly fetch unembed chunks

### Why indexes on status columns?
- **`pubmed_papers.fetch_status`**: Phase 2 queries this repeatedly over 9-hour fetch window
- **`documents.ingestion_status`**: Phase 3/4 query this for batch processing
- **Low cardinality** (3-4 values) normally bad for indexes, but:
  - High selectivity during active ingestion (many rows in one status)
  - Frequent queries justify small index overhead
  - B-tree indexes are tiny for status columns (10-20% of table size)

---

## Future Considerations

### Phase 2: Multi-Source Integration
When adding ClinicalTrials.gov, FDA, etc.:
- Use same `source` field to distinguish sources
- Store source-specific metadata in JSONB
- May need different chunking strategies (structured data vs prose)

### Phase 3: Re-chunking
If we want to experiment with different chunk sizes/overlaps:
1. Read documents with `section_offsets`
2. Reconstruct sections: `full_text[start:end]`
3. Re-chunk with new parameters
4. Delete old chunks, insert new ones

### Optimization Opportunities
- Cache embeddings to avoid re-computing
- Add materialized views for common queries
- Consider parallel ingestion for large datasets
- Batch database inserts for better performance

---

## References

- **JATS XML Spec:** https://jats.nlm.nih.gov/
- **PubMed Central API:** https://www.ncbi.nlm.nih.gov/pmc/tools/developers/
- **pgvector Documentation:** https://github.com/pgvector/pgvector
- **Ollama Documentation:** https://ollama.com/
- **nomic-embed-text Model:** https://ollama.com/library/nomic-embed-text
