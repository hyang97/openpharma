"""
Export evaluation results for manual review in ChatGPT/Claude/Gemini.

Phase 3: Manual LLM-as-Judge Review
Takes automated evaluation results and exports a sample of questions
with their RAG answers, citations, and retrieved chunk content for manual LLM-as-judge scoring.

Features:
- Includes LLM-as-judge prompt with RAGAS scoring criteria (Faithfulness, Answer Relevance, Context Precision, Context Recall)
- Enriches citations with full chunk content from database for verification
- Multiple sampling strategies: random, first N, or stratified (by answer correctness)
- Formatted markdown output ready for copy-paste into LLM interface

Usage:
    python tests/export_manual_review.py --run reranking_test --version baseline --sample 20 --output manual_review.md
    python tests/export_manual_review.py --run reranking_test --version baseline --sample 20 --strategy stratified

Output:
    Markdown file with LLM-as-judge instructions + sampled questions with full context
"""
import argparse
import json
from pathlib import Path
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine


def fetch_chunk_content_and_pmid(chunk_ids: List[int]) -> Dict[int, Dict[str, str]]:
    """
    Fetch chunk content and PMID from database by chunk IDs.

    Args:
        chunk_ids: List of document_chunk_id values

    Returns:
        Dict mapping chunk_id -> {'content': str, 'pmid': str}
    """
    if not chunk_ids:
        return {}

    stmt = text("""
        SELECT
            dc.document_chunk_id,
            dc.content,
            p.pmid
        FROM document_chunks dc
        JOIN documents d ON dc.document_id = d.document_id
        LEFT JOIN pubmed_papers p ON d.source_id = p.pmc_id
        WHERE dc.document_chunk_id = ANY(:chunk_ids)
    """)

    with Session(engine) as session:
        results = session.execute(stmt, {'chunk_ids': chunk_ids}).fetchall()

    return {
        row.document_chunk_id: {
            'content': row.content,
            'pmid': row.pmid if row.pmid else 'Unknown'
        }
        for row in results
    }


def load_eval_results(run: str, version: str) -> Dict:
    """Load evaluation results from JSON."""
    path = Path("logs/results") / run / f"{version}.json"
    with open(path, 'r') as f:
        return json.load(f)


def enrich_citations_with_content_and_pmid(citations: List[Dict]) -> List[Dict]:
    """
    Enrich citations with chunk content and PMID from database.

    Args:
        citations: List of citation dicts with chunk_id

    Returns:
        List of enriched citations with chunk_content and pmid added
    """
    # Extract chunk IDs
    chunk_ids = [cit["chunk_id"] for cit in citations]

    # Fetch content and PMID
    chunk_data_map = fetch_chunk_content_and_pmid(chunk_ids)

    # Enrich citations
    enriched_citations = []
    for cit in citations:
        cit_copy = cit.copy()
        chunk_data = chunk_data_map.get(cit["chunk_id"], {})
        cit_copy["chunk_content"] = chunk_data.get('content', 'Content not available')
        cit_copy["pmid"] = chunk_data.get('pmid', 'Unknown')
        enriched_citations.append(cit_copy)

    return enriched_citations


def sample_questions(results: List[Dict], sample_size: int, strategy: str = 'random') -> List[Dict]:
    """
    Sample questions from evaluation results.

    Args:
        results: List of evaluation result dicts
        sample_size: Number of questions to sample
        strategy: Sampling strategy ('random', 'first', 'stratified')

    Returns:
        List of sampled result dicts
    """
    import random

    if len(results) <= sample_size:
        return results

    if strategy == 'first':
        return results[:sample_size]

    elif strategy == 'random':
        return random.sample(results, sample_size)

    elif strategy == 'stratified':
        # Sample evenly across answer correctness (if available)
        correct = [r for r in results if r.get('is_correct', False)]
        incorrect = [r for r in results if not r.get('is_correct', False)]

        # Sample proportionally
        correct_count = min(len(correct), int(sample_size * len(correct) / len(results)))
        incorrect_count = sample_size - correct_count

        sampled = []
        if correct:
            sampled.extend(random.sample(correct, min(correct_count, len(correct))))
        if incorrect:
            sampled.extend(random.sample(incorrect, min(incorrect_count, len(incorrect))))

        return sampled

    else:
        # Default to first N
        return results[:sample_size]


