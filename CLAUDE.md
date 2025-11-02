# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenPharma is an AI-powered strategic intelligence engine for pharmaceutical competitive intelligence. It provides a conversational interface to pharma data, allowing users to ask complex strategic questions and receive synthesized answers with citations.

## Architecture Overview

The project follows a phased development approach across three phases:

### Phase 1: Research Literature Intelligence MVP (COMPLETE)
- **Tech Stack**: Next.js/React UI, FastAPI backend, Ollama Llama 3.1 8B/OpenAI GPT-4 (configurable), Local Postgres + pgvector
- **Primary Data Source**: PubMed Central Open Access (diabetes research focus, 110K papers ingested: 52K diabetes 2020-2025 + 58K historical top-cited papers)
- **Core Capability**: Multi-turn conversational RAG interface with conversation-wide citation numbering, optional cross-encoder reranking
- **Status**: ✅ Complete - Deployed to production (Cloudflare Tunnel + Vercel), ✅ Full RAG pipeline, ✅ Mobile-responsive UI, ✅ Multi-turn conversations, ✅ Cross-encoder reranking implemented
- **Next Steps**: Complete historical paper ingestion (44.7K papers remaining), user feedback collection, RAGAS evaluation setup

### Phase 2: Multi-Domain Intelligence Platform
- **Tech Stack**: FastAPI + LangChain/LangGraph for agent orchestration, Postgres JSONB for relationships
- **Data Sources**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed, SEC EDGAR (optional)
- **Key Features**: Agentic workflows, cross-domain queries, MCP tool integration

### Phase 3: Optimized ML Infrastructure
- **Tech Stack**: Self-hosted vLLM (Llama 3.1 70B) on GKE, fine-tuned PyTorch models, Ray Serve
- **Advanced Features**: Predictive analytics, cost-optimized inference, domain-specific fine-tuning

## Key Technical Components

### RAG Pipeline (Implemented)
- Hybrid semantic search (fresh + historical chunks) + optional cross-encoder reranking via pgvector
- Ollama Llama 3.1 8B or OpenAI GPT-4 (configurable)
- Multi-turn conversations with conversation-wide citation numbering
- Performance: 18-40s response time (97% LLM, 3% retrieval + reranking if enabled)
- Reranking models: ms-marco-MiniLM-L-6-v2 (default, ~0.8s), bge-reranker-v2-m3 (~48s), bge-small-en-v1.5 (~1s)
- See `docs/15_rag.md` for complete architecture

### React UI (Complete)
- Next.js 15 + TypeScript + Tailwind CSS with dark theme
- Mobile-responsive with collapsible sidebar
- Multi-turn conversation support with client-side caching
- Race condition prevention with useRef validation pattern
- Deployed: Frontend on Vercel, backend via Cloudflare Tunnel
- See `docs/20_ui_architecture.md`, `docs/21_ui_design_system.md`, `docs/22_conversation_management.md`, `docs/23_rag_ui_integration.md` for complete documentation

### Data Processing
- **Chunking**: 512 tokens with 50-token overlap, section-aware (abstract, methods, results separately)
- **Embeddings**: Ollama nomic-embed-text (768d, self-hosted, $0 cost)
  - **CRITICAL**: MUST use Ollama 0.11.x (tested on 0.11.11)
  - **DO NOT upgrade to 0.12.5** - regression bug causes EOF errors
  - Download: https://github.com/ollama/ollama/releases/tag/v0.3.11
- **Vector Index**: HNSW (m=16, ef_construction=64)
- **Reranking**: Optional cross-encoder reranking (configurable via `RERANKER_MODEL` env var in docker-compose.yml)
  - Default: cross-encoder/ms-marco-MiniLM-L-6-v2 (~0.8s per query)
  - Must pass env var through docker-compose.yml, requires restart to apply

