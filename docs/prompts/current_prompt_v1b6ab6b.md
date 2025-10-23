# RAG Generation Prompt - Current Version (Commit 1b6ab6b)

**Status:** Not working for multi-turn conversations (no citations after turn 1)

**Date:** 2025-10-22

**Changes from previous version:**
- Added "CRITICAL: EVERY response" emphasis
- Added explicit prohibition of "Step 1, Step 2" format
- Changed "must start" to "MUST start"
- Added more detailed examples with ## Answer and ## References format

---

## System Prompt

```
<Task Context>
This is the generation step of a retrieval-augmented generation (RAG) workflow that powers OpenPharma, an AI-powered research & insights product.
Users can ask questions in natural language and receive instant answers, transforming a multi-day research process into a matter of minutes in a chat-based interface.
Users may be competitive intelligence analysts, commercial strategists, brand managers, pharma consultants, etc. to inform business decisions.
</Task Context>

<Role Context>
You are an expert pharmaceutical researcher.
Your role is to synthesize findings from scientific literature for life sciences companies & consultants, providing answers that are backed by credible evidence and verifiable citations.
</Role Context>

<Task Description>
Query and Synthesize Scientific Literature: Users may ask questions about drug efficacy, safety, mechanisms of action, key opinion leaders, etc.
You will review scientific literature passages in <Literature> in order to answer the user's query.
You will think through step-by-step to pull in relevant details from <Literature> to support the answer. Reflect on your confidence in your answer based on the relevance, completeness, and consistency of the provided <Literature>.
You will respond concisely, summarizing the main answer, and providing supporting details from <Literature> with citations.
</Task Description>

<Constraints>
If there is insufficient information, your response must be **No sufficient evidence**
Your response must include only the response to the user's message.
Your answer must be based exclusively on the content provided in <Literature>.
CRITICAL: EVERY response MUST start with: ## Answer
CRITICAL: EVERY response MUST include a references section starting with: ## References
CRITICAL: You MUST cite sources using their EXACT [PMC...] identifiers from <Literature> inline in your answer text.
CRITICAL: Do NOT use numbered citations like [1], [2], [3]. ONLY use [PMCxxxxxx] format.
CRITICAL: Do NOT deviate from this format. Do NOT use "Step 1", "Step 2" or any other format.
</Constraints>

<Correct Examples>
"
## Answer:
GLP-1 agonists improve glycemic control [PMC12345678] and reduce cardiovascular risk [PMC87654321].
## References:
[PMC12345678] ...
[PMC12345678] ...
"
</Correct Examples>

<Incorrect Examples>
"GLP-1 agonists improve glycemic control [1] and reduce cardiovascular risk [2]."
"GLP-1 agonists improve glycemic control [PMC12345678] and reduce cardiovascular risk [PMC12345678].
Notes:
[PMC12345678] ...
[PMC12345678] ..."
</Incorrect Examples>"
```

---

## User Message Format (Turn 1 - No History)

```
<Literature>
Below are the top 5 most relevant literature passages to the user's query, as well as recently cited literature. Each passage starts with a unique [source_id].
[PMC10552437] Title: Chronic kidney outcomes associated with GLP-1 receptor agonists versus long-acting insulins among type 2 diabetes patients requiring intensive glycemic control: a nationwide cohort study | Our exploratory analyses identified CVD history and the MPR of prior oral GLAs as potential effect modifiers... | Journal: Cardiovascular Diabetology
[PMC9504435] Title: Comparison of Glucose-Lowering Drugs as Second-Line Treatment for Type 2 Diabetes: A Systematic Review and Meta-Analysis | therapies, with 2 hPG reductions ranging from 0.76 mmol/L... | Journal: Journal of Clinical Medicine
[PMC8434700] Title: The participatory development of a national core set of person-centred diabetes outcome constructs for use in routine diabetes care across healthcare sectors | diabetes were interviewed using the same research questions... | Journal: Research Involvement and Engagement
[PMC8959696] Title: Exercise Interventions Combined With Dietary Supplements in Type 2 Diabetes Mellitus Patients—A Systematic Review of Relevant Health Outcomes | 198 Men (126) and women (72)... | Journal: Frontiers in Nutrition
[PMC9504435] Title: Comparison of Glucose-Lowering Drugs as Second-Line Treatment for Type 2 Diabetes: A Systematic Review and Meta-Analysis | ) with GLP-1RAs+MET vs. TZDs+MET... | Journal: Journal of Clinical Medicine
</Literature>
User Query: tell me about glp-1s
```

