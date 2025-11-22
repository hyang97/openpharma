# OpenPharma RAG Evaluation System

Modular evaluation framework for measuring RAG performance across automated metrics and LLM-as-judge assessments.

## Quick Start Workflow

### 1. Run Evaluation

Runs automated evaluation and exports prompt for LLM-as-judge review.

```bash
python -m evals.run --run baseline --version v1 --limit 194

# Creates:
# - logs/eval_results/baseline/v1_auto_results.json
# - logs/eval_results/baseline/v1_llm_judge_prompt.md
```

**Options:**
- `--run` - Evaluation run name (e.g., `baseline`, `reranking_test`)
- `--version` - Version name (e.g., `v1`, `v2`, `with_rerank`)
- `--limit` - Limit number of questions (optional, useful for testing)
- `--dataset` - Path to CSV dataset (default: `data/golden_eval_set.csv`)
- `--endpoint` - RAG endpoint URL (default: `http://localhost:8000/chat`)

### 2. LLM-as-Judge Review (Manual)

Use Gemini to evaluate answer quality and RAGAS metrics.

1. Open Google AI Studio: https://aistudio.google.com/
2. Enable JSON mode
3. Paste schema from `evals/core/llm_judge_structured_output.json`
4. Paste prompt from `logs/eval_results/baseline/v1_llm_judge_prompt.md`
5. Save JSON output as `logs/eval_results/baseline/v1_llm_judge_results.json`

### 3. Merge Results

Combines automated metrics with LLM-as-judge scores.

```bash
python -m evals.merge_auto_and_judge --run baseline --version v1

# Creates:
# - logs/eval_results/baseline/v1_metrics.csv
```

### 4. Compare Versions

Side-by-side comparison of different run versions.

```bash
# Compare versions within same run
python -m evals.analyze_run baseline/v1 baseline/v2

# Compare across different runs
python -m evals.analyze_run baseline/v1 reranking_test/v1
```

## Complete Example: Reranking Comparison

```bash
# 1. Baseline evaluation (no reranking)
# Edit .env: RERANKER_MODEL=none
docker-compose down && docker-compose up -d
python -m evals.run --run reranking_test --version baseline --limit 194

# 2. Reranking evaluation
# Edit .env: RERANKER_MODEL=ms-marco-MiniLM-L-6-v2
docker-compose down && docker-compose up -d
python -m evals.run --run reranking_test --version with_rerank --limit 194

# 3. LLM-as-judge review for both versions (in Google AI Studio)
# Save as: baseline_llm_judge_results.json and with_rerank_llm_judge_results.json

# 4. Merge both versions
python -m evals.merge_auto_and_judge --run reranking_test --version baseline
python -m evals.merge_auto_and_judge --run reranking_test --version with_rerank

# 5. Compare
python -m evals.analyze_run reranking_test/baseline reranking_test/with_rerank
```

## File Structure

```
evals/
├── run.py                      # Step 1: Run evaluation
├── merge_auto_and_judge.py     # Step 3: Merge results
├── analyze_run.py     # Step 4: Compare versions
├── core/                       # Helper modules
│   ├── auto_metrics.py         # Automated metric calculations
│   ├── schemas.py              # Dataclasses
│   ├── utils.py                # Shared helpers
│   ├── llm_judge_structured_output.json  # Gemini JSON schema
│   ├── llm_judge_prompt.md               # Evaluation instructions
│   └── llm_judge_qa_template.md          # Question template
└── README.md

logs/eval_results/{run}/
├── {version}_auto_results.json         # Automated metrics
├── {version}_llm_judge_prompt.md       # For Gemini (input)
├── {version}_llm_judge_results.json    # From Gemini (output)
└── {version}_metrics.csv     # Merged
```

## Evaluation Metrics

### Automated Metrics

Objective measurements that don't require LLM judgment.

| Metric              | Description                          |
|---------------------|--------------------------------------|
| Retrieval Accuracy  | Was the correct article retrieved?   |
| Citation Validity   | % citations matching retrieved chunks|
| Response Time       | End-to-end latency (ms)              |

### LLM-as-Judge Metrics

Subjective quality assessments using Gemini 1.5 Pro/Flash.

| Metric            | Description                                    |
|-------------------|------------------------------------------------|
| Conclusion Match  | RAG reaches same yes/no/maybe conclusion       |
| Reasoning Match   | RAG reasoning aligns with expert explanation   |
| Faithfulness      | Answer grounded in context? (1-5)              |
| Answer Relevance  | Answer addresses question? (1-5)               |
| Context Precision | Retrieved chunks relevant? (1-5)               |
| Context Recall    | Context contains ground truth? (1-5)           |

## Customizing Prompts

Edit these files to customize LLM-as-judge evaluation:

- `llm_judge_prompt.md` - Overall evaluation instructions
- `llm_judge_qa_template.md` - Template for each question
- `llm_judge_structured_output.json` - JSON schema for Gemini

## Tips

**Quick iteration:** Use `--limit 10` to test on a small subset first
```bash
python -m evals.run --run test --version v1 --limit 10
```

**Naming conventions:**
- Use descriptive run names: `baseline`, `reranking_test`, `prompt_experiments`
- Use simple version names: `v1`, `v2`, `baseline`, `with_rerank`, `optimized`

**File organization:**
- All runs go in `logs/results/{run}/`
- Each version has 4 files: `*_auto_results.json`, `*_llm_judge_prompt.md`, `*_llm_judge_results.json`, `*_metrics.csv`
