# Configuration and Deployment

This document covers configuration details and deployment setup for OpenPharma.

## Docker Volume Mounts

**Problem**: Mounting the entire project directory (`.:/app`) caused "too many open files" errors due to `ui/node_modules/` (18K files) and `venv/` (23K files) being scanned by the container's file watcher.

**Solution**: Mount only backend directories needed at runtime (268 files vs 43K files, 99.4% reduction).

**Current Configuration** (`docker-compose.yml`):
```yaml
volumes:
  # Mount only backend code (exclude ui/, venv/, node_modules/)
  - ./app:/app/app
  - ./scripts:/app/scripts
  - ./tests:/app/tests
  - ./logs:/app/logs
  - ./data:/app/data
  - ./backups:/app/backups
  - ./archive:/app/archive
  - ./.env:/app/.env
```

**What's Excluded**:
- `ui/` - Frontend code (runs separately via `npm run dev`)
- `venv/` - Local Python virtualenv (container has its own)
- `docs/` - Documentation (not needed at runtime)
- Root-level markdown files (CLAUDE.md, TODO.md, README.md, etc.)

**Note**: `.dockerignore` only affects Docker build, not runtime volume mounts. Selective mounting is required to exclude directories at runtime.

## Environment Variables

See `.env.example` for all available configuration options.

**Critical Variables**:
- `DATABASE_URL` - Postgres connection string
- `USE_LOCAL_LLM` - Toggle between Ollama (true) and OpenAI (false)
- `OLLAMA_BASE_URL` - Ollama API endpoint (default: http://host.docker.internal:11434)
- `RERANKER_MODEL` - Cross-encoder model for reranking (default: cross-encoder/ms-marco-MiniLM-L-6-v2)

## Deployment Architectures

### Local Development (Current)
- **Database**: Postgres + pgvector in Docker
- **API**: FastAPI in Docker, exposed on localhost:8000
- **LLM**: Ollama on host machine (accessed via host.docker.internal)
- **UI**: Next.js dev server (npm run dev) on localhost:3000

### Phase 1 Demo (Implemented)
- **Database**: Postgres + pgvector running locally
- **API**: FastAPI on laptop, exposed via Cloudflare Tunnel
- **LLM**: Ollama Llama 3.1 8B running locally
- **UI**: Next.js deployed to Vercel free tier
- **Cost**: $0/month
- **Tradeoffs**: Laptop must stay on, 30-50s responses, ~300ms added latency

See `docs/00_cheatsheet.md` deployment section for Cloudflare Tunnel setup commands.
