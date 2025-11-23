# Evaluation Strategy

Evaluate RAG performance using PubMedQA golden dataset (194 expert-labeled yes/no/maybe questions). Compare config changes (reranking, models, prompts) to make data-driven decisions.

## Golden Dataset

`data/golden_eval_set.csv` - 194 questions from PubMedQA with ground truth (all papers ingested):
- `question_id`, `pmid`, `pmc_id` - Identifiers
- `question` - Research question
- `expected_answer` - yes/no/maybe
- `long_answer` - Expert explanation with reasoning

## Evaluation Metrics

Metrics are organized by evaluation method (Automated vs LLM-as-Judge) and implementation status.

### Automated Metrics

Objective measurements that don't require LLM judgment. Fast, deterministic, no API costs.

| Metric               | Description                              | Ground Truth    | Status         |
|----------------------|------------------------------------------|-----------------|----------------|
| Retrieval Accuracy   | Was the correct article retrieved?       | `pmc_id`        | ✅ Implemented |
| Citation Validity    | % citations matching retrieved chunks    | No              | ✅ Implemented |
| Response Time        | End-to-end latency (ms)                  | No              | ✅ Implemented |
| BLEU Score           | N-gram overlap with ground truth         | `long_answer`   | ❌ Future      |
| ROUGE Score          | Recall-oriented string similarity        | `long_answer`   | ❌ Future      |
| CHRF Score           | Character-level F-score                  | `long_answer`   | ❌ Future      |

### LLM-as-Judge Metrics

Subjective quality assessments using Gemini 1.5 Pro/Flash. Requires manual Google AI Studio workflow.

| Metric             | Description                              | Ground Truth      | Status         |
|--------------------|------------------------------------------|-------------------|----------------|
| Conclusion Match   | RAG reaches same yes/no/maybe conclusion | `expected_answer` | ✅ Implemented |
| Reasoning Match    | RAG reasoning aligns with expert         | `long_answer`     | ✅ Implemented |
| Faithfulness       | Answer grounded in context? (1-5)        | No                | ✅ Implemented |
| Answer Relevance   | Answer addresses question? (1-5)         | No                | ✅ Implemented |
| Context Precision  | Retrieved chunks relevant? (1-5)         | No                | ✅ Implemented |
| Context Recall     | Context contains ground truth? (1-5)     | `long_answer`     | ✅ Implemented |

## MLFlow Integration

**Architecture:**
- Per-question tracking: answers, citations, retrieval results, response time (stored in `eval_results_table.json`)
- Prompt versioning: system prompt + template structure logged as artifacts
- Custom metrics: closure pattern passes full DataFrame context to metric functions
- Experiments organized by type (baseline, reranking_test, etc.), runs by version (v1, v2, v3)

**Implementation:**
- `RAGEvaluator` class wraps `/chat` endpoint for `mlflow.evaluate()`
- Custom metrics use closure pattern to access full evaluation context
- MLFlow UI runs in Docker on port 5001 (http://127.0.0.1:5001)

**Each run tracks:**
- Parameters: run_id, dataset, endpoint, model, reranker, prompt_version, limit
- Metrics: retrieval_accuracy, citation_validity, avg_response_time_ms
- Artifacts: system_prompt.txt, prompt_template.json, eval_results_table.json

## Evaluation Workflow

### Step 1: Run Evaluation

```bash
# Full evaluation (194 questions)
docker-compose exec api python -m evals.run_mlflow --experiment baseline --run v1

# Quick test (2 questions)
docker-compose exec api python -m evals.run_mlflow --experiment baseline --run v1_test --limit 2
```

Calls `/chat` for each question, logs parameters/metrics/artifacts to MLFlow, exports LLM-as-judge prompt to `logs/eval_results/{experiment}/{run}_llm_judge_prompt.md`.

### Step 2: View Results (http://127.0.0.1:5001)

View experiments, compare runs, drill down to parameters/metrics/artifacts. Select 2+ runs and click "Compare" for side-by-side comparison.

### Step 3: LLM-as-Judge (Optional)

Paste `logs/eval_results/{experiment}/{run}_llm_judge_prompt.md` into Google AI Studio (JSON mode with `evals/core/llm_judge_structured_output.json` schema). Save output as `{run}_llm_judge_results.json`, then merge to log LLM-as-judge metrics to MLFlow:

```bash
docker-compose exec api python -m evals.merge_auto_and_judge --experiment baseline --run v1
```

This adds 6 new metrics to the MLFlow run: `conclusion_match_rate`, `reasoning_match_rate`, `avg_faithfulness`, `avg_relevance`, `avg_precision`, `avg_recall`.

## Example: Reranking Comparison

```bash
# 1. Baseline (edit .env: RERANKER_MODEL=none)
docker-compose down && docker-compose up -d
docker-compose exec api python -m evals.run_mlflow --experiment reranking_test --run baseline

# 2. With reranking (edit .env: RERANKER_MODEL=ms-marco-MiniLM-L-6-v2)
docker-compose down && docker-compose up -d
docker-compose exec api python -m evals.run_mlflow --experiment reranking_test --run with_rerank

# 3. Compare in MLFlow UI (http://127.0.0.1:5001)
# Select both runs → Click "Compare" → Compare metrics side-by-side

# 4. (Optional) LLM-as-judge + merge
docker-compose exec api python -m evals.merge_auto_and_judge --experiment reranking_test --run baseline
docker-compose exec api python -m evals.merge_auto_and_judge --experiment reranking_test --run with_rerank
```

## Directory Structure

```
evals/
├── run_mlflow.py               # MLFlow evaluation runner
├── merge_auto_and_judge.py     # Merge automated + LLM-as-judge, log to MLFlow
└── core/                       # Metrics, schemas, utils, LLM-judge templates

logs/eval_results/{experiment}/
├── {run}_llm_judge_prompt.md       # For Gemini
├── {run}_llm_judge_results.json    # From Gemini
└── {run}_complete_results.json     # Merged (if LLM-as-judge completed)

mlruns/{experiment_id}/{run_id}/
├── metrics/       # retrieval_accuracy, citation_validity, avg_response_time_ms
├── params/        # run_id, dataset, endpoint, model, reranker, prompt_version, limit
└── artifacts/     # system_prompt.txt, prompt_template.json, eval_results_table.json
```

## Implementation Status

**Completed**:
- ✅ Golden dataset (194 questions, all papers ingested)
- ✅ Automated metrics: retrieval accuracy, citation validity, response time
- ✅ LLM-as-judge metrics: conclusion/reasoning match, RAGAS (Faithfulness, Relevance, Precision, Recall)
- ✅ Gemini structured output integration (manual workflow)
- ✅ Merge workflow (automated + manual)
- ✅ CLI comparison tool (`analyze_run.py`)
- ✅ Modular `evals/` structure with `evals/core/` helpers
- ✅ MLFlow integration:
  - `mlflow.evaluate()` with custom metrics (closure pattern)
  - Per-question tracking via `eval_results_table.json`
  - Prompt versioning (system_prompt.txt, prompt_template.json artifacts)
  - MLFlow UI in Docker (port 5001)
  - Experiment/run organization

**Future Enhancements**:
- [ ] Add BLEU/ROUGE/CHRF string similarity metrics
- [ ] Automated Gemini API integration (replace manual Google AI Studio workflow)
- [ ] Statistical significance testing for comparisons
- [ ] Support for multi-turn conversation evaluation
- [ ] MLFlow LLM-as-judge evaluators (automated quality metrics)
