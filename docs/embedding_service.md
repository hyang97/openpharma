# Embedding Service Guide

The `EmbeddingService` class in `app/ingestion/embeddings.py` provides two ways to generate embeddings: **Regular API** (instant, standard pricing) and **Batch API** (slower, 50% cheaper).

## Quick Reference

### Regular API (Instant)
```python
from app.ingestion.embeddings import EmbeddingService

embedder = EmbeddingService()

# Embed chunks immediately
chunks_with_embeddings, _ = embedder.embed_chunks(
    chunks,
    use_batch=False
)
```

**When to use:**
- Testing and development
- Small datasets (<100 chunks)
- Need immediate results

**Cost:** Standard OpenAI pricing

---

### Batch API - Wait (Async, Cheaper)
```python
embedder = EmbeddingService()

# Submit and wait for completion (blocking)
chunks_with_embeddings, batch_id = embedder.embed_chunks(
    chunks,
    use_batch=True,
    wait=True
)
```

**When to use:**
- Medium datasets (100-1000 chunks)
- Can wait a few hours
- Want 50% cost savings

**Cost:** 50% off regular pricing
**Time:** Usually completes within hours

---

### Batch API - Submit and Check Later (Most Flexible)
```python
embedder = EmbeddingService()

# Submit batch (returns immediately)
_, batch_id = embedder.embed_chunks(
    chunks,
    use_batch=True,
    wait=False
)
print(f"Batch submitted: {batch_id}")

# Later... check status
status = embedder.get_batch_status(batch_id)
print(f"{status['completed_requests']}/{status['total_requests']} complete")

# When done, download and parse results
if status['status'] == 'completed':
    results_file = embedder.download_batch_results(batch_id)
    chunks_with_embeddings = embedder.parse_batch_results(results_file, chunks)
```

**When to use:**
- Large datasets (1000+ chunks)
- Run overnight/over weekend
- Maximum cost savings
- Don't want to keep script running

**Cost:** 50% off regular pricing
**Time:** Up to 24 hours

---

## How the Embedding Service Works

### Input Requirements

Chunks must have an `embedding_text` field:

```python
chunk = {
    "content": "We studied 100 patients...",
    "section": "methods",
    "embedding_text": "Document: Diabetes Study\nSection: methods\n\nWe studied 100 patients..."
}
```

The `embedding_text` is what gets sent to OpenAI (includes document title + section for better context).

### Output

After embedding, chunks will have an `embedding` field:

```python
chunk = {
    "content": "We studied 100 patients...",
    "section": "methods",
    "embedding_text": "Document: Diabetes Study\nSection: methods\n\nWe studied 100 patients...",
    "embedding": [0.123, -0.456, 0.789, ...]  # 1536 floats
}
```

---

## Regular API Details

### Methods

**`embed_text(text: str) -> List[float]`**
- Embed a single text string
- Returns 1536-dimensional embedding

**`embed_batch_sync(texts: List[str], batch_size: int = 100) -> List[List[float]]`**
- Embed multiple texts in batches
- Automatically handles rate limiting
- Returns embeddings in same order as inputs

### How it works

1. Groups texts into batches of 100 (configurable)
2. Calls OpenAI API for each batch
3. Waits 0.1s between batches to avoid rate limits
4. Returns all embeddings in order

---

## Batch API Details

### Workflow

```
1. Create JSONL file → 2. Upload to OpenAI → 3. Submit batch job
                                                        ↓
                                                   4. Poll status
                                                        ↓
                                                   5. Download results
                                                        ↓
                                                   6. Parse and match to chunks
```

### Methods

**`create_batch_file(chunks, output_path) -> str`**
- Creates JSONL file with embedding requests
- Each chunk gets a unique `custom_id` (e.g., "chunk_0", "chunk_1")
- Returns path to created file

**`submit_batch(batch_file_path) -> str`**
- Uploads file to OpenAI
- Creates batch job
- Returns batch_id for tracking

**`get_batch_status(batch_id) -> Dict`**
- Check current status
- Returns: `{status, total_requests, completed_requests, failed_requests}`
- Status values: "validating", "in_progress", "finalizing", "completed", "failed"

