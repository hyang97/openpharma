# Ingestion Pipeline Design

## Overview

The ingestion pipeline is decoupled into 4 independent stages. Each stage stores its output persistently, is independently resumable, and can be re-run without duplicating work.

## Architecture

```
Stage 1: Search PubMed → Store PMC IDs (pubmed_papers table)
Stage 2: Fetch Papers → Store Documents (documents table)
Stage 3: Chunk Documents → Create Chunks (document_chunks table)
Stage 4: Embed Chunks → Update Embeddings (document_chunks.embedding)
```

## Schema

### New Table: PubMedPaper

Tracks PMC IDs discovered from searches and their fetch status.

```python
class PubMedPaper(Base):
    __tablename__ = "pubmed_papers"

    pmc_id = Column(String, primary_key=True)           # "1234567" (numeric only, no PMC prefix)
    discovered_at = Column(DateTime, default=now)       # When we first found it
    fetch_status = Column(String, default='pending')    # 'pending', 'fetched', 'failed'
```

**Notes:**
- `pmc_id` stores numeric ID only (e.g., "1234567"), not "PMC1234567"
- PMC prefix added only for display/logging: `f"PMC{pmc_id}"`
- No foreign key to Document table (application-level enforcement)

### Modified Table: Document

Add ingestion status tracking.

```python
class Document(Base):
    # ... existing fields (document_id, source, source_id, title, abstract, full_text, doc_metadata) ...

    # NEW FIELD
    ingestion_status = Column(String, default='fetched')  # 'fetched', 'chunked', 'embedded'
```

**Relationship to PubMedPaper:**
- For PubMed documents: `source='pubmed'` and `source_id` matches a `pmc_id`
- Enforced at application level, not database constraint
- Can join: `JOIN pubmed_papers ON documents.source_id = pubmed_papers.pmc_id WHERE source='pubmed'`

### Unchanged Table: DocumentChunk

No schema changes needed. Existing `embedding` column already supports NULL.

```python
class DocumentChunk(Base):
    # ... existing fields ...
    embedding = Column(Vector(768))  # NULL = needs embedding (Ollama nomic-embed-text)
```

## Stage 1: Collect PMC IDs

### Script
```bash
python scripts/collect_pmc_ids.py --max-results 100000
```

### What it does
1. Searches PubMed with hardcoded query: `diabetes[Title/Abstract] AND open access[filter] AND 2020:2025[pdat]`
2. Gets list of numeric PMC IDs from NCBI API
3. Inserts into `pubmed_papers` table with `fetch_status='pending'`
4. Uses `INSERT ... ON CONFLICT DO NOTHING` to skip duplicates

### For monthly updates
```bash
python scripts/collect_pmc_ids.py --query "diabetes[Title/Abstract] AND 2025/02/01:2025/02/28[lr]"
```

**PubMed date fields:**
- `[pdat]` - Publication Date (for initial load)
- `[lr]` - Last Revision Date (for finding updated papers)
- `[crdt]` - Create Date (when added to PubMed)

### Output
- Rows in `pubmed_papers` table with `fetch_status='pending'`

### Idempotency
Re-running same search skips PMC IDs already in table (ON CONFLICT DO NOTHING)

## Stage 2: Fetch Papers

### Script
```bash
# Interactive (small batches for testing)
python scripts/fetch_papers.py --limit 100

# Background (large batches, requires --confirm-large-job to skip prompt)
nohup python scripts/fetch_papers.py --limit 25000 --confirm-large-job > fetch_papers.log 2>&1 &
```

### What it does
1. Queries `pubmed_papers` WHERE `fetch_status='pending'` LIMIT batch_size
2. For each PMC ID:
   - Fetches full XML from NCBI Entrez efetch API
   - Parses title, abstract, sections (using `PMCXMLParser`)
   - Fetches metadata from NCBI esummary API (authors, journal, DOI, etc.)
   - UPSERT into `documents` table (source='pmc', source_id=pmc_id)
   - Updates `pubmed_papers.fetch_status='fetched'`
3. Rate limiting: 2 API calls per paper with conservative timing
   - With API key: 0.15s between calls (~6.7 req/sec, ~0.3s per paper)
   - Without API key: 0.4s between calls (~2.5 req/sec, ~0.8s per paper)
   - Actual performance: ~0.6s per paper (~100 papers/minute)
4. On failure: sets `fetch_status='failed'`, logs error
5. Large job check (>1000 papers): Warns if not during off-peak hours (weekends or 9pm-5am ET weekdays)

### Output
- Rows in `documents` table with `ingestion_status='fetched'`
- Updated `fetch_status` in `pubmed_papers`

### Idempotency
Re-running processes only papers with `fetch_status='pending'`

