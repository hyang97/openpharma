"""
Manual reranking evaluation runner.

This script helps you run side-by-side comparisons of answers with/without reranking.
Saves results to a file for manual scoring.

Usage:
    # Run quick eval (5 questions)
    python -m tests.run_reranking_eval --quick

    # Run full eval (12 questions)
    python -m tests.run_reranking_eval

    # Run specific questions by ID
    python -m tests.run_reranking_eval --questions 1 3 5

    # Use specific reranker model
    python -m tests.run_reranking_eval --reranker-model BAAI/bge-reranker-v2-m3

    # Available models: ms-marco-MiniLM-L-6-v2 (default), BAAI/bge-reranker-v2-m3, BAAI/bge-small-en-v1.5
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
import requests
from typing import List, Dict
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.reranking_eval_questions import TEST_QUESTIONS, get_questions_for_quick_eval
from app.db.database import engine


def fetch_chunk_content(chunk_ids: List[int]) -> Dict[int, str]:
    """
    Fetch chunk content from database by chunk IDs.

    Args:
        chunk_ids: List of document_chunk_id values

    Returns:
        Dict mapping chunk_id -> content
    """
    if not chunk_ids:
        return {}

    stmt = text("""
        SELECT document_chunk_id, content
        FROM document_chunks
        WHERE document_chunk_id = ANY(:chunk_ids)
    """)

    with Session(engine) as session:
        results = session.execute(stmt, {'chunk_ids': chunk_ids}).fetchall()

    return {row.document_chunk_id: row.content for row in results}


def ask_question(question: str, use_reranker: bool = False, reranker_model: str = None, api_url: str = "http://localhost:8000") -> dict:
    """
    Send a question to the API and return the response.

    Args:
        question: Question text
        use_reranker: Whether to use reranking
        reranker_model: Reranker model name (optional)
        api_url: API base URL

    Returns:
        Response dict with answer, citations, timing
    """
    try:
        payload = {
            "user_message": question,
            "use_reranker": use_reranker,
            "conversation_id": None  # Fresh conversation for each question
        }

        if use_reranker and reranker_model:
            payload["reranker_model"] = reranker_model

        response = requests.post(
            f"{api_url}/chat",
            json=payload,
            timeout=300
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to get response: {e}")
        return None


def run_evaluation(questions: list, api_url: str = "http://localhost:8000", reranker_model: str = None):
    """
    Run evaluation for a list of questions.

    For each question, gets answers both with and without reranking,
    then saves results to a JSON file for manual scoring.

    Args:
        questions: List of question dicts
        api_url: API base URL
        reranker_model: Reranker model name (optional, defaults to API's default)

    Returns:
        Path to results file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = Path(f"logs/results/reranking_eval_results_{timestamp}.json")

    results = {
        "timestamp": timestamp,
        "api_url": api_url,
        "reranker_model": reranker_model or "default (ms-marco-MiniLM-L-6-v2)",
        "questions": []
    }

    print(f"\nRunning evaluation on {len(questions)} questions...")
    print(f"Reranker model: {reranker_model or 'default (ms-marco-MiniLM-L-6-v2)'}")
    print(f"Results will be saved to: {results_file}")
    print("=" * 80)

    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] Q{q['id']}: {q['question']}")
        print(f"Category: {q['category']}")
        print()

        question_result = {
            "id": q["id"],
            "question": q["question"],
            "category": q["category"],
            "why": q["why"],
            "baseline": None,
            "reranked": None
        }

        # Get baseline answer (no reranking)
        print("  Getting baseline answer (no reranking)...")
        baseline_start = time.time()
        baseline_response = ask_question(q["question"], use_reranker=False, reranker_model=reranker_model, api_url=api_url)
        baseline_time = time.time() - baseline_start

        if baseline_response:
            # Fetch chunk content for citations
            citations = baseline_response.get("response_citations", [])
            chunk_ids = [cit["chunk_id"] for cit in citations]
            chunk_content_map = fetch_chunk_content(chunk_ids)

            # Enrich citations with chunk content
            enriched_citations = []
            for cit in citations:
                cit_copy = cit.copy()
                cit_copy["chunk_content"] = chunk_content_map.get(cit["chunk_id"], "")
                enriched_citations.append(cit_copy)

            question_result["baseline"] = {
                "answer": baseline_response.get("generated_response"),
                "citations": enriched_citations,
                "llm_provider": baseline_response.get("llm_provider"),
                "generation_time_ms": baseline_response.get("generation_time_ms"),
                "total_time_s": round(baseline_time, 2)
            }
            print(f"    ✓ Got baseline answer ({baseline_time:.1f}s)")
        else:
            print(f"    ✗ Failed to get baseline answer")

        # Wait a bit to avoid overwhelming the API
        time.sleep(1)

        # Get reranked answer
        print(f"  Getting reranked answer (model: {reranker_model or 'default'})...")
        reranked_start = time.time()
        reranked_response = ask_question(q["question"], use_reranker=True, reranker_model=reranker_model, api_url=api_url)
        reranked_time = time.time() - reranked_start

        if reranked_response:
            # Fetch chunk content for citations
            citations = reranked_response.get("response_citations", [])
            chunk_ids = [cit["chunk_id"] for cit in citations]
            chunk_content_map = fetch_chunk_content(chunk_ids)

            # Enrich citations with chunk content
            enriched_citations = []
            for cit in citations:
                cit_copy = cit.copy()
                cit_copy["chunk_content"] = chunk_content_map.get(cit["chunk_id"], "")
                enriched_citations.append(cit_copy)

            question_result["reranked"] = {
                "answer": reranked_response.get("generated_response"),
                "citations": enriched_citations,
                "llm_provider": reranked_response.get("llm_provider"),
                "reranker_model": reranker_model or "ms-marco-MiniLM-L-6-v2",
                "generation_time_ms": reranked_response.get("generation_time_ms"),
                "total_time_s": round(reranked_time, 2)
            }
            print(f"    ✓ Got reranked answer ({reranked_time:.1f}s)")
        else:
            print(f"    ✗ Failed to get reranked answer")

        results["questions"].append(question_result)

        # Save after each question (in case of interruption)
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

    print()
    print("=" * 80)
    print(f"Evaluation complete! Results saved to: {results_file}")
    print()
    print("Next steps:")
    print("  1. Review the results file")
    print("  2. Compare baseline vs. reranked answers side-by-side")
    print("  3. Score each answer on relevance, citation quality, specificity (1-5 scale)")
    print("  4. Document findings in docs/decisions.md")
    print("=" * 80)

    return results_file


