# Project OpenPharma: Product Brief & Technical Specification

## 1. Product Vision

### Description and Value Proposition
OpenPharma is an AI-powered research & insights engine, providing life sciences companies and consultants with an "on-demand pharma analyst." Users can ask questions in natural language and receive instant, synthesized answers (backed by credible evidence with verifiable citations), transforming a multi-day research process into a matter of minutes. 

### Target User
- Competitive Intelligence Analysts
- Brand Managers
- Management Consultants (pharma/biotech)

### Pain points solved
- Accelerated time-to-insights: pharma research, synthesis, and insights takes days/weeks to manually review and synthesize dense literature. OpenPharma reduces this to minutes, providing immediate, synthesized answers with every assertion backed by direct citations.
- Hidden connections: manually researching and traingulating insights between multiple data sources across scientific literature, clinical trials, regulatory filings, etc. is complex. OpenPharma unifies this data and surfaces interconnected insights.

### Core Offering
OpenPharma is a conversational AI platform that allows users to:
1. Query and Synthesize Scientific Literature: Ask questions about drug efficiacy, safety, mechanisms of action, key opinion leaders, etc.
2. Analyze the Clinical Trial Landscape: Investigate competitor trial stratgies, compare study designs, and track development pipelines
3. Connect Research to Commercial Strategy: Link insights across scientific discoveries, clinical trials, regulatory approvals, corporate financial disclosures, etc. to build a 360-degree view of the market.

### Core Interface
User interacts with OpenPharma through a clean, intuitive, two-panel interface, similar to OpenEvidence.com and ChatGPT
1. Left Panel (20%): Persistent, searchable conversation history
2. Right Panel (80%): Primary workspace featuring chat interface, with a response area that clearly presents interactive, inline citations that link directly back to the source document
3. Landing Page: Clean, chat input interface, with an expandable set of example questions the user can ask

---



## 2. Development Plan

### **Phase 1: Research Literature Intelligence MVP (COMPLETE)**

**Implementation:** Diabetes research focus. Database contains 52,014 full-text articles for the keyword "diabetes" from PubMed Central from the last 5 years (1.89M chunks, 768d embeddings).

**Status:** ✅ Phase 1 complete - deployed to production with full RAG system, Next.js UI, and mobile responsiveness. See `archive/TODO_completed_20251024.md` for full completion details.

#### Business Capabilities
- **Core Use Case:** "What are the latest diabetes treatment efficacy results from clinical studies?"
- **User Value:** Synthesize research insights from thousands of papers in 10 minutes vs. weeks of manual literature review
- **Success Metric:** 10+ weekly active users, 80%+ query satisfaction

#### Data Sources
- **PubMed Central Open Access** - 8M+ full-text research papers
  - Diabetes research focus (~52K papers for Phase 1)
  - Published study results, treatment outcomes, biomarker data, safety profiles

#### Phase 1 Data Strategy

**Current Pipeline Implementation:**
- 4-phase decoupled ingestion pipeline (see `docs/ingestion_pipeline.md`)
- Initial target: ~52K diabetes papers from PubMed Central (2020-2025)
- Metadata extraction (already implemented):
  - Authors, journal, publication date, DOI, PMID (via NCBI esummary API)
  - Section structure and character offsets (via JATS XML parsing)
- Fully automated from search → fetch → chunk → embed
- Cost: $0 (all local processing with Ollama)

**Phase 1 Backlog: Data Enhancement "Quick Wins"**

To validate all Phase 1 use cases, these enhancements will be integrated into the existing ingestion pipeline:

**Quick Win #1: Enhanced Metadata Extraction** *(Partially Done)*
* **Status:** Basic author names already extracted via esummary. Need to add:
    - Author affiliations (institutional mapping for KOL analysis)
    - Publication type (clinical trial, review, meta-analysis, etc.)
    - MeSH (Medical Subject Headings) terms (biomarker and topic analysis)
* **Implementation:** Query PubMed database (not PMC) via efetch for additional metadata:
    ```
    https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={PMID}&retmode=xml
    ```
* **Note:** Need to convert PMC ID → PMID first (can use NCBI ID Converter API or extract from existing metadata)
* **Storage:** Add to `documents.doc_metadata` JSONB field
* **Benefit:** Enables filtering by research type, institution, and medical concepts

**Quick Win #2: Targeted Topic Expansion - Obesity**
* **Objective:** Demonstrate platform scalability with related therapeutic area
* **Target**: Obesity research (2020-2025) - ~30K papers
* **Implementation:** Run Stage 1 with query: `obesity[Title/Abstract] AND open access[filter] AND 2020/01/01:2025/12/31[pdat]`
* **Processing Time:** ~15 hours (fetch/chunk/embed)
* **Benefit:** Cross-disease queries, validates pipeline reusability, cardiometabolic focus

