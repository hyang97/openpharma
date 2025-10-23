# OpenPharma TODO List

Last updated: 2025-10-23

## Current Sprint: Phase 1 Demo Deployment

### Active Tasks
- [x] Implement semantic search retrieval (top-K similarity search)
- [x] Build LLM generation with citation tracking
- [x] Implement multi-turn conversation support with conversation-wide citation numbering
- [x] Create Next.js conversational UI with collapsible sidebar
- [x] Fix citation format consistency (store PMC IDs internally, renumber for display only)
- [x] Add performance timing instrumentation
- [x] Refactor citation flow: immutable Citations, chunk-level tracking, centralized data models
- [x] Debug and fix Turn 2+ citation generation regression (hybrid retrieval complexity issue)
- [x] Add UI animations (message fade-in, citation expand/collapse, sidebar transitions)
- [x] Deploy to production (Cloudflare Tunnel + Vercel)
- [ ] Share with 5-10 friends for feedback
- [ ] Set up RAGAS evaluation framework
- [ ] Optimize response time to < 30 seconds (deferred to Phase 2 with Gemini)

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

### Phase 2 - Cloud Deployment & Advanced RAG
- [ ] Deploy to GCP with Gemini API (8-10s responses)
  - Cloud Run for API
  - Gemini Flash/Pro via Vertex AI
  - Self-hosted DB via Cloudflare Tunnel (saves $30-50/month)
- [ ] Implement query rewriting for better multi-turn retrieval
- [ ] Add chunk reranking (cross-encoder or LLM-based)
- [ ] Add routing/classification for query types
- [ ] Implement query rewriting for better multi-turn retrieval (alternative to hybrid retrieval)
- [ ] Re-evaluate hybrid retrieval with more capable model (GPT-4 or Llama 3.1 70B)
- [ ] Add MLflow or LangSmith for prompt versioning and experiment tracking
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
- [ ] **PRIORITY: Optimize response time to < 30 seconds**
  - Current: 18-40s total (LLM generation: 18-40s, Retrieval: ~200ms)
  - Bottleneck identified: LLM inference time (97% of total)
  - Options: Reduce top_n chunks, try smaller models (phi4-mini, llama3.2:3b), or accept current performance
- [ ] Implement RAGAS evaluation framework
- [ ] Measure citation accuracy (95%+ target)

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
