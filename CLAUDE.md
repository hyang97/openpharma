# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenPharma is an AI-powered strategic intelligence engine for pharmaceutical competitive intelligence. It provides a conversational interface to pharma data, allowing users to ask complex strategic questions and receive synthesized answers with citations.

## Architecture Overview

The project follows a phased development approach across three phases:

### Phase 1: Research Literature Intelligence MVP
- **Tech Stack**: FastAPI backend, Streamlit UI, Ollama Llama 3.1 8B/OpenAI GPT-4 (configurable), Local Postgres + pgvector
- **Primary Data Source**: PubMed Central Open Access (200K+ cancer research papers)
- **Core Capability**: Conversational RAG interface for research literature queries

### Phase 2: Multi-Domain Intelligence Platform
- **Tech Stack**: Next.js/React frontend, FastAPI + LangChain/LangGraph for agent orchestration, Postgres JSONB for relationships
- **Data Sources**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed, SEC EDGAR (optional)
- **Key Features**: Agentic workflows, cross-domain queries, MCP tool integration

### Phase 3: Optimized ML Infrastructure
- **Tech Stack**: Self-hosted vLLM (Llama 3.1 70B) on GKE, fine-tuned PyTorch models, Ray Serve
- **Advanced Features**: Predictive analytics, cost-optimized inference, domain-specific fine-tuning

## Key Technical Components

### Data Processing
- **Chunking Strategy**: Token-based chunking (512 tokens, 50-token overlap) with section-based organization
- **Context Enhancement**: Document title + section name prepended to embeddings (not stored in content)
- **Vector Embeddings**: 1536 dimensions (OpenAI text-embedding-3-small)
- **Index Type**: HNSW (m=16, ef_construction=64) for fast similarity search

### Infrastructure Choices
- **Vector Store**: Local Postgres + pgvector (cost-effective for <1M documents)
- **Schema Design**:
  - `documents` table: Metadata only (no document-level embeddings)
  - `document_chunks` table: Chunked content with VECTOR(1536) embeddings
  - JSONB columns (`doc_metadata`) for source-specific fields
  - UNIQUE constraint on (source, source_id) for deduplication
- **LLM Strategy**: Hybrid local (Ollama) + cloud (OpenAI) via environment configuration
- **Deployment**: Local Docker development, GCP Cloud Run for demos
- **Monitoring**: Cloud Monitoring for production demos
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
3. **Evaluation-Driven**: Use RAGAS and custom metrics for citation accuracy measurement
4. **Cost-Conscious**: <$100 total project cost via local development + selective cloud demos
5. **Phase-based Learning**: Master RAG fundamentals before advancing to agents and optimization

## Data Sources and Integration

### Primary Sources by Phase
- **Phase 1**: PubMed Central Open Access (cancer research focus)
- **Phase 2**: ClinicalTrials.gov, FDA Drugs@FDA, DailyMed
- **Phase 3**: USPTO, NIH RePORTER, Patient Forums, Conference Abstracts

### Integration Patterns
- Weekly automated ingestion via Cloud Run Jobs
- Batch embedding workflow: Ingest documents → chunk → embed in batches
- Document updates: Delete old chunks, recreate with new embeddings
- Section-based organization (abstract, methods, results, discussion)
- Consistent embedding: OpenAI text-embedding-3-small with contextual enhancement

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