# Project OpenPharma: Product Brief & Technical Specification

## Part 1: Product Brief

### Mission Statement
Provide life sciences commercial teams with a unified strategic intelligence engine, transforming disconnected data into continuous, evidence-backed insights through a conversational AI interface.

### The Problem
Pharma Brand and Competitive Intelligence teams are drowning in data but starving for insight. Answering "What is our competitor's clinical trial strategy?" requires manually searching multiple databases, reading dense documents, and piecing together summaries. This process takes days and produces static reports that are instantly outdated.

### The Solution
OpenPharma is an AI-powered strategic intelligence engine providing a conversational interface to pharmaceutical data. Users ask complex strategic questions in natural language and receive immediate, synthesized answers with every assertion backed by direct citations.

### Target User
- Competitive Intelligence Analysts
- Brand Managers
- Management Consultants (pharma/biotech)

### Core Value Proposition
Move from manual research (8 hours) to real-time strategic reasoning (10 minutes). OpenPharma provides an "on-demand analyst" for pharmaceutical competitive intelligence.

---

## Part 2: Phased Development Roadmap

### **Phase 1: Research Literature Intelligence MVP (Weeks 1-4)**

**Current Implementation Focus:** Diabetes research (changed from cancer for initial development)

**Status:** Implementing 4-phase decoupled ingestion pipeline. See `docs/ingestion_pipeline.md` for technical architecture.

#### Business Capabilities
- **Core Use Case:** "What are the latest diabetes treatment efficacy results from clinical studies?"
- **User Value:** Synthesize research insights from thousands of papers in 10 minutes vs. weeks of manual literature review
- **Success Metric:** 10+ weekly active users, 80%+ query satisfaction

#### Data Sources
- **PubMed Central Open Access** - 8M+ full-text research papers
  - Diabetes research focus (~100K papers for Phase 1)
  - Published study results, treatment outcomes, biomarker data, safety profiles

#### System Architecture

```
Streamlit (UI for testing)
    ↓
FastAPI (REST API)
    ↓
    ├→ Ollama Llama 3.1 8B / OpenAI GPT-4 (LLM reasoning - configurable)
    ├→ Ollama nomic-embed-text (semantic search - 768d, self-hosted, $0 cost)
    └→ Local Postgres + pgvector (vector store)

Cloud Run Job (weekly data ingestion)
Cloud Storage (raw data backup)
Cloud Monitoring (observability)
```

#### Technology Stack
| Component | Technology | Rationale |
|-----------|------------|-----------|
| **API Backend** | FastAPI | Industry standard for ML APIs, async support |
| **UI** | Streamlit | Rapid prototyping, all-in-one Python |
| **LLM** | Ollama Llama 3.1 8B / OpenAI GPT-4 | Local development / Demo quality (configurable) |
| **Embeddings** | Ollama nomic-embed-text | 768 dims, self-hosted, $0 cost |
| **Vector Store** | Local Postgres + pgvector | Simple, cost-effective, fully local development |
| **Containerization** | Docker + Docker Compose | Local development, Cloud Run deployment |
| **Deployment** | Local Docker / GCP Cloud Run | Local development / Cloud demos only |
| **Evaluation** | RAGAS + Custom Metrics | RAG evaluation, citation accuracy measurement |
| **Data Ingestion** | Cloud Run Jobs | Serverless scheduling, no orchestration overhead |
| **Monitoring** | Cloud Monitoring | Built-in GCP, free tier sufficient |

#### Key Features
1. **Conversational RAG Interface**
   - Natural language queries about research findings
   - Semantic search over research paper sections
   - LLM synthesis with inline citations
   - <30 second response time (p95)

2. **Verifiable Citations**
   - Every claim linked to source paper (PMID)
   - Click-through to PubMed Central
   - 95%+ citation accuracy

3. **Weekly Data Updates**
   - Automated ingestion from PubMed Central API
   - Token-based chunking (512 tokens, 50-token overlap)
   - Section-based organization (Abstract, Methods, Results, Discussion)
   - Context-enhanced embeddings (title + section prepended)
   - Batch embedding workflow for cost efficiency

