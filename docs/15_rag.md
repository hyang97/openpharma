# RAG Architecture

OpenPharma's Retrieval-Augmented Generation (RAG) system for answering questions about diabetes research.

## Overview

The RAG pipeline has two main stages:
1. **Retrieval** - Find relevant paper chunks using semantic search
2. **Generation** - Synthesize an answer with citations using an LLM

## Module Structure

```
app/
├── retrieval/
│   ├── __init__.py
│   └── semantic_search.py     # Vector similarity search
└── rag/
    ├── __init__.py
    └── generation.py           # LLM synthesis with citations
```

## 1. Retrieval

### 1.1 Semantic Search (`app/retrieval/semantic_search.py`)

#### Function: `semantic_search(query: str, top_k: int = 20, top_n: int = 5, use_reranker: bool = False) -> List[SearchResult]`

Performs vector similarity search over 1.89M embedded chunks with optional cross-encoder reranking.

**Implementation:**
1. Embed query using cached EmbeddingService (Ollama nomic-embed-text, 768d)
2. Execute cosine similarity search via Postgres HNSW index to get top_k candidates
3. Join with documents table to get metadata
4. **Optional reranking** (if use_reranker=True):
   - Pass top_k chunks to cross-encoder reranker
   - Cross-encoder scores (query, chunk) pairs for relevance
   - Returns top_n highest-scored chunks
5. Return top_n chunks (reranked if enabled, otherwise first top_n from semantic search)

**SearchResult fields:**
- `chunk_id`, `document_id`, `section`, `content`
- `similarity_score: Optional[float]` (0-1 for semantic search, None for ID-based retrieval)
- `title`, `source_id` (PMC ID)
- `authors`, `publication_date`, `journal`, `doi` (optional metadata)

**Performance:**
- Query embedding: ~50-200ms (Ollama API call)
- Vector search: ~10-100ms (HNSW index over 1.89M chunks)
- Total: ~60-300ms
- Optimization: EmbeddingService instance cached at module level (saves 5-20ms/query)

**Quality:**
- Typical similarity scores: 0.84-0.86 for relevant results
- Tested with 7 gold-standard diabetes queries (see `tests/test_retrieval_quality.py`)

### Function: `fetch_chunks_by_chunk_ids(chunk_ids: List[int]) -> Dict[int, SearchResult]`

Fetches specific chunks by their database IDs (used for hybrid retrieval).

**Implementation:**
1. Query chunks table with `WHERE chunk_id = ANY(:chunk_ids)`
2. Join with documents table for metadata
3. Return dict mapping chunk_id -> SearchResult

**Use case:** Retrieve historically cited chunks for multi-turn conversations

### Function: `hybrid_retrieval(query: str, conversation_history: Optional[List[dict]], top_k: int = 20, top_n: int = 5, max_historical_chunks: int = 15) -> List[SearchResult]`

Combines fresh semantic search with historical chunks from conversation.

**Implementation:**
1. Perform semantic search for top_n fresh chunks (most relevant to current query)
2. Extract `cited_chunk_ids` from conversation_history (walking backwards)
3. Fetch historical chunks using `fetch_chunks_by_chunk_ids()`
4. Combine fresh + historical, deduplicating by chunk_id
5. Return combined list (fresh chunks first, then historical)

**Strategy:**
- Turn 1: Pure semantic search (no history) - returns N fresh chunks
- Turn 2+: Hybrid retrieval - returns N fresh + up to M historical chunks
- Prevents citation hallucination by making previously cited chunks available

**Performance:**
- Turn 1: ~50-300ms (semantic search only)
- Turn 2+: ~200-600ms (semantic search + chunk ID lookup)

### 1.2 Cross-Encoder Reranking (`app/retrieval/reranker.py`)

Reranks retrieved chunks using a cross-encoder model for improved relevance.

**Why Reranking?**
- Bi-encoder embeddings (nomic-embed-text) optimize for retrieval speed but sacrifice accuracy
- Cross-encoders score (query, document) pairs jointly for better relevance
- Two-stage pipeline: fast retrieval (top-20) → slow reranking (top-5)

