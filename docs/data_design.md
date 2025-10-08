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

**NOTE:** The ingestion pipeline has been redesigned as a decoupled 4-phase system. See `docs/ingestion_pipeline.md` for the complete architecture.

The original monolithic pipeline consisted of four main stages:

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
- Uses tiktoken (OpenAI's tokenizer) for consistency with embeddings
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
**File:** `app/ingestion/embeddings.py` (to be created)

- Generates embeddings using OpenAI `text-embedding-3-small` (1536 dimensions)
- Embeds the **embedding_text** field (title + section + content), not just content
- Processes in batches for efficiency
- Embedding text format: `"Document: {title}\\nSection: {section}\\n\\n{content}"`

### Stage 5: Store (Database)
**Tables:** `documents`, `document_chunks`

- Stores documents with metadata
- Stores chunks with embeddings
- Uses HNSW index for fast vector similarity search

---

## Database Schema

### `documents` Table

Stores document-level metadata and content.

```sql
CREATE TABLE documents (
  document_id SERIAL PRIMARY KEY,
  source VARCHAR NOT NULL,           -- "pubmed", "clinicaltrials", "fda"
  source_id VARCHAR NOT NULL,        -- "1234567" (PMC ID without "PMC" prefix)
  title TEXT NOT NULL,
  abstract TEXT,
  full_text TEXT,                    -- Concatenated sections (see below)
  doc_metadata JSONB,                -- Authors, journal, section_offsets, etc.
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP,
  UNIQUE(source, source_id)
);
```

### `document_chunks` Table

Stores chunk-level content and embeddings for RAG retrieval.

```sql
CREATE TABLE document_chunks (
  document_chunk_id SERIAL PRIMARY KEY,
  document_id INTEGER NOT NULL,
  section VARCHAR,                   -- "introduction", "methods", "results", etc.
  chunk_index INTEGER NOT NULL,      -- Order within document (0, 1, 2...)
  content TEXT NOT NULL,             -- Raw chunk text (without context)
  char_start INTEGER NOT NULL,       -- Character offset in full_text
  char_end INTEGER NOT NULL,         -- Character offset in full_text
  token_count INTEGER NOT NULL,      -- Number of tokens (~512)
  embedding VECTOR(1536),            -- OpenAI embedding (context-enhanced)
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

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
- **Tokenizer:** tiktoken `cl100k_base` (matches OpenAI embeddings)

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
for chunk in chunks:
    chunk["embedding"] = openai.embed(chunk["embedding_text"])
```

### 5. Store
```python
# Insert document
doc = Document(
    source="pubmed",
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
- Batch embedding API calls (OpenAI supports up to 100 inputs)
- Cache embeddings to avoid re-computing
- Add materialized views for common queries
- Consider parallel ingestion for large datasets

---

## References

- **JATS XML Spec:** https://jats.nlm.nih.gov/
- **PubMed Central API:** https://www.ncbi.nlm.nih.gov/pmc/tools/developers/
- **pgvector Documentation:** https://github.com/pgvector/pgvector
- **OpenAI Embeddings:** https://platform.openai.com/docs/guides/embeddings
