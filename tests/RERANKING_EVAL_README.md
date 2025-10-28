# Reranking Evaluation Guide

This directory contains tools for manually evaluating the impact of cross-encoder reranking on answer quality.

## Overview

The evaluation process:
1. **Test Questions**: 12 diverse questions across 6 categories
2. **Run Evaluation**: Get answers with/without reranking for each question
3. **Manual Scoring**: Score answers on relevance, citation quality, specificity
4. **Document Findings**: Summarize results and make deployment decision

## Files

- `reranking_eval_questions.py` - Test questions organized by category
- `run_reranking_eval.py` - Script to run evaluation and save results
- `reranking_eval_template.md` - Template for manual scoring
- `../logs/results/reranking_eval_results_*.json` - Results files (generated)

## Quick Start

### 1. View Test Questions

```bash
# See all 12 questions
python -m tests.reranking_eval_questions

# See just 5 questions for quick eval
python -m tests.reranking_eval_questions --quick
```

### 2. Integrate Reranker into API

**IMPORTANT**: Before running evaluation, you need to integrate the reranker into the API:

1. Add `use_reranker` parameter to `/ask` endpoint in `app/main.py`
2. Update `generate_answer()` to use reranker when enabled
3. Restart API: `docker-compose restart api`

See `TODO.md` for integration tasks.

### 3. Run Evaluation

```bash
# Quick eval (5 questions, ~10 minutes)
python -m tests.run_reranking_eval --quick

# Full eval (12 questions, ~20 minutes)
python -m tests.run_reranking_eval

# Specific questions only
python -m tests.run_reranking_eval --questions 1 3 5
```

This will:
- Query the API twice per question (with/without reranking)
- Save results to `logs/results/reranking_eval_results_TIMESTAMP.json`
- Take ~1-2 minutes per question (including API response time)

### 4. Score Results

1. Open the generated `reranking_eval_results_*.json` file
2. Copy `reranking_eval_template.md` to a new file (e.g., `reranking_eval_20251026.md`)
3. Fill in scores for each answer based on criteria
4. Compare baseline vs. reranked answers side-by-side
5. Complete the summary section

**Scoring takes ~30-45 minutes** for quick eval, ~1-2 hours for full eval.

### 5. Make Decision

Based on your scores:
- **Deploy reranking**: If reranked answers consistently better AND latency acceptable
- **Don't deploy**: If no significant improvement OR latency too high
- **Need more testing**: If results unclear or mixed

Document your decision in `docs/decisions.md`.

## Question Categories

1. **Specific Fact** (2 questions): Mechanism of action, efficacy data
2. **Comparison** (2 questions): Drug comparisons, outcome comparisons
3. **Adverse Events** (2 questions): Safety profiles, side effects
4. **Mechanism** (2 questions): Cellular biology, disease progression
5. **Treatment Guidelines** (2 questions): Clinical recommendations, decision-making
6. **Population Specific** (2 questions): Elderly, pregnancy

## Expected Results

**Hypothesis**: Reranking should improve:
- **Citation quality**: More relevant papers cited
- **Specificity**: More detailed answers from better context
- **Query-document alignment**: Better at finding papers that directly answer the question

**Trade-off**:
- Adds ~1-2s latency for reranking step
- Worth it if answer quality improves significantly

## Tips for Manual Evaluation

1. **Focus on differences**: Don't re-read identical parts of answers
2. **Check citations**: Actually look at the paper titles to verify relevance
3. **Be consistent**: Use the same scoring rubric for all questions
4. **Take notes**: Document interesting findings as you go
5. **Take breaks**: Don't rush - quality evaluation takes time

## Next Steps After Evaluation

If reranking helps:
- [ ] Deploy to production with `--use-reranker` flag
- [ ] Update UI to enable reranking by default
- [ ] Monitor latency and adjust `top_k` if needed
- [ ] Consider setting up RAGAS for ongoing evaluation

If reranking doesn't help:
- [ ] Archive evaluation results for reference
- [ ] Consider alternative improvements (query rewriting, better embeddings)
- [ ] Focus on other quality improvements

## Troubleshooting

**API not responding**:
```bash
docker-compose ps
docker-compose logs -f api
```

**Evaluation script fails**:
- Check API is running: `curl http://localhost:8000/health`
- Check reranker is integrated: Look for `use_reranker` parameter in `/ask` endpoint
- Check logs: `docker-compose logs -f api`

**Questions taking too long**:
- Normal: 30-60s per question (2 API calls)
- If >2 minutes: Check if LLM is running (Ollama or OpenAI)
- Can interrupt and resume: Script saves after each question