**`wait_for_batch(batch_id, poll_interval=60) -> Dict`**
- Polls status every 60 seconds
- Blocks until complete
- Returns final status

**`download_batch_results(batch_id, output_path) -> str`**
- Downloads results JSONL file
- Returns path to file

**`parse_batch_results(results_file_path, chunks) -> List[Dict]`**
- Matches embeddings back to original chunks using `custom_id`
- Adds `embedding` field to each chunk
- Returns updated chunks

### Files Created

Batch API creates these files (in `data/batches/`, gitignored):

```
data/batches/
├── embed_1696789012.jsonl          # Input requests
└── embed_1696789012_results.jsonl  # Output embeddings
```

---

## Error Handling

### Regular API

```python
try:
    chunks_with_embeddings, _ = embedder.embed_chunks(chunks, use_batch=False)
except Exception as e:
    logger.error(f"Embedding failed: {e}")
    # Handle error
```

Common errors:
- `ValueError`: Missing `embedding_text` field
- API errors: Rate limits, authentication, network issues

### Batch API

```python
try:
    chunks, batch_id = embedder.embed_chunks(chunks, use_batch=True, wait=True)
except TimeoutError:
    # Batch didn't complete within 24 hours
    logger.error("Batch timed out")
except RuntimeError as e:
    # Batch failed or was cancelled
    logger.error(f"Batch error: {e}")
```

**Recovering from batch failures:**

If batch fails partway through:
1. Check status: `embedder.get_batch_status(batch_id)`
2. If some succeeded, download partial results
3. Identify failed chunks from results
4. Re-submit only failed chunks

---

## Cost Comparison

**Example: 10,000 chunks**

| Method | Cost | Time |
|--------|------|------|
| Regular API | ~$2.00 | ~30 minutes |
| Batch API | ~$1.00 | 2-24 hours |

**Savings:** 50% with Batch API

---

## Best Practices

### Use Regular API when:
- Developing/testing
- <100 chunks
- Need results immediately
- Interactive workflow

### Use Batch API when:
- Production ingestion
- 100+ chunks
- Can wait hours
- Want cost savings
- Running scheduled jobs

### Tips:
1. **Always validate chunks have `embedding_text` before calling**
2. **Save batch_id** - you'll need it to retrieve results
3. **Don't delete batch files** - may need them for debugging
4. **Use wait=False for large batches** - don't keep script running
5. **Log batch_id** - easy to lose track of running batches

---

## Logging

The service logs extensively:

```
INFO - Initialized EmbeddingService with model: text-embedding-3-small
INFO - Embedding 150 texts in 2 batches (batch_size=100)
INFO - Completed batch 1/2
INFO - Completed batch 2/2
INFO - Successfully generated 150 embeddings
```

Set `LOG_LEVEL=DEBUG` for more detail:

```
DEBUG - Processing batch 1/2 (100 texts)
DEBUG - Generated embedding for text (length: 512 chars)
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

# Embed chunks (choose one method)

# Option 1: Regular API (instant)
embedder = EmbeddingService()
chunks_with_embeddings, _ = embedder.embed_chunks(all_chunks, use_batch=False)

# Option 2: Batch API (wait)
# chunks_with_embeddings, batch_id = embedder.embed_chunks(all_chunks, use_batch=True, wait=True)

# Option 3: Batch API (submit and check later)
# _, batch_id = embedder.embed_chunks(all_chunks, use_batch=True, wait=False)
# # Come back later...
# status = embedder.get_batch_status(batch_id)
# if status['status'] == 'completed':
#     results_file = embedder.download_batch_results(batch_id)
#     chunks_with_embeddings = embedder.parse_batch_results(results_file, all_chunks)

# Now chunks have embeddings - ready to store in database!
```

---

## Next Steps

After embedding, you'll use these chunks with the batch ingestion script to:
1. Insert documents into `documents` table
2. Insert chunks with embeddings into `document_chunks` table
3. Create HNSW index for fast similarity search

See `docs/data_design.md` for database storage details.
