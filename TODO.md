# OpenPharma TODO List

Last updated: 2025-10-12

## Current Sprint: Ollama Embeddings (In Progress)

### Migration to Self-Hosted Embeddings
- [x] Update schema: `app/db/models.py` line 164: `Vector(1536)` → `Vector(768)`
- [x] Drop and recreate document_chunks table (inside api container)
- [x] Update `app/ingestion/embeddings.py` to use Ollama API instead of OpenAI
- [x] Update `scripts/stage_4_embed_chunks.py` to use Ollama (remove batch mode)
- [x] Re-chunk all documents: `docker-compose exec api python -m scripts.stage_3_chunk_papers`
- [ ] Re-embed all chunks with Ollama (~18 hours): `docker-compose run --rm -d --name api-embed api bash -c "python -m scripts.stage_4_embed_chunks"`
- [ ] Update `tests/validate_embeddings.py` to use Ollama for queries
- [ ] Validate results with semantic quality tests

**Why switching:**
- 11x faster query embeddings (36ms vs 402ms)
- $0 per query (vs $0.00001)
- Better semantic clustering in tests
- 7x faster end-to-end RAG (60ms vs 426ms)

**CRITICAL: Ollama Version Requirement**
- **MUST use Ollama 0.11.x** (tested on 0.11.11)
- **DO NOT upgrade to 0.12.5** - has regression bug causing EOF errors on concurrent embedding requests
- Symptoms: `{"error":"do embedding request: Post \"http://127.0.0.1:XXXXX/embedding\": EOF"}`
- Root cause: Version 0.12.5 cannot handle rapid sequential embedding requests (crashes runner processes)
- Solution: Downgrade to 0.11.11 from https://github.com/ollama/ollama/releases/tag/v0.3.11
- Disable auto-updates for Ollama app to prevent regression

---

## Completed Sprint: Decoupled Ingestion Pipeline

### Schema Changes
- [x] Add `PubMedPaper` model to `app/db/models.py`
  - Fields: `pmc_id` (PK), `discovered_at`, `fetch_status`
  - Status values: 'pending', 'fetched', 'failed'
- [x] Add `ingestion_status` field to `Document` model
  - Values: 'fetched', 'chunked', 'embedded'
  - Default: 'fetched'
- [x] Create database migration for new schema (reinitialized database)
- [x] Add indexes for ingestion pipeline (fetch_status, ingestion_status, partial index on NULL embeddings)

### Stage 1: Collect PMC IDs
- [x] Create `scripts/collect_pmc_ids.py`
  - Search PubMed with configurable query
  - Insert PMC IDs into `pubmed_papers` table
  - Use INSERT ... ON CONFLICT DO UPDATE for resetting fetch_status
  - Support --query, --limit, --keyword, --start-date, --end-date, --date-field arguments
  - Default query: diabetes papers 2020-2025 (open access only)
  - Removed Journal Article[ptyp] filter (52K results vs 44)

### Stage 2: Fetch Papers
- [x] Create `scripts/fetch_papers.py`
  - Query `pubmed_papers` WHERE `fetch_status='pending'`
  - Fetch XML using existing `PubMedFetcher`
  - UPSERT into `documents` table (replace if exists)
  - Set `ingestion_status='fetched'`
  - Update `pubmed_papers.fetch_status='fetched'`
  - Handle failures: set `fetch_status='failed'`
  - Support --limit and --retry-failed arguments
  - Support --confirm-large-job for background jobs
  - Rate limiting: Conservative 0.15s between calls with API key (~6.7 req/sec)
  - NCBI off-peak hours check for large jobs (>1000 papers)
  - Added NCBI API key support to pubmed_fetcher.py
  - Changed source field from 'pubmed' to 'pmc' for accuracy
  - Added HTTP timeout (30s) to prevent hangs
  - Improved logging: log outcomes not attempts, configurable levels
  - Log file archiving (archive old logs, use consistent naming)
  - Extended timeout (120s) for --retry-failed option to handle large papers
- [x] Complete fetch of all papers (52,014/52,014 fetched and chunked successfully)

### Stage 3: Chunk Documents
- [x] Create `scripts/chunk_papers.py`
  - Query `documents` WHERE `ingestion_status='fetched'`
  - Delete old chunks if re-chunking
  - Use existing `DocumentChunker`
  - Insert chunks with `embedding=NULL`
  - Set `ingestion_status='chunked'`
  - Support --limit and --rechunk-all arguments
  - Log file archiving matching fetch_papers pattern
  - Use yield_per(100) for memory-efficient streaming (handles 30K+ docs)
  - Progress logging every 100 documents
