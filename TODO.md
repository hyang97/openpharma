# OpenPharma TODO List

Last updated: 2025-10-14

## Current Sprint: Complete Ollama Embeddings

### Active Tasks
- [ ] Re-embed all chunks with Ollama (~55 hours for 1.77M chunks)
  - Command: `docker-compose run --rm -d --name api-embed api bash -c "python -m scripts.stage_4_embed_chunks --workers 1"`
  - Monitor: `docker exec api-embed tail -f logs/stage_4_embed_chunks.log`
  - Current: 3,714 docs embedded (117K chunks), 48,300 docs remaining
- [ ] Validate full embeddings with semantic quality tests

**CRITICAL: Ollama Version Requirement**
- **MUST use Ollama 0.11.x** (tested on 0.11.11)
- **DO NOT upgrade to 0.12.5** - has regression bug causing EOF errors
- Download 0.11.11: https://github.com/ollama/ollama/releases/tag/v0.3.11
- Disable auto-updates in Ollama app

**Performance Notes:**
- Sequential processing: ~111ms/chunk (workers=1 recommended)
- Parallel workers provide NO speedup for real chunk sizes
- Ollama: 11x faster queries, $0 cost, better semantic clustering vs OpenAI

---

## Backlog (Future Phases)

### Phase 1 - Finish Testing
- [ ] Test full pipeline end-to-end after complete embedding
- [ ] Test re-fetching (UPSERT behavior)
- [ ] Test re-chunking (delete old chunks)
- [ ] Refine diabetes search with MeSH terms (may add ~few thousand more papers)

### Phase 2 - Multi-Domain Intelligence
- [ ] Add ClinicalTrials.gov integration
- [ ] Add FDA Drugs@FDA integration
- [ ] Add retry logic with exponential backoff
- [ ] Add parallel fetching across multiple workers
- [ ] Add `PubMedSearch` table to track search queries

### Phase 3 - Optimization
- [ ] Implement HNSW index creation/refresh
- [ ] Fine-tune chunking strategy based on evaluation
- [ ] Add monitoring dashboard

### Evaluation & Quality
- [ ] Implement RAGAS evaluation framework
- [ ] Measure citation accuracy (95%+ target)
- [ ] Test response time (<30 seconds target)

---

## Project Context

### Dataset Status (52K Papers)
- PMC IDs collected: 52,014
- Papers fetched: 52,014 (100%)
- Documents chunked: 52,014 (100% → 1.89M chunks, 717M tokens)
- Chunks embedded: 3,714 docs (117K chunks, 6%)
- Remaining: 48,300 docs (~55 hours at 111ms/chunk)

### Tech Stack
- Database: Postgres + pgvector, HNSW index (m=16, ef_construction=64)
- Embeddings: Ollama nomic-embed-text (768d, $0 cost)
- Schema: `pubmed_papers` → `documents` → `document_chunks`
- Ingestion: 4-stage decoupled pipeline (collect, fetch, chunk, embed)

### Key Constraints
- NCBI rate limiting: ~100 papers/minute actual performance
- Large jobs (>1000 papers): Run during off-peak hours (weekends or 9pm-5am ET weekdays)
- Ollama version: MUST use 0.11.x (0.12.5 has EOF regression bug)

---

## Completed Milestones

See `archive/TODO_completed_20251014.md` for detailed history.

**Phase 1 Ingestion Pipeline:**
- 4-stage decoupled pipeline implemented and tested
- 52K diabetes papers collected, fetched, and chunked
- Comprehensive documentation and test suite

**Ollama Migration:**
- Migrated from OpenAI (1536d, paid) to Ollama (768d, free)
- Schema updated, code simplified, docs updated
- Performance benchmarked: sequential processing recommended
