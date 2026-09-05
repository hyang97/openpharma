# 16 - Agentic Retrieval

Design for replacing the chunked-vector-DB RAG with a stateless tool-using agent that
retrieves from live PubMed Central on demand. This document covers the strategic bet, the
validation gate that must pass before committing, the architecture, and the build order.
It is design-only; implementation lives in `agent/`.

## Strategic bet

Move retrieval intelligence from index-time (a static embedding similarity function, fixed
at ingestion) to query-time (a model that writes a precise query, reads results, and answers).
The current system's quality ceiling is set by three static things (the embedding model, the
chunk index, the frozen corpus), none of which reason; the agent's ceiling tracks model
capability and has all of live PMC to work with.

The win is in two places that cannot be faked: **cost** (stateless, no Postgres/pgvector,
no Ollama, no HNSW, so the stopgap VM and the trial project can be torn down) and **scope /
freshness** (any topic, any recently published paper, things the frozen 110K snapshot
structurally cannot answer). The bar on answer quality is **parity**, not improvement.

Mechanism, mapped to the steps it replaces:

| RAG step | Agentic equivalent |
|---|---|
| Embed query, vector search | Model writes one precise PMC query (field-scoped, exact-phrase, or MeSH) |
| Rerank top_k to top_n | Model reads returned results in-context and uses the relevant ones |
| Generate from top_n chunks | Model synthesizes the answer with `[PMCxxxx]` citations |

## Validation gate

The redesign is not committed until it clears a two-stage gate, because the central risk is
that retrieval quality is now the model's job (a self-written query plus NCBI relevance
ranking) instead of a tuned reranker.

1. **Quick spike (directional).** Run a small set through the agent and read the answers:
   roughly 8 to 10 sampled in-corpus PubMedQA questions, the "GLP-1 receptor agonist"
   precision case (the known dense-retrieval failure mode), and 3 to 4 deliberately
   out-of-corpus or recent questions. Check whether it finds the right papers, cites them
   correctly, and reaches the right conclusion.
2. **Full eval (go / no-go).** If the spike holds up, run the 194-question PubMedQA harness
   through the existing MLFlow evaluation. The control must be the current RAG re-run on the
   **same generation model** the agent uses, so retrieval is the only variable; comparing
   against the old local-Llama baseline would conflate the retrieval change with a model
   upgrade. The out-of-corpus set runs alongside to demonstrate the scope gain (the agent
   answers, the current RAG returns nothing).

Decision rule: parity or better on PubMedQA, plus a clear scope win on the out-of-corpus set,
commits the redesign. Commit then settles hosting, the Gemini provider, and VM teardown.

## Architecture

A single retrieval round matching RAG's effort, not an open research loop. The only
provider-specific surface is the model call and how a provider returns a tool call;
everything else is provider-neutral, so that surface is isolated behind a thin seam.

### Provider seam

A small interface isolating the model call, so Anthropic and Gemini are swappable by
configuration. Anthropic (Sonnet 4.6) is implemented for the spike; Gemini drops into the
same interface at commit time. Illustrative contract:

```
ToolCall      = { id: str, name: str, arguments: dict }
LLMResponse   = { text: str | None, tool_calls: list[ToolCall] }

class LLMProvider:
    def generate(self, system: str, messages: list[Message], tools: list[ToolSchema]) -> LLMResponse
```

Normalized, provider-neutral message turns the loop maintains:

```
{ role: "user",      content: str }
{ role: "assistant", content: str }                       # final answer
{ role: "assistant", tool_calls: [ToolCall, ...] }        # tool request
{ role: "tool",      tool_call_id: str, content: str }    # tool result
```

Each adapter renders this history into its native shape and parses native responses back.
Anthropic uses `tool_use` / `tool_result` content blocks; Gemini uses `functionCall` /
`functionResponse` parts.

### Search tool

One provider-neutral function plus a JSON schema the model sees. It searches live PMC,
reusing the existing `PubMedFetcher` (`esearch` over `db=pmc`, relevance sort), then fetches
titles and abstracts for the top candidates in as few calls as possible (a batched fetch,
reusing the XML parser; per-candidate full-text retrieval is avoided here). It returns compact
records, each leading with the PMC ID so citation is direct:

```
search(query: str, max_results: int = 10) -> list[{ pmc_id, title, abstract, journal, authors, year, doi }]
```

The model is responsible for query precision; the tool simply runs what the model writes.
Full-text fetch for a selected paper is the one reserve lever, used only if abstracts prove
too thin to hit parity.

### Bounded loop

The model decides whether to search, may skip it on a context-answerable follow-up, and may
refine once. Searches are capped (about two) so effort stays matched to RAG; on exhausting
the budget the model is asked once more for a final answer with no tools available.

```
answer(question) -> { text, citations }:
    call provider.generate with the search tool
    while the response requests tool calls and budget remains:
        run search, append the result, call generate again
    return the final text
```

### Synthesis

The system prompt adapts the existing pharma-researcher framing and the strict citation rules
from `app/rag/generation.py`: cite sources by their exact `[PMCxxxx]` identifier inline, and
answer "No sufficient evidence" when searches return nothing relevant.

## Build order

Each step is implemented manually and reviewed before the next. The concrete Anthropic loop
comes first; the provider abstraction is extracted once its message and tool-call shapes are
known, rather than designed against guesses.

1. Tool-use loop against Anthropic with a stub search tool (hardcoded results) and the system
   prompt. Verify the loop round-trips and citations render.
2. Real search tool: NCBI `esearch` plus the batched abstract fetch, returning compact records.
   Verify standalone on a query.
3. Wire the real search into the loop. Verify one question end-to-end.
4. Extract the provider seam (the types, `LLMProvider`, and the Anthropic adapter) so a second
   provider can drop in later. Verify the same question still works through it.
5. Spike runner and question set. Run and read the answers.
6. If promising, wire the agent into the MLFlow harness for the full eval.

## Deferred (not in the spike)

- Gemini adapter (the seam is ready; implemented at commit).
- Full-text fetch (reserve lever only).
- Hosting decision (Cloud Run versus the shared e2-micro) and tunnel / Vercel wiring.
- MCP exposure (a thin adapter over the same functions, added later only if a Claude Desktop
  or Phase 2 multi-domain need appears).
- Multi-turn conversation, query rewriting, and integration with the existing API and UI.
- Cost tiering (a cheaper planner or Haiku synthesis), revisited after parity is proven.