- [x] Refactor `DocumentChunker` to extract sections from full_text
  - Simplified script interface (just pass title, full_text, section_offsets)
  - Chunker now handles section extraction internally
  - Title-only document handling (for corrections/errata)
  - Reduced logging verbosity (DEBUG for per-document, INFO for progress)
- [x] Complete chunking of all fetched documents (52,014/52,014 chunked, 100% complete)

### Stage 4: Embed Chunks
- [x] Create `scripts/stage_4_embed_chunks.py`
  - Regular API mode: Process documents with ingestion_status='chunked'
  - Batch API mode: Submit batches (50K chunks or 3M tokens per batch)
  - Get-batch mode: Retrieve results (stub, not yet implemented)
  - Cost calculation and budget checking
  - Support --mode, --limit, --budget, --model, --log-level arguments
- [x] Add `OpenAIBatch` model to track batch jobs
  - Fields: openai_batch_id (PK), status, submitted_at, completed_at, doc_count, chunk_count, token_count, input_file, output_file, error_message
- [x] Add `openai_batch_id` field to Document model for batch tracking
- [x] Update EmbeddingService.embed_chunks() to return (embeddings, cost) tuple
- [ ] Implement get-batch mode to retrieve and apply batch results
- [ ] Run Stage 4 regular API on full dataset (50K docs, ~$14.34 cost)

### Testing
- [x] Test Stage 1: Collect 100 PMC IDs (52K available)
- [x] Test Stage 2: Fetch papers (52,014 papers fetched successfully)
- [x] Test Stage 3: Chunk papers (52,014 documents chunked into 1.89M chunks, avg 36 chunks/doc)
- [x] Data quality validation (verified text extraction, section distribution, journal quality)
- [x] Test Stage 4 implementation (tested batch API, encountered 3M token queue limit)
- [ ] Test Stage 4: Embed chunks with regular API (50K docs ready, $14.34 cost)
- [ ] Test full pipeline end-to-end
- [ ] Test re-fetching (UPSERT behavior)
- [ ] Test re-chunking (delete old chunks)

### Documentation
- [x] Create `docs/ingestion_pipeline.md` with full design
- [x] Update `CLAUDE.md` with new pipeline architecture and workflow guidelines
- [x] Add monitoring queries to docs
- [x] Create `docs/cheatsheet.md` with common commands
- [x] Document NCBI rate limiting and off-peak hours policy
- [x] Update `docs/cheatsheet.md` with Stage 3 commands
- [x] Update `docs/logging.md` with "log outcomes not attempts" best practice
- [x] Add database connection details to CLAUDE.md (postgres service, openpharma db, admin user)
- [x] Rename scripts with stage prefixes (stage_1_*, stage_2_*, stage_3_*, stage_4_*)
- [x] Update docs/cheatsheet.md with new script names

### Cleanup
- [x] Move `docs/archive` to project-level `archive/`
- [x] Move `openpharma_spec_v1.md` to `docs/project_spec.md`
- [x] Move `test_pipeline.py` to `tests/test_pipeline.py`
- [ ] Archive old `scripts/ingest_papers.py` (replaced by 4-stage scripts) - NOT YET CREATED

## Backlog (Future Phases)

### Phase 1 Optional Enhancements
- [ ] Refine diabetes search with MeSH terms to catch edge cases
  - Query: `(diabetes[MeSH] OR diabetes[Title/Abstract]) AND open access[filter] AND 2020/01/01:2025/12/31[pdat]`
  - May add a few thousand more papers beyond current 52K
  - Test with --limit 100 first to estimate size increase

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
- Source field set to 'pmc' (not 'pubmed') for accuracy
- No foreign key constraint between `pubmed_papers` and `documents` (multi-source design)
- UPSERT replaces old documents (no version history needed)
- NULL embeddings indicate chunks needing embedding
- Use `[lr]` date field for finding updated papers
- NCBI rate limiting: Conservative 0.15s between calls with API key (~100 papers/minute actual performance)
- Large jobs (>1000 papers) must complete within off-peak hours (weekends or 9pm-5am ET weekdays)
- Background jobs use nohup inside container with --confirm-large-job flag
- Stage 1-3 complete: 52K papers collected, fetched, and chunked into 1.89M chunks (717M tokens)
- Embedding cost: $14.34 regular API vs $7.17 batch API (text-embedding-3-small)
- **Batch API impractical**: 3M token queue limit requires 240 sequential batches (8 months)
- **Recommendation**: Use regular API for $7 premium to complete in 12-15 hours vs months
