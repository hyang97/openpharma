# OpenPharma Command Cheatsheet

## CRITICAL: Ollama Version Requirements

**MUST use Ollama 0.11.x (tested on 0.11.11)**
- DO NOT upgrade to 0.12.5 - has regression bug causing EOF errors
- Download 0.11.11: https://github.com/ollama/ollama/releases/tag/v0.3.11
- Disable auto-updates in Ollama app (Preferences → Disable "Check for updates")
- Verify version: `ollama --version` (should show 0.11.11)

**Symptom of 0.12.5 bug:**
```
{"error":"do embedding request: Post \"http://127.0.0.1:XXXXX/embedding\": EOF"}
```

**If you hit this bug:**
1. Quit Ollama app
2. Delete `/Applications/Ollama.app`
3. Download and install 0.11.11 from link above
4. `ollama pull nomic-embed-text`
5. Verify embeddings work: `curl -X POST http://localhost:11434/api/embeddings -d '{"model": "nomic-embed-text", "prompt": "test"}'`

## Container Management
```bash
docker-compose up -d              # Start containers (background)
docker-compose down               # Stop containers
docker-compose ps                 # Check container status
docker-compose logs api           # View api logs
docker-compose logs -f api        # Follow api logs (live)
docker stop <container-name>      # Stop a specific container (e.g., api-fetch)
```

## Quick Start
```bash
# Interactive shell
docker-compose exec api bash

# Run a script directly
docker-compose exec api python -m scripts.collect_pmc_ids --limit 50

# Background job in separate container (for long-running tasks)
docker-compose run --rm -d --name api-fetch api bash -c "python -m scripts.fetch_papers --limit 30000"
docker-compose exec api-fetch tail -f logs/fetch_papers.log  # Monitor
docker stop api-fetch # Kill if needed
```

## Database Operations

**Run SQL from Mac:**
```bash
# Quick query
docker-compose exec postgres psql -U admin -d openpharma -c "SELECT COUNT(*) FROM pubmed_papers;"

# Interactive SQL
docker-compose exec postgres psql -U admin -d openpharma
```

**Monitoring queries (use in psql or with -c flag):**
```sql
-- Papers by fetch status
SELECT fetch_status, COUNT(*) FROM pubmed_papers GROUP BY fetch_status;

-- Documents by ingestion status
SELECT ingestion_status, COUNT(*) FROM documents GROUP BY ingestion_status;

-- Chunks needing embeddings (Ollama)
SELECT COUNT(*) FROM document_chunks WHERE embedding IS NULL;

-- Chunks with old OpenAI embeddings (backup)
SELECT COUNT(*) FROM document_chunks WHERE openai_embedding IS NOT NULL;
```

**Backup and restore:**
```bash
# Backup documents table only (recommended before migration)
docker-compose exec -T postgres pg_dump -U admin -d openpharma -t documents > backup_documents_$(date +%Y%m%d).sql

# Restore from backup
docker-compose exec -T postgres psql -U admin -d openpharma < backup_documents_20251012.sql
```

**Reinitialize database (inside api container - drops all data):**
```bash
python -c "from app.db.database import engine; from sqlalchemy import text; conn = engine.connect(); conn.execute(text('DROP TABLE IF EXISTS document_chunks, documents, pubmed_papers CASCADE')); conn.commit(); conn.close(); print('Dropped all tables')"
python -m app.db.init_db
```

## Ingestion Pipeline

```bash
# Stage 1: Collect PMC IDs
docker-compose exec api python -m scripts.stage_1_collect_ids --limit 50

# Stage 2: Fetch Papers
python -m scripts.stage_2_fetch_papers --limit 100                                            # Interactive, run within container
docker-compose exec api python -m scripts.stage_2_fetch_papers --retry-failed                 # Retry failures, run outside of container
docker-compose exec api python -m scripts.stage_2_fetch_papers --log-level DEBUG --limit 10   # Debug mode, run outside of container

# Large background fetch (>1K papers: run weekends or 9pm-5am ET weekdays)
# Performance: ~0.6s/paper = 100 papers/min = 6K/hour
docker-compose run --rm -d --name api-fetch api bash -c "python -m scripts.stage_2_fetch_papers --limit 30000 --confirm-large-job"
docker exec api-fetch tail -f logs/stage_2_fetch_papers.log  # Monitor (use docker, not docker-compose)

# Stage 3: Chunk Documents
python -m scripts.stage_3_chunk_papers --limit 50                                  # Interactive, run within container
docker-compose exec api python -m scripts.stage_3_chunk_papers                     # Chunk all fetched documents
docker-compose exec api python -m scripts.stage_3_chunk_papers --rechunk-all       # Re-chunk everything (deletes existing chunks)
docker-compose exec api python -m scripts.stage_3_chunk_papers --log-level DEBUG   # Debug mode

# Stage 4: Embed Chunks (Ollama - free, instant, 768d)

# Test with small batch
python -m scripts.stage_4_embed_chunks --limit 10                                               # Test with 10 documents (interactive)
docker-compose exec api python -m scripts.stage_4_embed_chunks --limit 100                      # 100 docs from outside container
docker-compose exec api python -m scripts.stage_4_embed_chunks --log-level DEBUG --limit 1      # Debug mode

# Full embedding job (free, ~18 hours for 52K docs)
# Estimate: 1.89M chunks × 36ms = ~19 hours total
docker-compose run --rm -d --name api-embed api bash -c "python -m scripts.stage_4_embed_chunks"
docker exec api-embed tail -f logs/stage_4_embed_chunks.log  # Monitor (use docker, not docker-compose)

# Reset documents to re-run embeddings (keeps chunks, clears embedding column)
docker-compose exec postgres psql -U admin -d openpharma -c "UPDATE documents SET ingestion_status = 'chunked' WHERE ingestion_status = 'embedded';"

# DEPRECATED: OpenAI Batch API (no longer supported with Ollama)
# docker-compose exec api python -m scripts.stage_4_embed_chunks --mode submit-batch
# docker-compose exec api python -m scripts.stage_4_embed_chunks --mode get-batch --batch-id batch_abc123
```
