# Embedding Service Guide

The `EmbeddingService` class in `app/ingestion/embeddings.py` provides embeddings using **Ollama** (self-hosted, free) with legacy OpenAI support.

## CRITICAL: Ollama Version Requirements

**MUST use Ollama 0.11.x (tested on 0.11.11)**
- DO NOT upgrade to 0.12.5 - has regression bug causing EOF errors
- Download 0.11.11: https://github.com/ollama/ollama/releases/tag/v0.3.11
- Disable auto-updates in Ollama app
- Verify version: `ollama --version`

**Symptom of 0.12.5 bug:**
```
{"error":"do embedding request: Post \"http://127.0.0.1:XXXXX/embedding\": EOF"}
```

## Quick Reference

### Ollama API (Primary, Free, 768d)

```python
from app.ingestion.embeddings import EmbeddingService

embedder = EmbeddingService()  # Uses Ollama by default

# Extract embedding texts from chunks
texts = [chunk["embedding_text"] for chunk in chunks]

# Embed texts (returns tuple: embeddings list, cost)
embeddings, cost = embedder.embed_chunks(texts)

# Add embeddings back to chunks
for chunk, embedding in zip(chunks, embeddings):
    chunk["embedding"] = embedding

# Check for failures
failed_indices = [i for i, emb in enumerate(embeddings) if emb is None]
if failed_indices:
    print(f"Warning: {len(failed_indices)} chunks failed to embed")
```

**When to use:**
- Always (primary method)
- Development, testing, and production
- Free ($0 cost)
- Fast (768d vectors)
- Self-hosted (no API keys needed)

**Cost:** $0 (self-hosted)
**Time:** Instant (~0.1s per chunk)
**Dimensions:** 768 (nomic-embed-text model)

**Error handling:** Failed embeddings are `None`, continue processing other chunks

---

## How the Embedding Service Works

### Input Requirements

All chunks must have an `embedding_text` field:

```python
chunk = {
    "content": "We studied 100 patients...",
    "section": "methods",
    "embedding_text": "Doc: Diabetes Study\nSection: methods\n\nWe studied 100 patients...",
    "chunk_index": 0
}
```

The `embedding_text` is what gets sent to Ollama (includes document title + section for better context).

### Output

After embedding, chunks will have an `embedding` field:

```python
chunk = {
    "content": "We studied 100 patients...",
    "section": "methods",
    "embedding_text": "Doc: Diabetes Study\nSection: methods\n\nWe studied 100 patients...",
    "embedding": [0.123, -0.456, 0.789, ...]  # 768 floats
}
```

---

## Ollama API Details

### Method

**`embed_chunks(texts: List[str], max_workers: int = None) -> tuple[List[Optional[List[float]]], float]`**
- Embed multiple texts using Ollama (self-hosted)
- Sequential processing by default (safest)
- Returns tuple: (embeddings list, cost=0.0)
- Embeddings are None for failed requests

### How it works

1. Processes texts sequentially (one at a time)
2. Calls Ollama API at `http://host.docker.internal:11434/api/embeddings`
3. If a request fails, logs error and sets that embedding to None, continues processing
4. Small delay (0.1s) between requests to prevent overwhelming Ollama
5. Returns all embeddings in order (with None for any failures) and cost ($0)

### Configuration

Default Ollama endpoint: `http://host.docker.internal:11434`
Override with environment variable: `OLLAMA_BASE_URL=http://localhost:11434`

---

## Error Handling

### Ollama API

The service continues processing even if some requests fail. Failed embeddings are set to `None`:

```python
texts = [chunk["embedding_text"] for chunk in chunks]
embeddings, cost = embedder.embed_chunks(texts)

# Add embeddings to chunks
for chunk, emb in zip(chunks, embeddings):
    chunk["embedding"] = emb

# Find failures
failed_indices = [i for i, emb in enumerate(embeddings) if emb is None]

if failed_indices:
    print(f"{len(failed_indices)} chunks failed")

    # Option 1: Retry failed chunks
    failed_texts = [texts[i] for i in failed_indices]
    retry_embeddings, _ = embedder.embed_chunks(failed_texts)

    # Merge successful retries back
    for fail_idx, retry_emb in zip(failed_indices, retry_embeddings):
        if retry_emb is not None:
            chunks[fail_idx]["embedding"] = retry_emb

    # Option 2: Filter out failed chunks and proceed
    successful_chunks = [c for c in chunks if c.get('embedding') is not None]
```

Common errors:
- Connection errors: Ollama not running, wrong URL → embeddings set to None
- EOF errors: Ollama version 0.12.5 regression bug → downgrade to 0.11.11
- Timeout: Model loading taking too long → increase timeout parameter

---

## Logging

The service logs extensively:

```
INFO - Initialized EmbeddingService with Ollama model: nomic-embed-text at http://host.docker.internal:11434
INFO - Generated 150/150 embeddings (768 dimensions, $0 cost)
```

Set `LOG_LEVEL=DEBUG` for more detail:

```
DEBUG - successfully embedded Doc: Effect of dipeptidyl peptidase-4 inhibitors...
```

---

## Example: Full Workflow

```python
from app.ingestion.pubmed_fetcher import PubMedFetcher
from app.ingestion.xml_parser import PMCXMLParser
from app.ingestion.chunker import DocumentChunker
from app.ingestion.embeddings import EmbeddingService
from app.logging_config import setup_logging

# Setup
setup_logging(level="INFO")

# Fetch papers
fetcher = PubMedFetcher()
pmc_ids = fetcher.search_diabetes_papers(max_results=5)
papers = fetcher.fetch_batch(pmc_ids)

# Chunk papers
chunker = DocumentChunker()
all_chunks = []
for paper in papers:
    chunks = chunker.chunk_document(paper)
    all_chunks.extend(chunks)

print(f"Total chunks: {len(all_chunks)}")

# Embed chunks with Ollama
embedder = EmbeddingService()

texts = [chunk["embedding_text"] for chunk in all_chunks]
embeddings, cost = embedder.embed_chunks(texts)

for chunk, emb in zip(all_chunks, embeddings):
    chunk["embedding"] = emb

# Retry failed chunks if any
failed_indices = [i for i, emb in enumerate(embeddings) if emb is None]
if failed_indices:
    print(f"Retrying {len(failed_indices)} failed chunks...")
    failed_texts = [texts[i] for i in failed_indices]
    retry_embeddings, _ = embedder.embed_chunks(failed_texts)

    for fail_idx, retry_emb in zip(failed_indices, retry_embeddings):
        if retry_emb is not None:
            all_chunks[fail_idx]["embedding"] = retry_emb

# Now chunks have embeddings - ready to store in database!
print(f"Embedded {len(all_chunks)} chunks at $0 cost")
```

---

## Legacy: OpenAI API Support

The service still supports OpenAI for backward compatibility, but Ollama is recommended.

**Deprecated methods:**
- `embed_chunks_openai()` - Use Ollama `embed_chunks()` instead
- `submit_batch_embed_openai()` - Batch API not needed with free Ollama
- `get_batch_embed_openai()` - Batch API not needed with free Ollama

See git history for OpenAI API documentation.

---

## Next Steps

After embedding, you'll use these chunks with the batch ingestion script to:
1. Insert documents into `documents` table
2. Insert chunks with embeddings into `document_chunks` table (768d vectors)
3. Create HNSW index for fast similarity search

See `docs/data_design.md` for database storage details.
