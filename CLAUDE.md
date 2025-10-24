# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenPharma is an AI-powered strategic intelligence engine for pharmaceutical competitive intelligence. It provides a conversational interface to pharma data, allowing users to ask complex strategic questions and receive synthesized answers with citations.

## Architecture Overview

The project follows a phased development approach across three phases:

### Phase 1: Research Literature Intelligence MVP (COMPLETE)
- **Tech Stack**: Next.js/React UI, FastAPI backend, Ollama Llama 3.1 8B/OpenAI GPT-4 (configurable), Local Postgres + pgvector
- **Primary Data Source**: PubMed Central Open Access (diabetes research focus, 52K papers fully ingested)
- **Core Capability**: Multi-turn conversational RAG interface with conversation-wide citation numbering
- **Status**: ✅ Complete - Deployed to production (Cloudflare Tunnel + Vercel), ✅ Full RAG pipeline, ✅ Mobile-responsive UI, ✅ Multi-turn conversations
- **Next Steps**: User feedback collection, RAGAS evaluation setup, performance optimization

### Phase 2: Multi-Domain Intelligence Platform
- **Tech Stack**: FastAPI + LangChain/LangGraph for agent orchestration, Postgres JSONB for relationships
- **Data Sources**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed, SEC EDGAR (optional)
- **Key Features**: Agentic workflows, cross-domain queries, MCP tool integration

### Phase 3: Optimized ML Infrastructure
- **Tech Stack**: Self-hosted vLLM (Llama 3.1 70B) on GKE, fine-tuned PyTorch models, Ray Serve
- **Advanced Features**: Predictive analytics, cost-optimized inference, domain-specific fine-tuning

## Key Technical Components

### RAG Pipeline (Implemented)
- **Retrieval**: Hybrid semantic search (historical + new chunks) via pgvector, top-20 chunks by cosine similarity
- **Generation**: Ollama Llama 3.1 8B or OpenAI GPT-4 (configurable via `use_local` flag)
- **Citation Tracking**: Immutable Citation objects with chunk-level tracking, conversation-wide numbering
- **Multi-turn Support**: Conversation history with hybrid retrieval (past chunks + new semantic search)
- **Response Model**: `RAGResponse` with answer, citations list, query, LLM provider, timing
- **Performance**: 18-40s response time (97% LLM generation, 3% retrieval)
- See `app/rag/generation.py` for implementation

### React UI (Complete)
- **Framework**: Next.js 15 + TypeScript + Tailwind CSS
- **Design**: Dark theme (slate + cobalt blue) with collapsible sidebar for conversation management
- **Components**: Modular components (ChatHeader, MessageList, MessageBubble, CitationList, ChatInput, ConversationSidebar)
- **State Management**: React useState in main page component
- **Features**: Multi-turn conversations, conversation-wide citation numbering, loading indicators, collapsible sidebar
- **Mobile**: Fully responsive with overlay sidebar, sticky header/input, touch-optimized interactions
- **Animations**: Message fade-in, citation expand/collapse, sidebar transitions, smooth scrolling
- **Shared Types**: `src/types/message.ts` for Message and Citation types
- **Deployment**: Frontend on Vercel, backend API via Cloudflare Tunnel
- See `docs/ui_design.md` for complete design documentation

### Data Processing
- **Chunking**: 512 tokens with 50-token overlap, section-aware (abstract, methods, results separately)
- **Embeddings**: Ollama nomic-embed-text (768d, self-hosted, $0 cost)
  - **CRITICAL**: MUST use Ollama 0.11.x (tested on 0.11.11)
  - **DO NOT upgrade to 0.12.5** - regression bug causes EOF errors
  - Download: https://github.com/ollama/ollama/releases/tag/v0.3.11
- **Vector Index**: HNSW (m=16, ef_construction=64)

### Database Schema
- **`pubmed_papers`**: Track PMC IDs and fetch status (pmc_id, fetch_status)
- **`documents`**: Full text + metadata (full_text, doc_metadata JSONB, ingestion_status)
- **`document_chunks`**: Chunked content with VECTOR(768) embeddings
- UNIQUE constraint on (source, source_id) for deduplication
- See `docs/data_design.md` for detailed schema

### Ingestion Pipeline (4 Decoupled Stages - Complete)
1. **Collect IDs**: `scripts/stage_1_collect_ids.py` → PubMed search → store PMC IDs
2. **Fetch Papers**: `scripts/stage_2_fetch_papers.py` → XML fetch/parse → UPSERT documents
3. **Chunk Documents**: `scripts/stage_3_chunk_papers.py` → tokenize → create chunks
4. **Embed Chunks**: `scripts/stage_4_embed_chunks.py` → Ollama embeddings → update vectors

