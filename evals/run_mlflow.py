"""
MLFlow-integrated evaluation runner for RAG system.

Runs automated evaluation using mlflow.evaluate() with per-question tracking.

Usage:
    python -m evals.run_mlflow --experiment baseline --run v1 --limit 10
"""
import argparse
import time
import os
import pandas as pd
import mlflow
from mlflow.models import make_metric
from mlflow.metrics import MetricValue
from typing import Dict, List

from evals.core.schemas import EvaluationConfig
from evals.core.auto_metrics import (
    retrieval_accuracy_mlflow,
    citation_validity_mlflow,
    response_time_mlflow
)
from evals.core.utils import (
    save_json,
    save_text,
    enrich_citations_with_content,
    format_question_for_llm_judge,
    get_llm_judge_prompt
)
from app.rag.generation import SYSTEM_PROMPT


class RAGEvaluator:
    """Wrapper for RAG system that works with mlflow.evaluate()."""

    def __init__(self, config: EvaluationConfig):
        self.config = config

    def predict(self, questions_df: pd.DataFrame) -> pd.DataFrame:
        """
        Call RAG system for each question and return results.

        Args:
            questions_df: DataFrame with columns: question_id, pmc_id, question

        Returns:
            DataFrame with columns: answer, citations, retrieved_chunk_ids,
                                   raw_llm_response, response_time_ms
        """
        import requests

        results = []
        total = len(questions_df)

        print(f"\nEvaluating {total} questions...")

        for idx, row in questions_df.iterrows():
            print(f"[{idx+1}/{total}] {row['question_id']}...", end=' ')

            try:
                start_time = time.time()

                payload = {
                    "user_message": row['question'],
                    "use_reranker": True,
                    "additional_chunks_per_doc": 20
                }

                response = requests.post(
                    self.config.rag_endpoint,
                    json=payload,
                    timeout=120
                )
                response.raise_for_status()

                elapsed_ms = (time.time() - start_time) * 1000
                data = response.json()

                result = {
                    "answer": data.get("generated_response", ""),
                    "citations": str(data.get("response_citations", [])),  # Serialize for DataFrame
                    "retrieved_chunk_ids": data.get("retrieved_chunk_ids", []),
                    "raw_llm_response": data.get("raw_llm_response", ""),
                    "response_time_ms": elapsed_ms,
                    "error": None
                }

                print(f"OK (time={elapsed_ms:.0f}ms)")

            except Exception as e:
                result = {
                    "answer": "",
                    "citations": "[]",
                    "retrieved_chunk_ids": [],
                    "raw_llm_response": "",
                    "response_time_ms": 0.0,
                    "error": str(e)
                }
                print(f"ERROR: {e}")

            results.append(result)

        return pd.DataFrame(results)


def export_auto_results(config: EvaluationConfig, eval_df: pd.DataFrame, predictions_df: pd.DataFrame):
    """Export automated results in legacy JSON format for backward compatibility."""
    from evals.core.auto_metrics import calculate_retrieval_accuracy, calculate_citation_validity
    import ast
    import os

    results = []
    for idx, row in eval_df.iterrows():
        pred_row = predictions_df.iloc[idx]

        # Parse citations string back to list
        citations = ast.literal_eval(pred_row['citations']) if pred_row['citations'] else []

        result = {
            'question_id': row['question_id'],
            'pmid': str(row['pmid']),
            'pmc_id': str(row['pmc_id']),
            'question': row['question'],
            'expected_answer': row['expected_answer'],
            'long_answer': row['long_answer'],
            'rag_answer': pred_row['answer'],
            'raw_llm_response': pred_row['raw_llm_response'],
            'citations': citations,
            'retrieved_chunk_ids': pred_row['retrieved_chunk_ids'],
            'correct_article_retrieved': calculate_retrieval_accuracy(row['pmc_id'], pred_row['retrieved_chunk_ids']),
            'citation_validity_rate': calculate_citation_validity(pred_row['raw_llm_response'], pred_row['retrieved_chunk_ids']),
            'response_time_ms': pred_row['response_time_ms'],
            'error': pred_row.get('error')
        }
        results.append(result)

    # Calculate summary stats
    total = len(results)
    correct_retrieval = sum(1 for r in results if r['correct_article_retrieved'])
    avg_citation_validity = sum(r['citation_validity_rate'] for r in results) / total if total > 0 else 0
    avg_response_time = sum(r['response_time_ms'] for r in results) / total if total > 0 else 0

    output = {
        'results': results,
        'summary': {
            'total_questions': total,
            'correct_article_retrieval_rate': correct_retrieval / total if total > 0 else 0,
            'avg_citation_validity_rate': avg_citation_validity,
            'avg_response_time_ms': avg_response_time
        },
        'config': {
            'experiment_name': config.experiment_name,
            'run_id': config.run_id,
            'dataset_path': config.dataset_path,
            'rag_endpoint': config.rag_endpoint
        }
    }

    # Ensure output directory exists
    os.makedirs(config.get_output_dir(), exist_ok=True)

    # Save to file
    save_json(output, config.get_auto_results_path())
    print(f"Automated results exported to: {config.get_auto_results_path()}")