4. **Evaluation & Quality Assurance**
   - RAGAS evaluation framework (faithfulness, answer relevancy, context recall)
   - Citation accuracy measurement and tracking
   - Response quality metrics and automated testing
   - Performance benchmarking and optimization

#### Technical Details
- **Document Processing:** 512-token chunks with 50-token overlap, section-based organization
- **Vector Embeddings:** 768 dimensions (Ollama nomic-embed-text)
  - **CRITICAL:** MUST use Ollama 0.11.x (tested on 0.11.11). DO NOT upgrade to 0.12.5 (has regression bug causing EOF errors)
- **Vector Index:** HNSW (m=16, ef_construction=64) for fast similarity search
- **Database Schema:**
  - `documents` table: Metadata only (no document-level embeddings)
  - `document_chunks` table: Chunked content with VECTOR(768) embeddings
  - UNIQUE(source, source_id) constraint for deduplication
  - JSONB columns for flexible source-specific metadata
- **Retrieval:** Top-20 semantic nearest neighbors via cosine similarity
- **Development Cost:** $0/month (local Ollama + local Postgres)
- **Demo Cost:** $5-15/month (OpenAI GPT-4 calls when needed)
- **Embedding Cost:** $0 (self-hosted Ollama)
- **GCP Credit Strategy:** Leverage free tiers (Cloud Run 2M requests, Cloud SQL shared-core)

#### Non-Functional Requirements
- 99%+ uptime during business hours (demo purposes)
- Data freshness <1 week (sufficient for learning)
- Per-query cost <$0.10
- Total project cost: <$100 personal + <$50 GCP credits

#### Hybrid Development Strategy
- **Local Development:** Docker Compose (Postgres + FastAPI + Streamlit)
- **LLM Flexibility:** Environment variable to switch Ollama ↔ OpenAI GPT-4
- **Embeddings:** Ollama nomic-embed-text (self-hosted, free, 768d)
- **Cloud Deployment:** GCP Cloud Run for portfolio demos only
- **Cost Optimization:** 95% development local ($0), 5% demos with GPT-4 ($5-15/month)

---

### **Phase 2: Multi-Domain Intelligence Platform (Weeks 5-12)**

#### Business Capabilities Unlocked
- **Cross-Domain Analysis:** "What clinical trials support the drugs mentioned in recent oncology research, and what are their regulatory statuses?"
- **Regulatory Intelligence:** "Compare drug labels for competing PD-1 inhibitors"
- **Research-to-Market Analysis:** "Which therapies from recent research papers have progressed to clinical trials?"
- **Agentic Workflows:** Multi-step research tasks with tool use

#### Data Sources Added
- **ClinicalTrials.gov** - Active clinical studies, trial status, sponsors
- **FDA Drugs@FDA** - Approved drugs, regulatory actions
- **DailyMed** - Structured product labeling
- **SEC EDGAR** - 10-K/10-Q filings for corporate strategy (optional)

#### System Architecture

```
Next.js/React (production UI)
    ↓
FastAPI + LangChain/LangGraph (agent orchestration)
    ↓
    ├→ OpenAI GPT-4 (LLM)
    ├→ MCP (Model Context Protocol - tool integration)
    ├→ Cloud SQL: Postgres + pgvector (vectors)
    └→ Postgres JSONB (structured relationships)

MLflow (experiment tracking)
Cloud Run Jobs (multi-source ingestion)
Cloud Storage (document store)
Cloud Monitoring (production observability)
```

#### Technology Stack Additions
| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Orchestration** | LangChain + LangGraph | Agentic workflows, tool use, multi-step reasoning |
| **Tool Protocol** | MCP | Anthropic's standard for LLM-tool integration |
| **Knowledge Graph** | Neo4j | Complex relationship modeling (drugs ↔ trials ↔ companies ↔ publications) |
| **Frontend** | Next.js/React | Professional UI, streaming responses |
| **Experiments** | MLflow | Track prompt variations, model comparisons |