**Model:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (default)
- Fast and lightweight cross-encoder
- Reranking time: ~0.8s for 20 chunks
- Alternative models available via RERANKER_MODEL env var:
  - `BAAI/bge-reranker-v2-m3`: Higher quality, ~48s for 20 chunks
  - `BAAI/bge-small-en-v1.5`: Balanced, ~1s for 20 chunks

**Configuration:**
- Set in `.env`: `RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2`
- Must be passed through `docker-compose.yml` environment section
- Default in code: `app/retrieval/reranker.py` line 40
- Requires container restart to pick up env var changes

**Usage:** Pass `use_reranker=True` to `/chat` endpoint or `semantic_search()` function

**Evaluation:** Automated framework in `tests/reranking_eval_*.py` with LLM-as-judge

## 2. Generation (`app/rag/generation.py`)

### Function: `answer_query(query: str, top_k: int = 10, llm_provider: str = "ollama") -> AnswerResult`

Generates synthesized answers with inline citations.

**Implementation (planned):**
1. Call `semantic_search()` to get relevant chunks
2. Build prompt with numbered chunks (format: [1], [2], etc.)
3. Call LLM (Ollama Llama 3.1 8B or OpenAI GPT-4)
4. Parse response and build Citation objects
5. Return AnswerResult

**Citation format:**
```
Answer: "Metformin is the first-line treatment [1]. GLP-1 agonists provide cardiovascular benefits [2][3]."

Citations:
[1] Smith et al. 2023, "Diabetes Guidelines", PMC12345
[2] Jones et al. 2024, "GLP-1 Outcomes", PMC67890
[3] Lee et al. 2023, "Cardiovascular Safety", PMC11111
```

**AnswerResult fields:**
- `query` - Original question
- `answer` - Synthesized response with inline citations
- `citations` - List of Citation objects
- `chunks_used` - Source SearchResult chunks
- `llm_provider` - "ollama" or "openai"
- `generation_time_ms` - Total latency

**Citation fields:**
- `number` - Citation number [1], [2], etc.
- `title`, `source_id` (PMC ID)
- `authors`, `publication_date` (optional)
- `chunk_id` - Original chunk for traceability

## Design Decisions

**Why separate retrieval and generation?**
- Retrieval can be tested/optimized independently
- Easy to swap retrieval strategies (dense, sparse, hybrid)
- Generation can be reused with different retrieval sources
- Clear separation of concerns

**Why call semantic_search() internally?**
- Simpler API - one function does end-to-end RAG
- Users don't need to understand retrieval details
- Can still use semantic_search() directly for debugging

**Why inline citation format [1], [2]?**
- Standard academic convention
- Easy for LLM to generate
- Simple to parse and verify
- Clean reading experience

**Why support both Ollama and OpenAI?**
- Ollama for local development ($0 cost)
- OpenAI for higher quality demos (GPT-4)
- Learn to handle multiple LLM providers

## Usage Example

```python
from app.rag import answer_query

# Ask a question
result = answer_query(
    "What are GLP-1 agonists used for in diabetes treatment?",
    top_k=10,
    llm_provider="ollama"
)

# Print answer
print(result.answer)
# "GLP-1 agonists are used for type 2 diabetes treatment [1][2].
#  They provide weight loss benefits [1] and cardiovascular protection [3]."

# Print citations
for citation in result.citations:
    print(f"[{citation.number}] {citation.title} (PMC{citation.source_id})")
# [1] Smith et al. 2023, "GLP-1 Mechanisms" (PMC12345)
# [2] Jones et al. 2024, "Diabetes Therapy" (PMC67890)
# [3] Lee et al. 2023, "Cardiovascular Safety" (PMC11111)
```

## 3. Multi-Turn Conversations (Phase 1 - In Progress)

### Ollama KV Cache and Conversation Support

