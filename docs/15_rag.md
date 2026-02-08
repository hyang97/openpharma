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
│   ├── semantic_search.py        # Vector similarity search
│   └── reranker.py               # Cross-encoder reranking
├── rag/
│   ├── __init__.py
│   ├── generation.py             # LLM synthesis
│   ├── conversation_manager.py   # Conversation state & citations
│   └── response_processing.py    # Citation extraction & display formatting
└── main.py                       # FastAPI endpoints
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

### Function: `generate_response(user_message: str, chunks: List[SearchResult], use_local: bool = True, conversation_history: Optional[List[dict]] = None) -> str`

Generates synthesized answers with inline `[PMCxxxxxx]` citations.

**Implementation:**
1. Build messages array with system prompt, conversation history, and literature chunks
2. Call LLM (Ollama Llama 3.1 8B or Claude Haiku 3)
3. Return raw response text with `## Answer` and `## References` headings

**LLM Response Format:**
```
## Answer:
Metformin is the first-line treatment [PMC12345]. GLP-1 agonists provide cardiovascular benefits [PMC67890][PMC11111].

## References:
[PMC12345] Smith et al. 2023, "Diabetes Guidelines"
[PMC67890] Jones et al. 2024, "GLP-1 Outcomes"
[PMC11111] Lee et al. 2023, "Cardiovascular Safety"
```

**Design Notes:**
- Retrieval done by caller (endpoint level)
- Returns raw text only (no RAGResponse object)
- Citations in `[PMCxxxxxx]` format (renumbered later by `response_processing.py`)
- Headings stripped for display by `prepare_messages_for_display()`

## 3. Response Processing (`app/rag/response_processing.py`)

### Heading Detection Patterns

Standardized regex patterns for consistent detection across streaming and non-streaming:

```python
# Matches: "## Answer", "##Answer", "## Answer:", etc.
ANSWER_HEADING_PATTERN = r'(?:^|\n)\s*##\s*Answer\s*:?\s*'

# Matches: "## References", "##References", "References:", "**References**"
REFERENCES_HEADING_PATTERN = r'(?:^|\n)\s*(?:##\s*References|References\s*:|[\*]{2}References[\*]{2})\s*:?\s*'
```

### Function: `extract_and_store_citations(generated_response: str, chunks: List[SearchResult], conversation_id: str, conversation_manager: ConversationManager) -> List[Citation]`

Extracts `[PMCxxxxxx]` citations from answer section only (excludes bibliography).

**Implementation:**
1. Extract answer section using `extract_answer_section()` (before `## References`)
2. Find all `[PMCxxxxxx]` citations in answer text using regex
3. Build Citation objects via ConversationManager (assigns conversation-wide numbers)
4. Return numbered citations

**Key Behavior:**
- Only counts citations actually used in answer (not sources listed in bibliography)
- Preserves order of first appearance
- Deduplicates citations

### Function: `prepare_messages_for_display(messages: List[dict], conversation_id: str, conversation_manager: ConversationManager) -> List[dict]`

Prepares assistant messages for frontend display.

**Implementation:**
1. Strip `## Answer` heading using `strip_answer_heading()`
2. Strip `## References` section using `strip_references_section()`
3. Renumber citations: `[PMCxxxxxx] → [1]` using conversation-wide mapping
4. Return cleaned messages

## 4. Conversation Management (`app/rag/conversation_manager.py`)

Manages conversation state, messages, and conversation-wide citation numbering.

**Key Features:**
- In-memory conversation storage with auto-cleanup (1 hour TTL)
- Conversation-wide citation numbering (first appearance gets [1], second gets [2], etc.)
- Multi-turn conversation support with message history

**See `docs/22_conversation_management.md` for full details**

## Design Decisions

**Why separate retrieval at endpoint level?**
- Generation functions testable in isolation
- Easy to add streaming variant with same retrieval logic
- Clear separation: endpoints orchestrate, generation functions generate

**Why [PMCxxxxxx] format from LLM?**
- Unambiguous source identifiers (no renumbering needed until display)
- Stable across conversation turns (citations don't change numbers when new sources added)
- Easy to verify citations against prompt chunks

**Why strip headings for display?**
- Cleaner UX (users don't need to see structural markers)
- Headings are for LLM structuring only
- Allows flexibility in LLM response format without breaking frontend

**Why conversation-wide citation numbering?**
- Consistent citation numbers across conversation (citation [1] stays [1] even in turn 5)
- Users can reference citations from previous turns
- Simpler mental model for multi-turn conversations

## Streaming Responses (Phase 1 - Complete)

### Overview
SSE (Server-Sent Events) streaming for progressive token display during LLM generation.

**Endpoints:**
- `/chat/stream` - Streaming endpoint (SSE)
- `/chat` - Standard endpoint (non-streaming)

### Streaming Generator (`app/rag/generation.py:103-202`)

**Function:** `generate_response_stream(user_message, chunks, use_local, conversation_history)`

**Implementation:**
- Async generator that yields token dictionaries: `{"type": "token", "content": "..."}` or `{"type": "complete"}`
- Two-state FSM with lookahead buffering:
  1. **Preamble state**: Buffer until `## Answer` heading found (waits 3 tokens after match to capture `:` and `\n`)
  2. **Streaming state**: Yield tokens with 5-token lookahead to detect `## References` and stop
- Fallback: start streaming after 100 tokens if no heading found

**Backend Endpoint** (`app/main.py:119-190`):
```python
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    # 1. Retrieval (same as standard endpoint)
    chunks = semantic_search(...)

    # 2. Stream generator
    async def event_generator():
        yield f'data: {json.dumps({"type": "start"})}\n\n'

        async for event in generate_response_stream(...):
            if event["type"] == "token":
                yield f'data: {json.dumps(event)}\n\n'
            elif event["type"] == "end_of_response":
                # Post-process, extract citations, save to conversation
                yield f'data: {json.dumps({"type": "complete"})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**See `docs/24_streaming_responses.md` for complete streaming architecture.**

## Usage Examples

**Standard (Non-Streaming):**
```python
from app.rag.generation import generate_response
from app.retrieval import semantic_search
from app.rag.response_processing import extract_and_store_citations

# 1. Retrieve chunks
chunks = semantic_search("What are GLP-1 agonists?", top_k=20, top_n=5)

# 2. Generate response
generated_text = generate_response(
    user_message="What are GLP-1 agonists?",
    chunks=chunks,
    use_local=True
)
# Returns: "## Answer:\nGLP-1 agonists are... [PMC12345]\n\n## References:\n[PMC12345]..."

# 3. Extract citations
citations = extract_and_store_citations(
    generated_response=generated_text,
    chunks=chunks,
    conversation_id=conv_id,
    conversation_manager=manager
)
# Returns: [Citation(number=1, source_id="12345", title="...", ...)]
```

**Streaming:**
```python
from app.rag.generation import generate_response_stream

# Async generator yields tokens
async for event in generate_response_stream(user_message, chunks, True, history):
    if event["type"] == "token":
        print(event["content"], end="", flush=True)
    elif event["type"] == "end_of_response":
        full_response = event["full_response"]
        # Post-process and extract citations from full_response
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
