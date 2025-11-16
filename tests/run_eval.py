"""
Evaluation harness for RAG system using PubMedQA golden dataset.

Phase 1: Custom metrics (answer correctness, citation hallucination, timing)
Phase 2: RAGAS traditional metrics (BLEU, ROUGE, CHRF) - add later
Phase 3: Manual review export - add later

Usage:
    python tests/run_eval.py --config baseline --output logs/results/eval_baseline.json
"""
import argparse
import csv
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import requests
from dataclasses import dataclass, asdict


@dataclass
class EvaluationResult:
    """Result for a single question evaluation."""
    question_id: str
    pmid: str
    pmc_id: str
    question: str
    expected_answer: str
    long_answer: str

    # RAG outputs
    rag_answer: str
    citations: List[Dict]
    retrieved_chunks: List[Dict]

    # Metrics
    answer_correct: bool
    citation_hallucination_rate: float
    citation_coverage: float
    response_time_ms: float

    # Error tracking
    error: Optional[str] = None


class RAGEvaluator:
    """Evaluates RAG system on golden dataset."""

    def __init__(self, rag_endpoint: str, dataset_path: str):
        """
        Initialize evaluator.

        Args:
            rag_endpoint: URL of RAG /chat endpoint (e.g., http://localhost:8000/chat)
            dataset_path: Path to golden_eval_set.csv
        """
        self.rag_endpoint = rag_endpoint
        self.dataset_path = Path(dataset_path)

    def load_dataset(self) -> List[Dict]:
        """Load questions from CSV."""
        questions = []
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
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
        print(f"Loaded {len(questions)} questions from {self.dataset_path}")
        return questions

    def call_rag(self, question: str, conversation_id: Optional[str] = None) -> Dict:
        """
        Call RAG /chat endpoint.

        Args:
            question: Question to ask
            conversation_id: Optional conversation ID for multi-turn (not used in Phase 1)

        Returns:
            Response dict with: answer, citations, retrieved_chunks, timing
        """
        try:
            start_time = time.time()

            payload = {"user_message": question}
            if conversation_id:
                payload["conversation_id"] = conversation_id

            response = requests.post(
                self.rag_endpoint,
                json=payload,
                timeout=120  # 2 minute timeout
            )
            response.raise_for_status()

            elapsed_ms = (time.time() - start_time) * 1000
            data = response.json()

            return {
                "answer": data.get("generated_response", ""),
                "citations": data.get("response_citations", []),
                "retrieved_chunks": [],  # API doesn't return chunks, would need separate endpoint
                "response_time_ms": elapsed_ms,
                "error": None
            }
        except Exception as e:
            return {
                "answer": "",
                "citations": [],
                "retrieved_chunks": [],
                "response_time_ms": 0,
                "error": str(e)
            }

    def calculate_answer_correctness(self, rag_answer: str, expected_answer: str) -> bool:
        """
        Check if RAG answer matches expected answer (yes/no/maybe).

        Args:
            rag_answer: RAG-generated answer text
            expected_answer: Ground truth (yes/no/maybe)

        Returns:
            True if RAG answer contains expected answer
        """
        # TODO: Implement
        # Simple approach: check if expected_answer appears in rag_answer (case-insensitive)
        # Advanced: extract yes/no/maybe from RAG answer using regex or simple parsing

        # Placeholder: return False to avoid crashes
        return False

    def calculate_citation_hallucination(self, citations: List[Dict], retrieved_chunks: List[Dict]) -> float:
        """
        Calculate citation hallucination rate.

        Args:
            citations: List of citations in RAG answer
            retrieved_chunks: List of chunks retrieved from semantic search

        Returns:
            Float 0-1: Percentage of citations NOT found in retrieved chunks
        """
        # TODO: Implement
        # For each citation, check if citation.chunk_id exists in retrieved_chunks
        # hallucination_rate = (citations not in retrieved) / total citations

        # Placeholder: return 0.0 to avoid crashes
        return 0.0

    def calculate_citation_coverage(self, citations: List[Dict], retrieved_chunks: List[Dict]) -> float:
        """
        Calculate citation coverage.

        Args:
            citations: List of citations in RAG answer
            retrieved_chunks: List of chunks retrieved from semantic search

        Returns:
            Float 0-1: Percentage of retrieved chunks that were cited
        """
        # TODO: Implement
        # coverage = unique_cited_chunks / total_retrieved_chunks

        # Placeholder: return 0.0 to avoid crashes
        return 0.0

    def evaluate_question(self, question_data: Dict) -> EvaluationResult:
        """
        Evaluate RAG on a single question.

        Args:
            question_data: Dict with question_id, pmid, pmc_id, question, expected_answer, long_answer

        Returns:
            EvaluationResult with metrics
        """
        # Call RAG
        rag_response = self.call_rag(question_data['question'])

        # If error, return error result
        if rag_response['error']:
            return EvaluationResult(
                question_id=question_data['question_id'],
                pmid=question_data['pmid'],
                pmc_id=question_data['pmc_id'],
                question=question_data['question'],
                expected_answer=question_data['expected_answer'],
                long_answer=question_data['long_answer'],
                rag_answer="",
                citations=[],
                retrieved_chunks=[],
                answer_correct=False,
                citation_hallucination_rate=0.0,
                citation_coverage=0.0,
                response_time_ms=0.0,
                error=rag_response['error']
            )

        # Calculate metrics (TODO: You'll implement these)
        answer_correct = self.calculate_answer_correctness(
            rag_response['answer'],
            question_data['expected_answer']
        )
        citation_hallucination = self.calculate_citation_hallucination(
            rag_response['citations'],
            rag_response['retrieved_chunks']
        )
        citation_coverage = self.calculate_citation_coverage(
            rag_response['citations'],
            rag_response['retrieved_chunks']
        )

        return EvaluationResult(
            question_id=question_data['question_id'],
            pmid=question_data['pmid'],
            pmc_id=question_data['pmc_id'],
            question=question_data['question'],
            expected_answer=question_data['expected_answer'],
            long_answer=question_data['long_answer'],
            rag_answer=rag_response['answer'],
            citations=rag_response['citations'],
            retrieved_chunks=rag_response['retrieved_chunks'],
            answer_correct=answer_correct,
            citation_hallucination_rate=citation_hallucination,
            citation_coverage=citation_coverage,
            response_time_ms=rag_response['response_time_ms'],
            error=None
        )

    def evaluate_dataset(self, limit: Optional[int] = None) -> Dict:
        """
        Evaluate RAG on entire dataset.

        Args:
            limit: Optional limit on number of questions to evaluate

        Returns:
            Dict with: config, results (list), summary (aggregated stats)
        """
        # Load dataset
        questions = self.load_dataset()

        # Apply limit
        if limit:
            questions = questions[:limit]

        # Evaluate each question
        results = []
        print(f"\nEvaluating {len(questions)} questions...")
        for i, question_data in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] {question_data['question_id']}...", end=' ')

            result = self.evaluate_question(question_data)
            results.append(asdict(result))

            if result.error:
                print(f"ERROR: {result.error}")
            else:
                print(f"OK (correct={result.answer_correct}, time={result.response_time_ms:.0f}ms)")

        # Calculate summary statistics
        successful_results = [r for r in results if r['error'] is None]

        if successful_results:
            summary = {
                "total_questions": len(results),
                "successful": len(successful_results),
                "errors": len(results) - len(successful_results),
                "answer_accuracy": sum(r['answer_correct'] for r in successful_results) / len(successful_results),
                "avg_citation_hallucination_rate": sum(r['citation_hallucination_rate'] for r in successful_results) / len(successful_results),
                "avg_citation_coverage": sum(r['citation_coverage'] for r in successful_results) / len(successful_results),
                "avg_response_time_ms": sum(r['response_time_ms'] for r in successful_results) / len(successful_results),
            }
        else:
            summary = {
                "total_questions": len(results),
                "successful": 0,
                "errors": len(results),
                "answer_accuracy": 0.0,
                "avg_citation_hallucination_rate": 0.0,
                "avg_citation_coverage": 0.0,
                "avg_response_time_ms": 0.0,
            }

        return {
            "results": results,
            "summary": summary
        }

    def save_results(self, results: Dict, output_path: str):
        """Save evaluation results to JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"Results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG system on PubMedQA dataset")
    parser.add_argument("--run", required=True, help="Evaluation run name (e.g., baseline_vs_reranking)")
    parser.add_argument("--version", required=True, help="Version name (e.g., baseline, reranking, v1, v2)")
    parser.add_argument("--dataset", default="data/golden_eval_set.csv", help="Path to golden dataset CSV")
    parser.add_argument("--endpoint", default="http://localhost:8000/chat", help="RAG /chat endpoint URL")
    parser.add_argument("--limit", type=int, help="Limit number of questions (for testing)")

    args = parser.parse_args()

    # Construct output path: logs/results/{run}/{version}.json
    output_path = Path("logs/results") / args.run / f"{args.version}.json"

    # Initialize evaluator
    evaluator = RAGEvaluator(
        rag_endpoint=args.endpoint,
        dataset_path=args.dataset
    )

    # Run evaluation
    print(f"Starting evaluation")
    print(f"Run: {args.run}")
    print(f"Version: {args.version}")
    print(f"Dataset: {args.dataset}")
    print(f"RAG endpoint: {args.endpoint}")
    if args.limit:
        print(f"Limit: {args.limit} questions")
    print(f"Output: {output_path}")

    results = evaluator.evaluate_dataset(limit=args.limit)

    # Add config metadata
    results["config"] = {
        "run": args.run,
        "version": args.version,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dataset": args.dataset,
        "endpoint": args.endpoint,
    }

    # Save results
    evaluator.save_results(results, str(output_path))

    # Print summary
    print("\n=== Evaluation Summary ===")
    summary = results.get("summary", {})
    print(f"Total questions: {summary.get('total_questions', 0)}")
    print(f"Answer accuracy: {summary.get('answer_accuracy', 0):.1%}")
    print(f"Avg citation hallucination: {summary.get('avg_citation_hallucination_rate', 0):.1%}")
    print(f"Avg response time: {summary.get('avg_response_time_ms', 0):.0f}ms")


if __name__ == "__main__":
    main()
