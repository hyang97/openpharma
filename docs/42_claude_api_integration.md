# 42. Claude API Integration and Evaluation

## Goal

Add Claude (Anthropic) as an LLM provider alongside Ollama, then run the 194-question PubMedQA eval to get a head-to-head comparison: Llama 3.1 8B vs Claude Sonnet.

## Baseline (Llama 3.1 8B + reranking)

| Metric | Score |
|---|---|
| Conclusion Match | 75.8% (147/194) |
| Reasoning Match | 79.9% (155/194) |
| Retrieval Accuracy | 83.5% (162/194) |
| Citation Validity | 98.2% |
| Avg Faithfulness | 4.8/5 |
| Avg Response Time | 38.6s |

---

## Task 1: Add `anthropic` dependency

**File: `requirements.txt`**

Add:
```
anthropic>=0.42.0
```

Then rebuild the Docker image:
```bash
docker-compose build api
```

---

## Task 2: Add env vars to docker-compose.yml

**File: `docker-compose.yml`**

Add two env vars to the `api` service `environment` list:

```yaml
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_MODEL=${ANTHROPIC_MODEL}
```

**File: `.env`**

Add:
```
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
```

---

## Task 3: Implement Claude path in `generate_response()`

**File: `app/rag/generation.py`**

This is the core change. The Anthropic API differs from Ollama in one key way: the system message is a top-level parameter, not part of the messages array.

### 3a. Add import and model config (top of file)

```python
import anthropic

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
```

### 3b. Add helper to convert messages for Claude

The existing `build_messages()` returns `[{"role": "system", ...}, {"role": "user", ...}, ...]`.
Claude needs system as a separate param and messages without the system entry.

```python
def _split_system_message(messages: List[dict]) -> tuple[str, List[dict]]:
    """Extract system message from messages list for Anthropic API."""
    system_content = ""
    chat_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            chat_messages.append(msg)
    return system_content, chat_messages
```

### 3c. Replace the `else` branch in `generate_response()`

Current code (lines 236-239):
```python
        else:
            # TODO: Add OpenAI integration later
            logger.warning("OpenAI integration requested but not implemented")
            raise HTTPException(status_code=501, detail="OpenAI integration not yet implemented")
```

Replace with:
```python
        else:
            llm_start = time.time()
            logger.info(f"Using model: {ANTHROPIC_MODEL}")
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            system_content, chat_messages = _split_system_message(messages)
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                system=system_content,
                messages=chat_messages
            )
            llm_time = (time.time() - llm_start) * 1000
            logger.info(f"LLM generation time: {llm_time:.0f}ms")
            return response.content[0].text
```

### 3d. Refactor `generate_response_stream()` to swap token source, not duplicate state machine

The streaming state machine (preamble buffer, answer detection, references lookahead) is the same regardless of provider. Only the token source differs. Refactor so the provider choice produces a `token_iter()`, then the existing loop consumes it.

**Replace lines 130-161** (the early return + message building + Ollama stream setup + token extraction inside loop):

```python
    # Build messages
    messages = build_messages(user_message, chunks, conversation_history)

    # Create token iterator based on provider
    if use_local:
        client = ollama.Client(host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        raw_stream = client.chat(model=OLLAMA_MODEL, messages=messages, stream=True, options={'keep_alive': -1})
        def token_iter():
            for chunk in raw_stream:
                token = chunk.get('message', {}).get('content')
                if token:
                    yield token
    else:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        system_prompt, chat_messages = _extract_system_message(messages)
        def token_iter():
            with client.messages.stream(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=chat_messages
            ) as stream:
                yield from stream.text_stream
```

**Then replace the loop header and token extraction** (the `for chunk in stream:` + empty check + `token = chunk['message']['content']` lines) with just:

```python
    for token in token_iter():
```

The rest of the state machine (preamble_buffer, streaming_started, lookahead_buffer, etc.) stays exactly as-is. No other changes needed.

---

## Task 4: Fix eval runner for `user_id` (required since anonymous sessions)

