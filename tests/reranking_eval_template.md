# Reranking Evaluation Results

**Date**: [FILL IN]
**Evaluator**: [FILL IN]
**Results File**: [FILL IN - e.g., reranking_eval_results_20251026_123456.json]

## Scoring Criteria (1-5 scale)

For each answer, score on:
- **Relevance** (1-5): Does it directly answer the question?
- **Citation Quality** (1-5): Are cited papers actually relevant?
- **Specificity** (1-5): Is it detailed and specific vs. vague?
- **Overall** (1-5): Overall quality of the answer

**Scale**:
- 5 = Excellent
- 4 = Good
- 3 = Acceptable
- 2 = Poor
- 1 = Very Poor

---

## Question 1: [COPY QUESTION TEXT]

**Category**: [COPY CATEGORY]

### Baseline (No Reranking)
**Answer**: [COPY ANSWER]

**Citations**: [COUNT] papers cited

**Timing**:
- Retrieval: [X]ms
- Generation: [X]ms
- Total: [X]s

**Scores**:
- Relevance: [ ] / 5
- Citation Quality: [ ] / 5
- Specificity: [ ] / 5
- Overall: [ ] / 5

**Notes**: [Your observations about baseline answer]

---

### Reranked
**Answer**: [COPY ANSWER]

**Citations**: [COUNT] papers cited

**Timing**:
- Retrieval: [X]ms
- Reranking: [X]ms
- Generation: [X]ms
- Total: [X]s

**Scores**:
- Relevance: [ ] / 5
- Citation Quality: [ ] / 5
- Specificity: [ ] / 5
- Overall: [ ] / 5

**Notes**: [Your observations about reranked answer]

---

### Comparison
**Winner**: [ ] Baseline / [ ] Reranked / [ ] Tie

**Key Differences**:
- [List notable differences between baseline and reranked answers]

**Latency Impact**: [X]s added by reranking (is it worth it?)

---

[REPEAT FOR EACH QUESTION]

---

## Summary

### Overall Scores

| Question | Baseline Overall | Reranked Overall | Winner |
|----------|------------------|------------------|--------|
| Q1       | [ ] / 5          | [ ] / 5          | [ ]    |
| Q2       | [ ] / 5          | [ ] / 5          | [ ]    |
| Q3       | [ ] / 5          | [ ] / 5          | [ ]    |
| Q4       | [ ] / 5          | [ ] / 5          | [ ]    |
| Q5       | [ ] / 5          | [ ] / 5          | [ ]    |
| **Avg**  | [ ] / 5          | [ ] / 5          | -      |

### Win/Loss/Tie
- Reranked Wins: [ ] / [ ] questions ([ ]%)
- Baseline Wins: [ ] / [ ] questions ([ ]%)
- Ties: [ ] / [ ] questions ([ ]%)

### Latency Analysis
- Average baseline time: [ ]s
- Average reranked time: [ ]s
- Average reranking overhead: [ ]s (+[ ]%)

### Key Findings

**What improved with reranking**:
- [List improvements]

**What didn't improve**:
- [List areas with no improvement]

**Unexpected findings**:
- [Any surprises?]

### Recommendation

[ ] Deploy reranking - Clear improvement worth the latency
[ ] Don't deploy - No significant improvement
[ ] Need more testing - Results unclear

**Reasoning**: [Explain your recommendation]

---

## Next Steps
- [ ] Document findings in docs/decisions.md
- [ ] If deploying: Add --use-reranker flag to API
- [ ] If deploying: Update UI to use reranking
- [ ] If not deploying: Archive this evaluation for future reference
