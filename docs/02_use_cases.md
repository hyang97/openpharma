# Target Use-Cases

## Phase 1: Research Literature Intelligence MVP

**Objective:** To validate the core value proposition by delivering a fast, reliable, and transparent conversational interface for querying published medical research. The focus is on perfecting the core user experience and building trust.
**Core User Persona:** Competitive Intelligence Analyst, R&D Strategist, Management Consultant.
**Job-to-be-Done:** "Help me quickly understand the current scientific evidence and key players in a therapeutic area to inform my strategic analysis."
**Key Data Source:** PubMed Central.
**Key Success Metrics:**
- Reduce the time to generate a competitor pipeline analysis from 8 hours (manual) to under 10 minutes.
- Attain an 80%+ query satisfaction rate.
- Ensure 95%+ citation accuracy for all generated statements.


### Phase 1 Target Use Cases

**Comparative Efficacy & Safety Analysis:**
- "Summarize the latest efficacy and safety data from studies published in the last 18 months for SGLT2 inhibitors versus GLP-1 agonists in treating Type 2 Diabetes with associated cardiovascular risk." (Starting point)
- "Summarize the reported efficacy of metformin compared to sulfonylureas in treatment-naive Type 2 diabetes patients from studies published in the last 3 years."
- "Create a table comparing the primary endpoints and outcomes of studies for [Competitor Drug A] and [Competitor Drug B]." (Tests data extraction and structuring)
- "What are the most commonly reported adverse events associated with GLP-1 therapies for type 2 diabetes in recent literature?"

**Mechanism of Action (MoA) & Biomarker Intelligence:**
- "What are the most commonly discussed biomarkers for predicting diabetic nephropathy in recent literature?" (Helps inform clinical trial design and market segmentation)
- "What novel mechanisms of action are being investigated for treating type 1 diabetes, based on papers from the last 24 months?"

**Key Opinion Leader (KOL) & Institutional Mapping:**
- "Which institutions are leading research on islet cell transplantation based on the number of publications?" (Identifies potential collaborators, competitors, and market influencers)
- "Who are the most frequently published authors from the Joslin Diabetes Center in the last 5 years?"

**Unmet Needs & Research Gaps:**
"Based on the discussion sections of recent review articles, what are the stated limitations and unmet needs in managing gestational diabetes?" (Directly informs strategy and opportunity analysis)


### Phase 1 Front-End Requirements

**Session Management:**
- No Accounts: The application will not require user registration or login.
- Cookie-Based History: Conversation history will be managed on a per-browser basis using cookies and localStorage. A disclaimer will inform the user that history is device-specific.

**Layout:**
- Two-Panel Interface: A clean layout with a persistent, locally-stored conversation history on the left and the main query/response workspace on the right.

**Core Interaction:**
- Query Input: A prominent, multi-line text input bar.
- Response Display: The workspace must render Markdown, including properly formatted lists, bold/italic text, and tables.
- Loading State: Clear visual feedback (e.g., "Searching PubMed...", "Synthesizing results...") must be displayed while the backend processes a query.

**Citations:**
- Inline Markers: Every assertion in the text must be accompanied by a non-intrusive citation marker (e.g., [1]).
- Interactive Sources: Hovering over a marker reveals a pop-over with source details (title, author, journal). Clicking the marker pins the full abstract and a direct source link in a side panel.

**Utilities:**
- Copy & Export: One-click functionality to copy the response to the clipboard or export the full conversation as a PDF or Markdown file.
- New Session: A button to clear the local session history and start a new conversation.

## Phase 2: Multi-Domain Intelligence Platform

**Objective:** To expand the platform's strategic value by integrating clinical trial and regulatory data, enabling users to connect scientific research to real-world product development and corporate strategy.
**Core User Persona:** Brand Manager, Clinical Operations Lead, Management Consultant.
**Job-to-be-Done:** "Help me connect the dots between scientific research, ongoing clinical trials, and regulatory approvals to build a complete competitive picture."
**Key Data Sources:** PubMed Central, ClinicalTrials.gov, FDA Drug Labels.
**Key Success Metrics:**
- Successfully support cross-domain queries linking clinical, regulatory, and research data.
- Enable multi-step, agentic research workflows for complex questions.
- Populate a knowledge graph with over 1 million relationships between drugs, trials, and companies.
- Users begin citing OpenPharma insights in internal strategic planning documents.


### Phase 2 Target Use Cases

