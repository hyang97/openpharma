# OpenPharma Command Cheatsheet

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

-- Chunks needing embeddings
SELECT COUNT(*) FROM document_chunks WHERE embedding IS NULL;
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

# Stage 4: Embed Chunks

## Regular API (instant results, full price)
python -m scripts.stage_4_embed_chunks --mode regular --limit 10                                 # Test with 10 documents (interactive)
docker-compose exec api python -m scripts.stage_4_embed_chunks --mode regular --limit 100        # Regular API: 100 docs
docker-compose exec api python -m scripts.stage_4_embed_chunks --budget 1.0 --limit 500          # Set budget limit ($1.00)
docker-compose exec api python -m scripts.stage_4_embed_chunks --log-level DEBUG --limit 1       # Debug mode

## Batch API (50% cheaper, 24-hour turnaround)
# Submit batches (auto-splits into 3K doc batches, marks docs as 'batch_submitted')
docker-compose exec api python -m scripts.stage_4_embed_chunks --mode submit-batch --limit 2000 --budget 0.5
docker-compose exec api python -m scripts.stage_4_embed_chunks --mode submit-batch --budget 50.0  # All chunked docs

# Check status / retrieve results (24 hours later) - not yet implemented
docker-compose exec api python -m scripts.stage_4_embed_chunks --mode get-batch --batch-id batch_abc123
docker-compose exec api python -m scripts.stage_4_embed_chunks --mode get-batch --batch-file data/stage_4_batches/batch_metadata_20251012_010000.jsonl
```