The eval runner calls `/chat` but the `UserRequest` model now requires `user_id`. The eval was last run before this field was added.

**File: `evals/run_mlflow.py`**

In `RAGEvaluator.predict()`, update the payload (around line 64):

Also add `use_local` to the payload so the eval can control which model is used. Combined update:

```python
                payload = {
                    "user_message": row['question'],
                    "user_id": f"eval-{self.config.run_id}",
                    "use_local": self.config.use_local,
                    "use_reranker": True,
                    "additional_chunks_per_doc": 20
                }
```

---

## Task 5: Add `use_local` flag to EvaluationConfig

**File: `evals/core/schemas.py`**

Add to `EvaluationConfig`:
```python
    use_local: bool = True
```

---

## Task 6: Add `--use-claude` CLI flag to eval runner

**File: `evals/run_mlflow.py`**

In `main()`, add the arg (around line 211):
```python
    parser.add_argument("--use-claude", action="store_true", help="Use Claude API instead of Ollama")
```

Pass it to config (around line 214):
```python
    config = EvaluationConfig(
        experiment_name=args.experiment,
        run_id=args.run,
        dataset_path=args.dataset,
        rag_endpoint=args.endpoint,
        limit=args.limit,
        use_local=not args.use_claude
    )
```

Update the model param logging (around line 249):
```python
        if config.use_local:
            mlflow.log_param("model", os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
        else:
            mlflow.log_param("model", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"))
```

---

## Task 7: Test locally before full eval

### Quick sanity check (1 question)

```bash
# Rebuild container with anthropic dependency
docker-compose build api
docker-compose up -d api

# Test Claude via curl (non-streaming)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "What are the latest findings on GLP-1 agonists?",
    "user_id": "test",
    "use_local": false,
    "use_reranker": true
  }'

# Test Claude streaming
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "What are the latest findings on GLP-1 agonists?",
    "user_id": "test",
    "use_local": false,
    "use_reranker": true
  }'
```

### Quick eval test (5 questions)

```bash
docker-compose exec api python -m evals.run_mlflow \
  --experiment claude_vs_llama \
  --run claude_sonnet_test \
  --use-claude \
  --limit 5
```

Check the output looks right before running the full eval.

---

## Task 8: Run full Claude eval (194 questions)

Estimated cost: ~$2-5 (194 questions x ~2K input tokens x ~500 output tokens at Sonnet pricing).
Estimated time: ~15-30 min (API latency, no local GPU bottleneck).

```bash
docker-compose exec api python -m evals.run_mlflow \
  --experiment claude_vs_llama \
  --run claude_sonnet_v1 \
  --use-claude
```

This produces:
- `logs/eval_results/claude_vs_llama/claude_sonnet_v1_auto_results.json` (automated metrics)
- `logs/eval_results/claude_vs_llama/claude_sonnet_v1_llm_judge_prompt.md` (for LLM-as-judge)

### Automated metrics you get immediately:
- Retrieval accuracy (should be ~identical since same retrieval pipeline)
- Citation validity
- Response time

---

## Task 9: Run LLM-as-judge on Claude results

Same manual process as before:
1. Open Google AI Studio
2. Enable JSON mode, paste schema from `evals/core/llm_judge_structured_output.json`
3. Paste the prompt from `logs/eval_results/claude_vs_llama/claude_sonnet_v1_llm_judge_prompt.md`
4. Save JSON output as `logs/eval_results/claude_vs_llama/claude_sonnet_v1_llm_judge_results.json`
5. Merge:

```bash
docker-compose exec api python -m evals.merge_auto_and_judge \
  --experiment claude_vs_llama \
  --run claude_sonnet_v1
```

---

## Expected Results

Retrieval accuracy should be identical (~83.5%) since the retrieval pipeline is unchanged.

