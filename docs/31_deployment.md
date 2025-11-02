# Deployment Guide

## Deployment Configurations

### Local Development (Default)
- **Stack**: Docker (Postgres + API), host Ollama, UI dev server
- **Commands**: `docker-compose up -d`, `cd ui && npm run dev`
- **Cost**: $0

### Phase 1 Demo (Current)
- **Stack**: Local backend + Ollama, Cloudflare Tunnel, Vercel UI
- **Cost**: $0/month
- **Performance**: 30-50s responses, ~300ms tunnel latency
- **Limitation**: Laptop must stay on

**Setup**:
```bash
# Install Cloudflare Tunnel
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create openpharma

# Configure tunnel (~/.cloudflared/config.yml)
tunnel: <tunnel-id>
credentials-file: /Users/<username>/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: openpharma-api.your-domain.com
    service: http://localhost:8000
  - service: http_status:404

# Start services
docker-compose up -d
cloudflared tunnel run openpharma

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
USE_LOCAL_LLM=true
OLLAMA_BASE_URL=http://localhost:11434
```

**Phase 2 Cloud**:
```bash
DATABASE_URL=postgresql://user:pass@<cloud-sql-ip>:5432/openpharma
USE_LOCAL_LLM=false
OPENAI_API_KEY=<your-key>
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
