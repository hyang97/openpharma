# Migration: OpenAI → Ollama Embeddings

**Date**: 2025-10-12
**Status**: Planned

## Executive Summary

Migrating from OpenAI text-embedding-3-small to self-hosted Ollama nomic-embed-text for 11x faster query embeddings and zero per-query costs.

## Performance Comparison

| Metric | OpenAI (Current) | Ollama (Target) | Improvement |
|--------|------------------|-----------------|-------------|
| Query embedding latency | 402ms | 36ms | **11x faster** |
| DB retrieval latency | 809ms (with JOIN) | 24ms (optimized) | **33x faster** |
| End-to-end RAG latency | ~1,211ms | ~60ms | **20x faster** |
| Cost per query | $0.00001 | $0 | **Free forever** |
| Embedding dimensions | 1536 | 768 | 50% smaller |
| Works offline | ✗ | ✓ | Internet not required |
| Semantic quality | Good | Good (better in tests) | Equal or better |

**Key Finding**: Ollama query embeddings are 11x faster (36ms vs 402ms) and semantic quality tests show equal or better clustering.

## Migration Cost-Benefit

**Costs:**
- Lose $2 of OpenAI embeddings (203K chunks already embedded)
- ~1 hour of developer time for code changes
- ~18 hours of compute time for re-embedding (automated, run overnight)

**Benefits:**
- 20x faster end-to-end RAG queries (60ms total)
- $0 per query forever (vs $0.00001/query)
- Works offline (no internet dependency)
- Better semantic clustering in tests

**ROI**: Break-even at ~200K queries ($2 / $0.00001). For a demo/MVP, the speed improvement alone justifies the migration.

## Technical Changes

### Schema Changes

**Before:**
```python
# app/db/models.py:164
embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small
```

**After:**
```python
# app/db/models.py:164
embedding = Column(Vector(768))   # Ollama nomic-embed-text
```

### Embedding Service Changes

**Before (OpenAI):**
```python
# app/ingestion/embeddings.py
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=texts
)
embeddings = [item.embedding for item in response.data]
```

**After (Ollama):**
```python
# app/ingestion/embeddings.py
import requests

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

response = requests.post(
    f"{OLLAMA_URL}/api/embeddings",
    json={"model": "nomic-embed-text", "prompt": text}
)
embedding = response.json()["embedding"]
```

### Query Optimization Applied

In addition to switching embedding models, we optimized database queries:

**Before:**
```sql
-- Slow: JOIN forces table scan (809ms)
SELECT dc.*, d.title
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.document_id
WHERE dc.embedding IS NOT NULL
ORDER BY dc.embedding <=> query_vector
LIMIT 10
```

**After:**
```sql
-- Fast: Separate queries, forced index (24ms)
SET enable_seqscan = off;
SET hnsw.ef_search = 40;

-- Step 1: Get chunks (20ms)
SELECT document_chunk_id, document_id, section, content, similarity
FROM document_chunks
WHERE embedding IS NOT NULL
ORDER BY embedding <=> query_vector
LIMIT 10;

-- Step 2: Batch-fetch titles (<1ms)
SELECT document_id, title
FROM documents
WHERE document_id IN (doc_ids_from_step_1);
```

## Migration Steps

### Phase 1: Prepare Schema (5 minutes)

1. **Backup current data** (optional but recommended)
   ```bash
   docker-compose exec -T postgres pg_dump -U admin -d openpharma -t documents > backups/backup_documents_$(date +%Y%m%d).sql
   ```

2. **Update schema**
   - Edit `app/db/models.py` line 164
   - Change: `Vector(1536)` → `Vector(768)`

3. **Drop and recreate tables**
   ```bash
   # Inside api container
   docker-compose exec api python -c "from app.db.database import engine; from sqlalchemy import text; conn = engine.connect(); conn.execute(text('DROP TABLE IF EXISTS document_chunks CASCADE')); conn.commit()"

   docker-compose exec api python -m app.db.init_db
   ```

### Phase 2: Update Code (30 minutes)