def main():
    parser = argparse.ArgumentParser(
        description="Run manual reranking evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--quick", action="store_true",
                       help="Run quick eval with 5 questions (one from each category)")
    parser.add_argument("--questions", type=int, nargs="+",
                       help="Run specific questions by ID (e.g., --questions 1 3 5)")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000",
                       help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--reranker-model", type=str, default=None,
                       help="Reranker model to use (default: ms-marco-MiniLM-L-6-v2). "
                            "Options: cross-encoder/ms-marco-MiniLM-L-6-v2, BAAI/bge-reranker-v2-m3, BAAI/bge-small-en-v1.5")

    args = parser.parse_args()

    # Determine which questions to run
    if args.questions:
        # Run specific questions by ID
        all_questions = []
        for category_questions in TEST_QUESTIONS.values():
            all_questions.extend(category_questions)

        questions = [q for q in all_questions if q["id"] in args.questions]
        if not questions:
            print(f"ERROR: No questions found with IDs: {args.questions}")
            return

        print(f"Running evaluation on {len(questions)} selected questions...")

    elif args.quick:
        # Run quick eval (5 questions)
        questions = get_questions_for_quick_eval(5)
        print(f"Running quick evaluation with {len(questions)} questions...")

    else:
        # Run full eval (all questions)
        all_questions = []
        for category_questions in TEST_QUESTIONS.values():
            all_questions.extend(category_questions)
        questions = sorted(all_questions, key=lambda q: q["id"])
        print(f"Running full evaluation with {len(questions)} questions...")

    # Check if API is running
    try:
        response = requests.get(f"{args.api_url}/health", timeout=5)
        response.raise_for_status()
        print(f"✓ API is running at {args.api_url}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Cannot connect to API at {args.api_url}")
        print(f"Please start the API with: docker-compose up -d")
        return

    # Run evaluation
    results_file = run_evaluation(questions, api_url=args.api_url, reranker_model=args.reranker_model)


if __name__ == "__main__":
    main()