**Quick Win #3: Landmark Papers (Top 1% Across All Biomedicine)**
* **Objective:** Add historical context with most influential papers (1990-2020)
* **Data Source:** NIH iCite Database Snapshot (28.75GB download, includes citation metrics for all PubMed papers)
* **Filtering Criteria:**
    - `nih_percentile >= 99` (top 1% by field-normalized citations)
    - `year >= 1990 AND year <= 2020` (30-year historical window)
    - Open access only (filtered via NCBI ID Converter)
* **Implementation:**
    1. Download iCite snapshot to `data/icite_2025_09/`
    2. Import to Postgres: `icite_metadata` (12GB) + `citation_links` (12-18GB)
    3. Create `CitationFilter` helper in `app/ingestion/citation_filter.py`
    4. Use with Stage 1 flag: `--filter-citations --percentile 99`
* **Expected Result:** ~20K-25K landmark papers across all biomedicine
* **Processing Time:** ~5-8 hours (iCite import) + ~10-12 hours (fetch/chunk/embed)
* **Storage:** Citation data enables KOL identification, co-citation analysis (2-hop SQL queries)
* **Benefit:** Historical context, cross-domain discovery, "top 1% most influential biomedical research" positioning
* **Phase 2 Migration Path:** Can migrate citation data to Neo4j if building Graph RAG or citation network visualizations

**Quick Win #4: Paper Quality Control (`is_active` flag)**
* **Objective:** Add ability to exclude papers from search without deleting data (e.g., retracted papers, low quality)
* **Implementation:**
    1. Add `is_active BOOLEAN DEFAULT true` to `pubmed_papers` table
    2. Update semantic search to filter `WHERE is_active = true`
    3. Create admin script to mark papers inactive/active
* **Schema Change:**
    ```sql
    ALTER TABLE pubmed_papers ADD COLUMN is_active BOOLEAN DEFAULT true;
    CREATE INDEX idx_pubmed_papers_is_active ON pubmed_papers(is_active);
    ```
* **Benefit:** Separate ingestion state (`fetch_status`) from inclusion logic (`is_active`), preserves history, easy to reverse
* **Status:** Future enhancement - not required for MVP

#### System Architecture