Where Claude should improve:
- **Conclusion match on NO questions**: Llama 8B has positivity bias (73% on NO vs 80% on YES). Claude should handle null findings better.
- **Reasoning quality**: Better nuanced reasoning on MAYBE questions (Llama was 62.5%).
- **Response time**: Likely faster (8-15s API vs 35s+ local Llama 8B).
- **Citation format compliance**: Claude tends to follow structured output instructions well.

Realistic targets:
- Conclusion match: 75.8% -> 82-88%
- Reasoning match: 79.9% -> 85-90%
- Response time: 38.6s -> 8-15s

---

---

## Task 10: Add suggested questions to landing page

Add an expand/collapse panel of demo-ready questions to the empty state landing page. Questions are organized by pharma business function and designed to produce excellent responses from the 52K diabetes + 58.7K historical corpus.

### Final 6 questions (tested and validated)

Selected from 28 candidates across diabetes and non-diabetes topics. Ranked by response quality (citation count, specificity, structure, accuracy).

**Competitive Intelligence**

1. "What are the latest findings on statin therapy for primary and secondary prevention of cardiovascular disease?"
   - 2 citations, names JUPITER and SPARCL trials, discusses pleiotropic effects
2. "What mechanisms of resistance to immune checkpoint inhibitors have been identified in cancer research?"
   - 2 citations, structured innate vs acquired breakdown, specific genes (B2M, JAK/STAT, WNT)

**R&D Strategy**

3. "What neuroprotective mechanisms have been proposed for metformin in recent studies?"
   - 3 citations, numbered list of 5 mechanisms (AMPK, SIRT-1, ROS). Best answer of all 28 tested.
4. "What are the emerging approaches to combat antimicrobial resistance?"
   - 3 citations, specific approaches (ARBs, plant extract synergy, adjuvants)

**Clinical Development**

5. "How has CRISPR gene editing technology been applied in therapeutic development?"
   - 2 citations, mentions first human trial (China 2016), clinical trial overview
6. "What biomarkers are being used to predict response to cancer immunotherapy?"
   - 2 citations, specific (TMB, TIGS, radiomic biomarkers)

### 10a. Add `directMessage` param to `processMessage` in useChat

**File: `ui/src/hooks/useChat.ts`**

The problem: clicking a suggested question needs to set input AND send in the same handler. But `processMessage()` reads `input` from React state, and `setInput()` is async. We need a way to pass the message directly.

Update `processMessage` signature and first few lines:

```typescript
const processMessage = (useStreamingOverride?: boolean, directMessage?: string) => {
    const messageText = directMessage || input
    if (messageText.trim() === '' || isLoading(currConversationId)) return

    // ... rest of function uses messageText instead of input
```

Then replace all references to `input` inside `processMessage` with `messageText`:
- `const user_input = messageText` (was `const user_input = input`)
- Keep `setInput('')` as-is (still clears the input field)

---

### 10b. Create `SuggestedQuestions` component

**File: `ui/src/components/SuggestedQuestions.tsx`** (new file)

Component structure:
- Props: `onSelectQuestion: (question: string) => void`
- Internal state: `isExpanded: boolean` (default `false`)
- Toggle button: "Explore example questions" with chevron that rotates
- Panel: slides open/closed with CSS transition (use existing `animate-slide-down` from globals.css or CSS max-height transition)
- Categories: uppercase label in `text-xs font-semibold uppercase tracking-wide text-slate-400`
- Question cards: `bg-slate-800 border border-slate-700 rounded-lg` with hover state `hover:border-accent`
- Arrow icon on each card (top-right arrow character)
- On click: call `onSelectQuestion(questionText)`

Question data: define as a const array at the top of the file:

```typescript
const SUGGESTED_QUESTIONS = [
  {
    category: "Competitive Intelligence",
    questions: [
      "What are the latest findings on statin therapy for primary and secondary prevention of cardiovascular disease?",
      "What mechanisms of resistance to immune checkpoint inhibitors have been identified in cancer research?",
    ]
  },
  {
    category: "R&D Strategy",
    questions: [
      "What neuroprotective mechanisms have been proposed for metformin in recent studies?",
      "What are the emerging approaches to combat antimicrobial resistance?",
    ]
  },
  {
    category: "Clinical Development",
    questions: [
      "How has CRISPR gene editing technology been applied in therapeutic development?",
      "What biomarkers are being used to predict response to cancer immunotherapy?",
    ]
  }
]
```