def format_question_for_review(result: Dict, enriched_citations: List[Dict]) -> str:
    """
    Format a single question result as markdown for manual review.

    Args:
        result: Question evaluation result dict
        enriched_citations: Citations with chunk_content

    Returns:
        Markdown-formatted string for ChatGPT/Claude review
    """
    # Extract timing - may be nested in 'timing' dict or at top level
    timing = result.get('timing', {})
    retrieval_ms = timing.get('retrieval_ms', result.get('retrieval_time_ms', 0))
    generation_ms = timing.get('generation_ms', result.get('generation_time_ms', 0))
    reranking_ms = timing.get('reranking_ms', result.get('reranking_time_ms', 0))

    # Total time in seconds
    response_time_ms = result.get('response_time_ms', 0)
    total_s = response_time_ms / 1000 if response_time_ms else timing.get('total_s', 0)

    md = f"""## Question {result['question_id']}

**Question**: {result['question']}

**Expected Answer (Ground Truth)**: {result.get('expected_answer', 'N/A')}

**Expected Long Answer (Ground Truth)**: {result.get('long_answer', 'N/A')}

---

### RAG Answer

{result.get('rag_answer', 'N/A')}

---

### Citations ({len(enriched_citations)} papers cited)

{format_citations(enriched_citations)}

---

### Timing
- Retrieval: {retrieval_ms}ms
{f'- Reranking: {reranking_ms}ms' if reranking_ms > 0 else ''}
- Generation: {generation_ms}ms
- **Total**: {total_s:.2f}s

---

### Evaluation (Score 1-5 for each RAGAS metric)

**Faithfulness** (1-5): Is the answer grounded in the retrieved context?
- Check if claims are supported by chunk content above
- Score: [ ] / 5
- Notes:

**Answer Relevance** (1-5): Does the answer directly address the question?
- Score: [ ] / 5
- Notes:

**Context Precision** (1-5): Are the retrieved chunks relevant to the question?
- Check the chunk content above - is it relevant?
- Score: [ ] / 5
- Notes:

**Context Recall** (1-5): Does the retrieved context contain all ground truth information?
- Compare chunk content against the Expected Long Answer above
- Score: [ ] / 5
- Notes:

**Overall Average** (1-5): Average of the 4 metrics above
- Score: [ ] / 5

---

"""
    return md


def format_citations(citations: List[Dict]) -> str:
    """Format citations as markdown with full context as seen by LLM."""
    if not citations:
        return "No citations"

    output = ""
    for i, cit in enumerate(citations, 1):
        chunk_content = cit.get('chunk_content', 'Content not available')
        title = cit.get('title', 'Unknown title')
        authors = cit.get('authors', [])
        authors_str = ', '.join(authors) if authors else 'Unknown authors'
        publication_date = cit.get('publication_date', 'Unknown date')
        source_id = cit.get('source_id', 'Unknown PMC ID')
        pmid = cit.get('pmid', 'Unknown')
        journal = cit.get('journal', 'Unknown journal')

        # Format exactly as the LLM sees it (from generation.py line 94)
        llm_context = f"Title: {title} | {chunk_content} | Journal: {journal}"

        output += f"""
#### [{i}] {title}
- **Authors**: {authors_str}
- **Journal**: {journal}
- **Publication Date**: {publication_date}
- **PMID**: {pmid}
- **PMC ID**: {source_id}
- **Chunk ID**: {cit.get('chunk_id', 'Unknown')}

**Context as seen by LLM**:
```
{llm_context}
```
"""

    return output


