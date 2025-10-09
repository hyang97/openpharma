# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenPharma is an AI-powered strategic intelligence engine for pharmaceutical competitive intelligence. It provides a conversational interface to pharma data, allowing users to ask complex strategic questions and receive synthesized answers with citations.

## Architecture Overview

The project follows a phased development approach across three phases:

### Phase 1: Research Literature Intelligence MVP (Current)
- **Tech Stack**: FastAPI backend, Streamlit UI (planned), Ollama Llama 3.1 8B/OpenAI GPT-4 (configurable), Local Postgres + pgvector
- **Primary Data Source**: PubMed Central Open Access (diabetes research focus)
- **Core Capability**: Conversational RAG interface for research literature queries
- **Current Status**: Implementing 4-phase decoupled ingestion pipeline (see `docs/ingestion_pipeline.md`)

### Phase 2: Multi-Domain Intelligence Platform
- **Tech Stack**: Next.js/React frontend, FastAPI + LangChain/LangGraph for agent orchestration, Postgres JSONB for relationships
- **Data Sources**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed, SEC EDGAR (optional)
- **Key Features**: Agentic workflows, cross-domain queries, MCP tool integration

### Phase 3: Optimized ML Infrastructure
- **Tech Stack**: Self-hosted vLLM (Llama 3.1 70B) on GKE, fine-tuned PyTorch models, Ray Serve
- **Advanced Features**: Predictive analytics, cost-optimized inference, domain-specific fine-tuning

## Key Technical Components