#### Key Features Added
1. **Agentic Workflows**
   - Multi-step research: "Find trials → analyze results → compare to competitor"
   - Tool use: calculator, web search, database queries
   - Demonstrates LangGraph agent patterns

2. **Knowledge Graph Queries**
   - Graph traversal: "All KOLs publishing on drugs competing with our asset"
   - Relationship modeling: Drug → Trial → Publication → Author → Institution
   - Enables questions impossible with vector search alone

3. **Advanced Document Processing**
   - Already implemented in Phase 1: Token-based chunking (512 tokens, 50 overlap)
   - Context-enhanced embeddings with document title + section
   - Multi-format parsing (XML, JSON, PDF, SEC filings) - Phase 2 addition
   - JSONB metadata storage for source-specific fields

4. **Experiment Tracking**
   - Compare embedding models, chunking strategies, prompt variations
   - A/B test different LLM providers
   - Log evaluation metrics (faithfulness, relevancy)

#### Technical Details
- **Relationship Schema:** Papers ↔ Trials ↔ Drugs ↔ Companies (Postgres JSONB, not Neo4j in Phase 2)
- **Agent Types:** ReAct, Plan-and-Execute, Multi-agent collaboration
- **Neo4j Migration:** Optional Phase 3 upgrade if graph complexity warrants dedicated graph DB
- **Monthly Cost:** $150-400 (multiple data sources + OpenAI API calls)

---

### **Phase 3: Optimized ML Infrastructure (Weeks 13+)**

#### Business Capabilities Unlocked
- **Predictive Analytics:** "Forecast patent cliff events for our portfolio 3-5 years out"
- **Patient Insights:** "What unmet needs are patients discussing in forums for Disease X?"
- **Emerging Science:** "Which early-stage therapeutic modalities are receiving NIH funding?"
- **Cost-Optimized Operations:** 80% reduction in inference costs through self-hosting

#### Data Sources Added
- **USPTO** - Patent filings, Orange Book exclusivity
- **NIH RePORTER** - Federal grant awards
- **Patient Forums** - Reddit, PatientsLikeMe (sentiment, unmet needs)
- **Conference Abstracts** - ASCO, ASH, ESMO (emerging data)

#### System Architecture

```
Next.js/React (UI)
    ↓
FastAPI (API gateway)
    ↓
    ├→ vLLM (self-hosted Llama 3.1 70B on GKE)
    ├→ Fine-tuned PyTorch models (domain-specific QA)
    ├→ Cloud SQL: Postgres + pgvector
    └→ Neo4j (knowledge graph)

Ray Serve (distributed inference)
MLflow (model registry + experiments)
Cloud Monitoring (primary observability)
[Optional] Prometheus + Grafana (if using GKE extensively)
Cloud Storage (document store)
```

#### Technology Stack Additions
| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Self-Hosted LLM** | vLLM | 10-20x faster inference, cost optimization |
| **Fine-Tuning** | PyTorch + Transformers | Domain-specific model for specialized tasks |
| **Distributed Serving** | Ray Serve on GKE | Scale self-hosted models across GPUs |
| **Advanced Monitoring** | Prometheus + Grafana (optional) | Only if GKE deployment warrants unified metrics |

#### Key Features Added
1. **Self-Hosted Inference**
   - Deploy Llama 3.1 70B with vLLM on GKE
   - Cost analysis: API vs. self-hosted
   - Demonstrates production ML infrastructure skills

2. **Fine-Tuned Domain Models**
   - Train Llama 3.1 8B on pharmaceutical Q&A
   - Outperform larger general models on domain tasks
   - Model versioning and A/B testing via MLflow

3. **Predictive Analytics**
   - Patent cliff forecasting (LOE events)
   - Trial success probability models
   - Time-series analysis of competitive activity

4. **Advanced Evaluation**
   - RAGAS framework (faithfulness, relevancy, context recall)
   - Automated citation accuracy checking
   - Cost-per-query optimization

