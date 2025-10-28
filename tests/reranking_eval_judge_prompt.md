# LLM-as-Judge Prompt for Reranking Evaluation

Copy this prompt into Gemini (or any LLM) along with your evaluation results JSON.

---

You are an expert evaluator assessing the quality of RAG (Retrieval-Augmented Generation) system outputs for a pharmaceutical research intelligence product.

## Task

I will provide you with evaluation results comparing two RAG system configurations:
1. **Baseline**: Standard semantic search (top-5 chunks)
2. **Reranked**: Semantic search + cross-encoder reranking (top-20 → rerank to top-5)

For each question, both systems provided an answer with citations. Your job is to evaluate which answer is better.

## Evaluation Criteria

For each answer pair, evaluate on these 4 criteria (1-5 scale):

**IMPORTANT**: Each citation includes `chunk_content` - the actual text from the paper that was used to generate the answer. Use this to verify accuracy and citation quality.

1. **Relevance** (1-5): Does the answer directly address the question?
   - 5 = Perfectly answers the question
   - 3 = Partially answers, some gaps
   - 1 = Doesn't answer the question

2. **Citation Quality** (1-5): Are the cited chunks actually relevant to the question?
   - Read the `chunk_content` for each citation
   - 5 = All chunk content highly relevant to question
   - 3 = Some chunks relevant, some tangential
   - 1 = Chunk content not relevant to question

3. **Specificity** (1-5): Is the answer detailed and specific vs. vague?
   - 5 = Highly specific with concrete details/numbers
   - 3 = Moderately specific
   - 1 = Very vague or generic

4. **Accuracy** (1-5): Is the information in the answer actually supported by the chunk content?
   - Check if claims in the answer match the `chunk_content` provided
   - 5 = All claims directly supported by chunk content
   - 3 = Mostly accurate, some unsupported claims
   - 1 = Contains claims not supported by chunk content

## Output Format

For each question, provide:

```
Question [ID]: [Question text]
Category: [category]

BASELINE SCORES:
- Relevance: X/5
- Citation Quality: X/5
- Specificity: X/5
- Accuracy: X/5
- Overall: X/5 (average)
Brief justification: [1-2 sentences]

RERANKED SCORES:
- Relevance: X/5
- Citation Quality: X/5
- Specificity: X/5
- Accuracy: X/5
- Overall: X/5 (average)
Brief justification: [1-2 sentences]

WINNER: [Baseline / Reranked / Tie]
Key difference: [What made the winner better?]

---
```

## Summary at End

After evaluating all questions, provide:

1. **Overall Scores Table**:
```
| Question | Baseline Overall | Reranked Overall | Winner |
|----------|------------------|------------------|--------|
| Q1       | X.X / 5          | X.X / 5          | [...]  |
...
| Average  | X.X / 5          | X.X / 5          | -      |
```

2. **Win/Loss/Tie Summary**:
- Reranked Wins: X / Y questions (Z%)
- Baseline Wins: X / Y questions (Z%)
- Ties: X / Y questions (Z%)

3. **Key Findings** (bullet points):
- What improved with reranking?
- What didn't improve?
- Any unexpected findings?

4. **Deployment Recommendation**:
[Deploy / Don't Deploy / Unclear] - [Brief reasoning considering improvement vs latency trade-off]

---

## Evaluation Results JSON

[PASTE YOUR reranking_eval_results_TIMESTAMP.json FILE CONTENTS HERE]

---

## Additional Context

- **Latency consideration**: Reranking adds ~1-2 seconds per query
- **Trade-off**: Is the quality improvement worth the latency?
- **Use case**: Competitive intelligence analysts need accurate, well-cited answers quickly
- **Current performance**: Baseline takes ~30-40s per query, reranking would add ~1-2s (3-5% increase)