**Status**: 52,014 papers fully ingested → 1.89M chunks with 768d embeddings (100% complete)
Each stage is independently resumable and idempotent. See `docs/ingestion_pipeline.md`.

## Common Commands Reference

**Always refer to these examples when running commands. DO NOT guess syntax.**

### Docker Commands
```bash
# Start/stop containers
docker-compose up -d              # Start in background
docker-compose down               # Stop containers
docker-compose ps                 # Check status
docker-compose logs -f api        # Follow logs

# Execute commands in running container
docker-compose exec api python -m scripts.stage_1_collect_ids --limit 50
docker-compose exec postgres psql -U admin -d openpharma -c "SELECT COUNT(*) FROM documents;"

# Run detached background job (for long-running tasks)
docker-compose run --rm -d --name api-fetch api bash -c "python -m scripts.stage_2_fetch_papers"
docker exec api-fetch tail -f logs/stage_2_fetch_papers.log  # Monitor (use docker, not docker-compose)
docker stop api-fetch  # Stop when done
```

### UI Commands
```bash
cd ui
npm install              # Install dependencies (first time)
npm run dev              # Start dev server at http://localhost:3000
```

**See `docs/cheatsheet.md` for complete command reference.**

## Development Guidelines

This is a learning-focused AI engineering project optimized for hands-on experience with modern AI tools:

1. **NEVER Write Large Code Files in One Go**: This is a learning project. Build incrementally:
   - Discuss plan first, get approval
   - Start with skeleton (imports, main, argparse)
   - Add one function at a time with explanation
   - Test each piece before proceeding
   - If writing >50 lines in one message, STOP and break it down
2. **Hybrid Development**: Local development with Ollama, cloud demos with OpenAI GPT-4
3. **Docker-First**: All services containerized for consistent development and deployment
4. **Evaluation-Driven**: Use RAGAS and custom metrics for citation accuracy measurement (planned)
5. **Cost-Conscious**: <$100 total project cost via local development + selective cloud demos
6. **Phase-based Learning**: Master RAG fundamentals before advancing to agents and optimization
7. **Documentation-First**: Always document design decisions before implementation (see `docs/`)
   - **Significant architectural decisions** → `docs/decisions.md` (e.g., Postgres vs Pinecone, React vs Streamlit)
   - **UI/UX design patterns** → `docs/ui_design.md`
   - **Pipeline architecture** → `docs/ingestion_pipeline.md`
   - **NOT for minor styling choices** (e.g., Tailwind class names, color palette tweaks)
8. **Slow and Steady**: Build understanding step-by-step, prioritize learning over speed
9. **Professional Documentation**: No emojis in code files, documentation, or comments. Emojis are fine in conversational responses to the user.
10. **No One-Off Scripts**: Avoid creating temporary Python scripts for debugging or database checks. Use bash commands with inline Python or docker-compose exec for ad-hoc operations.
11. **Archive, Don't Delete**: When replacing or deprecating files, move them to `archive/` with a timestamp suffix (e.g., `old_script_20250108.py`) rather than deleting. This preserves project history for learning.
12. **Manual Coding Workflow**: When the user wants to code manually and learn:
    - Provide explanations, answer questions, suggest approaches, give examples, and explain concepts as needed
    - DO NOT write code unless explicitly asked
    - Help debug and review user's code
13. **End-of-Session Workflow**: When the user asks to wrap up:
    - Archive completed tasks from `TODO.md` to `archive/TODO_completed_YYYYMMDD.md`
    - Update `TODO.md` to remove completed tasks and add any new tasks discovered during the session
    - Review all code changes made during the session
    - Update all relevant design docs in `docs/` to reflect implementation changes
    - Update `CLAUDE.md` and `docs/project_spec.md` to reflect current project state
    - Create a git commit with a one-line message summarizing the session's work (NO multi-line messages)
14. **Update Docs at Session End Only**: Do NOT update design docs incrementally during implementation - only update them at the end of the session during wrap-up.
15. **Task Archival**: When major milestones are completed, archive detailed task lists to `archive/TODO_completed_YYYYMMDD.md` before removing from TODO.md. This preserves achievement history for learning and future reference.

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
│   └── embeddings.py       # Ollama embedding generation
├── rag/
│   ├── __init__.py              # Exports RAGResponse, Citation
│   ├── generation.py            # RAG generation with citation extraction
│   └── conversation_manager.py  # Multi-turn conversation state management
├── retrieval/
│   ├── __init__.py              # Exports search functions
│   └── semantic_search.py       # Hybrid semantic search via pgvector
├── models.py               # Pydantic models for API (RAGResponse, Citation, Message, Conversation)
├── logging_config.py       # Centralized logging configuration
└── main.py                 # FastAPI application with /ask endpoint