#### Technical Details
- **vLLM Configuration:** Tensor parallelism across 4x A100 GPUs
- **Fine-Tuning Dataset:** 10K+ pharmaceutical Q&A pairs from trial abstracts
- **Monthly Cost:** $500-1000 (GPU compute + storage + managed services)
- **Monitoring Strategy:** Cloud Monitoring primary; add Prometheus/Grafana only if GKE metrics justify operational overhead

---

## Part 3: Key Design Decisions

### Why These Choices?

**Postgres + pgvector vs. Pinecone:**
- Postgres sufficient for <1M documents
- $0-50/month vs. $70-200/month
- HNSW index provides excellent performance for our scale
- Simpler deployment, no external dependencies
- Upgrade to dedicated vector DB only when scale demands it

**Ollama nomic-embed-text (self-hosted):**
- 768 dims (efficient, proven for semantic search)
- Self-hosted via Ollama ($0 cost)
- **CRITICAL:** Must use Ollama 0.11.x (0.12.5 has regression bug)
- Fast inference (~36ms per embedding)
- Better semantic clustering than OpenAI in benchmarks

**Chunk-level search only (no document embeddings):**
- Prevents context bloat (20-page paper → focused 512-token chunk)
- Better retrieval accuracy for specific questions
- Lower LLM costs (smaller context windows)
- Documents table stores metadata only

**Streamlit (Phase 1) → React (Phase 2):**
- Streamlit = rapid prototyping, ship in days
- React = professional polish, production UX
- Prove value before investing in frontend complexity

**Raw Python RAG (Phase 1) → LangChain (Phase 2):**
- Understand primitives before abstractions
- Better interview narrative: "Built from scratch, then adopted industry tools"
- LangChain valuable when adding agents and complex workflows

**Cloud Monitoring throughout:**
- Native GCP integration, sufficient for most use cases
- Add Prometheus/Grafana in Phase 3 only if GKE deployment requires it
- Avoid operational overhead of self-hosted monitoring unless necessary

**MCP in Phase 2:**
- Emerging standard for LLM-tool integration
- Shows awareness of cutting-edge protocols
- Natural fit when adding multiple tools and data sources

---

## Part 4: Success Metrics by Phase

### Phase 1
- 10+ weekly active users within 1 month
- <10 min to generate competitor pipeline analysis (vs. 8 hours manual)
- 80%+ query satisfaction rate
- 95%+ citation accuracy

### Phase 2
- Support cross-domain queries (clinical + regulatory + financial)
- Enable multi-step agentic research workflows
- Knowledge graph contains 1M+ relationships
- Users cite OpenPharma insights in strategic planning documents

### Phase 3
- 80% cost reduction through self-hosting
- Fine-tuned models match/exceed GPT-4 on domain tasks
- Predictive analytics used in annual portfolio planning
- <100ms inference latency for self-hosted models

---

## Appendix: Technology Resume Value

| Technology | Phase | Job Posting Frequency | Transferability |
|------------|-------|----------------------|-----------------|
| FastAPI | 1-3 | ⭐⭐⭐⭐⭐ | High (any ML API) |
| LangChain | 2-3 | ⭐⭐⭐⭐⭐ | High (RAG/agents) |
| LangGraph | 2-3 | ⭐⭐⭐⭐⭐ | High (agentic workflows) |
| Neo4j | 2-3 | ⭐⭐⭐⭐ | Medium (knowledge graphs) |
| vLLM | 3 | ⭐⭐⭐⭐⭐ | High (inference optimization) |
| PyTorch | 3 | ⭐⭐⭐⭐ | High (fine-tuning) |
| MLflow | 2-3 | ⭐⭐⭐⭐ | High (MLOps) |
| MCP | 2-3 | ⭐⭐⭐ | Medium (emerging standard) |
| Ray | 3 | ⭐⭐⭐⭐ | High (distributed ML) |

**Philosophy:** Start simple, add industry-standard tools intentionally with documented rationale. This demonstrates both technical judgment and breadth of experience.