---

## User Message Format (Turn 2 - With History)

**Conversation History Added:**
```
{'role': 'user', 'content': 'tell me about glp-1s'}
{'role': 'assistant', 'content': '## Answer:\nGLP-1 receptor agonists (GLP-1RAs) are a class of medications used to treat type 2 diabetes [PMC10552437]...\n## References:\n[PMC10552437] ...\n[PMC9504435] ...'}
```

**New User Message:**
```
<Literature>
Below are the top 9 most relevant literature passages to the user's query, as well as recently cited literature. Each passage starts with a unique [source_id].
[PMC12232352] Title: Long‐term outcomes following alternative second‐line oral glucose‐lowering treatments... | Journal: Diabetes, Obesity & Metabolism
[PMC12399455] Title: Treatment Preferences for Novel Type 2 Diabetes Oral Medications... | Journal: Diabetes Therapy
[PMC11006598] Title: The association between sodium glucose cotransporter‐2 inhibitors vs dipeptidyl peptidase‐4 inhibitors... | Journal: Journal of Diabetes
[PMC9576049] Title: Comparison of cardiovascular and renal outcomes between dapagliflozin and empagliflozin... | Journal: PLoS ONE
[PMC8841312] Title: Risk of lower extremity amputations in patients with type 2 diabetes... | Journal: Acta Diabetologica
[PMC7173685] Title: Dipeptidyl peptidase-4 inhibitors and the risks of autoimmune diseases... | Journal: Acta Diabetologica
[PMC8929338] Title: Risk of genital and urinary tract infections associated with SGLT‐2 inhibitors... | Journal: Pharmacology Research & Perspectives
[PMC11235957] Title: Glucagonlike peptide‐1 receptor agonists versus dipeptidyl peptidase‐4 inhibitors... | Journal: European Journal of Neurology
[PMC10613530] Title: Safety of sodium-glucose transporter 2 (SGLT-2) inhibitors... | Journal: Frontiers in Pharmacology
</Literature>
User Query: how do SGLT2s compare to DPP4s for T2D?
```

---

## Observed Behavior

**Turn 1:** ✅ Works correctly
- Generates response with `[PMCxxxxxx]` citations
- Follows `## Answer` and `## References` format
- Citations extracted successfully

**Turn 2:** ❌ Fails
- LLM generates response WITHOUT any `[PMCxxxxxx]` citations
- Does NOT follow `## Answer` format
- Generates generic response with bullet points and headers
- 0 citations extracted

**Example Turn 2 Response (Bad):**
```
Sodium-glucose cotransporter 2 (SGLT2) inhibitors and dipeptidyl peptidase-4 (DPP4) inhibitors are two classes of medications used to treat type 2 diabetes mellitus (T2DM). Here's a summary of how they compare:

**Similarities:**
* Both SGLT2is and DPP4is are oral antidiabetic drugs.
* They can be used as monotherapy or in combination with other medications...

**Differences:**
* **Mechanism of action:** SGLT2is work by inhibiting the reabsorption...
...
```

---

## Retrieval Method

- Using `hybrid_retrieval()` which combines semantic search + historical chunks
- Turn 1: 5 new chunks, 0 historical
- Turn 2: 5 new chunks, 4 historical chunks (9 total)

---

## Hypothesis

The Llama 3.1 8B model may be struggling with:
1. Seeing previous `## Answer` / `## References` format in conversation history confuses it
2. Model not powerful enough to maintain complex formatting across multi-turn conversations
3. Increased context (9 chunks vs 5) may be overwhelming the model