```
Next.js/React (UI)
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
| **UI** | Next.js 15 + React + TypeScript | Production-ready, modern web stack |
| **Styling** | Tailwind CSS | Rapid UI development, dark theme support |
| **LLM** | Ollama Llama 3.1 8B / OpenAI GPT-4 | Local development / Demo quality (configurable) |
| **Embeddings** | Ollama nomic-embed-text | 768 dims, self-hosted, $0 cost |
| **Vector Store** | Local Postgres + pgvector | Simple, cost-effective, fully local development |
| **Containerization** | Docker + Docker Compose | Local development, Cloud Run deployment |
| **Deployment** | Local Docker / GCP Cloud Run | Local development / Cloud demos only |
| **Evaluation** | RAGAS + Custom Metrics | RAG evaluation, citation accuracy measurement |
| **Data Ingestion** | Cloud Run Jobs | Serverless scheduling, no orchestration overhead |
| **Monitoring** | Cloud Monitoring | Built-in GCP, free tier sufficient |

#### Key Features
1. **React Chat Interface** ✅ *(Complete)*
   - Next.js 15 + TypeScript dark-themed UI
   - Fully mobile-responsive with touch-optimized interactions
   - Collapsible sidebar for conversation management
   - Real-time loading indicators and animations
   - Sticky header and input on mobile
   - See `docs/ui_design.md` for complete design documentation

2. **Conversational RAG Interface** ✅ *(Complete)*
   - Natural language queries about research findings
   - Semantic search over research paper sections (top-20 chunks)
   - LLM synthesis with inline citations [1], [2], etc.
   - Multi-turn conversation support with hybrid retrieval
   - Conversation-wide citation numbering
   - Current performance: 18-40s responses (97% LLM, 3% retrieval)
   - Query rewriting and reranking planned for Phase 2

3. **Verifiable Citations** ✅ *(Complete)*
   - Every claim linked to source paper with sequential numbering
   - Citation cards showing journal, PMC ID, paper title, excerpt
   - Expandable/collapsible citation details
   - Chunk-level citation tracking with immutable Citation objects
   - Click-through to PubMed Central *(Planned Phase 2)*
   - Citation accuracy measurement pending RAGAS evaluation

4. **4-Phase Decoupled Ingestion Pipeline** ✅ *(Complete)*
   - Stage 1: Collect PMC IDs from PubMed searches
   - Stage 2: Fetch and parse full-text papers (JATS XML)
   - Stage 3: Token-based chunking (512 tokens, 50-token overlap) with section-aware processing
   - Stage 4: Generate embeddings with Ollama (free, 768d)
   - Each stage is independently resumable and stores persistent state
   - 52,014 papers fully ingested (1.89M chunks with embeddings)
   - See `docs/ingestion_pipeline.md` for complete architecture

5. **Production Deployment** ✅ *(Complete)*
   - Backend API via Cloudflare Tunnel (self-hosted)
   - Frontend via Vercel (serverless)
   - Database self-hosted via Cloudflare Tunnel
   - Cost: ~$0/month for demo (all self-hosted)

6. **Evaluation & Quality Assurance** ⏳ *(Planned)*
   - RAGAS evaluation framework implementation (next priority)
   - Citation accuracy measurement and tracking
   - Response quality metrics and automated testing
   - Performance benchmarking and optimization

#### Technical Details
- **Document Processing:** 512-token chunks with 50-token overlap, section-based organization
- **Vector Embeddings:** 768 dimensions (Ollama nomic-embed-text)
  - **CRITICAL:** MUST use Ollama 0.11.x (tested on 0.11.11). DO NOT upgrade to 0.12.5 (has regression bug causing EOF errors)
- **Vector Index:** HNSW (m=16, ef_construction=64) for fast similarity search
- **Database Schema:**
  - `pubmed_papers` table: Track PMC IDs and fetch status (supports 4-phase pipeline)
  - `documents` table: Full document content and metadata with ingestion_status tracking
  - `document_chunks` table: Chunked content with VECTOR(768) embeddings
  - UNIQUE(source, source_id) constraint on documents for deduplication
  - JSONB columns for flexible source-specific metadata
  - See `docs/data_design.md` for complete schema documentation
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

**Objective:** Expand the platform's strategic value by integrating clinical trial and regulatory data, enabling users to connect scientific research to real-world product development and corporate strategy.

**Core User Persona:** Brand Manager, Clinical Operations Lead, Management Consultant.

**Key Success Metrics:**
- Successfully support cross-domain queries linking clinical, regulatory, and research data
- Enable multi-step, agentic research workflows for complex questions
- Populate a knowledge graph with over 1 million relationships between drugs, trials, and companies
- Users begin citing OpenPharma insights in internal strategic planning documents

**Target Use Cases:** See `docs/use_cases.md` for detailed Phase 2 use cases covering clinical trial strategy, regulatory intelligence, cross-domain competitive landscape, and agentic workflows.

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

#### Phase 2 Front-End Requirements

**Multi-Source Data Handling:**
- Source Indicators: Citation markers will be visually distinct to differentiate between PubMed, ClinicalTrials.gov, and FDA data sources
- Structured Data Views: Clicking a citation for a clinical trial will open a dedicated, structured view in the side panel showing key fields like Phase, Status, Sponsor, and Endpoints

**Agentic Workflow Visualization:**
- Execution Plan Display: For multi-step queries, the UI will first display the agent's plan (e.g., "Step 1: Identify competitors... Step 2: Analyze trials...")
- Real-time Progress: The UI will visually indicate which step is currently being executed (e.g., with a loading spinner) and which steps are complete (e.g., with a checkmark)

**Optional User Accounts:**
- Introduce an optional, simple account system (e.g., SSO with Google/Microsoft) to enable features like cross-device conversation history
- Cookie-based approach will remain the default for guest users

#### Technical Details
- **Relationship Schema:** Papers ↔ Trials ↔ Drugs ↔ Companies (Postgres JSONB, not Neo4j in Phase 2)
- **Agent Types:** ReAct, Plan-and-Execute, Multi-agent collaboration
- **Neo4j Migration:** Optional Phase 3 upgrade if graph complexity warrants dedicated graph DB
- **Monthly Cost:** $150-400 (multiple data sources + OpenAI API calls)

---

### **Phase 3: Optimized ML Infrastructure (Weeks 13+)**

**Objective:** Transition from a reactive information retrieval tool to a proactive strategic foresight engine by incorporating predictive analytics, unstructured data sources, and optimized, self-hosted models.

**Core User Persona:** Director of Strategy, Business Development & Licensing Lead, Portfolio Manager.

**Key Success Metrics:**
- Achieve an 80% cost reduction for inference through self-hosted models
- Fine-tuned models match or exceed GPT-4 performance on domain-specific tasks
- Platform-generated predictive analytics are used in a client's annual portfolio planning process
- Maintain <100ms inference latency for self-hosted models

**Target Use Cases:** See `docs/use_cases.md` for detailed Phase 3 use cases covering predictive analytics, emerging science analysis, patient voice insights, and financial/corporate strategy linkage.

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

## 3. Future Design Decisions

Implementation decisions are tracked in `docs/decisions.md`. The following are planned for future phases:

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