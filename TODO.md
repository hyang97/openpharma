# OpenPharma TODO List

Last updated: 2025-10-24

## Current Sprint: User Feedback & Evaluation

### Active Tasks
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

See archived TODO files for detailed completion history:
- `archive/TODO_completed_20251024.md` - Phase 1 Demo Deployment (RAG, UI, Mobile, Production)
- `archive/TODO_completed_20251014.md` - Ingestion Pipeline & Ollama Migration

**Phase 1 Demo Deployment (COMPLETE):**
- Full RAG system with semantic search, LLM generation, and citation tracking
- Next.js UI with dark theme, mobile responsiveness, and polished UX
- Multi-turn conversation support with conversation-wide citation numbering
- Production deployment via Cloudflare Tunnel + Vercel
- Performance: 18-40s responses (97% LLM, 3% retrieval)

**Phase 1 Ingestion Pipeline (COMPLETE):**
- 4-stage decoupled pipeline implemented and fully executed
- 52,014 diabetes papers: collected → fetched → chunked → embedded
- 1.89M chunks with 768d Ollama embeddings (100% complete)
- Total cost: $0 (all self-hosted with Ollama)
