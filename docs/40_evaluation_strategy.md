# Evaluation Strategy

## Overview

Evaluate RAG performance using PubMedQA golden dataset (194 expert-labeled questions) with RAGAS framework + custom metrics.

**Goal**: Compare config changes (reranking, models, prompts) to make data-driven decisions.

## Golden Dataset

**Source**: `data/golden_eval_set.csv` (194 questions from PubMedQA expert-labeled subset)

**Format**: Single-paper yes/no/maybe questions with ground truth
- `question_id`, `pmid`, `pmc_id`: Identifiers
- `question`: "Do mitochondria play a role in remodelling lace plant leaves during programmed cell death?"
- `expected_answer`: "yes" / "no" / "maybe" ← **Reference answer for answer correctness**
- `long_answer`: Full expert explanation ← **Reference answer for RAGAS metrics**
- `year`, `meshes`, `num_contexts`: Metadata

**Coverage**: All 194 papers fully ingested and searchable

**Reference Answers Available**:
- ✅ `expected_answer` (yes/no/maybe) - For simple answer correctness checking
- ✅ `long_answer` (expert explanation) - For RAGAS Context Recall, Answer Correctness, BLEU/ROUGE

## Evaluation Metrics

### Phase 1: Custom Metrics (Start Here - Pure Python, No Dependencies)

| Metric                             | Requires Ground Truth? | What We Have        | Implementation |
|------------------------------------|------------------------|---------------------|----------------|
| Answer Correctness (yes/no/maybe)  | ✅ Yes                 | `expected_answer`   | Phase 1        |
| Citation Hallucination             | ❌ No                  | -                   | Phase 1        |
| Citation Coverage                  | ❌ No                  | -                   | Phase 1        |
| Response Time                      | ❌ No                  | -                   | Phase 1        |

### Phase 2: RAGAS Traditional Metrics (Add After Phase 1 Works)

| Metric                             | Requires Ground Truth? | What We Have        | Implementation |
|------------------------------------|------------------------|---------------------|----------------|
| BLEU Score                         | ✅ Yes                 | `long_answer`       | Phase 2        |
| ROUGE Score                        | ✅ Yes                 | `long_answer`       | Phase 2        |
| CHRF Score                         | ✅ Yes                 | `long_answer`       | Phase 2        |

### Phase 3: Manual LLM-as-Judge (Optional - For Qualitative Analysis)

| Metric                             | Requires Ground Truth? | What We Have        | Implementation |
|------------------------------------|------------------------|---------------------|----------------|
| Faithfulness                       | ❌ No                  | -                   | Manual review  |
| Answer Relevance                   | ❌ No                  | -                   | Manual review  |
| Context Precision                  | ❌ No                  | -                   | Manual review  |
| Context Recall                     | ✅ Yes                 | `long_answer`       | Manual review  |

**Implementation Strategy**: Build incrementally, validate each phase before adding complexity

## Implementation Phases

### Phase 1: Core Evaluation Loop (Start Here)

**`tests/run_eval.py`** - Custom metrics only
```bash
python tests/run_eval.py --run reranking_test --version baseline --limit 5

# Does:
# 1. Load data/golden_eval_set.csv
# 2. For each question: call /chat, extract answer + citations + timing
# 3. Calculate: answer correctness, citation hallucination, response time
# 4. Save to logs/results/reranking_test/baseline.json
```

**`tests/compare_evals.py`** - Basic comparison
```bash
python tests/compare_evals.py --run reranking_test --v1 baseline --v2 reranking

# Output:
# | Metric              | baseline | reranking | Delta |
# |---------------------|----------|-----------|-------|
# | Answer Accuracy     | 84%      | 87%       | +3%   |
# | Citation Halluc.    | 12%      | 5%        | -7%   |
# | Avg Response (s)    | 18.2     | 22.4      | +4.2  |
```

**Directory Structure:**
```
logs/results/
└── reranking_test/
    ├── baseline.json
    └── reranking.json
```

### Phase 2: Add RAGAS Traditional Metrics

