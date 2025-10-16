# OpenPharma TODO List

Last updated: 2025-10-16

## Current Sprint: Build RAG Query Interface

### Active Tasks
- [ ] Implement semantic search retrieval (top-K similarity search)
- [ ] Build LLM synthesis with citation tracking
- [ ] Create Streamlit conversational interface
- [ ] Set up RAGAS evaluation framework

**CRITICAL: Ollama Version Requirement**
- **MUST use Ollama 0.11.x** (tested on 0.11.11)
- **DO NOT upgrade to 0.12.5** - has regression bug causing EOF errors
- Download 0.11.11: https://github.com/ollama/ollama/releases/tag/v0.3.11
- Disable auto-updates in Ollama app

---

## Backlog (Future Phases)

### Phase 1 - Testing & Enhancement
- [ ] Test re-fetching (UPSERT behavior)
- [ ] Test re-chunking (delete old chunks)
- [ ] Refine diabetes search with MeSH terms (may add ~few thousand more papers)
- [ ] Enhanced metadata extraction (author affiliations, MeSH terms)
- [ ] Targeted topic expansion (Obesity, Cardiovascular Disease)
- [ ] Landmark paper augmentation (highly-cited foundational papers)

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

### Dataset Status (52K Papers - COMPLETE)
- PMC IDs collected: 52,014
- Papers fetched: 52,014 (100%)
- Documents chunked: 52,014 (100% → 1.89M chunks, 717M tokens)
- Chunks embedded: 52,014 (100% → 1.89M chunks with 768d vectors)
- **Ingestion pipeline complete** - ready for RAG implementation

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

**Phase 1 Ingestion Pipeline (COMPLETE):**
- 4-stage decoupled pipeline implemented and fully executed
- 52,014 diabetes papers: collected → fetched → chunked → embedded
- 1.89M chunks with 768d Ollama embeddings (100% complete)
- Comprehensive documentation and test suite
- Total cost: $0 (all self-hosted with Ollama)

**Ollama Migration:**
- Migrated from OpenAI (1536d, paid) to Ollama (768d, free)
- Schema updated, code simplified, docs updated
- Performance benchmarked: sequential processing recommended
- Successfully embedded entire 52K paper corpus
