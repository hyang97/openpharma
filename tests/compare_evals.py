"""
Compare two evaluation runs side-by-side.

Usage:
    python tests/compare_evals.py logs/results/eval_baseline.json logs/results/eval_reranking.json
"""
import argparse
import json
from pathlib import Path
from typing import Dict


def load_eval_results(run: str, version: str) -> Dict:
    """Load evaluation results from JSON."""
    path = Path("logs/results") / run / f"{version}.json"

    with open(path, 'r') as f:
        return json.load(f)


def calculate_delta(val1: float, val2: float, is_percentage: bool = False) -> str:
    """
    Calculate delta between two values.

    Args:
        val1: Baseline value
        val2: Comparison value
        is_percentage: If True, format as percentage points

    Returns:
        Formatted delta string (e.g., "+3%", "-0.05", "+4.2s")
    """
    delta = val2 - val1
    sign = "+" if delta > 0 else ""

    if is_percentage:
        # For percentages, multiply by 100 to get percentage points
        return f"{sign}{delta * 100:.1f}pp"
    else:
        return f"{sign}{delta:.2f}"


def print_comparison_table(results1: Dict, results2: Dict):
    """
    Print side-by-side comparison table.

    Args:
        results1: Baseline evaluation results
        results2: Comparison evaluation results
    """
    # Extract version names and summaries
    config1 = results1.get("config", {}).get("version", "Version 1")
    config2 = results2.get("config", {}).get("version", "Version 2")
    summary1 = results1.get("summary", {})
    summary2 = results2.get("summary", {})

    # Print header
    print(f"| Metric                     | {config1:15s} | {config2:15s} | Delta        |")
    print(f"|----------------------------|-----------------|-----------------|--------------|")

    # Answer Accuracy
    acc1 = summary1.get("answer_accuracy", 0)
    acc2 = summary2.get("answer_accuracy", 0)
    delta_acc = calculate_delta(acc1, acc2, is_percentage=True)
    print(f"| Answer Accuracy            | {acc1:14.1%} | {acc2:14.1%} | {delta_acc:12s} |")

    # Citation Hallucination
    hall1 = summary1.get("avg_citation_hallucination_rate", 0)
    hall2 = summary2.get("avg_citation_hallucination_rate", 0)
    delta_hall = calculate_delta(hall1, hall2, is_percentage=True)
    print(f"| Citation Hallucination     | {hall1:14.1%} | {hall2:14.1%} | {delta_hall:12s} |")

    # Citation Coverage
    cov1 = summary1.get("avg_citation_coverage", 0)
    cov2 = summary2.get("avg_citation_coverage", 0)
    delta_cov = calculate_delta(cov1, cov2, is_percentage=True)
    print(f"| Citation Coverage          | {cov1:14.1%} | {cov2:14.1%} | {delta_cov:12s} |")

    # Response Time
    time1 = summary1.get("avg_response_time_ms", 0) / 1000  # Convert to seconds
    time2 = summary2.get("avg_response_time_ms", 0) / 1000
    delta_time = calculate_delta(time1, time2)
    print(f"| Avg Response Time (s)      | {time1:14.1f} | {time2:14.1f} | {delta_time:12s} |")

    # Total Questions
    total1 = summary1.get("total_questions", 0)
    total2 = summary2.get("total_questions", 0)
    print(f"\n| Total Questions            | {total1:15d} | {total2:15d} |              |")

    # Successful vs Errors
    success1 = summary1.get("successful", 0)
    success2 = summary2.get("successful", 0)
    errors1 = summary1.get("errors", 0)
    errors2 = summary2.get("errors", 0)
    print(f"| Successful                 | {success1:15d} | {success2:15d} |              |")
    print(f"| Errors                     | {errors1:15d} | {errors2:15d} |              |")


def main():
    parser = argparse.ArgumentParser(description="Compare two evaluation runs")
    parser.add_argument("--run", required=True, help="Evaluation run name")
    parser.add_argument("--v1", required=True, help="First version to compare")
    parser.add_argument("--v2", required=True, help="Second version to compare")

    args = parser.parse_args()

    # Load results
    print(f"Loading evaluation results from run '{args.run}'...")
    print(f"Comparing: {args.v1} vs {args.v2}")
    results1 = load_eval_results(args.run, args.v1)
    results2 = load_eval_results(args.run, args.v2)

    # Print comparison
    print(f"\n=== Evaluation Comparison: {args.run} ===\n")
    print_comparison_table(results1, results2)


if __name__ == "__main__":
    main()
