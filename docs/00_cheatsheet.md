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

### Backend (FastAPI)
```bash
# Interactive shell
docker-compose exec api bash

# Run a script directly
docker-compose exec api python -m scripts.stage_1_collect_ids --limit 50

# Background job in separate container (for long-running tasks)
docker-compose run --rm -d --name api-fetch api bash -c "python -m scripts.stage_2_fetch_papers --limit 30000"
docker-compose exec api-fetch tail -f logs/stage_2_fetch_papers.log  # Monitor
docker stop api-fetch # Kill if needed
```

### Frontend (React)
```bash
cd ui
npm install              # Install dependencies (first time only)
npm run dev              # Start dev server at http://localhost:3000
npm run build            # Build for production
npm start                # Serve production build
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

# Stage 4: Embed Chunks (Ollama - free, 768d)

# Test with small batch
python -m scripts.stage_4_embed_chunks --limit 10                      # Interactive test
docker-compose exec api python -m scripts.stage_4_embed_chunks --limit 100 --log-level DEBUG

# Long-running embedding job (~55 hours for 1.77M chunks at 111ms/chunk)
# Option 1: Detached container (BEST - survives laptop sleep/close)
docker-compose run --rm -d --name api-embed api bash -c "python -m scripts.stage_4_embed_chunks --workers 1"
docker exec api-embed tail -f logs/stage_4_embed_chunks.log           # Monitor
docker stop api-embed                                                  # Stop if needed

# Option 2: Keep Mac awake (simpler but requires terminal open)
caffeinate -i docker-compose exec api python -m scripts.stage_4_embed_chunks --workers 1

# Check progress
docker exec api-embed grep "Remaining" logs/stage_4_embed_chunks.log
docker-compose exec postgres psql -U admin -d openpharma -c "SELECT COUNT(*) FROM documents WHERE ingestion_status='embedded';"

# Resume after interruption (idempotent - only processes status='chunked')
docker-compose run --rm -d --name api-embed api bash -c "python -m scripts.stage_4_embed_chunks --workers 1"
```

## Testing

### Reranking Evaluation
```bash
# View test questions
docker-compose exec api python -m tests.reranking_eval_questions --quick

# Run quick eval (5 questions, ~15-20 min)
docker-compose exec api python -m tests.run_reranking_eval --quick

# Run full eval (12 questions, ~30-40 min)
docker-compose exec api python -m tests.run_reranking_eval

# Results saved to: tests/reranking_eval_results_TIMESTAMP.json
# Use tests/reranking_eval_judge_prompt.md with Gemini to evaluate
```

### Other Tests
```bash
# Run tests
docker-compose exec api python -m tests.test_generation

# Test API endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_message": "What is metformin?", "use_local": true, "use_reranker": false}'
```

## Deployment (Production)

### Cloudflare Tunnel Setup

**Install cloudflared:**
```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared --version
```

**Authenticate:**
```bash
cloudflared tunnel login  # Opens browser, saves credentials to ~/.cloudflared/cert.pem
```

**Create tunnel:**
```bash
cloudflared tunnel create openpharma-api  # Creates tunnel with UUID
ls ~/.cloudflared/*.json  # Find your tunnel credentials file
```

**Configure tunnel (create ~/.cloudflared/config.yml):**
```yaml
tunnel: openpharma-api
credentials-file: /Users/YOUR_USERNAME/.cloudflared/TUNNEL_UUID.json

ingress:
  - hostname: api.byhenry.me
    service: http://localhost:8000
  - service: http_status:404
```

**Route DNS:**
```bash
cloudflared tunnel route dns openpharma-api api.byhenry.me
```

**Run tunnel:**
```bash
cloudflared tunnel run openpharma-api  # Keep terminal open, or run as service
```

**Test tunnel:**
```bash
curl https://api.byhenry.me/health  # Should return {"status":"healthy",...}
```

---

### Vercel Deployment (UI)

**Install Vercel CLI:**
```bash
npm install -g vercel
```

**Deploy:**
```bash
cd ui
vercel                    # First time: answers prompts, creates project
vercel --prod             # Deploy to production
```

**Set environment variables:**
```bash
vercel env add NEXT_PUBLIC_API_URL production  # Enter: https://api.byhenry.me
vercel env ls                                   # List environment variables
```

**Add custom domain:**
```bash
vercel domains add openpharma.byhenry.me
# Then add A record in Cloudflare DNS: openpharma → 76.76.21.21
```

**Check deployment:**
```bash
vercel ls                 # List deployments
vercel logs               # View logs
```

---

### Production Checklist

**Before sharing with users:**
- [ ] Docker services running: `docker-compose ps`
- [ ] Cloudflare tunnel running: `cloudflared tunnel run openpharma-api`
- [ ] API accessible: `curl https://api.byhenry.me/health`
- [ ] UI deployed: `https://openpharma.byhenry.me`
- [ ] CORS configured: Check `app/main.py` includes production domain
- [ ] Environment variables set in Vercel dashboard

**Keep running during demo:**
- Docker containers (postgres + api)
- Cloudflare tunnel terminal
- Keep laptop on/awake

**To stop:**
```bash
# Stop tunnel: Ctrl+C in tunnel terminal
docker-compose down       # Stop backend
# Vercel UI stays online (hosted on Vercel's servers)
```