**Clinical Trial Strategy & Design Analysis:**
- "For all ongoing Phase 3 trials for PD-1 inhibitors in oncology, what are the primary endpoints and estimated enrollment numbers? Display the results in a table." (Directly leverages ClinicalTrials.gov)
- "Compare the inclusion/exclusion criteria for Amgen's pivotal trials for their KRAS G12C inhibitor against Mirati Therapeutics' trials." (A high-value competitive analysis)
- "Which therapies first discussed in research papers in 2022 have now progressed to Phase 1 or Phase 2 clinical trials?" (Shows research-to-market velocity)

**Regulatory & Label Expansion Intelligence:**
- "Summarize the approved indications for Keytruda from its FDA label. Then, find all ongoing trials that could support a label expansion." (Combines FDA data with ClinicalTrials.gov for a forward-looking view)
- "What were the key clinical trials cited in the FDA approval package for [Newly Approved Drug]?"

**Cross-Domain Competitive Landscape:**
- "Generate a profile for [Competitor Company]'s diabetes portfolio. Include their approved drugs, active clinical trials, and recent publications from their researchers." (This is a true multi-source synthesis, your "on-demand analyst")
- "A recent paper mentions a novel compound for treating obesity. Are there any active clinical trials for this compound, and who is the sponsor?" (Connects a scientific signal to a corporate actor)

**Agentic / Multi-Step Workflows:**
- "First, identify the top 3 competitors to our lead asset in heart failure. Second, summarize their ongoing clinical trial strategies. Third, highlight any significant efficacy or safety data they have published recently." (Demonstrates the power of LangGraph)


### Phase 2 Front-End Requirements

**Multi-Source Data Handling:**
- Source Indicators: Citation markers will be visually distinct (e.g., icons) to differentiate between PubMed, ClinicalTrials.gov, and FDA data sources.
- Structured Data Views: Clicking a citation for a clinical trial will open a dedicated, structured view in the side panel showing key fields like Phase, Status, Sponsor, and Endpoints.

**Agentic Workflow Visualization:**
- Execution Plan Display: For multi-step queries, the UI will first display the agent's plan (e.g., "Step 1: Identify competitors... Step 2: Analyze trials...").
- Real-time Progress: The UI will visually indicate which step is currently being executed (e.g., with a loading spinner) and which steps are complete (e.g., with a checkmark).

**Optional User Accounts:**
- Introduce an optional, simple account system (e.g., SSO with Google/Microsoft) to enable features like cross-device conversation history. The cookie-based approach will remain the default for guest users.


## Phase 3: Optimized ML Infrastructure & Predictive Analytics

**Objective:** To transition from a reactive information retrieval tool to a proactive strategic foresight engine by incorporating predictive analytics, unstructured data sources, and optimized, self-hosted models.
**Core User Persona:** Director of Strategy, Business Development & Licensing Lead, Portfolio Manager.
**Job-to-be-Done:** "Help me anticipate market shifts, identify future opportunities, and de-risk my strategic bets with predictive, data-driven insights."
**Key Data Sources:** All previous sources, plus USPTO (patents), NIH RePORTER (funding), SEC filings, and potentially unstructured data from patient forums.
**Key Success Metrics:**
- Achieve an 80% cost reduction for inference through self-hosted models.
- Fine-tuned models match or exceed GPT-4 performance on domain-specific tasks.
- Platform-generated predictive analytics are used in a client's annual portfolio planning process.
- Maintain <100ms inference latency for self-hosted models.


### Phase 3 Target Use Cases

**Predictive Analytics & Event Forecasting:**
- "Identify key patents for Humira expiring in the next five years. Which companies have biosimilars in late-stage development, and what is their trial status?" (Combines USPTO data with ClinicalTrials.gov)
- "Based on ongoing Phase 3 trial completion dates, create a timeline of expected data readouts and potential regulatory submissions for key competitors in the Alzheimer's market over the next 18 months."

**Emerging Science & "White Space" Opportunity Analysis:**
- "Which therapeutic modalities for oncology are receiving the most NIH funding but have the fewest assets in clinical trials?" (Identifies areas ripe for investment or partnership by combining NIH RePORTER with ClinicalTrials.gov)
- "Summarize the key findings from abstracts presented at last year's ASCO conference regarding antibody-drug conjugates. Which of these have since initiated new clinical trials?"

**Patient Voice & Unmet Needs Analysis:**
- "Analyze discussions on patient forums for atopic dermatitis. What are the most common complaints about current treatments, and what unmet needs are most frequently mentioned?" (Leverages unstructured patient data to inform product development)

**Financial & Corporate Strategy Linkage:**
- (Optional, uses SEC filings) "In their latest 10-K filing, what strategic priorities did [Competitor Company] state for their immunology franchise? How does this align with their recent clinical trial initiations and research publications?" (Provides a 360-degree view of competitor strategy)

