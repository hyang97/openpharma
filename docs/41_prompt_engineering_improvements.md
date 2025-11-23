# 41. RAG System Improvements: Data-Driven Experiment Plan (2025-11-23)

## Executive Summary

**Baseline Performance:** 75.8% conclusion match (147/194), 79.9% reasoning match (155/194)

**Key Finding:** Failures split evenly between retrieval (51%) and reasoning (49%). The 75.8% baseline is respectable, but we have clear paths to 85%+ through targeted improvements.

**Recommended Experiments:**
1. **Test Llama 3.1 70B** - Addresses positivity bias in NO questions (+5-8% potential gain)
2. **Minimal prompt refinements** - Remove hedging triggers (+2-3% potential gain)

**Note**: Reranking is already enabled in baseline (ms-marco-MiniLM-L-6-v2), so retrieval is already optimized.

**NOT Recommended:** Complex prompt engineering, query rewriting, CoT architectures - insufficient ROI for complexity cost.

---

## Corrected Baseline Analysis

### Performance Summary (v2)
- **Questions Evaluated**: 194
- **Conclusion Match**: 147/194 (75.8%) ✅ [Note: Initial report of 47.9% was due to summary calculation bug]
- **Reasoning Match**: 155/194 (79.9%) ✅
- **Article Retrieval**: 162/194 (83.5%)
- **Citation Validity**: 98.2%
- **Avg Faithfulness**: 4.5/5
- **Avg Response Time**: 38.6s

### Key Metrics by Retrieval Quality
```
Correct Retrieval (162 cases):
  → Correct Conclusion: 139/162 (85.8%)
  → Wrong Conclusion:   23/162 (14.2%)

Wrong Retrieval (32 cases):
  → Correct Conclusion: 8/32 (25.0% - got lucky!)
  → Wrong Conclusion:   24/32 (75.0%)
```

**Insight:** When retrieval works, reasoning works 86% of the time. Wrong retrieval causes failure 75% of the time.

---

## Failure Mode Analysis

### 47 Total Failures Breakdown

**1. RETRIEVAL FAILURES: 24 cases (51%)**
- **Root Cause**: Wrong article retrieved, no relevant chunks
- **Impact**: 75% conversion to wrong conclusions (24/32 retrieval failures)
- **Addressable By**: Reranking, query rewriting, better embeddings
- **Ceiling Gain**: +19 questions (75.8% → 85.8%)

**2. REASONING FAILURES: 23 cases (49%)**
- **Root Cause**: Correct article retrieved but wrong conclusion drawn
- **Breakdown by Answer Type**:
  - YES questions: 9 failures (21/107 total YES = 80.4% success)
  - NO questions: 11 failures (17/63 total NO = 73.0% success) ⚠️ **Positivity Bias**
  - MAYBE questions: 3 failures (9/24 total MAYBE = 62.5% success) ⚠️ **Poor Calibration**
- **Addressable By**: Better model, prompt refinements, CoT
- **Ceiling Gain**: +15 questions (75.8% → 83.5%)

### Critical Insight: Positivity Bias

The model performs 7.4% worse on NO questions vs YES questions. Examples:
- "Are women with depression identifiable in population data?" → Says YES, answer is NO
- "Does healthier lifestyle reduce healthcare utilization?" → Says "unclear", answer is NO (increases preventive care)
- "Regional vs general anesthesia reduce morbidity?" → Says "better outcomes", answer is NO DIFFERENCE

**Pattern**: Model weights positive findings more than null findings, struggles to say "NO" definitively.

### Response Time vs Accuracy (Surprising Finding)

```
Fastest quartile (<32s):     79.6% accuracy
Second quartile (32-37s):    81.2% accuracy
Third quartile (37-44s):     72.9% accuracy
Slowest quartile (>44s):     69.4% accuracy
```

**Insight**: Longer responses are LESS accurate, not more. Harder questions take longer and generate more hedging/unnecessary reasoning.

---

## Proposed Experiments (Prioritized by ROI)

### ~~Experiment 1: Enable Cross-Encoder Reranking~~ [ALREADY ENABLED]

**Status**: ❌ **NOT NEEDED** - Reranking is already enabled in baseline!

