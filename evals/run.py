"""
Main evaluation runner for RAG system.

Runs automated evaluation and exports prompt for LLM-as-judge review.

Usage:
    python -m evals.run --run baseline --version v1 --limit 10
"""
import argparse
import csv
import time
from typing import Dict, List
import requests

from evals.core.schemas import EvaluationResult, EvaluationConfig
from evals.core.auto_metrics import (
    calculate_retrieval_accuracy,
    calculate_citation_validity,
    calculate_summary_stats
)
from evals.core.utils import (
    save_json,
    save_text,
    enrich_citations_with_content,
    format_question_for_llm_judge,
    get_llm_judge_prompt
)


def load_dataset(config: EvaluationConfig) -> List[Dict]:
    """Load questions from CSV."""
    questions = []
    with open(config.dataset_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append({
                'question_id': row['question_id'],
                'pmid': row['pmid'],
                'pmc_id': row['pmc_id'],
                'question': row['question'],
                'expected_answer': row['expected_answer'],
                'long_answer': row['long_answer'],
            })
    print(f"Loaded {len(questions)} questions from {config.dataset_path}")
    return questions


def call_rag(config: EvaluationConfig, question: str) -> Dict:
    """Call RAG /chat endpoint and return response with timing."""
    try:
        start_time = time.time()

        payload = {
            "user_message": question,
            "use_reranker": True,
            "additional_chunks_per_doc": 20
        }

        response = requests.post(
            config.rag_endpoint,
            json=payload,
            timeout=120
        )
        response.raise_for_status()

        elapsed_ms = (time.time() - start_time) * 1000
        data = response.json()

        return {
            "answer": data.get("generated_response", ""),
            "citations": data.get("response_citations", []),
            "retrieved_chunk_ids": data.get("retrieved_chunk_ids", []),
            "raw_llm_response": data.get("raw_llm_response", ""),
            "response_time_ms": elapsed_ms,
            "error": None
        }

    except Exception as e:
        return {
            "answer": "",
            "citations": [],
            "retrieved_chunk_ids": [],
            "raw_llm_response": "",
            "response_time_ms": 0,
            "error": str(e)
        }


def evaluate_question(config: EvaluationConfig, question_data: Dict) -> EvaluationResult:
    """Evaluate RAG on a single question."""
    rag_response = call_rag(config, question_data['question'])

    if rag_response['error']:
        return EvaluationResult(
            question_id=question_data['question_id'],
            pmid=question_data['pmid'],
            pmc_id=question_data['pmc_id'],
            question=question_data['question'],
            expected_answer=question_data['expected_answer'],
            long_answer=question_data['long_answer'],
            rag_answer="",
            raw_llm_response="",
            citations=[],
            retrieved_chunk_ids=[],
            correct_article_retrieved=False,
            citation_validity_rate=0.0,
            response_time_ms=0,
            error=rag_response['error']
        )

    # Calculate automated metrics
    correct_article_retrieved = calculate_retrieval_accuracy(
        question_data['pmc_id'],
        rag_response['retrieved_chunk_ids']
    )
    citation_validity = calculate_citation_validity(
        rag_response['raw_llm_response'],
        rag_response['retrieved_chunk_ids']
    )

    return EvaluationResult(
        question_id=question_data['question_id'],
        pmid=question_data['pmid'],
        pmc_id=question_data['pmc_id'],
        question=question_data['question'],
        expected_answer=question_data['expected_answer'],
        long_answer=question_data['long_answer'],
        rag_answer=rag_response['answer'],
        raw_llm_response=rag_response['raw_llm_response'],
        citations=rag_response['citations'],
        retrieved_chunk_ids=rag_response['retrieved_chunk_ids'],
        correct_article_retrieved=correct_article_retrieved,
        citation_validity_rate=citation_validity,
        response_time_ms=rag_response['response_time_ms'],
        error=None
    )


def evaluate_dataset(config: EvaluationConfig) -> Dict:
    """Evaluate RAG on dataset and return results with summary."""
    questions = load_dataset(config)

    if config.limit:
        questions = questions[:config.limit]

    results = []
    print(f"\nEvaluating {len(questions)} questions...")
    for i, question_data in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question_data['question_id']}...", end=' ')

        result = evaluate_question(config, question_data)
        results.append(result.to_dict())

        if result.error:
            print(f"ERROR: {result.error}")
        else:
            print(f"OK (retrieved={result.correct_article_retrieved}, time={result.response_time_ms:.0f}ms)")

    summary = calculate_summary_stats(results)

    return {
        "results": results,
        "summary": summary
    }


