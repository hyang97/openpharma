# OpenPharma

> Your on-demand pharmaceutical research analyst. Transform multi-day research into minutes. Ask natural language questions about diabetes research and get AI-synthesized answers with verifiable citations from 110K+ research papers.

## Live Demo: [openpharma.byhenry.me](https://openpharma.byhenry.me)

![OpenPharma home screen](images/desktop-home.png)

### Chat in Browser
![Desktop conversation view](images/desktop-convo.png)

### Chat on Mobile
<img src="images/mobile-convo.png" alt="Mobile conversation view" width="300">

## What It Does

Ask questions like:
- "What are the latest findings on GLP-1 agonists for weight loss?"
- "Compare SGLT2 inhibitors vs traditional therapies"
- "What are the safety profiles of SGLT2 inhibitors?"

Get instant synthesized answers backed by credible evidence with verifiable citations.

## System Stats

- **110K papers** from PubMed Central (2020-2025 diabetes research + high-impact historical papers)
- **4.7M semantic chunks** with 768-dimensional embeddings
- **165 GB database** including full papers and NIH citation metadata
- **<$50 total cost** via self-hosted Ollama (embeddings + LLM)

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

## Key Technical Decisions

- **Self-hosted Ollama:** Reduced embedding costs from $500+ to $0
- **NIH iCite citation filtering:** 95th percentile filter reduced 2.6M papers to 58K high-impact historical papers
- **Section-aware chunking:** Preserves paper structure (abstract, methods, results) for accurate citations
- **Cross-encoder reranking:** Improves retrieval quality with minimal latency cost (~0.8s)

## More Info

See [docs/](docs/) for detailed design decisions, architecture, and implementation.

Full case study coming soon.

---

**Note:** This is a personal learning project. Not for clinical/professional use.
