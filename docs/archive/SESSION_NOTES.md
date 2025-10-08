# Session Notes - 2025-10-07

## What We Built Today

### 1. Complete Data Ingestion Pipeline (Fetcher → Parser → Chunker → Embeddings)

**Files Created:**
- `app/ingestion/pubmed_fetcher.py` - Fetch papers from PubMed Central
- `app/ingestion/xml_parser.py` - Parse JATS XML, extract sections
- `app/ingestion/chunker.py` - Token-based section-aware chunking
- `app/ingestion/embeddings.py` - OpenAI embeddings (regular + batch API)
- `app/logging_config.py` - Centralized logging system

**Key Design Decisions:**
1. **Diabetes research focus** (changed from cancer)
2. **Section storage strategy**: Store complete `full_text` with character offsets in metadata
3. **Title + Abstract in full_text**: Everything in one column for consistency
4. **Section-aware chunking**: Each section chunked separately (title NOT chunked)
5. **Field naming**: `embedding_text` instead of `context` for clarity
6. **Dual embedding APIs**: Regular (instant) + Batch (50% cheaper, slower)
7. **Logging strategy**: Static filename for API, timestamps for batch scripts

### 2. Documentation

**Created:**
- `README.md` - Simple project overview
- `docs/data_design.md` - Complete pipeline documentation
- `docs/logging.md` - Logging guide
- `docs/embedding_service.md` - Embedding service reference
- `examples/logging_demo.py` - Working logging examples

**Updated:**
- `CLAUDE.md` - Project context for AI assistant
- `.gitignore` - Added logs/ and data/batches/
- `.env.example` - Added LOG_LEVEL

### 3. Database Schema

**Key Points:**
- `documents.full_text` contains: TITLE + ABSTRACT + BODY SECTIONS (all with headers)
- `documents.doc_metadata['section_offsets']` tracks character positions
- `document_chunks.content` stores raw chunk text
- `document_chunks.section` identifies source section
- `document_chunks.char_start/char_end` point into parent's full_text
- Embeddings generated from `embedding_text` field (not stored in DB)

## Next Session TODO

### Immediate Next Steps

1. **Review embedding service** (`app/ingestion/embeddings.py`)
   - Understand regular API vs batch API
   - Read through each method
   - Understand the workflow diagrams in `docs/embedding_service.md`

2. **Build batch ingestion script**
   - Create `scripts/ingest_papers.py`
   - Wire together: fetcher → parser → chunker → embedder → database
   - Handle errors gracefully
   - Add progress logging

3. **Test with sample papers**
   - Ingest 5-10 diabetes papers
   - Verify data in database (use Beekeeper Studio)
   - Check embeddings are generated correctly
   - Validate section offsets work

### Questions to Consider

- **Batch size**: How many papers to ingest at once?
- **Error handling**: What if a paper fails to parse?
- **Deduplication**: How to handle papers we've already ingested?
- **Progress tracking**: How to resume if script crashes?

### Files to Read Before Next Session

1. `app/ingestion/embeddings.py` - Main file to understand
2. `docs/embedding_service.md` - Your guide to the embedding service
3. `docs/data_design.md` - Review section storage strategy

## Key Concepts Learned

### Logging in Python
- `logging.getLogger(__name__)` creates module-specific loggers
- Levels: DEBUG < INFO < WARNING < ERROR < CRITICAL
- Configure once at app startup, use everywhere
- Log to console + file for persistence

### OpenAI Batch API
- 50% cheaper than regular API
- Up to 24-hour turnaround
- Submit JSONL file → Poll status → Download results
- Perfect for bulk ingestion, not real-time

### Section-Aware Chunking
- Chunk each section separately (introduction, methods, results, etc.)
- Preserves semantic boundaries
- Better for retrieval (methods chunks only contain methods)
- Track section in chunk metadata for context

### tiktoken
- OpenAI's tokenizer library
- Counts tokens exactly as OpenAI does
- Essential for staying within embedding limits (8191 tokens)
- Ensures chunks are predictable size

## Important Reminders

- **Don't prepend "PMC" to IDs** - Store numeric IDs, source column tells us it's PMC
- **Title is in full_text but NOT chunked** - It's already in every chunk's embedding_text
- **embedding_text is not stored** - Rebuilt from title + section + content when needed
- **Batch files are gitignored** - They contain raw data, can be large
- **LOG_LEVEL=DEBUG for development** - See everything while learning

## Code Patterns Established

### Logging Pattern
```python
from app.logging_config import get_logger

logger = get_logger(__name__)

logger.info("Starting process...")
logger.error(f"Error occurred: {e}", exc_info=True)  # Include stack trace
```

### Error Handling Pattern
```python
try:
    result = risky_operation()
    logger.info(f"Success: {result}")
except Exception as e:
    logger.error(f"Failed: {e}", exc_info=True)
    raise  # Re-raise for caller to handle
```

### Section Offset Pattern
```python
# In full_text:
"INTRODUCTION\nText here...\n\nMETHODS\nMore text..."

# In metadata:
"section_offsets": [
    {"section": "introduction", "char_start": 13, "char_end": 500},
    {"section": "methods", "char_start": 510, "char_end": 900}
]

# Recovery:
intro_text = full_text[13:500]
```

## Tools Setup

- **Beekeeper Studio** - Database GUI (installed and connected)
- **Docker** - Running Postgres + pgvector
- **psql** - Command-line database access
- **Logging** - Configured and working

## Repository State

**Branch:** main
**Last Commit:** (check with `git log`)
**Clean status:** (check with `git status`)

All code is committed and documented. Ready to pick up tomorrow!

---

## For Tomorrow's Session

Start by:
1. Reading this file
2. Reading `docs/embedding_service.md`
3. Opening `app/ingestion/embeddings.py` in your editor
4. Ask questions about anything unclear
5. Then proceed with building the ingestion script

Good luck!