### Handling Updates
When a paper is re-fetched (found via `[lr]` search):
- UPSERT replaces old document content
- Deletes old chunks (handled in Stage 3)
- Re-chunks and re-embeds (Phases 3-4)

## Stage 3: Chunk Documents

### Script
```bash
python scripts/chunk_papers.py --batch-size 50
```

### What it does
1. Queries `documents` WHERE `ingestion_status='fetched'` LIMIT batch_size
2. For each document:
   - If chunks exist (re-chunking): DELETE all chunks for this document_id
   - Runs `DocumentChunker.chunk_document(paper)`
   - Creates chunks with `embedding=NULL`
   - Adds required fields: `source='pubmed'`, `source_id=pmc_id` (for Batch API)
   - Updates `document.ingestion_status='chunked'`

### Output
- Rows in `document_chunks` table with `embedding=NULL`
- Documents marked as `ingestion_status='chunked'`

### Idempotency
Re-running processes only documents with `ingestion_status='fetched'`

### Re-chunking
When a document is updated, Stage 2 sets `ingestion_status='fetched'` again, triggering re-chunking

## Stage 4: Embed Chunks

### Script
```bash
# Regular API (instant, standard pricing)
python scripts/embed_chunks.py --batch-size 1000

# Batch API (50% cheaper, 2-24 hour turnaround)
python scripts/embed_chunks.py --use-batch-api --batch-size 10000
```

### What it does

**Regular API:**
1. Queries `document_chunks` WHERE `embedding IS NULL` LIMIT batch_size
2. Extracts `embedding_text` from chunks
3. Calls `EmbeddingService.embed_chunks(texts)`
4. Updates chunks with embeddings
5. For each document, checks if ALL chunks now have embeddings
6. If complete: updates `document.ingestion_status='embedded'`

**Batch API:**
1. Queries chunks WHERE `embedding IS NULL`
2. Calls `EmbeddingService.submit_batch_embed(chunks)`
3. Saves batch_id to file
4. Exits (run completion script later when batch finishes)
5. Completion script: loads chunks, calls `get_batch_embed()`, updates embeddings

### Output
- Chunks with `embedding` populated (Vector(768) - Ollama nomic-embed-text)
- Documents marked as `ingestion_status='embedded'`

### Idempotency
Re-running only processes chunks with `embedding IS NULL`

### Error Handling
**Failed embeddings:**
- If any chunks fail to embed for a document, document stays at `ingestion_status='chunked'`
- Failed chunks keep `embedding=NULL`
- Can re-run Stage 4 to retry
- Log warnings for failed chunks

**Option (not implemented in Stage 1):** Skip entire document if any chunk fails

## Workflow Examples

### Initial Load: 100K Diabetes Papers

```bash
# Stage 1: Collect PMC IDs
python scripts/collect_pmc_ids.py --max-results 100000
# → 100K rows in pubmed_papers

# Stage 2: Fetch papers (can run multiple times to resume)
python scripts/fetch_papers.py --batch-size 100
# → 100K rows in documents (may take ~9 hours with rate limiting)

# Stage 3: Chunk documents
python scripts/chunk_papers.py --batch-size 50
# → ~10M rows in document_chunks (assuming ~100 chunks/paper)

# Stage 4: Embed chunks
python scripts/embed_chunks.py --batch-size 1000
# → All chunks get embeddings (may take hours, costs ~$200 with Regular API)

# OR use Batch API (50% cheaper)
python scripts/embed_chunks.py --use-batch-api --batch-size 100000
# → Submit to OpenAI, come back tomorrow
python scripts/complete_batch_embed.py --batch-id batch_abc123
```

### Monthly Updates: New and Revised Papers

```bash
# Find papers revised in February 2025
python scripts/collect_pmc_ids.py --query "diabetes[Title/Abstract] AND 2025/02/01:2025/02/28[lr]"
# → Sets fetch_status='pending' for updated papers

# Fetch updated papers (replaces old content)
python scripts/fetch_papers.py --batch-size 100
# → UPSERTs documents, sets ingestion_status='fetched'

# Re-chunk (deletes old chunks)
python scripts/chunk_papers.py --batch-size 50
# → Creates new chunks with embedding=NULL

# Re-embed
python scripts/embed_chunks.py --batch-size 1000
# → Updates embeddings
```

### Add New Therapeutic Area (Oncology)

```bash
# Collect oncology PMC IDs
python scripts/collect_pmc_ids.py --query "cancer[Title/Abstract] AND 2020:2025[pdat]" --max-results 100000

# Run phases 2-4 as usual
python scripts/fetch_papers.py --batch-size 100
python scripts/chunk_papers.py --batch-size 50
python scripts/embed_chunks.py --batch-size 1000
```