### Data Processing
- **Chunking Strategy**: Token-based chunking (512 tokens, 50-token overlap) with section-aware processing
  - Each section (abstract, introduction, methods, results, etc.) chunked separately to preserve semantic boundaries
  - Title NOT chunked (included in every chunk's embedding context)
- **Context Enhancement**: Document title + section name prepended to embeddings via `embedding_text` field (not stored in DB)
- **Vector Embeddings**: 1536 dimensions (OpenAI text-embedding-3-small)
- **Index Type**: HNSW (m=16, ef_construction=64) for fast similarity search

### Infrastructure Choices
- **Vector Store**: Local Postgres + pgvector (cost-effective for <1M documents)
- **Schema Design**:
  - `pubmed_papers` table: Tracks PMC IDs and fetch status (NEW - Phase 1)
    - `pmc_id` (PK): Numeric ID only (e.g., "1234567", not "PMC1234567")
    - `fetch_status`: 'pending', 'fetched', 'failed'
  - `documents` table: Stores complete document text + metadata
    - `full_text` contains title + abstract + all body sections with headers
    - `doc_metadata['section_offsets']` tracks character positions for section recovery
    - `ingestion_status`: 'fetched', 'chunked', 'embedded' (NEW - Phase 1)
    - See `docs/data_design.md` for detailed section storage strategy
  - `document_chunks` table: Chunked content with VECTOR(1536) embeddings
    - `content` field stores raw chunk text
    - `section` field identifies source section (abstract, methods, results, etc.)
    - `char_start/char_end` point into parent document's `full_text`
    - `embedding` can be NULL (indicates needs embedding)
  - JSONB columns (`doc_metadata`) for source-specific fields
  - UNIQUE constraint on (source, source_id) for deduplication
- **LLM Strategy**: Hybrid local (Ollama) + cloud (OpenAI) via environment configuration
- **Deployment**: Local Docker development, GCP Cloud Run for demos (planned)
- **Logging**: Python logging module with configurable levels (DEBUG/INFO/WARNING/ERROR/CRITICAL)
  - API logs: `logs/openpharma.log` (static filename)
  - Batch scripts: timestamped filenames
- **Orchestration**: LangChain + LangGraph for agentic workflows (Phase 2+)

### Key Design Patterns
- Conversational RAG with semantic search
- Verifiable citations linked to source data
- Multi-step agentic research workflows
- Knowledge graph traversal for complex queries

## Development Guidelines

This is a learning-focused AI engineering project optimized for hands-on experience with modern AI tools:

1. **Hybrid Development**: Local development with Ollama, cloud demos with OpenAI GPT-4
2. **Docker-First**: All services containerized for consistent development and deployment
3. **Evaluation-Driven**: Use RAGAS and custom metrics for citation accuracy measurement (planned)
4. **Cost-Conscious**: <$100 total project cost via local development + selective cloud demos
5. **Phase-based Learning**: Master RAG fundamentals before advancing to agents and optimization
6. **Documentation-First**: Always document design decisions before implementation (see `docs/`)
7. **Slow and Steady**: Build understanding step-by-step, prioritize learning over speed
8. **Professional Documentation**: No emojis in code files, documentation, or comments. Emojis are fine in conversational responses to the user.
9. **No One-Off Scripts**: Avoid creating temporary Python scripts for debugging or database checks. Use bash commands with inline Python or docker-compose exec for ad-hoc operations.
10. **Archive, Don't Delete**: When replacing or deprecating files, move them to `archive/` with a timestamp suffix (e.g., `old_script_20250108.py`) rather than deleting. This preserves project history for learning.
11. **End-of-Session Workflow**: When the user asks to wrap up:
    - Review all code changes made during the session
    - Update all relevant design docs in `docs/` to reflect implementation changes
    - Create a git commit with a short one-liner message summarizing the session's work
12. **Update Docs at Session End Only**: Do NOT update design docs incrementally during implementation - only update them at the end of the session during wrap-up.

## Code Structure

```
app/
├── db/
│   ├── models.py           # SQLAlchemy models (Document, DocumentChunk, PubMedPaper)
│   ├── database.py         # Database connection setup
│   └── init_db.py          # Database initialization script
├── ingestion/
│   ├── pubmed_fetcher.py   # Fetch papers from PubMed Central API
│   ├── xml_parser.py       # Parse JATS XML from PMC (includes table extraction)
│   ├── chunker.py          # Token-based section-aware chunking
│   └── embeddings.py       # OpenAI embedding generation (regular + batch API)
├── logging_config.py       # Centralized logging configuration
└── main.py                 # FastAPI application

scripts/
├── collect_pmc_ids.py      # Stage 1: Search and store PMC IDs
├── fetch_papers.py         # Stage 2: Fetch and store documents
├── chunk_papers.py         # Stage 3: Chunk documents
└── embed_chunks.py         # Stage 4: Embed chunks

docs/
├── project_spec.md         # Project specification and requirements
├── ingestion_pipeline.md   # 4-stage decoupled pipeline architecture
├── data_design.md          # Database schema and storage strategy
├── embedding_service.md    # EmbeddingService API reference
└── logging.md              # Logging guide and best practices

tests/
└── test_pipeline.py        # Integration tests for ingestion pipeline

archive/                    # Archived/outdated files (code, docs, configs)
data/batches/               # Batch API files (gitignored)
```

## Data Sources and Integration

### Primary Sources by Phase
- **Phase 1**: PubMed Central Open Access (diabetes research focus)
- **Phase 2**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed
- **Phase 3**: USPTO, NIH RePORTER, Patient Forums, Conference Abstracts

### Integration Patterns - 4-Phase Decoupled Pipeline

**See `docs/ingestion_pipeline.md` for complete architecture.**

1. **Phase 1 - Collect PMC IDs**: Search PubMed → Store IDs in `pubmed_papers` table
2. **Phase 2 - Fetch Papers**: Fetch XML → Parse → UPSERT into `documents` table
3. **Phase 3 - Chunk Documents**: Create chunks with NULL embeddings
4. **Phase 4 - Embed Chunks**: Generate embeddings, update chunks

**Key Features:**
- Each phase is independent and resumable
- Idempotent operations (can re-run without duplicates)
- Document updates via PubMed `[lr]` (last revision) date field
- UPSERT replaces old documents (no version history)
- Embedding options:
  - **Regular API**: Instant results, standard pricing (~$100 for 100K papers)
  - **Batch API**: 24-hour turnaround, 50% cheaper (~$50 for 100K papers)
- Rate limiting: NCBI API limited to 3 requests/second (0.34s sleep between calls)

## Success Metrics

### Phase 1 Targets (Learning Focused)
- Working RAG system with research literature
- <30 second response time for complex queries
- 95%+ citation accuracy measurement
- Docker deployment + Cloud Run demo
- RAGAS evaluation framework implementation

### Phase 2 Targets
- Support cross-domain queries
- Enable multi-step agentic workflows
- 1M+ knowledge graph relationships

### Phase 3 Targets
- 80% cost reduction through self-hosting
- Fine-tuned models match/exceed GPT-4 on domain tasks
- <100ms inference latency for self-hosted models