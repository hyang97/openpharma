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

### **Phase 1: Clinical Pipeline Intelligence MVP (Weeks 1-4)**

#### Business Capabilities
- **Core Use Case:** "What are Merck's active Phase 3 oncology trials?"
- **User Value:** Generate complete competitor clinical trial landscape in 10 minutes vs. 1 day of manual work
- **Success Metric:** 10+ weekly active users, 80%+ query satisfaction

#### Data Sources
- **ClinicalTrials.gov** - 450K+ clinical studies
  - Trial design, phase, status, sponsors, conditions, interventions

#### System Architecture

```
Streamlit (UI for testing)
    ↓
FastAPI (REST API)
    ↓
    ├→ Vertex AI Gemini (LLM reasoning)
    ├→ Vertex AI Embeddings (semantic search)
    └→ Cloud SQL: Postgres + pgvector (vector store)

Cloud Run Job (daily data ingestion)
Cloud Storage (raw data backup)
Cloud Monitoring (observability)
```

#### Technology Stack
| Component | Technology | Rationale |
|-----------|------------|-----------|
| **API Backend** | FastAPI | Industry standard for ML APIs, async support |
| **UI** | Streamlit | Rapid prototyping, all-in-one Python |
| **LLM** | Vertex AI Gemini | Managed API, enterprise SLAs |
| **Embeddings** | Vertex AI Embeddings | Native GCP integration |
| **Vector Store** | Postgres + pgvector | Simple, cost-effective for MVP scale |
| **Data Ingestion** | Cloud Run Jobs | Serverless scheduling, no orchestration overhead |
| **Monitoring** | Cloud Monitoring | Built-in GCP, free tier sufficient |

#### Key Features
1. **Conversational RAG Interface**
   - Natural language queries about clinical trials
   - Semantic search over trial documents
   - LLM synthesis with inline citations
   - <30 second response time (p95)

2. **Verifiable Citations**
   - Every claim linked to source (NCT ID)
   - Click-through to ClinicalTrials.gov
   - 95%+ citation accuracy

3. **Daily Data Updates**
   - Automated ingestion from ClinicalTrials.gov
   - Simple paragraph-based chunking
   - Incremental updates to vector store

#### Technical Details
- **Document Processing:** Simple split on paragraph breaks (`\n\n`)
- **Vector Dimensions:** 768 (Vertex AI embedding model)
- **Retrieval:** Top-20 semantic nearest neighbors
- **Monthly Cost:** $20-50 (Cloud Run + Cloud SQL free tier + API calls)

#### Non-Functional Requirements
- 99%+ uptime during business hours
- Data freshness <24 hours
- Per-query cost <$0.10

---

### **Phase 2: Multi-Domain Intelligence Platform (Weeks 5-12)**

#### Business Capabilities Unlocked
- **Cross-Domain Analysis:** "What clinical trials support the drugs Pfizer highlighted in their Q3 earnings as key growth drivers?"
- **Regulatory Intelligence:** "Compare drug labels for competing PD-1 inhibitors"
- **Strategic Synthesis:** "What therapeutic areas is Merck prioritizing based on their trial portfolio and SEC filings?"
- **Agentic Workflows:** Multi-step research tasks with tool use

#### Data Sources Added
- **PubMed** - Published trial results, KOL identification
- **FDA Drugs@FDA** - Approved drugs, regulatory actions
- **DailyMed** - Structured product labeling
- **SEC EDGAR** - 10-K/10-Q filings for corporate strategy

#### System Architecture

```
Next.js/React (production UI)
    ↓
FastAPI + LangChain/LangGraph (agent orchestration)
    ↓
    ├→ Vertex AI Gemini (LLM)
    ├→ MCP (Model Context Protocol - tool integration)
    ├→ Cloud SQL: Postgres + pgvector (vectors)
    └→ Neo4j (knowledge graph)

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
   - Token-based chunking with overlap (512 tokens, 50 overlap)
   - Metadata preservation for complex citations
   - Multi-format parsing (XML, JSON, PDF, SEC filings)

4. **Experiment Tracking**
   - Compare embedding models, chunking strategies, prompt variations
   - A/B test different LLM providers
   - Log evaluation metrics (faithfulness, relevancy)

#### Technical Details
- **Graph Schema:** (Company)-[:SPONSORS]->(Trial)-[:PUBLISHED_AS]->(Paper)-[:WRITTEN_BY]->(Author)
- **Agent Types:** ReAct, Plan-and-Execute, Multi-agent collaboration
- **Monthly Cost:** $100-300 (increased data sources + Neo4j hosting)

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

**Postgres + pgvector (Phase 1) vs. Pinecone:**
- Postgres sufficient for <1M documents
- $0-50/month vs. $70-200/month
- Simpler deployment, no external dependencies
- Upgrade to dedicated vector DB only when scale demands it

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