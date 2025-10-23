# RAG Generation Prompt - Working Version (Commit d091b20)

**Status:** ✅ Working for multi-turn conversations

**Date:** Before hybrid retrieval implementation

**Key Differences from current:**
- Simpler constraints (no "EVERY response" emphasis)
- Simpler examples (no ## Answer/References shown in examples)
- Uses `semantic_search()` only (no hybrid retrieval with historical chunks)
- Uses `messages.extend(conversation_history)` instead of loop

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
Your answer must start with ## Answer
Your references section must start with ## References
CRITICAL: You MUST cite sources using their EXACT [PMC...] identifiers from <Literature> inline in your answer text.
CRITICAL: Do NOT use numbered citations like [1], [2], [3]. ONLY use [PMCxxxxxx] format.

<Correct Examples>
"GLP-1 agonists improve glycemic control [PMC12345678] and reduce cardiovascular risk [PMC87654321]."
</Correct Examples>

<Incorrect Examples>
"GLP-1 agonists improve glycemic control [1] and reduce cardiovascular risk [2]."
"GLP-1 agonists improve glycemic control [PMC12345678] and reduce cardiovascular risk [PMC12345678].
References:
[PMC12345678] ...
[PMC12345678] ..."
</Incorrect Examples>"
```

---

## User Message Format (Turn 1 - No History)

```
<Literature>
Below are the top 5 most relevant literature passages to the user's query. Each passage starts with a unique [source_id].
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

**Conversation History Added via `messages.extend()`:**
```
{'role': 'user', 'content': 'tell me about glp-1s'}
{'role': 'assistant', 'content': '## Answer:\nGLP-1 receptor agonists (GLP-1RAs) are a class of medications...[PMC10552437]...\n## References:\n[PMC10552437]...'}
```

**New User Message:**
```
<Literature>
Below are the top 5 most relevant literature passages to the user's query. Each passage starts with a unique [source_id].
[PMC12182540] Title: Time to Treatment Intensification with Glucagon-Like Peptide-1 Receptor Agonists... | Journal: Diabetes Therapy
[PMC12434700] Title: GLP‐1RA comparative effectiveness against dementia onset... | Journal: Alzheimer's & Dementia
[PMC11976231] Title: Comparative cardiovascular effectiveness of newer glucose-lowering drugs... | Journal: eClinicalMedicine
[PMC11417194] Title: Efficacy and safety of finerenone in individuals with type 2 diabetes... | Journal: Metabolism Open
[PMC8959696] Title: Exercise Interventions Combined With Dietary Supplements... | Journal: Frontiers in Nutrition
</Literature>
User Query: what about DPP4s
```

---

## Code Implementation

```python
def build_messages(user_message: str, chunks: list[SearchResult], top_n: int, conversation_history: Optional[List[dict]]) -> List[dict]:
    messages = []
    messages.append({'role': 'system', 'content': SYSTEM_PROMPT})

    # Add conversation history
    if conversation_history:
        messages.extend(conversation_history)

    # Build literature section
    current_message = f"<Literature>\nBelow are the top {top_n} most relevant literature passages to the user's query. Each passage starts with a unique [source_id].\n"

    for idx, chunk in enumerate(chunks[:top_n], 1):
        cleaned_content = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', chunk.content)
        current_message += f"[PMC{chunk.source_id}] Title: {chunk.title} | {cleaned_content} | Journal: {chunk.journal}\n"

    current_message += f"</Literature>\nUser Query: {user_message}"
    messages.append({'role': 'user', 'content': current_message})

    return messages
```

---

## Retrieval Method

```python
# In generate_response()
chunks = semantic_search(user_message, top_k=top_k)

# Returns only NEW chunks based on current query
# No historical chunks from previous turns
# Always 5 chunks (or top_k value)
```

---

## Observed Behavior

**Turn 1:** ✅ Works correctly
- Generates response with `[PMCxxxxxx]` citations
- Follows `## Answer` and `## References` format
- Citations extracted successfully

**Turn 2:** ✅ Works correctly
- Generates response with `[PMCxxxxxx]` citations
- Follows `## Answer` and `## References` format
- Citations extracted successfully

---

## Key Success Factors

1. **Simpler prompt**: No over-emphasis with "CRITICAL: EVERY"
2. **Simpler examples**: Inline citation example, not full formatted response
3. **Consistent chunk count**: Always top_n chunks (usually 5), no variation between turns
4. **No historical chunks**: Each turn is independent retrieval
5. **Direct history extension**: Uses `messages.extend()` instead of manual loop