Install RAGAS, add BLEU/ROUGE/CHRF to `run_eval.py`, update `compare_evals.py` table

### Phase 3: Manual Review Support (Optional)

**`tests/export_manual_review.py`** - Export samples for ChatGPT/Claude
```bash
python tests/export_manual_review.py --run reranking_test --version baseline --sample 20 --output manual_review.md

# Does:
# 1. Load evaluation results from logs/results/{run}/{version}.json
# 2. Sample N questions (random/stratified/edge cases)
# 3. Fetch chunk content from database for each citation
# 4. Format as markdown with question, RAG answer, citations, ground truth
# 5. Save to logs/results/{run}/manual_review.md for ChatGPT/Claude
```

## Example Workflow (Phase 1)

```bash
# Baseline evaluation
docker-compose down && docker-compose up -d  # Apply .env: RERANKER_MODEL=none
docker-compose exec api python3 tests/run_eval.py --run reranking_test --version baseline

# Reranking evaluation
docker-compose down && docker-compose up -d  # Apply .env: RERANKER_MODEL=ms-marco-MiniLM-L-6-v2
docker-compose exec api python3 tests/run_eval.py --run reranking_test --version reranking

# Compare
docker-compose exec api python3 tests/compare_evals.py --run reranking_test --v1 baseline --v2 reranking
# Shows: Answer accuracy +3%, Citation hallucination -7%, Response time +4.2s

# Decision: Reranking worth the latency trade-off
```

## Status

**Completed**:
- ✅ Golden dataset created (194 questions, all papers ingested)
- ✅ PMID→PMC mapping complete

**Phase 1 Tasks**:
- ✅ Scaffold `tests/run_eval.py` (loads CSV, calls /chat, saves JSON with --run/--version structure)
- ✅ Scaffold `tests/compare_evals.py` (side-by-side comparison table)
- [ ] **Implement metric calculations** in `run_eval.py`:
  - [ ] `calculate_answer_correctness()` - Check yes/no/maybe match
  - [ ] `calculate_citation_hallucination()` - % citations not in retrieved chunks
  - [ ] `calculate_citation_coverage()` - % retrieved chunks cited
- [ ] Run baseline vs reranking comparison on 194 questions
- [ ] Make decision: Is reranking worth the latency?

**Phase 2 Tasks (Later)**:
- [ ] Install RAGAS (`pip install ragas`)
- [ ] Add BLEU/ROUGE/CHRF to `run_eval.py`
- [ ] Update `compare_evals.py` to include RAGAS metrics

**Phase 3 Tasks (Optional)**:
- ✅ Scaffold `tests/export_manual_review.py` (chunk fetching, citation enrichment done)
- ✅ **Implement markdown formatting** for ChatGPT/Claude review (RAGAS metrics: Faithfulness, Answer Relevance, Context Precision, Context Recall)
- ✅ **Implement sampling strategy** (random/stratified/first N)
- [ ] Manually review 20 samples in ChatGPT/Claude

## Design Decisions

**Phased Implementation**:
- Phase 1: Custom metrics only (pure Python, immediate value)
- Phase 2: Add RAGAS traditional metrics (BLEU/ROUGE) when needed
- Phase 3: Manual review support (optional qualitative analysis)

**Why Custom Metrics First?**
- Answer correctness (yes/no/maybe) is domain-specific and actionable
- Citation hallucination is critical for pharma compliance
- Response time tracking for cost/latency decisions
- No dependencies, fast to implement

**Why Add RAGAS Later?**
- BLEU/ROUGE provide industry-standard comparison
- Only add if custom metrics insufficient for decision-making

**Implementation Status**:
- Phase 1: Scaffolding complete, metric calculations TODO
- Phase 2: Not started
- Phase 3: Scaffolding complete (chunk fetching done), formatting TODO

**Cost**: $0 (all automated metrics free, manual review uses paid subscriptions)

## References

- RAGAS: https://github.com/explodinggradients/ragas
- Golden dataset: `data/golden_eval_set.csv`
- RAG endpoint: `app/main.py::/chat`