**Discovery**: After review, `RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2` was already enabled during the baseline v2 eval. The 75.8% performance already includes reranking benefits.

**Implication**: The 83.5% retrieval accuracy (162/194) is already WITH reranking. This is good news - our retrieval system is already optimized with the quick win. The 32 retrieval failures are harder cases that reranking couldn't fix.

**Alternative Experiment**: Test a STRONGER reranker (e.g., `bge-reranker-v2-m3`) to see if more powerful reranking helps, but expect diminishing returns. The ~48s latency cost likely not worth marginal gains.

---

### Experiment 1: Upgrade to Llama 3.1 70B [MEDIUM ROI, HIGH COST]

**Hypothesis**: Larger model will reduce positivity bias, improve NO question accuracy, and handle nuanced reasoning better.

**Current State**:
- Using Llama 3.1 8B (4-bit quantized, ~5GB RAM)
- Response time: ~35s for LLM generation (97% of total time)
- Zero cost (local inference)

**Model Comparison**:
| Model | Parameters | Quant | RAM | Est. Speed | Cost |
|-------|-----------|-------|-----|------------|------|
| Llama 3.1 8B | 8B | 4-bit | 5GB | 35s | $0 |
| Llama 3.1 70B | 70B | 4-bit | 40GB | 90-120s | $0 (local) |
| GPT-4o | ? | - | - | 8-12s | ~$0.30/eval |

**Expected Impact**:
- **Target**: Improve reasoning on NO questions from 73.0% → 82%+ (63 → 52+ correct)
- **Gain**: +8-10 questions on NO/MAYBE questions (75.8% → 80-82%)
- **Tradeoff**: 2.5-3x slower responses (35s → 90-120s)

**Test Plan (Phased)**:
1. **Phase 1 - Small Sample** (20 questions: 10 NO failures + 10 random):
   - Install Llama 3.1 70B: `ollama pull llama3.1:70b`
   - Update `OLLAMA_MODEL=llama3.1:70b` in docker-compose.yml
   - Run mini-eval, manually review outputs
   - Decision point: If NO question accuracy improves significantly, proceed to Phase 2

2. **Phase 2 - Full Eval** (194 questions):
   - Run full eval: `python -m evals.run_mlflow --experiment model_comparison --run v1_70b --limit all`
   - Compare to baseline v2
   - Analyze cost/benefit: Is +5-8% accuracy worth 3x slower responses?

**Success Criteria**:
- NO question conclusion match: 73.0% → 80%+ (46 → 50+)
- Overall conclusion match: 75.8% → 81%+ (147 → 158+)
- Response time: <120s acceptable for learning project (not production)

**Decision Rule**: If Phase 1 shows <5% improvement on NO questions, skip Phase 2 (model size not the issue). If Phase 2 shows <5% overall improvement, not worth latency cost for production.

**Alternative**: Test GPT-4o on subset (50 questions) for comparison
- Pro: Faster (8-12s), potentially better reasoning
- Con: $15-20 for full eval (acceptable for one-time test), API dependency
- Test command: Update `use_local=False` in `app/main.py:chat` endpoint

---

### Experiment 2: Prompt Refinements (Minimal) [LOW ROI, ZERO COST]

**Hypothesis**: Removing hedging triggers and adding NO question guidance will reduce positivity bias.

**Analysis of Current Prompt Issues**:

1. ❌ **"Reflect on your confidence"** (line 41) - Triggers over-cautious language
2. ✅ **"No sufficient evidence" fallback** (line 46) - Appropriate, keep as-is
3. ❌ **No guidance on YES/NO/MAYBE calibration** - Model defaults to YES when uncertain
4. ✅ **Citation format enforcement** - Working well (98.2% validity)

**Proposed Changes** (Minimal, Focused):

```diff
# File: app/rag/generation.py, lines 38-43

- You will think through step-by-step to pull in relevant details from <Literature> to support the answer. Reflect on your confidence in your answer based on the relevance, completeness, and consistency of the provided <Literature>.
+ You will think through step-by-step to pull in relevant details from <Literature> to support the answer.
  You will respond concisely, summarizing the main answer, and providing supporting details from <Literature> with citations.
+
+ When answering yes/no questions:
+ - YES: Evidence clearly supports the claim
+ - NO: Evidence clearly refutes the claim, shows no effect, or shows null/negative results
+ - MAYBE: Evidence is genuinely mixed or inconclusive
+ - INSUFFICIENT: No relevant information in <Literature>
+ Note: "No effect shown" or "no significant difference" means NO, not MAYBE or INSUFFICIENT.
```