### Database Schema
- `pubmed_papers`, `documents`, `document_chunks` with VECTOR(768) embeddings
- `icite_metadata`, `citation_links` for filtering by citation impact
- See `docs/12_data_design.md` for complete schema

### Ingestion Pipeline (4 Stages + Citation Filtering)
- Stage 1-4: Collect IDs → Fetch → Chunk → Embed (independently resumable)
- Stage 1.1-1.2: PMID backfill → Citation-based filtering
- Status: 110.7K papers fetched (66.2K embedded, 44.5K pending embedding), 2.98M total chunks (2.54M embedded)
- See `docs/13_ingestion_pipeline.md` for complete pipeline

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

**See `docs/00_cheatsheet.md` for complete command reference.**

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
   - **Design docs are CONCISE design-only, NOT implementation guides**: Design docs describe architecture, decisions, and strategy in 1-2 pages max. They should NOT contain actual code implementations or detailed walkthroughs.
   - **Keep it SHORT**: If a design doc exceeds 200 lines, it's too long. Break it down or cut unnecessary detail.
   - **Significant architectural decisions** → `docs/03_decisions.md` (e.g., Postgres vs Pinecone, React vs Streamlit)
   - **UI/UX design patterns** → `docs/20_ui_design.md`
   - **Pipeline architecture** → `docs/13_ingestion_pipeline.md`
   - **NOT for minor styling choices** (e.g., Tailwind class names, color palette tweaks)
   - **Code examples in design docs**: Keep them minimal and illustrative (pseudocode, function signatures, schema definitions). Full implementations belong in actual code files.
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
│   ├── embeddings.py       # Ollama embedding generation
│   └── citation_utils.py   # Citation filtering and PMID conversion
├── rag/
│   ├── __init__.py              # Exports RAGResponse, Citation
│   ├── generation.py            # RAG generation with citation extraction
│   └── conversation_manager.py  # Multi-turn conversation state management
├── retrieval/
│   ├── __init__.py              # Exports search functions
│   ├── semantic_search.py       # Hybrid semantic search via pgvector
│   └── reranker.py              # Cross-encoder reranking service
├── models.py               # Pydantic models for API (RAGResponse, Citation, Message, Conversation)
├── logging_config.py       # Centralized logging configuration
└── main.py                 # FastAPI application with /chat endpoint

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
├── stage_1_1_backfill_pmids.py # Stage 1.1: Backfill PMIDs for citation filtering
├── stage_1_2_set_fetch_status.py # Stage 1.2: Set fetch status by citation metrics
├── stage_2_fetch_papers.py    # Stage 2: Fetch and store documents
├── stage_3_chunk_papers.py    # Stage 3: Chunk documents
└── stage_4_embed_chunks.py    # Stage 4: Embed chunks

docs/                                   # Documentation organized by prefix: 00-04 (requirements), 11-15 (backend), 20+ (frontend), 30+ (config/deployment)
├── 00_cheatsheet.md                    # Common commands reference
├── 01_project_spec.md                  # Project specification and requirements
├── 02_use_cases.md                     # User stories and use cases
├── 03_decisions.md                     # Architecture decision log
├── 04_pmc_collection_tracker.md        # PMC paper collection history (52K diabetes + 58K historical)
├── 11_logging.md                       # Logging guide and best practices
├── 12_data_design.md                   # Database schema and storage strategy
├── 13_ingestion_pipeline.md            # 4-stage decoupled pipeline architecture
├── 14_embedding_service.md             # EmbeddingService API reference
├── 15_rag.md                           # RAG pipeline architecture and implementation
├── 20_ui_architecture.md               # Frontend architecture and state management
├── 21_ui_design_system.md              # UI design system (colors, typography, components)
├── 22_conversation_management.md       # Conversation lifecycle and switching patterns
├── 23_rag_ui_integration.md            # RAG-specific UI patterns and citation display
├── 30_configuration.md                 # Configuration settings and Docker setup
└── 31_deployment.md                    # Deployment architectures and guide