**How Ollama handles multi-turn conversations:**
- Ollama automatically reuses KV cache based on **prompt prefix matching**
- No explicit session management needed - just send full message history
- If messages array starts with previously seen messages, KV cache is reused
- Only new tokens at the end require computation

**Implementation approach:**
```python
# Request 1
messages = [
    {'role': 'user', 'content': 'What is metformin?'}
]
# Ollama computes and caches KV

# Request 2 (follow-up)
messages = [
    {'role': 'user', 'content': 'What is metformin?'},
    {'role': 'assistant', 'content': '...previous response...'},
    {'role': 'user', 'content': 'What about side effects?'}
]
# Ollama sees prefix matches → reuses cached KV
# Only computes new tokens for "What about side effects?"
```

**Our implementation (Phase 1 - COMPLETED):**
1. **Conversation Manager** (`app/rag/conversation_manager.py`)
   - Store conversations in-memory dict (keyed by conversation_id)
   - Manage message history (user/assistant turns)
   - Track citations with conversation-wide numbering (source_id -> number)
   - Store `cited_chunk_ids` and `cited_source_ids` per message
   - Clean up old conversations after timeout

2. **Updated `/chat` endpoint** (`app/main.py`)
   - Accept optional `conversation_id` in request
   - Retrieve conversation history from manager
   - Use hybrid retrieval (fresh + historical chunks)
   - Extract citations from LLM response (PMC format)
   - Assign conversation-wide citation numbers
   - Store messages with cited_chunk_ids/cited_source_ids
   - Pass full messages array to Ollama
   - Set `keep_alive=-1` to keep model loaded

3. **Data Models** (`app/models.py`)
   - `SearchResult` - Retrieved chunk with metadata
   - `Citation` - Numbered citation (immutable)
   - `RAGResponse` - LLM response with embedded [PMCxxxxxx] citations
   - `Conversation` - Message history + citation tracking

4. **No stateful sessions with Ollama needed**
   - Backend manages conversation state
   - Ollama automatically optimizes via KV cache reuse

**Citation Flow:**
1. LLM generates response with [PMCxxxxxx] format
2. Backend extracts PMC IDs and builds Citation objects
3. ConversationManager assigns conversation-wide numbers ([1], [2], etc.)
4. Frontend display renumbers [PMCxxxxxx] -> [1] for user
5. Messages store both source_ids (for display) and chunk_ids (for retrieval)

**Performance benefits:**
- Without cache reuse: ~2-5s per turn (reprocesses everything)
- With cache reuse: ~0.5-2s per turn (only new tokens)

**Limitations:**
- KV cache reuse may not work with sliding window attention models (e.g., Gemma 3)
- Works well with Llama 3.1 (our current model)

## Future Enhancements

**Phase 1 improvements (Current):**
- ✅ Multi-turn conversation support with KV cache optimization
- ✅ Hybrid retrieval (fresh semantic search + historical chunks)
- ✅ Chunk-level citation tracking (prevents hallucination)
- ✅ Conversation-wide citation numbering
- ⏳ Fix Turn 2 citation issue (separate fresh/historical in prompt)
- ⏳ Query rewriting for follow-up questions ("What about side effects?" → "What are the side effects of metformin?")
- ⏳ Citation accuracy verification (post-process to check claims match chunks)
- Structured output (JSON) to enforce citation format
- Query expansion (synonyms, related terms)
- Reranking (MMR for diversity, section weighting)
- Filters (by date, journal, section type)

**Phase 2 improvements:**
- Multi-step reasoning with LangGraph
- Cross-domain queries (clinical trials + research papers)
- Persistent conversation storage (database instead of in-memory)
- Streaming responses for better UX

## Related Documentation

- `data_design.md` - Database schema for documents and chunks
- `ingestion_pipeline.md` - How papers are fetched, chunked, and embedded
- `embedding_service.md` - Ollama embedding API reference
- `decisions.md` - Architecture decisions (Postgres vs Pinecone, chunk-level search, etc.)