**Expected Impact**:
- **Target**: Reduce NO question failures from 11 → 6-8
- **Gain**: +3-5 questions (75.8% → 77-79%)
- **Risk**: Minimal (easily reversible)

**Test Plan**:
1. Update prompt in `app/rag/generation.py`
2. Restart API container
3. Run subset eval (50 questions: 20 NO failures + 30 random): `--limit 50`
4. If improvement ≥3%, run full eval

**Success Criteria**:
- NO question conclusion match: 73.0% → 78%+ (46 → 49+)
- Overall conclusion match: 75.8% → 78%+ (147 → 152+)
- Maintain faithfulness ≥4.3 (don't sacrifice accuracy for confidence)

**Decision Rule**: If subset shows <2% improvement, prompt is not the bottleneck (model capability is). If ≥3%, run full eval.

---

### Experiment 3: Combined Winner [IF Experiments 1-2 Show Promise]

**Setup**: Combine best-performing changes from Experiments 1-2
- Model: Llama 70B (if Exp 1 gains ≥5% and latency acceptable) OR keep 8B
- Prompt: Refined (if Exp 2 gains ≥3%)

**Expected Impact**: Additive gains from independent improvements
- **Target**: 75.8% → 85%+ (147 → 165+)

**Test Plan**: Full 194-question eval with combined changes

---

## Experiments NOT Recommended (Low ROI)

### ❌ Complex Prompt Engineering (Chain-of-Thought, Few-Shot Examples)

**Why Skip**:
- Current faithfulness is 4.5/5 - model already understands chunks well
- 41 cases of high faithfulness but wrong conclusion indicates capability issue, not instruction issue
- Adding complexity (CoT, examples) unlikely to fix positivity bias
- Better to test model upgrade (Exp 2) first

### ❌ Query Rewriting for Multi-Turn Conversations

**Why Skip**:
- No evidence of multi-turn-specific failures in eval (all single-turn questions)
- Adds architectural complexity and latency
- Should revisit after optimizing single-turn performance

### ❌ Two-Step Reasoning (Extract Facts → Draw Conclusion)

**Why Skip**:
- Doubles LLM calls = 2x latency (38s → 76s) and cost
- Reasoning match already 79.9% - not the bottleneck
- Better to test model upgrade (cheaper, simpler)

### ❌ Self-Consistency (Generate Multiple Answers, Vote)

**Why Skip**:
- 3-5x LLM calls = unacceptable latency and cost
- Overkill for 24% error rate (would make sense at >50% error rate)
- Better ROI from retrieval and model improvements

---

## Implementation Roadmap

### Week 1: Quick Wins
- **Day 1**: Run Experiment 2 (prompt) - Subset eval (50 questions)
- **Day 2**: If promising (≥3% gain), run full prompt eval
- **Day 3**: Analyze prompt results

### Week 2: Model Testing
- **Day 1-2**: Install Llama 70B, run Experiment 1 Phase 1 (20 questions)
- **Day 3-4**: If promising, run Experiment 1 Phase 2 (full eval)
- **Day 5**: Analyze model comparison results

### Week 3: Combined Testing (if needed)
- **Day 1-2**: Run Experiment 3 (combined winner) if Experiments 1-2 show gains
- **Day 3**: Final analysis and production deployment decision
- **Day 4-5**: Document learnings, update design docs

---

## Success Criteria and Decision Framework

### Production Deployment Threshold
- **Conclusion Match**: 85%+ (165/194)
- **Response Time**: <45s (acceptable for v1, optimize later)
- **Cost**: <$5 per 1000 queries (local models preferred)

### Learning Goals (Primary for this project)
- ✅ Understand impact of retrieval quality vs model capability
- ✅ Quantify reranking benefits
- ✅ Compare 8B vs 70B model performance on reasoning tasks
- ✅ Test prompt engineering limits vs model capability limits

### Decision Matrix

| Experiment | If Gain <3% | If Gain 3-7% | If Gain >7% |
|------------|-------------|--------------|-------------|
| Reranking | Skip, too complex | Deploy if no latency cost | Deploy immediately |
| Llama 70B | Use 8B | Consider for offline analysis | Deploy if latency acceptable |
| Prompt | Capability issue | Deploy minor changes | Deploy + document |

---

## Monitoring and Iteration

### Metrics to Track in MLFlow
- Conclusion match rate (by answer type: yes/no/maybe)
- Reasoning match rate
- Faithfulness score (must stay ≥4.3)
- Response time (p50, p95)
- Retrieval accuracy
- Per-question improvements (which questions got fixed?)

### Red Flags (Rollback Triggers)
- Faithfulness drops below 4.0 (hallucination increase)
- Response time >60s p95 (user experience degradation)
- NO question accuracy decreases (overcorrection)

### Iteration Strategy
1. Run experiment
2. Analyze failures in new eval
3. Categorize remaining errors
4. Prioritize next highest-ROI fix
5. Repeat until hitting ceiling (83.5%) or production threshold (85%)

---

## Technical Notes

### File Modifications
- **Reranking**: `docker-compose.yml` (line 26: `RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2`)
- **Model**: `docker-compose.yml` (line 25: `OLLAMA_MODEL=llama3.1:70b`)
- **Prompt**: `app/rag/generation.py` (lines 26-71: SYSTEM_PROMPT)

### Evaluation Commands
```bash
# Full eval
docker-compose exec api python -m evals.run_mlflow --experiment <name> --run <id> --limit all

# Subset eval (faster iteration)
docker-compose exec api python -m evals.run_mlflow --experiment <name> --run <id> --limit 50

# Merge results
docker-compose exec api python -m evals.merge_auto_and_judge --experiment <name> --run <id>

# View results
open http://127.0.0.1:5001  # MLFlow UI
```

### Git Strategy
- Branch per experiment: `exp/reranking-v1`, `exp/llama-70b`, `exp/prompt-v3`
- Tag evaluated versions: `git tag eval-reranking-v1`
- MLFlow tracks prompt text as artifact automatically

---

## References

- **Baseline Eval**: `logs/eval_results/baseline/v2_complete_results.json`
- **Current Prompt**: `app/rag/generation.py:26-71`
- **Reranking Implementation**: `app/retrieval/reranker.py`
- **Evaluation Pipeline**: `evals/run_mlflow.py`, `evals/merge_auto_and_judge.py`
- **Analysis Notebook**: (TODO: Create Jupyter notebook with failure analysis)

---

## Appendix: Detailed Failure Analysis

### High-Faithfulness Wrong-Conclusion Cases (41 total)

These represent the purest "reasoning failures" - model accurately reads chunks but draws wrong conclusion:

**Sample Case 1: Positivity Bias**
- Q: "Visceral adipose tissue area at single level represent volume?"
- Expected: YES
- RAG: "may not accurately represent... However, strongest correlation found at L3 (0.853)"
- Issue: Hedges in opening despite strong evidence, then contradicts itself
- Faithfulness: 5/5

**Sample Case 2: Null Result Interpretation**
- Q: "Regional vs general anesthesia reduce morbidity in hip fracture?"
- Expected: NO (no difference)
- RAG: "Regional anesthesia shown to have better outcomes"
- Issue: Weights one positive finding over multiple null findings
- Faithfulness: 5/5

**Pattern**: Model has data but lacks reasoning capability or instruction to handle:
1. Null/negative results
2. "No significant difference" conclusions
3. Threshold-based determinations ("inadequate" vs "some")

This strongly suggests **model capability** is the bottleneck, not prompt engineering.

---

## Conclusion

The baseline 75.8% performance is solid but has clear improvement paths:

1. **Reranking** (Exp 1): Low-hanging fruit, test first
2. **Model upgrade** (Exp 2): Addresses root cause of reasoning failures
3. **Prompt refinements** (Exp 3): Marginal gains, worth testing

Combined, these could achieve 85%+ conclusion match, meeting production threshold.

**Key Learning**: Evals revealed the failure mode split (51% retrieval, 49% reasoning) and identified positivity bias as the core reasoning issue. This data-driven approach prevents wasting time on low-ROI prompt engineering when model capability is the real bottleneck.
