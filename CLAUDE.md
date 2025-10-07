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
- **Current Status**: Data ingestion pipeline complete (fetcher, parser, chunker, embeddings). Next: batch ingestion script + testing.

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
  - `documents` table: Stores complete document text + metadata
    - `full_text` contains title + abstract + all body sections with headers
    - `doc_metadata['section_offsets']` tracks character positions for section recovery
    - See `docs/data_design.md` for detailed section storage strategy
  - `document_chunks` table: Chunked content with VECTOR(1536) embeddings
    - `content` field stores raw chunk text
    - `section` field identifies source section (abstract, methods, results, etc.)
    - `char_start/char_end` point into parent document's `full_text`
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

## Code Structure

```
app/
├── db/
│   ├── models.py           # SQLAlchemy models (Document, DocumentChunk)
│   ├── database.py         # Database connection setup
│   └── init_db.py          # Database initialization script
├── ingestion/
│   ├── pubmed_fetcher.py   # Fetch papers from PubMed Central API
│   ├── xml_parser.py       # Parse JATS XML from PMC
│   ├── chunker.py          # Token-based section-aware chunking
│   └── embeddings.py       # OpenAI embedding generation (regular + batch API)
├── logging_config.py       # Centralized logging configuration
└── main.py                 # FastAPI application

docs/
├── data_design.md          # Complete data pipeline and schema documentation
└── logging.md              # Logging guide and best practices

examples/
└── logging_demo.py         # Working logging examples

data/batches/               # Batch API files (gitignored)
```

## Data Sources and Integration

### Primary Sources by Phase
- **Phase 1**: PubMed Central Open Access (cancer research focus)
- **Phase 2**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed
- **Phase 3**: USPTO, NIH RePORTER, Patient Forums, Conference Abstracts

### Integration Patterns
- Weekly automated ingestion via Cloud Run Jobs (planned)
- Batch embedding workflow: Fetch from PubMed → Parse XML → Chunk by section → Embed → Store
- Document updates: Delete old chunks, recreate with new embeddings
- Section-aware processing: Title, abstract, and body sections tracked with character offsets
- Embedding options:
  - **Regular API**: Instant results, standard pricing (good for <100 chunks, testing)
  - **Batch API**: 24-hour turnaround, 50% cheaper (recommended for production ingestion)
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