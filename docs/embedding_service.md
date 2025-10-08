# Embedding Service Guide

The `EmbeddingService` class in `app/ingestion/embeddings.py` provides two ways to generate embeddings: **Regular API** (synchronous, instant) and **Batch API** (asynchronous, 50% cheaper).

## Quick Reference

### Regular API (Synchronous, Instant)
```python
from app.ingestion.embeddings import EmbeddingService

embedder = EmbeddingService()

# Extract embedding texts from chunks
texts = [chunk["embedding_text"] for chunk in chunks]

# Embed texts (returns list of embeddings, None for failed)
embeddings = embedder.embed_chunks(texts)

# Add embeddings back to chunks
for chunk, embedding in zip(chunks, embeddings):
    chunk["embedding"] = embedding

# Check for failures
failed_indices = [i for i, emb in enumerate(embeddings) if emb is None]
if failed_indices:
    print(f"Warning: {len(failed_indices)} chunks failed to embed")
```

**When to use:**
- Development and testing
- Small datasets (<500 chunks)
- Need immediate results
- Interactive workflows

**Cost:** Standard OpenAI pricing (~$0.02/1M tokens)
**Time:** Instant (few seconds to minutes)

**Error handling:** Failed embeddings are `None`, continue processing other chunks

---

### Batch API (Asynchronous, Cheaper)
```python
embedder = EmbeddingService()

# Step 1: Create and submit batch file
batch_file = embedder.create_batch_file(chunks, "data/batches/embed_123.jsonl")
batch_id = embedder.submit_batch(batch_file)
print(f"Batch submitted: {batch_id}")

# Step 2: Check status later (manual or in a separate job)
status = embedder.get_batch_status(batch_id)
print(f"Status: {status['status']}")
print(f"Progress: {status['completed_requests']}/{status['total_requests']}")

# Step 3: Download and parse results when completed
if status['status'] == 'completed':
    chunks_with_embeddings = embedder.complete_batch(batch_id, chunks)
    # Check for any failed chunks in the batch results
    failed = [i for i, c in enumerate(chunks_with_embeddings) if c.get('embedding') is None]
    if failed:
        print(f"Warning: {len(failed)} chunks in batch had errors")
```

**When to use:**
- Production ingestion
- Large datasets (500+ chunks)
- Scheduled/automated jobs
- Cost optimization is important
- Can wait hours/overnight

**Cost:** 50% off regular pricing (~$0.01/1M tokens)
**Time:** 2-24 hours (typically completes in a few hours)

**Note:** Batch API requires chunks to have `source`, `source_id`, `chunk_index` fields for generating composite key IDs

---

## How the Embedding Service Works

### Input Requirements

**All chunks** must have an `embedding_text` field:

```python
chunk = {
    "content": "We studied 100 patients...",
    "section": "methods",
    "embedding_text": "Document: Diabetes Study\nSection: methods\n\nWe studied 100 patients...",
    "chunk_index": 0
}
```

**Batch API** additionally requires these fields for generating deterministic IDs:

```python
chunk = {
    "content": "We studied 100 patients...",
    "section": "methods",
    "embedding_text": "Document: Diabetes Study\nSection: methods\n\nWe studied 100 patients...",
    "source": "pubmed",           # Data source (e.g., "pubmed", "clinicaltrials")
    "source_id": "PMC8234567",    # Source's unique ID for the document
    "chunk_index": 0              # Sequential chunk number within document
}
```

The `embedding_text` is what gets sent to OpenAI (includes document title + section for better context).

The composite key (`source_sourceid_chunkindex`) is used as the `custom_id` in batch requests, enabling idempotent operations and easier result matching.

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

### Method

**`embed_chunks(texts: List[str], batch_size: int = 100) -> List[List[float]]`**
- Embed multiple texts using the regular (synchronous) OpenAI API
- Processes texts in batches of 100 to the API for efficiency and error isolation
- Automatically handles rate limiting
- Returns embeddings in same order as inputs (None for failed texts)

### How it works

1. Groups texts into batches of 100 (configurable)
2. Calls OpenAI API for each batch of 100 texts
3. If a batch fails, logs error and sets those embeddings to None, continues processing
4. Waits 0.1s between batches to avoid rate limits
5. Returns all embeddings in order (with None for any failures)

---

## Batch API Details

### Workflow

```
1. Create & submit     →  2. Wait (hours)  →  3. Complete batch
   create_batch_file()    get_batch_status()  complete_batch()
   submit_batch()         (check progress)    (download & parse)
   (returns batch_id)
```

### Primary Methods

**`create_batch_file(chunks: List[Dict], output_path: str) -> str`**
- Creates JSONL batch file for OpenAI Batch API
- Uses composite key `{source}_{source_id}_{chunk_index}` as custom_id
- Requires chunks to have: `embedding_text`, `source`, `source_id`, `chunk_index`
- Returns path to created JSONL file

**`submit_batch(batch_file_path: str) -> str`**
- Uploads JSONL file to OpenAI and creates batch job
- Returns batch_id for tracking

**`get_batch_status(batch_id: str) -> Dict`**
- Check current status of a submitted batch
- Returns: `{status, total_requests, completed_requests, failed_requests}`
- Status values: "validating", "in_progress", "finalizing", "completed", "failed"

**`complete_batch(batch_id: str, chunks: List[Dict]) -> List[Dict]`**
- Convenience method: downloads results and adds embeddings to chunks in one call
- Validates batch is completed before downloading
- Returns chunks with `embedding` field added (None for failed chunks)