4. **Update `app/ingestion/embeddings.py`**
   - Replace OpenAI client with Ollama API calls
   - Update `EmbeddingService.embed_chunks()` method
   - Remove batch API support (Ollama doesn't have it)
   - Test: Generate one embedding to verify it works

5. **Update `scripts/stage_4_embed_chunks.py`**
   - Use new Ollama embedding service
   - Remove `--mode submit-batch` option
   - Update cost calculations (now $0)
   - Update progress estimates (36ms per chunk)

6. **Update `tests/validate_embeddings.py`**
   - Change `get_query_embedding()` to use Ollama
   - Remove OpenAI import, add requests
   - Keep query optimizations (no JOIN, force index)

### Phase 3: Re-process Data (18 hours automated)

7. **Re-chunk all documents** (~30 minutes)
   ```bash
   docker-compose exec api python -m scripts.stage_3_chunk_papers
   ```
   - Creates 1.89M chunks with NULL embeddings
   - Uses new 768-dimensional schema

8. **Re-embed all chunks** (~18 hours)
   ```bash
   # Run in background
   docker-compose run --rm -d --name api-embed api bash -c "python -m scripts.stage_4_embed_chunks"

   # Monitor progress
   docker exec api-embed tail -f logs/stage_4_embed_chunks.log
   ```
   - Estimated time: 1.89M chunks × 36ms = ~18 hours
   - Run overnight
   - HNSW index builds automatically

### Phase 4: Validate (15 minutes)

9. **Test embeddings**
   ```bash
   docker-compose exec api python -m tests.validate_embeddings
   ```
   - Check semantic quality
   - Verify query performance (~60ms end-to-end)
   - Confirm HNSW index is being used

10. **Verify metrics**
    - ✓ All chunks embedded (embedding IS NOT NULL)
    - ✓ Query time <100ms
    - ✓ Semantic similarity scores >0.6 for relevant results
    - ✓ Topic coverage maintained

## Rollback Plan

If migration fails or quality is poor:

1. **Restore from backup**
   ```bash
   docker-compose exec -T postgres psql -U admin -d openpharma < backups/backup_documents_20251012.sql
   ```

2. **Revert code changes**
   - Git revert embedding service changes
   - Change schema back to Vector(1536)

3. **Re-initialize with OpenAI**
   - Re-chunk with 1536d schema
   - Re-embed with OpenAI (costs ~$14 for all docs)

**Recovery time**: ~1 hour + 8 hours re-embedding

## Infrastructure Requirements

### Ollama Setup

**Current state**: Ollama running natively on Mac
- Host: `http://localhost:11434`
- Model: `nomic-embed-text` (already pulled)
- LLM: `llama3.1:8b` (for chat)

**Docker access**: API container connects via `host.docker.internal:11434`

**Environment variables:**
```bash
# .env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### Resource Requirements

**Disk space:**
- Ollama model: ~274MB (nomic-embed-text)
- Database: ~5GB (1.89M chunks × 768d)
- Backup: ~3GB (documents table)
- Total: ~8GB

**Memory:**
- Ollama: ~500MB RAM during embedding
- Postgres: ~2GB RAM (HNSW index)
- API container: ~500MB RAM

**Compute time:**
- Re-chunking: ~30 minutes
- Re-embedding: ~18 hours (can run overnight)

## Success Criteria

Migration is successful when:

1. ✓ All 1.89M chunks embedded with 768d vectors
2. ✓ HNSW index built and performing well
3. ✓ Query latency <100ms end-to-end
4. ✓ Semantic quality tests pass (similarity >0.6 for relevant results)
5. ✓ Topic coverage maintained (validated with test queries)
6. ✓ No OpenAI API calls in production code

## Monitoring Post-Migration

Track these metrics after migration:

- Query latency (target: <100ms)
- Embedding generation time (target: <50ms)
- Semantic quality scores (target: >0.6 for relevant results)
- HNSW index performance (should use index, not seq scan)
- Memory usage (Postgres + Ollama)

## Timeline

| Phase | Duration | Can Run Overnight? |
|-------|----------|-------------------|
| Backup + schema update | 5 min | No |
| Code changes | 30 min | No |
| Re-chunking | 30 min | Yes |
| Re-embedding | 18 hours | **Yes** |
| Testing + validation | 15 min | No |
| **Total active time** | **~1 hour** | |
| **Total elapsed time** | **~19 hours** | |

**Recommended schedule:**
- Day 1 evening: Backup, schema update, code changes, start re-chunking
- Day 1 night: Re-chunking completes, start re-embedding
- Day 2 morning: Re-embedding completes, validate results

## References

- Performance comparison: `tests/compare_openai_vs_ollama.py`
- Index optimization: `tests/test_rag_optimizations.py`
- Validation script: `tests/validate_embeddings.py`
- Ollama API docs: https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings
- nomic-embed-text: https://huggingface.co/nomic-ai/nomic-embed-text-v1