tests/
├── test_refactored_flow.py                 # End-to-end RAG flow tests
├── test_hybrid_retrieval.py                # Multi-turn retrieval tests
├── test_heading_stripping.py               # Citation extraction tests
├── test_data_integrity.py                  # Database health checks
├── test_citation_utils.py                  # Citation utility tests (PMID conversion, filtering)
├── test_filter_by_metrics.py               # iCite citation filtering tests
├── reranking_eval_questions.py             # Test questions for reranking evaluation
├── run_reranking_eval.py                   # Automated reranking evaluation runner
├── reranking_eval_judge_prompt.md          # LLM-as-judge prompt for Gemini
├── reranking_eval_template.md              # Manual evaluation template
└── RERANKING_EVAL_README.md                # Reranking evaluation guide

archive/                                # Archived/outdated files (code, docs, configs, completed TODOs)
├── TODO_completed_20251028.md          # iCite Integration, Reranking, Evaluation Framework
├── TODO_completed_20251024.md          # Phase 1 Demo Deployment
├── TODO_completed_20251014.md          # Ingestion Pipeline & Ollama Migration
├── icite_integration_20251026/         # iCite integration SQL scripts and docs
├── tests_20251028/                     # Archived one-time/outdated tests
└── backfill_citations_20251026.py      # One-time citation backfill script
logs/
├── results/                    # Evaluation results (reranking, RAGAS, etc.) - gitignored
└── stage_*.log                 # Pipeline execution logs - gitignored
data/                          # Reserved for batch API files (gitignored)
backups/                       # Database backups (gitignored)
```

## Data Sources and Integration

### Primary Sources by Phase
- **Phase 1**: PubMed Central Open Access (diabetes research focus)
- **Phase 2**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed
- **Phase 3**: USPTO, NIH RePORTER, Patient Forums, Conference Abstracts

### Ingestion Pipeline Details

**See `docs/13_ingestion_pipeline.md` for complete architecture.**

**Key Features:**
- Each phase is independent and resumable
- Idempotent operations (can re-run without duplicates)
- Document updates via PubMed `[lr]` (last revision) date field
- UPSERT replaces old documents (no version history)
- Rate limiting: NCBI API limited to 3 requests/second (0.34s sleep between calls)
- **Timeout Handling**: Stage 2 uses ThreadPoolExecutor with configurable timeout (30s default, 120s with `--retry-failed`)
  - Handles large papers (some exceed 3MB) that can hang during fetch
  - Abandoned threads don't block pipeline progress
- **NCBI Large Job Policy**: Run large jobs (>1000 papers) during off-peak hours only:
  - Weekends (anytime)
  - Weekdays: 9pm - 5am Eastern Time
  - Violation may result in IP blocking

## Success Metrics

### Phase 1 Targets (Learning Focused)
- ✅ Working RAG system with research literature (110.7K papers fetched, 66.2K embedded, 2.54M embedded chunks)
- ✅ React UI with dark theme, citation display, and collapsible sidebar
- ✅ Multi-turn conversation support with hybrid retrieval
- ✅ Conversation-wide citation numbering
- ✅ Chunk reranking to improve retrieval quality (cross-encoder implemented)
- ⏳ Complete embedding remaining 44.5K papers (7.8K chunked, 36.7K fetched)
- ⏳ Reranking evaluation and deployment decision
- ⏳ Query rewriting for better multi-turn retrieval
- ⏳ <30 second response time for complex queries (current: 18-40s, bottleneck: LLM generation)
- ⏳ 95%+ citation accuracy measurement
- ⏳ RAGAS evaluation framework implementation

### Phase 2 Targets
- Support cross-domain queries
- Enable multi-step agentic workflows
- 1M+ knowledge graph relationships

### Phase 3 Targets
- 80% cost reduction through self-hosting
- Fine-tuned models match/exceed GPT-4 on domain tasks
- <100ms inference latency for self-hosted models
