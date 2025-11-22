# Evaluation Strategy

## Overview

Evaluate RAG performance using PubMedQA golden dataset (194 expert-labeled questions).

**Goal**: Compare config changes (reranking, models, prompts) to make data-driven decisions.

## Golden Dataset

**Source**: `data/golden_eval_set.csv` (194 questions from PubMedQA expert-labeled subset)

**Format**: Single-paper yes/no/maybe questions with ground truth
- `question_id`, `pmid`, `pmc_id`: Identifiers
- `question`: "Do mitochondria play a role in remodelling lace plant leaves during programmed cell death?"
- `expected_answer`: "yes" / "no" / "maybe" - Simple yes/no/maybe answer
- `long_answer`: Full expert explanation with reasoning
- `year`, `meshes`, `num_contexts`: Metadata

**Coverage**: All 194 papers fully ingested and searchable

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

## Evaluation Workflow

### Step 1: Run Automated Evaluation

Run evaluation to collect automated metrics and export for manual review.

```bash
python -m evals.run \
  --run baseline \
  --version v1 \
  --limit 194

# Creates:
# - logs/eval_results/baseline/v1_auto_results.json
# - logs/eval_results/baseline/v1_llm_judge_prompt.md
```

**What happens:**
1. Load `data/golden_eval_set.csv`
2. For each question: call `/chat` endpoint, capture response
3. Calculate automated metrics: retrieval accuracy, citation validity, response time
4. Save automated results to `{version}_auto_results.json`
5. Export formatted prompt to `{version}_llm_judge_prompt.md` for Gemini

### Step 2: LLM-as-Judge Review

Use Gemini to evaluate answer quality and RAGAS metrics.

1. Open Google AI Studio: https://aistudio.google.com/
2. Enable JSON mode
3. Paste schema from `evals/core/llm_judge_structured_output.json`
4. Paste prompt from `logs/eval_results/baseline/v1_llm_judge_prompt.md`
5. Save JSON output as `logs/eval_results/baseline/v1_llm_judge_results.json`

### Step 3: Merge Results

Combine automated and LLM-as-judge scores into a single complete dataset.

```bash
python -m evals.merge_auto_and_judge \
  --run baseline \
  --version v1

# Creates: logs/eval_results/baseline/v1_metrics.csv
```

### Step 4: Compare Configurations

Side-by-side comparison using `{run}/{version}` format.

```bash
# Compare versions within same run
python -m evals.analyze_run baseline/v1 baseline/v2

# Compare across different runs
python -m evals.analyze_run baseline/v1 reranking_test/v1

# Example output:
# ┌─────────────────────────┬──────────────┬──────────────┬────────┐
# │ Metric                  │ baseline/v1  │ baseline/v2  │ Delta  │
# ├─────────────────────────┼──────────────┼──────────────┼────────┤
# │ Retrieval Accuracy      │ 84.0%        │ 87.0%        │ +3.0%  │
# │ Citation Validity       │ 88.0%        │ 95.0%        │ +7.0%  │
# │ Avg Response Time (ms)  │ 18200        │ 22400        │ +4200  │
# │ Conclusion Match        │ 65.0%        │ 70.0%        │ +5.0%  │
# │ Reasoning Match         │ 58.0%        │ 62.0%        │ +4.0%  │
# │ Avg Faithfulness        │ 3.8          │ 4.2          │ +0.4   │
# │ Avg Relevance           │ 4.1          │ 4.3          │ +0.2   │
# └─────────────────────────┴──────────────┴──────────────┴────────┘
```

## Example: Reranking Comparison

Full workflow comparing baseline vs reranking configurations.

```bash
# 1. Baseline evaluation (no reranking)
# Edit .env: RERANKER_MODEL=none
docker-compose down && docker-compose up -d
python -m evals.run --run reranking_test --version baseline --limit 194

# 2. Reranking evaluation
# Edit .env: RERANKER_MODEL=ms-marco-MiniLM-L-6-v2
docker-compose down && docker-compose up -d
python -m evals.run --run reranking_test --version with_rerank --limit 194

# 3. LLM-as-judge review for both versions (Gemini)
# (Paste baseline_llm_judge_prompt.md and with_rerank_llm_judge_prompt.md into Google AI Studio)
# Save outputs as baseline_llm_judge_results.json and with_rerank_llm_judge_results.json

# 4. Merge results
python -m evals.merge_auto_and_judge --run reranking_test --version baseline
python -m evals.merge_auto_and_judge --run reranking_test --version with_rerank

# 5. Compare
python -m evals.analyze_run reranking_test/baseline reranking_test/with_rerank

# Decision: Is reranking worth the latency trade-off?
```

## Directory Structure

```
evals/
├── __init__.py
├── run.py                      # Main evaluation runner
├── merge_auto_and_judge.py     # Merge automated + LLM-as-judge scores
├── analyze_run.py     # Compare eval runs
├── core/                       # Helper modules
│   ├── __init__.py
│   ├── auto_metrics.py         # Automated metric calculations
│   ├── schemas.py              # Dataclasses
│   ├── utils.py                # Shared helpers (DB, formatting, I/O)
│   ├── llm_judge_structured_output.json  # Gemini JSON schema
│   ├── llm_judge_prompt.md               # Evaluation instructions
│   └── llm_judge_qa_template.md          # Question template
└── README.md                   # Workflow guide

logs/eval_results/{run}/
├── {version}_auto_results.json         # Automated metrics
├── {version}_llm_judge_prompt.md       # For Gemini (input)
├── {version}_llm_judge_results.json    # From Gemini (output)
└── {version}_metrics.csv     # Merged
```

**Example:**
```
logs/eval_results/reranking_test/
├── baseline_auto_results.json
├── baseline_llm_judge_prompt.md
├── baseline_llm_judge_results.json
├── baseline_metrics.csv
├── with_rerank_auto_results.json
├── with_rerank_llm_judge_prompt.md
├── with_rerank_llm_judge_results.json
└── with_rerank_metrics.csv
```

## Implementation Status

**Completed**:
- ✅ Golden dataset (194 questions, all papers ingested)
- ✅ Automated metrics: retrieval accuracy, citation validity, response time
- ✅ LLM-as-judge metrics: conclusion/reasoning match, RAGAS (Faithfulness, Relevance, Precision, Recall)
- ✅ Gemini structured output integration
- ✅ Merge workflow (automated + manual)
- ✅ Comparison tool
- ✅ Modular `evals/` structure with `evals/core/` helpers

**Future Enhancements**:
- [ ] Add BLEU/ROUGE/CHRF string similarity metrics
- [ ] Automated Gemini API integration (replace manual Google AI Studio workflow)
- [ ] Statistical significance testing for comparisons
- [ ] Support for multi-turn conversation evaluation
