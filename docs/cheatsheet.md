# OpenPharma Command Cheatsheet

## Container Management
```bash
docker-compose up -d              # Start containers (background)
docker-compose down               # Stop containers
docker-compose ps                 # Check container status
docker-compose logs api           # View api logs
docker-compose logs -f api        # Follow api logs (live)
```

## Running Scripts (from Mac or in container)
```bash
docker-compose exec api bash      # Interactive shell in api container
docker-compose exec api python -m scripts.collect_pmc_ids  # Run script directly
```

## Database Queries

**Quick count (from Mac):**
```bash
docker-compose exec postgres psql -U admin -d openpharma -c "SELECT COUNT(*) FROM pubmed_papers;"
```

**Quick count (from inside api container):**
```bash
psql -h postgres -U admin -d openpharma -c "SELECT COUNT(*) FROM pubmed_papers;"
```

**Interactive SQL (from Mac):**
```bash
docker-compose exec postgres psql -U admin -d openpharma
# Then: SELECT * FROM pubmed_papers LIMIT 10;
# Exit: \q
```

**Interactive SQL (from inside api container):**
```bash
psql -h postgres -U admin -d openpharma
# Then: SELECT * FROM pubmed_papers LIMIT 10;
# Exit: \q
```

## Database Management

**Reinitialize database (drops all data):**
```bash
# In api container - drop all tables
python -c "from app.db.database import engine; from sqlalchemy import text; conn = engine.connect(); conn.execute(text('DROP TABLE IF EXISTS document_chunks, documents, pubmed_papers CASCADE')); conn.commit(); conn.close(); print('Dropped all tables')"

# Recreate tables with correct schema
python -m app.db.init_db
```

## Common Monitoring Queries

**Check ingestion progress:**
```sql
-- Papers by fetch status
SELECT fetch_status, COUNT(*) FROM pubmed_papers GROUP BY fetch_status;

-- Documents by ingestion status
SELECT ingestion_status, COUNT(*) FROM documents GROUP BY ingestion_status;

-- Chunks needing embeddings
SELECT COUNT(*) FROM document_chunks WHERE embedding IS NULL;
```

## File Operations
```bash
ls                                # List files
cat filename                      # View file
git status                        # Check git changes
git add -A && git commit -m "msg" # Commit changes
```

## Ingestion Pipeline

**Stage 1: Collect PMC IDs**
```bash
docker-compose exec api python -m scripts.collect_pmc_ids
docker-compose exec api python -m scripts.collect_pmc_ids --limit 50
```

**Stage 2: Fetch Papers**
```bash
# Interactive 
docker-compose exec api python -m scripts.fetch_papers # fetch all pending papers (watch it run, must keep terminal open)
docker-compose exec api python -m scripts.fetch_papers --limit 100 # fetch only 100 papers (for testing)

# Retry failed papers
docker-compose exec api python -m scripts.fetch_papers --retry-failed

# Background - fetch papers overnight (run from inside container)
# Note: Large jobs (>1000) must finish within off-peak hours (weekends or 9pm-5am ET weekdays)
# Actual performance: ~0.6s per paper (~100 papers/minute)
docker-compose exec api bash
# Inside container:
nohup python -m scripts.fetch_papers --limit 25000 --confirm-large-job > fetch_papers.log 2>&1 &
# Exit container (job keeps running)
exit

# Watch background process (from Mac)
docker-compose exec api tail -f fetch_papers.log
```

**Stage 3: Chunk Documents**
```bash
docker-compose exec api python -m scripts.chunk_papers --batch-size 50
```

**Stage 4: Embed Chunks**
```bash
docker-compose exec api python -m scripts.embed_chunks --batch-size 1000
```