def export_for_llm_judge(config: EvaluationConfig, results: Dict):
    """Export evaluation results for LLM-as-judge review."""
    prompt_parts = [get_llm_judge_prompt(), "\n\n"]

    for result in results['results']:
        enriched_citations = enrich_citations_with_content(result['citations'])
        prompt_parts.append(format_question_for_llm_judge(result, enriched_citations))

    prompt = "".join(prompt_parts)
    save_text(prompt, config.get_llm_judge_prompt_path())
    print(f"LLM-as-judge prompt exported to: {config.get_llm_judge_prompt_path()}")

    # Create empty file for LLM-as-judge results
    with open(config.get_llm_judge_results_path(), 'w') as f:
        f.write("")
    print(f"Empty LLM-as-judge results file created at: {config.get_llm_judge_results_path()}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG system")
    parser.add_argument("--run", required=True, help="Evaluation run name (e.g., baseline)")
    parser.add_argument("--version", required=True, help="Version name (e.g., v1, v2)")
    parser.add_argument("--dataset", default="data/golden_eval_set.csv", help="Path to dataset CSV")
    parser.add_argument("--endpoint", default="http://localhost:8000/chat", help="RAG endpoint URL")
    parser.add_argument("--limit", type=int, help="Limit number of questions")

    args = parser.parse_args()

    config = EvaluationConfig(
        run_name=args.run,
        version=args.version,
        dataset_path=args.dataset,
        rag_endpoint=args.endpoint,
        limit=args.limit
    )

    print(f"Starting evaluation")
    print(f"Run: {config.run_name}")
    print(f"Version: {config.version}")
    print(f"Dataset: {config.dataset_path}")
    print(f"RAG endpoint: {config.rag_endpoint}")
    if config.limit:
        print(f"Limit: {config.limit} questions")
    print(f"Output: {config.get_auto_results_path()}")

    # Run evaluation
    results = evaluate_dataset(config)

    # Add config metadata
    results["config"] = {
        "run": config.run_name,
        "version": config.version,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dataset": config.dataset_path,
        "endpoint": config.rag_endpoint,
    }

    # Save automated results
    save_json(results, config.get_auto_results_path())

    # Print summary
    print("\n=== Evaluation Summary ===")
    summary = results.get("summary", {})
    print(f"Total questions: {summary.get('total_questions', 0)}")
    print(f"Successful: {summary.get('successful', 0)}")
    print(f"Errors: {summary.get('errors', 0)}")
    print(f"Correct article retrieval: {summary.get('correct_article_retrieval_rate', 0):.1%}")
    print(f"Avg citation validity: {summary.get('avg_citation_validity_rate', 0):.1%}")
    print(f"Avg citations per question: {summary.get('avg_citations_per_question', 0):.1f}")
    print(f"Avg response time: {summary.get('avg_response_time_ms', 0):.0f}ms")

    # Export for LLM-as-judge review
    print(f"\n=== Exporting for LLM-as-Judge Review ===")
    export_for_llm_judge(config, results)

    print(f"\n{'='*60}")
    print("Next Steps:")
    print(f"{'='*60}")
    print(f"1. Open Google AI Studio: https://aistudio.google.com/")
    print(f"2. Enable JSON mode, paste schema: evals/core/llm_judge_structured_output.json")
    print(f"3. Paste prompt from: {config.get_llm_judge_prompt_path()}")
    print(f"4. Save JSON output as: {config.get_llm_judge_results_path()}")
    print(f"5. Merge: python -m evals.merge_auto_and_judge --run {config.run_name} --version {config.version}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
