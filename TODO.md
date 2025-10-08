# OpenPharma TODO List

Last updated: 2025-10-07

## Current Sprint: Decoupled Ingestion Pipeline

### Schema Changes
- [ ] Add `PubMedPaper` model to `app/db/models.py`
  - Fields: `pmc_id` (PK), `discovered_at`, `fetch_status`
  - Status values: 'pending', 'fetched', 'failed'
- [ ] Add `ingestion_status` field to `Document` model
  - Values: 'fetched', 'chunked', 'embedded'
  - Default: 'fetched'
- [ ] Create database migration for new schema

### Phase 1: Collect PMC IDs
- [ ] Create `scripts/collect_pmc_ids.py`
  - Search PubMed with configurable query
  - Insert PMC IDs into `pubmed_papers` table
  - Use INSERT ... ON CONFLICT DO NOTHING for deduplication
  - Support --query, --max-results arguments
  - Default query: diabetes papers 2020-2025

### Phase 2: Fetch Papers
- [ ] Create `scripts/fetch_papers.py`
  - Query `pubmed_papers` WHERE `fetch_status='pending'`
  - Fetch XML using existing `PubMedFetcher`
  - UPSERT into `documents` table (replace if exists)
  - Set `ingestion_status='fetched'`
  - Update `pubmed_papers.fetch_status='fetched'`
  - Handle failures: set `fetch_status='failed'`
  - Support --batch-size argument
  - Rate limiting: 3 req/sec

### Phase 3: Chunk Documents
- [ ] Create `scripts/chunk_papers.py`
  - Query `documents` WHERE `ingestion_status='fetched'`
  - Delete old chunks if re-chunking
  - Use existing `DocumentChunker`
  - Insert chunks with `embedding=NULL`
  - Set `ingestion_status='chunked'`
  - Support --batch-size argument

### Phase 4: Embed Chunks
- [ ] Create `scripts/embed_chunks.py`
  - Query `document_chunks` WHERE `embedding IS NULL`
  - Use existing `EmbeddingService.embed_chunks()` for Regular API
  - Update chunks with embeddings
  - When all chunks for a document are embedded, set `ingestion_status='embedded'`
  - Support --batch-size argument
  - Log costs (already implemented in EmbeddingService)

### Phase 4 (Batch API - Optional)
- [ ] Add `--use-batch-api` flag to `scripts/embed_chunks.py`
  - Call `EmbeddingService.submit_batch_embed()`
  - Save batch_id to file
  - Exit (don't wait for completion)
- [ ] Create `scripts/complete_batch_embed.py`
  - Load batch_id from file
  - Call `EmbeddingService.get_batch_embed(batch_id, chunks)`
  - Update chunks with embeddings
  - Update document `ingestion_status='embedded'`

### Testing
- [ ] Test Phase 1: Collect 10 PMC IDs
- [ ] Test Phase 2: Fetch those 10 papers
- [ ] Test Phase 3: Chunk those papers
- [ ] Test Phase 4: Embed chunks (Regular API)
- [ ] Test full pipeline end-to-end
- [ ] Test re-fetching (UPSERT behavior)
- [ ] Test re-chunking (delete old chunks)

### Documentation
- [x] Create `docs/ingestion_pipeline.md` with full design
- [ ] Update `CLAUDE.md` with new pipeline architecture
- [ ] Add monitoring queries to docs

### Cleanup
- [ ] Archive old `scripts/ingest_papers.py` (replaced by 4-phase scripts)
- [ ] Archive `test_pipeline.py` (was for testing monolithic approach)

## Backlog (Future Phases)

### Phase 2 Enhancements
- [ ] Add `PubMedSearch` table to track search queries
- [ ] Add retry logic with exponential backoff
- [ ] Add parallel fetching across multiple workers
- [ ] Add ClinicalTrials.gov integration
- [ ] Add FDA Drugs@FDA integration

### Phase 3 Enhancements
- [ ] Implement HNSW index creation/refresh
- [ ] Fine-tune chunking strategy based on evaluation
- [ ] Add monitoring dashboard

### Evaluation & Quality
- [ ] Implement RAGAS evaluation framework
- [ ] Measure citation accuracy (95%+ target)
- [ ] Test response time (<30 seconds target)

## Completed
- [x] Initial project setup (FastAPI, Docker, Postgres, pgvector)
- [x] Database models (Document, DocumentChunk)
- [x] PubMed fetcher with XML parser
- [x] Table extraction in XML parser
- [x] Token-based chunker with section awareness
- [x] Embedding service (Regular + Batch API)
- [x] Cost tracking in embedding service
- [x] Test ingestion pipeline end-to-end
- [x] Design decoupled 4-phase pipeline architecture
- [x] Write ingestion pipeline documentation

## Notes
- PMC IDs stored as numbers only (e.g., "1234567"), not "PMC1234567"
- No foreign key constraint between `pubmed_papers` and `documents` (multi-source design)
- UPSERT replaces old documents (no version history needed)
- NULL embeddings indicate chunks needing embedding
- Use `[lr]` date field for finding updated papers
