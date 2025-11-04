# OpenPharma

> AI-powered research assistant for pharmaceutical literature

**[🚀 Live Demo](https://openpharma.byhenry.me)**

Ask questions about diabetes research, get AI-synthesized answers with citations from 110K+ research papers.

### Desktop
![Desktop conversation view](images/desktop-convo.png)

### Mobile
<img src="images/mobile-convo.png" alt="Mobile conversation view" width="300">

## What It Does

- "What are the latest findings on GLP-1 agonists for weight loss?"
- "Compare SGLT2 inhibitors vs traditional therapies"

Built a full-stack RAG system with semantic search, citation tracking, and multi-turn conversations.

## Stats

- **110K papers** (PubMed Central 2020-2025 + high-impact historical)
- **4.7M chunks** with semantic embeddings
- **165 GB database** (papers + citation metadata)
- **<$50 total cost** (self-hosted Ollama)

## Tech Stack

**Backend:** FastAPI • PostgreSQL + pgvector • Ollama
**Frontend:** Next.js • TypeScript • Tailwind
**Pipeline:** 4-stage ingestion (collect → fetch → chunk → embed)

## Architecture

```
User Query
    ↓
Semantic Search (pgvector) → 4.7M chunks
    ↓
Cross-Encoder Reranking → top 3 chunks
    ↓
LLM Generation (Llama 3.1 / GPT-4)
    ↓
Answer + Citations
```

## Key Decisions

- **Self-hosted Ollama:** Reduced embedding costs from $500+ → $0
- **Citation filtering:** NIH iCite 95th percentile (2.6M papers → 58K high-impact)
- **Section-aware chunking:** Preserved paper structure for better citations
- **Cross-encoder reranking:** Improved quality with minimal latency (~0.8s)

## More Info

See [docs/](docs/) for detailed design decisions, architecture, and implementation.

Full case study coming soon.

---

**Note:** This is a personal learning project. Not for clinical/professional use.
