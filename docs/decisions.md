# Architecture Decision Log
Key technical decisions made during OpenPharma development.

## Phase 1: Postgres + pgvector vs. Pinecone
**Problem**: Need vector database for 52K papers (~1.9M chunks).
**Decision**: Use Postgres + pgvector with HNSW index.
**Why**: Sufficient for <1M documents, $0-50/month vs. $70-200/month, simpler deployment, no external dependencies.
**Tradeoff**: May need dedicated vector DB at massive scale, but not relevant for current phase.

## Phase 1: Ollama nomic-embed-text for embeddings
**Problem**: Need embedding model for semantic search.
**Decision**: Self-hosted Ollama nomic-embed-text (768d).
**Why**: $0 cost, fast inference (~36ms), better semantic clustering than OpenAI in benchmarks.
**Tradeoff**: MUST use Ollama 0.11.x (0.12.5 has regression bug). Requires local hosting.

## Phase 1: Chunk-level search only
**Problem**: How to structure retrieval - document-level or chunk-level embeddings?
**Decision**: Only embed chunks (512 tokens), not full documents. Store metadata in documents table.
**Why**: Prevents context bloat, better retrieval accuracy for specific questions, lower LLM costs (smaller context windows).
**Tradeoff**: Can't do document-level similarity search (not needed for current use cases).

## 2025-10-19: Built React UI in Phase 1 (Decision Reversal)
**Problem**: Need UI for Phase 1 MVP, but want professional polish.
**Original Decision**: Start with Streamlit (Phase 1), migrate to React (Phase 2).
**Actual Decision**: Built Next.js + React + TypeScript UI directly in Phase 1.
**Why**: User experience matters from day 1, React skills transferable to other projects, modern web stack more portfolio-friendly than Streamlit.
**Tradeoff**: Steeper learning curve for React beginners, but worth it for production-quality UI from start.
**Note**: This reversed the original plan documented below. Keeping for historical context.

## Phase 1-2: Raw Python RAG → LangChain progression
**Problem**: Build RAG from scratch or use framework?
**Decision**: Raw Python for Phase 1, adopt LangChain in Phase 2.
**Why**: Understand primitives before abstractions, better learning experience, LangChain valuable when adding agents and complex workflows.
**Tradeoff**: More initial code to write, but deeper understanding of RAG fundamentals.

## 2025-10-16: Cache EmbeddingService instance across queries
**Problem**: Creating new `EmbeddingService()` on every query added 5-20ms overhead.
**Decision**: Create once at module level, reuse for all queries.
**Why**: Stateless service with minimal memory, no persistent connections.
**Tradeoff**: Lives for application lifetime, slightly harder to unit test.

## 2025-10-21: Store PMC IDs internally, renumber only for display
**Problem**: Multi-turn conversations broke when LLM saw previous responses with numbered citations [1], [2] instead of [PMC...] format.
**Decision**: Store messages with original [PMC...] format in conversation history, only renumber to [1], [2] when sending to frontend.
**Why**: Keeps LLM prompts consistent (always uses PMC IDs), prevents confusion in follow-up responses, separates storage from display concerns.
**Implementation**: `generation.py` returns [PMC...], `main.py` stores [PMC...], `renumber_text_for_display()` converts to [1], [2] only for API responses.
**Tradeoff**: Slight overhead from renumbering on every request, but negligible compared to LLM generation time.

## 2025-10-22: Revert hybrid retrieval - Use semantic search only
**Problem**: Hybrid retrieval (semantic search + historical chunks) broke citation generation on Turn 2+ with Llama 3.1 8B. Model generated responses without any [PMC...] citations.
**Root Cause**:
- Variable chunk count (5 → 9) between turns confused model
- "Recently cited literature" phrase signaled model not to cite
- Llama 3.1 8B struggles with complex multi-turn reasoning when context changes significantly
**Decision**: Revert to pure semantic_search() for now. Defer hybrid retrieval to Phase 2 with more capable model.
**Implementation**:
- `generation.py`: Use `semantic_search(query, top_k=20)[:top_n]` (always 5 chunks)
- Remove "as well as recently cited literature" from prompt
- Keep simpler constraint language (removed "CRITICAL: EVERY" over-emphasis)
**Result**: ✅ Citations now work correctly on all turns (tested Turn 1: 2 citations, Turn 2: 4 citations)
**Future**: Re-evaluate hybrid retrieval in Phase 2 with GPT-4 or Llama 3.1 70B, or implement query rewriting as alternative approach.
**Learning**: Simpler is better for smaller models. Prompt versioning is critical - created `docs/prompts/` for tracking.
**Tradeoff**: No historical context in retrieval, but model wasn't using it correctly anyway. Query rewriting may be better approach.