def export_for_llm_judge(config: EvaluationConfig, eval_df: pd.DataFrame, predictions_df: pd.DataFrame):
    """Export evaluation results for LLM-as-judge review."""
    import ast

    prompt_parts = [get_llm_judge_prompt(), "\n\n"]

    for idx, row in eval_df.iterrows():
        pred_row = predictions_df.iloc[idx]

        # Parse citations string back to list
        citations = ast.literal_eval(pred_row['citations']) if pred_row['citations'] else []

        result_dict = {
            'question_id': row['question_id'],
            'pmid': row['pmid'],
            'pmc_id': row['pmc_id'],
            'question': row['question'],
            'expected_answer': row['expected_answer'],
            'long_answer': row['long_answer'],
            'rag_answer': pred_row['answer'],
            'citations': citations
        }

        enriched_citations = enrich_citations_with_content(citations)
        prompt_parts.append(format_question_for_llm_judge(result_dict, enriched_citations))

    prompt = "".join(prompt_parts)
    save_text(prompt, config.get_llm_judge_prompt_path())
    print(f"LLM-as-judge prompt exported to: {config.get_llm_judge_prompt_path()}")

    # Create empty file for LLM-as-judge results
    with open(config.get_llm_judge_results_path(), 'w') as f:
        f.write("")
    print(f"Empty LLM-as-judge results file created at: {config.get_llm_judge_results_path()}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG system with MLFlow")
    parser.add_argument("--experiment", required=True, help="Experiment name (e.g., baseline, reranking_test)")
    parser.add_argument("--run", required=True, help="Run identifier (e.g., v1, v2, v3)")
    parser.add_argument("--dataset", default="data/golden_eval_set.csv", help="Path to dataset CSV")
    parser.add_argument("--endpoint", default="http://localhost:8000/chat", help="RAG endpoint URL")
    parser.add_argument("--limit", type=int, help="Limit number of questions")

    args = parser.parse_args()

    config = EvaluationConfig(
        experiment_name=args.experiment,
        run_id=args.run,
        dataset_path=args.dataset,
        rag_endpoint=args.endpoint,
        limit=args.limit
    )

    print(f"Starting MLFlow evaluation")
    print(f"Experiment: {config.experiment_name}")
    print(f"Run: {config.run_id}")
    print(f"Dataset: {config.dataset_path}")
    print(f"RAG endpoint: {config.rag_endpoint}")
    if config.limit:
        print(f"Limit: {config.limit} questions")

    # Load dataset
    eval_df = pd.read_csv(config.dataset_path)
    if config.limit:
        eval_df = eval_df.head(config.limit)

    print(f"Loaded {len(eval_df)} questions")

    # Create RAG evaluator
    rag_evaluator = RAGEvaluator(config)

    # Set MLFlow experiment
    mlflow.set_experiment(config.experiment_name)

    # Run MLFlow evaluation
    with mlflow.start_run(run_name=config.run_id):
        # Log parameters
        mlflow.log_param("run_id", config.run_id)
        mlflow.log_param("dataset", config.dataset_path)
        mlflow.log_param("endpoint", config.rag_endpoint)
        mlflow.log_param("model", os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
        mlflow.log_param("reranker", os.getenv("RERANKER_MODEL", "none"))
        mlflow.log_param("prompt_version", "v1.0")  # TODO: Make this configurable
        if config.limit:
            mlflow.log_param("limit", config.limit)

        # Log system prompt
        mlflow.log_text(SYSTEM_PROMPT, "system_prompt.txt")

        # Log prompt template structure
        prompt_template_config = {
            "chunk_format": "[PMC{id}] Title: {title} | {content} | Journal: {journal}",
            "literature_wrapper": "<Literature>...</Literature>",
            "user_query_wrapper": "User Query: {message}",
            "citation_cleaning": "Strip [digits] from original text",
            "conversation_history": "Enabled"
        }
        mlflow.log_dict(prompt_template_config, "prompt_template.json")

        # Call RAG system
        predictions_df = rag_evaluator.predict(eval_df)

        # Merge predictions with eval data for MLFlow
        eval_with_predictions = pd.concat([eval_df.reset_index(drop=True), predictions_df.reset_index(drop=True)], axis=1)

        # Create metric functions with access to full DataFrame via closure
        def make_retrieval_accuracy_metric(full_df):
            def metric_fn(predictions: pd.Series, targets: pd.Series, metrics: Dict):
                from evals.core.auto_metrics import calculate_retrieval_accuracy
                scores = []
                for idx in predictions.index:
                    row = full_df.loc[idx]
                    correct = calculate_retrieval_accuracy(row['pmc_id'], row['retrieved_chunk_ids'])
                    scores.append(1.0 if correct else 0.0)
                aggregate_score = sum(scores) / len(scores) if scores else 0.0
                return MetricValue(
                    scores=scores,
                    aggregate_results={"retrieval_accuracy": aggregate_score}
                )
            return metric_fn

        def make_citation_validity_metric(full_df):
            def metric_fn(predictions: pd.Series, targets: pd.Series, metrics: Dict):
                from evals.core.auto_metrics import calculate_citation_validity
                scores = []
                for idx in predictions.index:
                    row = full_df.loc[idx]
                    validity = calculate_citation_validity(row['raw_llm_response'], row['retrieved_chunk_ids'])
                    scores.append(validity)
                aggregate_score = sum(scores) / len(scores) if scores else 0.0
                return MetricValue(
                    scores=scores,
                    aggregate_results={"citation_validity": aggregate_score}
                )
            return metric_fn

        def make_response_time_metric(full_df):
            def metric_fn(predictions: pd.Series, targets: pd.Series, metrics: Dict):
                scores = [full_df.loc[idx, 'response_time_ms'] for idx in predictions.index]
                avg_time = sum(scores) / len(scores) if scores else 0.0
                return MetricValue(
                    scores=scores,
                    aggregate_results={"avg_response_time_ms": avg_time}
                )
            return metric_fn

        # Create metric instances
        retrieval_accuracy = make_metric(
            eval_fn=make_retrieval_accuracy_metric(eval_with_predictions),
            greater_is_better=True,
            name="retrieval_accuracy"
        )

        citation_validity = make_metric(
            eval_fn=make_citation_validity_metric(eval_with_predictions),
            greater_is_better=True,
            name="citation_validity"
        )

        response_time = make_metric(
            eval_fn=make_response_time_metric(eval_with_predictions),
            greater_is_better=False,
            name="avg_response_time_ms"
        )

        # Evaluate with MLFlow
        results = mlflow.evaluate(
            data=eval_with_predictions,
            targets="expected_answer",
            predictions="answer",
            extra_metrics=[retrieval_accuracy, citation_validity, response_time],
            evaluator_config={"col_mapping": {"inputs": "question"}}
        )

        print(f"\nMLFlow tracking: Experiment '{config.experiment_name}', Run '{config.run_id}'")
        print(f"View at: http://127.0.0.1:5001\n")

        # Print summary
        print("=== Evaluation Summary ===")
        metrics = results.metrics
        print(f"Total questions: {len(eval_df)}")
        print(f"Correct article retrieval: {metrics.get('retrieval_accuracy', 0):.1%}")
        print(f"Avg citation validity: {metrics.get('citation_validity', 0):.1%}")
        print(f"Avg response time: {metrics.get('avg_response_time_ms', 0):.0f}ms")

        # Export results for backward compatibility
        print(f"\n=== Exporting Results ===")
        export_auto_results(config, eval_df, predictions_df)
        export_for_llm_judge(config, eval_df, predictions_df)

        print(f"\n{'='*60}")
        print("Next Steps:")
        print(f"{'='*60}")
        print(f"1. Open Google AI Studio: https://aistudio.google.com/")
        print(f"2. Enable JSON mode, paste schema: evals/core/llm_judge_structured_output.json")
        print(f"3. Paste prompt from: {config.get_llm_judge_prompt_path()}")
        print(f"4. Save JSON output as: {config.get_llm_judge_results_path()}")
        print(f"5. Merge: python -m evals.merge_auto_and_judge --experiment {config.experiment_name} --run {config.run_id}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