ui/
├── src/
│   ├── app/
│   │   ├── page.tsx        # Main chat page (client component)
│   │   ├── layout.tsx      # Root layout
│   │   └── globals.css     # Global Tailwind styles
│   ├── components/
│   │   ├── ChatHeader.tsx         # Header with hamburger menu (mobile-responsive)
│   │   ├── MessageList.tsx        # Message container with loading state
│   │   ├── MessageBubble.tsx      # Individual message display (user bubbles only)
│   │   ├── CitationList.tsx       # Expandable citation cards
│   │   ├── ChatInput.tsx          # Auto-expanding input with send button
│   │   └── ConversationSidebar.tsx # Collapsible conversation history sidebar
│   └── types/
│       └── message.ts      # Shared TypeScript types
├── package.json
└── tsconfig.json

scripts/
├── stage_1_collect_ids.py     # Stage 1: Search and store PMC IDs
├── stage_2_fetch_papers.py    # Stage 2: Fetch and store documents
├── stage_3_chunk_papers.py    # Stage 3: Chunk documents
└── stage_4_embed_chunks.py    # Stage 4: Embed chunks

docs/
├── project_spec.md         # Project specification and requirements
├── ui_design.md            # UI design documentation
├── rag.md                  # RAG pipeline architecture and implementation
├── ingestion_pipeline.md   # 4-stage decoupled pipeline architecture
├── data_design.md          # Database schema and storage strategy
├── decisions.md            # Architecture decision log
├── use_cases.md            # User stories and use cases
├── embedding_service.md    # EmbeddingService API reference
├── logging.md              # Logging guide and best practices
└── cheatsheet.md           # Common commands reference

tests/
├── test_pipeline.py           # Integration tests for ingestion pipeline
├── test_refactored_flow.py    # End-to-end RAG flow tests
├── test_hybrid_retrieval.py   # Multi-turn retrieval tests
├── test_heading_stripping.py  # Citation extraction tests
├── test_data_integrity.py     # Database health checks
├── test_embedding_performance.py # Embedding performance benchmarks
└── validate_embeddings.py     # Embedding quality validation

archive/                       # Archived/outdated files (code, docs, configs, completed TODOs)
  ├── TODO_completed_20251024.md # Phase 1 Demo Deployment completion archive
  ├── TODO_completed_20251014.md # Ingestion Pipeline & Ollama Migration archive
  └── logs_20251023/             # Archived log files from cleanup
data/                          # Reserved for batch API files (gitignored)
backups/                       # Database backups (gitignored)
```

## Data Sources and Integration

### Primary Sources by Phase
- **Phase 1**: PubMed Central Open Access (diabetes research focus)
- **Phase 2**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed
- **Phase 3**: USPTO, NIH RePORTER, Patient Forums, Conference Abstracts

### Ingestion Pipeline Details

**See `docs/ingestion_pipeline.md` for complete architecture.**

**Key Features:**
- Each phase is independent and resumable
- Idempotent operations (can re-run without duplicates)
- Document updates via PubMed `[lr]` (last revision) date field
- UPSERT replaces old documents (no version history)
- Rate limiting: NCBI API limited to 3 requests/second (0.34s sleep between calls)
- **NCBI Large Job Policy**: Run large jobs (>1000 papers) during off-peak hours only:
  - Weekends (anytime)
  - Weekdays: 9pm - 5am Eastern Time
  - Violation may result in IP blocking

## Success Metrics

### Phase 1 Targets (Learning Focused)
- ✅ Working RAG system with research literature (52K papers, 1.89M chunks)
- ✅ React UI with dark theme, citation display, and collapsible sidebar
- ✅ Multi-turn conversation support with hybrid retrieval
- ✅ Conversation-wide citation numbering
- ⏳ Query rewriting for better multi-turn retrieval
- ⏳ Chunk reranking to improve retrieval quality
- ⏳ <30 second response time for complex queries (current: 18-40s, bottleneck: LLM generation)
- ⏳ 95%+ citation accuracy measurement
- ⏳ RAGAS evaluation framework implementation
- ⏳ Docker deployment + Cloud Run demo

### Phase 2 Targets
- Support cross-domain queries
- Enable multi-step agentic workflows
- 1M+ knowledge graph relationships

### Phase 3 Targets
- 80% cost reduction through self-hosting
- Fine-tuned models match/exceed GPT-4 on domain tasks
- <100ms inference latency for self-hosted models
