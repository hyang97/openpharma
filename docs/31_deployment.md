# Deployment Guide

## Deployment Configurations

### Local Development (Default)
- **Stack**: Docker (Postgres + API), host Ollama, UI dev server
- **Commands**: `docker-compose up -d`, `cd ui && npm run dev`
- **Cost**: $0

### Current Production: GCP VM
- **Host**: GCP VM `openpharma-vm` (e2-medium, us-west1, project `openpharma-497402`)
- **Stack**: Docker (Postgres+pgvector + API), native Ollama (`nomic-embed-text` for query embeddings only). Generation uses Claude via `REMOTE_LLM_ONLY=true` (the VM has no local LLM); model `claude-haiku-4-5`.
- **DB**: trimmed (excludes `icite_metadata`, no `openai_embedding` column), ~50 GB, moved via `pg_dump -Fc --compress=zstd` → GCS → restore. The 18 GB HNSW index is rebuilt on restore (needs RAM; built on a temporary larger machine, then resized back).
- **Tunnel**: CLI-managed `openpharma-gcp-tunnel`, config at `/etc/cloudflared/config.yml` on the VM (ingress `api.byhenry.me → localhost:8000`), run as a systemd service. DNS: `api` is a Tunnel record pointing at this tunnel.
- **Frontend**: Vercel, unchanged, points at `https://api.byhenry.me`.
- **Reboot resilience**: containers use `restart: unless-stopped`; `ollama` and `cloudflared` are systemd-enabled.
- **Cost**: ~$24/mo (currently on GCP trial credit).

### Phase 1 Demo (original: laptop + Cloudflare Tunnel, superseded by the GCP VM above)
- **Stack**: Local backend + Ollama, Cloudflare Tunnel, Vercel UI
- **Cost**: $0/month
- **Performance**: 30-50s responses, ~300ms tunnel latency
- **Limitation**: Laptop must stay on

**Setup**:
```bash
# Install Cloudflare Tunnel
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create byhenry-tunnel

# Configure tunnel (~/.cloudflared/config.yml)
tunnel: <tunnel-id>
credentials-file: /Users/<username>/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: openpharma-api.your-domain.com
    service: http://localhost:8000
  - service: http_status:404

# Start services
docker-compose up -d
cloudflared tunnel run byhenry-tunnel

# Deploy UI to Vercel
cd ui && vercel --prod
# Set NEXT_PUBLIC_API_URL in Vercel dashboard
```

### Phase 2: Cloud (Planned)
- **Stack**: Cloud Run, Cloud SQL, Gemini 1.5 Pro
- **Cost**: $20-50/month (GCP credits)
- **Performance**: 8-10s responses

### Phase 3: Self-Hosted ML (Future)
- **Stack**: GKE, vLLM (Llama 70B)
- **Cost**: $100-200/month (80% reduction)
- **Performance**: 5-8s responses

## Environment Variables by Deployment

**Local Development**:
```bash
DATABASE_URL=postgresql://admin:password@postgres:5432/openpharma
USE_LOCAL_LLM=true
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

**Phase 1 Demo**:
```bash
DATABASE_URL=postgresql://admin:password@localhost:5432/openpharma
USE_LOCAL_LLM=false
OLLAMA_BASE_URL=http://localhost:11434
ANTHROPIC_API_KEY=<your-key>
```

**Phase 2 Cloud**:
```bash
DATABASE_URL=postgresql://user:pass@<cloud-sql-ip>:5432/openpharma
USE_LOCAL_LLM=false
ANTHROPIC_API_KEY=<your-key>
```

## Health Checks

```bash
# API
curl http://localhost:8000/health

# Database
docker-compose exec postgres psql -U admin -d openpharma -c "SELECT COUNT(*) FROM documents;"

# Ollama
curl http://localhost:11434/api/tags
```
