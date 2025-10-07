# Logging Guide

OpenPharma uses Python's built-in `logging` module for consistent logging across all components.

## Quick Start

### In your code

```python
from app.logging_config import get_logger

logger = get_logger(__name__)

# Use it
logger.info("Processing document...")
logger.error(f"Failed to process: {error}")
```

### Running the app

```bash
# Set log level via environment variable
export LOG_LEVEL=DEBUG  # or INFO, WARNING, ERROR, CRITICAL

# Run the API
python -m uvicorn app.main:app --reload
```

## Log Levels

Use different levels for different types of messages:

| Level | When to Use | Example |
|-------|-------------|---------|
| **DEBUG** | Detailed diagnostic info | `logger.debug(f"Token count: {len(tokens)}")` |
| **INFO** | General informational messages | `logger.info("Chunking document...")` |
| **WARNING** | Something unexpected but not an error | `logger.warning("No abstract found")` |
| **ERROR** | An error occurred | `logger.error(f"Failed to parse XML: {e}")` |
| **CRITICAL** | Critical failure | `logger.critical("Database connection lost!")` |

## Log Output

Logs go to two places:
1. **Console** (stdout) - See logs while running
2. **File** (`logs/openpharma.log`) - Persistent log file

### Console output format:
```
2025-10-07 14:30:15 - app.ingestion.chunker - INFO - Chunked 523 tokens into 2 chunks
│                    │                        │     │
│                    │                        │     └─ Message
│                    │                        └─ Level
│                    └─ Module name
└─ Timestamp
```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Development vs Production

**Development** - See everything:
```bash
LOG_LEVEL=DEBUG
```

**Production** - Only important stuff:
```bash
LOG_LEVEL=WARNING
```

## Best Practices

### 1. Use appropriate levels

```python
# ✅ Good
logger.info(f"Processing {len(papers)} papers")
logger.warning(f"Paper {id} has no abstract")
logger.error(f"Failed to connect to database: {e}", exc_info=True)

# ❌ Bad
logger.info(f"Error occurred: {e}")  # Should be .error()
logger.error("Starting process")     # Should be .info()
```

### 2. Include context in messages

```python
# ✅ Good - tells you what failed and why
logger.error(f"Failed to parse PMC{pmc_id}: {e}", exc_info=True)

# ❌ Bad - not enough context
logger.error("Parse failed")
```

### 3. Use exc_info for exceptions

```python
try:
    risky_operation()
except Exception as e:
    # ✅ Good - includes full stack trace
    logger.error(f"Operation failed: {e}", exc_info=True)

    # ❌ Bad - loses stack trace
    logger.error(f"Operation failed: {e}")
```

### 4. Don't log sensitive data

```python
# ❌ Bad - logs API key
logger.info(f"Using API key: {api_key}")

# ✅ Good - redacts sensitive info
logger.info("Using API key: [REDACTED]")
```

## Examples

### Example 1: Basic logging in a function

```python
from app.logging_config import get_logger

logger = get_logger(__name__)

def fetch_papers(query: str, max_results: int = 100):
    logger.info(f"Fetching papers for query: {query} (max: {max_results})")

    try:
        papers = api.search(query, max_results)
        logger.info(f"Found {len(papers)} papers")
        return papers
    except Exception as e:
        logger.error(f"Failed to fetch papers: {e}", exc_info=True)
        raise
```

### Example 2: Progress logging

```python
def process_documents(documents):
    total = len(documents)
    logger.info(f"Processing {total} documents")

    for i, doc in enumerate(documents, 1):
        logger.debug(f"Processing document {i}/{total}: {doc.title[:50]}")
        process_document(doc)

        # Log progress every 10 documents
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{total} documents processed")

    logger.info(f"Completed processing {total} documents")
```

### Example 3: Conditional debug logging

```python
def chunk_text(text):
    tokens = tokenize(text)

    # Only shows if LOG_LEVEL=DEBUG
    logger.debug(f"Tokenized {len(text)} chars into {len(tokens)} tokens")

    chunks = create_chunks(tokens)

    # Always shows (if LOG_LEVEL is INFO or lower)
    logger.info(f"Created {len(chunks)} chunks")

    return chunks
```

## Testing Logging

Run the demo script to see logging in action:

```bash
python examples/logging_demo.py
```

This will:
- Show all log levels on console
- Create `logs/demo.log` with the same logs
- Demonstrate formatting, exceptions, and more

## Troubleshooting

### Not seeing DEBUG messages?

Check your `LOG_LEVEL`:
```bash
echo $LOG_LEVEL
```

Set it to DEBUG:
```bash
export LOG_LEVEL=DEBUG
```

### Log file not created?

The `logs/` directory is created automatically. If it fails, check file permissions.

### Third-party library logs are noisy?

We automatically set urllib3, httpx, and httpcore to WARNING level. To quiet other libraries:

```python
import logging
logging.getLogger("noisy_library").setLevel(logging.WARNING)
```

## See Also

- Python logging docs: https://docs.python.org/3/library/logging.html
- `app/logging_config.py` - Configuration code
- `examples/logging_demo.py` - Working examples