### Advanced Methods

Most users only need the four methods above. These provide lower-level control if needed:

**`download_batch_results(batch_id: str, output_path: str = None) -> str`**
- Downloads results JSONL file from completed batch
- Usually just use `complete_batch()` instead

**`parse_batch_results(results_file_path: str, chunks: List[Dict]) -> List[Dict]`**
- Matches embeddings back to chunks using composite key custom_id
- Requires chunks to have 'source', 'source_id', 'chunk_index' fields
- Usually just use `complete_batch()` instead

### Files Created

Batch API creates these files (in `data/batches/`, gitignored):

```
data/batches/
├── embed_1696789012.jsonl          # Input requests with custom_id = source_sourceid_chunkindex
└── embed_1696789012_results.jsonl  # Output embeddings matched by custom_id
```

**Example batch file entry:**
```json
{
  "custom_id": "pubmed_PMC8234567_0",
  "method": "POST",
  "url": "/v1/embeddings",
  "body": {
    "model": "text-embedding-3-small",
    "input": "Document: Diabetes Study\nSection: abstract\n\nWe investigated..."
  }
}
```

---

## Error Handling

### Regular API

The regular API continues processing even if some batches fail. Failed embeddings are set to `None`:

```python
texts = [chunk["embedding_text"] for chunk in chunks]
embeddings = embedder.embed_chunks(texts)

# Add embeddings to chunks
for chunk, emb in zip(chunks, embeddings):
    chunk["embedding"] = emb

# Find failures
failed_indices = [i for i, emb in enumerate(embeddings) if emb is None]

if failed_indices:
    print(f"{len(failed_indices)} chunks failed")

    # Option 1: Retry failed chunks
    failed_texts = [texts[i] for i in failed_indices]
    retry_embeddings = embedder.embed_chunks(failed_texts)

    # Merge successful retries back
    for fail_idx, retry_emb in zip(failed_indices, retry_embeddings):
        if retry_emb is not None:
            chunks[fail_idx]["embedding"] = retry_emb

    # Option 2: Filter out failed chunks and proceed
    successful_chunks = [c for c in chunks if c.get('embedding') is not None]
```

Common errors:
- API errors: Rate limits, network issues, authentication → embeddings set to None, processing continues

### Batch API

```python
# Submit batch
batch_file = embedder.create_batch_file(chunks, "data/batches/embed_123.jsonl")
batch_id = embedder.submit_batch(batch_file)

# Later, check and complete
try:
    chunks_with_embeddings = embedder.complete_batch(batch_id, chunks)

    # Check for failures in results
    failed = [i for i, c in enumerate(chunks_with_embeddings) if c.get('embedding') is None]
    if failed:
        print(f"{len(failed)} chunks failed in batch")

except ValueError as e:
    # Batch not completed yet
    logger.warning(f"Batch not ready: {e}")
    # Check again later

except RuntimeError as e:
    # Batch failed or was cancelled
    logger.error(f"Batch error: {e}")
```

**Recovering from batch failures:**

If batch fails:
1. Check status: `embedder.get_batch_status(batch_id)`
2. If status is "failed", check `status_info.get('errors')`
3. Re-submit as new batch using `create_batch_file()` and `submit_batch()`

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
- <500 chunks
- Need results immediately
- Interactive workflow

### Use Batch API when:
- Production ingestion
- 500+ chunks
- Can wait hours/overnight
- Want 50% cost savings
- Running scheduled jobs

### Tips:
1. **Always validate chunks have `embedding_text` before calling**
2. **Save batch_id** - you'll need it to retrieve results later
3. **Don't delete batch files** - may need them for debugging
4. **Use `complete_batch()`** - it's easier than manually downloading and parsing
5. **Check status before completing** - avoid errors by checking batch is "completed" first

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

# Option 1: Regular API (instant, default)
embedder = EmbeddingService()

texts = [chunk["embedding_text"] for chunk in all_chunks]
embeddings = embedder.embed_chunks(texts)

for chunk, emb in zip(all_chunks, embeddings):
    chunk["embedding"] = emb

# Retry failed chunks if any
failed_indices = [i for i, emb in enumerate(embeddings) if emb is None]
if failed_indices:
    print(f"Retrying {len(failed_indices)} failed chunks...")
    failed_texts = [texts[i] for i in failed_indices]
    retry_embeddings = embedder.embed_chunks(failed_texts)

    for fail_idx, retry_emb in zip(failed_indices, retry_embeddings):
        if retry_emb is not None:
            all_chunks[fail_idx]["embedding"] = retry_emb

# Option 2: Batch API (async, cheaper)
# batch_file = embedder.create_batch_file(all_chunks, "data/batches/embed_123.jsonl")
# batch_id = embedder.submit_batch(batch_file)
# print(f"Submitted batch: {batch_id}")
# # Come back later (hours/overnight)...
# status = embedder.get_batch_status(batch_id)
# if status['status'] == 'completed':
#     chunks_with_embeddings = embedder.complete_batch(batch_id, all_chunks)

# Now chunks have embeddings - ready to store in database!
```

---

## Next Steps

After embedding, you'll use these chunks with the batch ingestion script to:
1. Insert documents into `documents` table
2. Insert chunks with embeddings into `document_chunks` table
3. Create HNSW index for fast similarity search

See `docs/data_design.md` for database storage details.