def get_llm_judge_prompt() -> str:
    """Return the LLM-as-judge prompt for manual evaluation using RAGAS metrics."""
    return """# LLM-as-Judge Evaluation Instructions

You are an expert evaluator assessing RAG (Retrieval-Augmented Generation) system outputs for a pharmaceutical research intelligence product.

## Your Task

Evaluate each RAG answer below on 4 RAGAS metrics using a 1-5 scale.

## Evaluation Criteria

**IMPORTANT**: Each citation includes `chunk_content` - the actual text from the paper that was used to generate the answer. Use this to verify the metrics below.

1. **Faithfulness** (1-5): Is the answer grounded in the retrieved context?
   - Check if claims in the answer are supported by the chunk_content provided
   - 5 = All claims directly supported by chunk content, no hallucinations
   - 3 = Mostly accurate, some unsupported claims
   - 1 = Contains claims not supported by chunk content (hallucinations)

2. **Answer Relevance** (1-5): Does the answer directly address the question?
   - 5 = Perfectly answers the question, highly relevant
   - 3 = Partially answers, some gaps or tangential information
   - 1 = Doesn't answer the question, irrelevant

3. **Context Precision** (1-5): Are the retrieved chunks relevant to answering the question?
   - Read the chunk_content for each citation
   - 5 = All retrieved chunks highly relevant to question
   - 3 = Some chunks relevant, some tangential or noisy
   - 1 = Retrieved chunks not relevant to question

4. **Context Recall** (1-5): Does the retrieved context contain all information from the ground truth answer?
   - Compare chunk_content against the Expected Long Answer (ground truth)
   - 5 = Retrieved context contains all key information from ground truth
   - 3 = Retrieved context contains some but not all ground truth information
   - 1 = Retrieved context missing most ground truth information

## After Evaluating All Questions

Provide a summary with:
1. Average scores for each metric
2. Key findings: What worked well? What didn't?
3. Recommendation: Is this configuration suitable for production?

---

"""


def export_manual_review(run: str, version: str, sample_size: int, output_path: str, strategy: str = 'random'):
    """
    Export evaluation results for manual review.

    Args:
        run: Evaluation run name
        version: Version name
        sample_size: Number of questions to sample
        output_path: Output markdown file path
        strategy: Sampling strategy ('random', 'first', 'stratified')
    """
    # Load evaluation results
    print(f"Loading evaluation results from {run}/{version}...")
    eval_data = load_eval_results(run, version)

    results = eval_data.get("results", [])
    print(f"Total questions: {len(results)}")

    # Sample questions
    sampled = sample_questions(results, sample_size, strategy)
    print(f"Sampled {len(sampled)} questions for manual review (strategy: {strategy})")

    # Generate markdown output
    markdown_output = get_llm_judge_prompt()
    markdown_output += f"""# Manual Review: {run} - {version}

**Total Questions**: {len(results)}
**Sample Size**: {len(sampled)}
**Sampling Strategy**: {strategy}
**Timestamp**: {eval_data.get('config', {}).get('timestamp', 'Unknown')}

---

"""

    for i, result in enumerate(sampled, 1):
        print(f"[{i}/{len(sampled)}] Processing {result['question_id']}...")

        # Enrich citations with chunk content and PMID
        citations = result.get("citations", [])
        enriched_citations = enrich_citations_with_content_and_pmid(citations)

        # Format for review
        markdown_output += format_question_for_review(result, enriched_citations)

    # Save to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(markdown_output)

    print(f"\nManual review exported to: {output_path}")
    print(f"\nNext steps:")
    print(f"1. Open {output_path}")
    print(f"2. Copy-paste into ChatGPT/Claude/Gemini")
    print(f"3. The LLM will score each question based on the criteria")
    print(f"4. Review the LLM's analysis and recommendations")


def main():
    parser = argparse.ArgumentParser(description="Export evaluation results for manual review")
    parser.add_argument("--run", required=True, help="Evaluation run name")
    parser.add_argument("--version", required=True, help="Version name")
    parser.add_argument("--sample", type=int, default=20, help="Number of questions to sample (default: 20)")
    parser.add_argument("--output", default="manual_review.md", help="Output markdown file path")
    parser.add_argument("--strategy", default="random", choices=["random", "first", "stratified"],
                        help="Sampling strategy: random, first, or stratified (default: random)")

    args = parser.parse_args()

    # If just filename, save to logs/results/{run}/
    output_path = Path(args.output)
    if not output_path.parent.name or output_path.parent == Path('.'):
        output_path = Path("logs/results") / args.run / output_path

    export_manual_review(args.run, args.version, args.sample, str(output_path), args.strategy)


if __name__ == "__main__":
    main()