## Key Design Decisions

### 1. Decoupled Phases
Each phase is independent and stores persistent state. Benefits:
- Resume from failure at any point
- Re-run specific phases without redoing earlier work
- Cost efficient (don't re-fetch if embedding fails)

### 2. No Version History
When documents are updated (via `[lr]` search):
- UPSERT replaces old content in `documents` table
- Old chunks are deleted and recreated
- Only latest version stored

Rationale: Simplifies schema, reduces storage, matches user requirement "don't need old versions"

### 3. Application-Level Foreign Keys
`pubmed_papers.pmc_id` matches `documents.source_id` when `source='pubmed'`, but no database FK constraint.

Rationale:
- Document table is multi-source (PubMed, ClinicalTrials, FDA, etc.)
- Can't create conditional FK ("only enforce if source='pubmed'")
- Application enforces consistency during insertion

### 4. Status Tracking via Columns
- `pubmed_papers.fetch_status`: 'pending', 'fetched', 'failed'
- `documents.ingestion_status`: 'fetched', 'chunked', 'embedded'
- `document_chunks.embedding`: NULL = needs embedding

Rationale: Simple, queryable, no separate status tables needed

### 5. NULL Embeddings for Failures
If embedding fails, chunk is inserted with `embedding=NULL`.

Rationale:
- Don't lose data
- Can re-run Stage 4 to retry failed chunks
- Alternative (not implemented): Skip entire document if any chunk fails

### 6. PMC IDs as Numbers Only
Store `pmc_id = "1234567"`, not `"PMC1234567"`

Rationale:
- Matches NCBI API return format
- Cleaner data storage
- Add "PMC" prefix only for display/logging

## Future Enhancements (Not in Stage 1)

1. **Search tracking**: Add `PubMedSearch` table to track which queries found which papers
2. **Retry logic**: Track `fetch_attempts`, exponential backoff for failures
3. **Parallel fetching**: Multiple workers fetching papers simultaneously
4. **Batch API completion**: Implement completion workflow for async embedding
5. **Index management**: Automatic HNSW index creation/refresh
6. **Monitoring dashboard**: Track ingestion progress, failure rates, costs
7. **Deduplication logic**: Handle papers found in multiple therapeutic areas
8. **Priority queuing**: Fetch most recent papers first

## Cost Estimates

### Initial Load: 100K Papers

**Assumptions:**
- 100K papers
- ~100 chunks/paper = 10M chunks
- ~500 tokens/chunk average

**Costs:**

| Phase | Time | Cost | Notes |
|-------|------|------|-------|
| Stage 1: Collect IDs | ~10 min | Free | NCBI API is free |
| Stage 2: Fetch papers | ~9 hours | Free | 3 req/sec limit, free API |
| Stage 3: Chunk | ~1 hour | Free | Local processing |
| Stage 4: Embed (Regular) | ~2 hours | ~$100 | 10M chunks × 500 tokens × $0.02/1M |
| Stage 4: Embed (Batch) | 2-24 hours | ~$50 | 50% discount |

**Total:** ~$50-100 for initial load (depending on Regular vs Batch API)

### Monthly Updates: ~5K Papers

**Assumptions:**
- 5% of papers revised/added monthly = 5K papers
- ~500K chunks

**Costs:**
- Stage 1-3: Free (~30 min total)
- Stage 4: ~$5 (Batch API) or ~$10 (Regular API)

**Annual ongoing cost:** ~$60-120/year

## Monitoring Queries

### Check ingestion progress
```sql
-- Papers by fetch status
SELECT fetch_status, COUNT(*)
FROM pubmed_papers
GROUP BY fetch_status;

-- Documents by ingestion status
SELECT ingestion_status, COUNT(*)
FROM documents
GROUP BY ingestion_status;

-- Chunks needing embeddings
SELECT COUNT(*)
FROM document_chunks
WHERE embedding IS NULL;
```

### Find failed papers
```sql
-- Papers that failed to fetch
SELECT pmc_id, discovered_at
FROM pubmed_papers
WHERE fetch_status = 'failed';

-- Documents missing chunks
SELECT d.document_id, d.source_id, d.title
FROM documents d
LEFT JOIN document_chunks c ON d.document_id = c.document_id
WHERE d.ingestion_status = 'fetched'
GROUP BY d.document_id
HAVING COUNT(c.document_chunk_id) = 0;
```

### Track costs
```sql
-- Count embedded chunks (for cost tracking)
SELECT COUNT(*),
       COUNT(*) * 500 * 0.00002 as estimated_cost_usd
FROM document_chunks
WHERE embedding IS NOT NULL;
```