---

### 10c. Wire into landing page

**File: `ui/src/app/page.tsx`**

Import the component and add it between the ChatInput and the disclaimer (inside the empty state block, lines 47-69).

```tsx
import { SuggestedQuestions } from "@/components/SuggestedQuestions"
```

Add handler:
```tsx
const handleSuggestedQuestion = (question: string) => {
    chat.setInput(question)
    chat.processMessage(undefined, question)
}
```

Add component below ChatInput in the empty state (after the `<div className="w-full max-w-3xl">` block):
```tsx
<div className="w-full max-w-3xl mt-4">
    <SuggestedQuestions onSelectQuestion={handleSuggestedQuestion} />
</div>
```

---

## Task 11: Fix hallucinated citation numbers leaking into responses

The LLM sometimes copies reference numbers from the original paper text (e.g., `[3-5]`, `[6-11]`) into its response. These don't match the `[PMCxxxxx]` format, so they pass through the citation pipeline untouched and appear as broken references in the frontend.

### Root cause

In `build_messages()`, chunk content is cleaned with:
```python
cleaned_content = re.sub(r'\[\d+(?:,\s*\d+)*\]', '', chunk.content)
```

This catches `[1]`, `[2,3]` but **not** range citations like `[3-5]` or `[6-11]`.

### 11a. Pre-LLM: Expand citation stripping regex in `build_messages()`

**File: `app/rag/generation.py`**

Update the regex in `build_messages()` to also strip range and mixed citations:

```python
cleaned_content = re.sub(r'\[[\d,\s\-]+\]', '', chunk.content)
```

This catches all numeric citation patterns: `[1]`, `[2,3]`, `[3-5]`, `[6-11]`, `[1,3-5,8]`.

### 11b. Post-LLM safety net: Strip unmatched number brackets in `prepare_messages_for_display()`

**File: `app/rag/response_processing.py`**

After the existing `[PMCxxxxx]` -> `[N]` replacement in `prepare_messages_for_display()`, add a cleanup pass that strips any remaining bare number brackets that don't correspond to a real citation number:

```python
# After PMC replacement, strip any remaining bare number citations
# that weren't part of our citation system (leaked from source papers)
valid_numbers = set(str(n) for n in pmc_to_number.values())
def strip_invalid_citation(match):
    nums_in_bracket = re.findall(r'\d+', match.group(0))
    if any(n in valid_numbers for n in nums_in_bracket):
        return match.group(0)  # Keep - contains a valid citation
    return ''  # Strip - all numbers are invalid

content = re.sub(r'\[[\d,\s\-]+\]', strip_invalid_citation, content)
```

This preserves valid citations like `[1]`, `[2]` while stripping leaked references like `[3-5]`, `[6-11]`.

---

## Summary of files to change

| File | Change |
|---|---|
| `requirements.txt` | Add `anthropic>=0.42.0` |
| `.env` | Add `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| `docker-compose.yml` | Pass through two new env vars |
| `app/rag/generation.py` | Add Claude in `generate_response()` and `generate_response_stream()` |
| `evals/core/schemas.py` | Add `use_local` field to `EvaluationConfig` |
| `evals/run_mlflow.py` | Add `user_id` to payload, add `--use-claude` flag, pass `use_local` |
| `ui/src/hooks/useChat.ts` | Add `directMessage` param to `processMessage` |
| `ui/src/components/SuggestedQuestions.tsx` | New component with expand/collapse question panel |
| `ui/src/app/page.tsx` | Wire `SuggestedQuestions` into empty state landing page |
| `app/rag/generation.py` | Expand citation stripping regex in `build_messages()` |
| `app/rag/response_processing.py` | Strip unmatched number brackets in `prepare_messages_for_display()` |
