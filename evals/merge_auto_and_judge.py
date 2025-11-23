"""
Merge automated evaluation results with LLM-as-judge scores.

Combines automated metrics with LLM-as-judge evaluations from Gemini and logs them to MLFlow.

Usage:
    python -m evals.merge_auto_and_judge --experiment baseline --run v1
"""
import argparse
import csv
import json
import mlflow

from evals.core.schemas import EvaluationConfig
from evals.core.utils import load_json, save_json


def merge_results(config: EvaluationConfig):
    """Merge automated and LLM-as-judge evaluation results."""
    print(f"Loading automated results from: {config.get_auto_results_path()}")
    automated = load_json(config.get_auto_results_path())

    print(f"Loading LLM-as-judge scores from: {config.get_llm_judge_results_path()}")
    llm_judge = load_json(config.get_llm_judge_results_path())

    # Create mapping of question_id -> LLM-as-judge scores
    judge_scores = {
        eval_item['question_id']: eval_item
        for eval_item in llm_judge['evaluations']
    }

    # Merge results
    print(f"Merging {len(automated['results'])} automated results with {len(judge_scores)} LLM-as-judge scores...")

    merged_results = []
    metrics_rows = []
    matched_count = 0

    for auto_result in automated['results']:
        question_id = auto_result['question_id']
        merged = auto_result.copy()

        # Build metrics-only row for CSV
        metrics_row = {
            'question_id': auto_result['question_id'],
            'pmid': auto_result['pmid'],
            'pmc_id': auto_result['pmc_id'],
            'correct_article_retrieved': auto_result['correct_article_retrieved'],
            'citation_validity_rate': auto_result['citation_validity_rate'],
            'response_time_ms': auto_result['response_time_ms'],
            'num_citations': len(auto_result['citations']),
            'num_chunks_retrieved': len(auto_result['retrieved_chunk_ids']),
            'error': auto_result.get('error', ''),
        }

        # Add LLM-as-judge scores if available
        if question_id in judge_scores:
            judge_score = judge_scores[question_id]
            merged['llm_judge_eval'] = {
                'conclusion_match': judge_score['conclusion_match'],
                'reasoning_match': judge_score['reasoning_match'],
                'faithfulness': judge_score['faithfulness'],
                'relevance': judge_score['relevance'],
                'precision': judge_score['precision'],
                'recall': judge_score['recall'],
                'notes': judge_score.get('notes', '')
            }
            metrics_row['conclusion_match'] = judge_score['conclusion_match']
            metrics_row['reasoning_match'] = judge_score['reasoning_match']
            metrics_row['faithfulness'] = judge_score['faithfulness']
            metrics_row['relevance'] = judge_score['relevance']
            metrics_row['precision'] = judge_score['precision']
            metrics_row['recall'] = judge_score['recall']
            matched_count += 1
        else:
            merged['llm_judge_eval'] = None
            metrics_row['conclusion_match'] = ''
            metrics_row['reasoning_match'] = ''
            metrics_row['faithfulness'] = ''
            metrics_row['relevance'] = ''
            metrics_row['precision'] = ''
            metrics_row['recall'] = ''

        merged_results.append(merged)
        metrics_rows.append(metrics_row)

    # Create combined summary
    combined_summary = {
        **automated['summary'],
        'llm_judge_evaluation': llm_judge['summary']
    }

    # Save complete results as JSON
    output = {
        'results': merged_results,
        'summary': combined_summary,
        'config': automated['config']
    }
    json_path = config.get_complete_results_path()
    save_json(output, json_path)

    # Save metrics-only as CSV
    csv_path = config.get_metrics_csv_path()
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'question_id', 'pmid', 'pmc_id',
            'correct_article_retrieved', 'citation_validity_rate', 'response_time_ms',
            'num_citations', 'num_chunks_retrieved', 'error',
            'conclusion_match', 'reasoning_match', 'faithfulness', 'relevance', 'precision', 'recall'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metrics_rows)

    print(f"\n{'='*60}")
    print("Merge Summary")
    print(f"{'='*60}")
    print(f"Automated results: {len(automated['results'])}")
    print(f"LLM-as-judge scores: {len(judge_scores)}")
    print(f"Matched: {matched_count}")
    print(f"Unmatched: {len(automated['results']) - matched_count}")
    print(f"\nComplete results (JSON): {json_path}")
    print(f"Metrics only (CSV):      {csv_path}")
    print(f"{'='*60}")

    # Print combined metrics
    print(f"\nCombined Metrics:")
    print(f"  Automated:")
    print(f"    Article Retrieval: {combined_summary['correct_article_retrieval_rate']:.1%}")
    print(f"    Citation Validity: {combined_summary['avg_citation_validity_rate']:.1%}")
    print(f"    Avg Response Time: {combined_summary['avg_response_time_ms']:.0f}ms")
    print(f"  LLM-as-Judge:")
    judge_sum = combined_summary['llm_judge_evaluation']
    total_judge = len(judge_scores)
    print(f"    Conclusion Match: {judge_sum['conclusion_match_correct']}/{total_judge} ({judge_sum['conclusion_match_correct']/total_judge:.1%})")
    print(f"    Reasoning Match: {judge_sum['reasoning_match_correct']}/{total_judge} ({judge_sum['reasoning_match_correct']/total_judge:.1%})")
    print(f"    Avg Faithfulness: {judge_sum['avg_faithfulness']:.1f}/5")
    print(f"    Avg Relevance: {judge_sum['avg_relevance']:.1f}/5")
    print(f"    Avg Precision: {judge_sum['avg_precision']:.1f}/5")
    print(f"    Avg Recall: {judge_sum['avg_recall']:.1f}/5")

    return combined_summary


