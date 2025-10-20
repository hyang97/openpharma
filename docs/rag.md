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

## 1. Retrieval (`app/retrieval/semantic_search.py`)

### Function: `semantic_search(query: str, top_k: int = 10) -> List[SearchResult]`

Performs vector similarity search over 1.89M embedded chunks.

**Implementation:**
1. Embed query using cached EmbeddingService (Ollama nomic-embed-text, 768d)
2. Execute cosine similarity search via Postgres HNSW index
3. Join with documents table to get metadata
4. Return top-K chunks ordered by similarity (highest first)

**SearchResult fields:**
- `chunk_id`, `document_id`, `section`, `content`
- `similarity_score` (0-1, higher is better)
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

**Our implementation (Phase 1):**
1. **Conversation Manager** (`app/rag/conversation_manager.py`)
   - Store conversations in-memory dict (keyed by conversation_id)
   - Manage message history (user/assistant turns)
   - Clean up old conversations after timeout

2. **Updated `/ask` endpoint** (`app/main.py`)
   - Accept optional `conversation_id` in request
   - Retrieve conversation history from manager
   - Append new user message
   - Pass full messages array to Ollama
   - Store assistant response
   - Set `keep_alive=-1` to keep model loaded

3. **No stateful sessions with Ollama needed**
   - Backend manages conversation state
   - Ollama automatically optimizes via KV cache reuse

**Performance benefits:**
- Without cache reuse: ~2-5s per turn (reprocesses everything)
- With cache reuse: ~0.5-2s per turn (only new tokens)

**Limitations:**
- KV cache reuse may not work with sliding window attention models (e.g., Gemma 3)
- Works well with Llama 3.1 (our current model)

## Future Enhancements

**Phase 1 improvements (Current):**
- ✅ Multi-turn conversation support with KV cache optimization
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
