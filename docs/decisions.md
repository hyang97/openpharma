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

## Phase 1-2: Streamlit → React progression
**Problem**: Need UI for Phase 1 MVP, but want professional polish later.
**Decision**: Start with Streamlit (Phase 1), migrate to React (Phase 2).
**Why**: Streamlit enables rapid prototyping (ship in days), React provides production UX. Prove value before investing in frontend complexity.
**Tradeoff**: Will need to rewrite UI in Phase 2, but speed-to-market more important initially.

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