def log_to_mlflow(config: EvaluationConfig, combined_summary: dict):
    """Log LLM-as-judge metrics to existing MLFlow run."""
    mlflow.set_experiment(config.experiment_name)

    # Find the existing run by run_name
    experiment = mlflow.get_experiment_by_name(config.experiment_name)
    if not experiment:
        print(f"Warning: Experiment '{config.experiment_name}' not found in MLFlow. Skipping MLFlow logging.")
        return

    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=f"tags.mlflow.runName = '{config.run_id}'"
    )

    if runs.empty:
        print(f"Warning: Run '{config.run_id}' not found in experiment '{config.experiment_name}'. Skipping MLFlow logging.")
        return

    run_id = runs.iloc[0].run_id

    # Log LLM-as-judge metrics to the existing run
    with mlflow.start_run(run_id=run_id):
        judge_sum = combined_summary['llm_judge_evaluation']
        total_questions = combined_summary.get('total_questions', 0)

        # Log aggregate metrics
        mlflow.log_metric("conclusion_match_rate", judge_sum['conclusion_match_correct'] / total_questions if total_questions > 0 else 0)
        mlflow.log_metric("reasoning_match_rate", judge_sum['reasoning_match_correct'] / total_questions if total_questions > 0 else 0)
        mlflow.log_metric("avg_faithfulness", judge_sum['avg_faithfulness'])
        mlflow.log_metric("avg_relevance", judge_sum['avg_relevance'])
        mlflow.log_metric("avg_precision", judge_sum['avg_precision'])
        mlflow.log_metric("avg_recall", judge_sum['avg_recall'])

        # Log complete results as artifact
        mlflow.log_artifact(config.get_complete_results_path(), "merged_results")

        print(f"\n✅ LLM-as-judge metrics logged to MLFlow run: {run_id}")
        print(f"   View at: http://127.0.0.1:5001")


def main():
    parser = argparse.ArgumentParser(description="Merge automated and LLM-as-judge evaluation results")
    parser.add_argument("--experiment", required=True, help="Experiment name")
    parser.add_argument("--run", required=True, help="Run identifier")

    args = parser.parse_args()

    config = EvaluationConfig(
        experiment_name=args.experiment,
        run_id=args.run
    )

    combined_summary = merge_results(config)
    log_to_mlflow(config, combined_summary)


if __name__ == "__main__":
    main()
