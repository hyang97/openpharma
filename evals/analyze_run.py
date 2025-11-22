"""
Analyze evaluation results for one or two run versions.

Usage:
    # Single version - show metrics
    python -m evals.analyze_run baseline/v1

    # Two versions - side-by-side comparison
    python -m evals.analyze_run baseline/v1 baseline/v2
    python -m evals.analyze_run baseline/v1 reranking_test/v1
"""
import argparse
from pathlib import Path
from typing import Dict

from evals.core.utils import load_json


def parse_run_version(run_version: str) -> tuple:
    """Parse 'run/version' format into (run, version)."""
    parts = run_version.split('/')
    if len(parts) != 2:
        raise ValueError(f"Invalid format: {run_version}. Expected 'run/version' (e.g., baseline/v1)")
    return parts[0], parts[1]


def load_complete_results(run: str, version: str) -> Dict:
    """Load complete merged evaluation results."""
    path = Path("logs/eval_results") / run / f"{version}_complete_results.json"
    return load_json(str(path))


def calculate_delta(val1: float, val2: float, is_percentage: bool = False) -> str:
    """Calculate delta between two values."""
    delta = val2 - val1
    sign = "+" if delta > 0 else ""

    if is_percentage:
        return f"{sign}{delta * 100:.1f}pp"
    else:
        return f"{sign}{delta:.2f}"


def print_single_version(label: str, results: Dict):
    """Print metrics for a single version."""
    summary = results.get("summary", {})

    # Automated metrics table
    print("Automated Metrics")
    print(f"| Metric                  | {label:15s} |")
    print(f"|-------------------------|-----------------|")

    ret = summary.get("correct_article_retrieval_rate", 0)
    print(f"| Article Retrieval       | {ret:14.1%} |")

    cit = summary.get("avg_citation_validity_rate", 0)
    print(f"| Citation Validity       | {cit:14.1%} |")

    time = summary.get("avg_response_time_ms", 0)
    print(f"| Avg Response Time (ms)  | {time:14.0f} |")

    total = summary.get("total_questions", 0)
    print(f"| Total Questions         | {total:15d} |")

    success = summary.get("successful", 0)
    print(f"| Successful              | {success:15d} |")

    errors = summary.get("errors", 0)
    print(f"| Errors                  | {errors:15d} |")

    # LLM-as-Judge metrics (if available)
    judge = summary.get("llm_judge_evaluation")
    if judge:
        print(f"\nLLM-as-Judge Metrics")
        print(f"| Metric                  | {label:15s} |")
        print(f"|-------------------------|-----------------|")

        total = summary.get("total_questions", 1)
        concl = judge['conclusion_match_correct'] / total
        print(f"| Conclusion Match        | {concl:14.1%} |")

        reas = judge['reasoning_match_correct'] / total
        print(f"| Reasoning Match         | {reas:14.1%} |")

        faith = judge['avg_faithfulness']
        print(f"| Faithfulness (1-5)      | {faith:14.1f} |")

        rel = judge['avg_relevance']
        print(f"| Relevance (1-5)         | {rel:14.1f} |")

        prec = judge['avg_precision']
        print(f"| Precision (1-5)         | {prec:14.1f} |")

        rec = judge['avg_recall']
        print(f"| Recall (1-5)            | {rec:14.1f} |")


def print_comparison_table(label1: str, label2: str, results1: Dict, results2: Dict):
    """Print side-by-side comparison tables."""
    summary1 = results1.get("summary", {})
    summary2 = results2.get("summary", {})

    # Automated metrics table
    print("Automated Metrics")
    print(f"| Metric                  | {label1:15s} | {label2:15s} | Delta        |")
    print(f"|-------------------------|-----------------|-----------------|--------------|")

    ret1 = summary1.get("correct_article_retrieval_rate", 0)
    ret2 = summary2.get("correct_article_retrieval_rate", 0)
    delta_ret = calculate_delta(ret1, ret2, is_percentage=True)
    print(f"| Article Retrieval       | {ret1:14.1%} | {ret2:14.1%} | {delta_ret:12s} |")

    cit1 = summary1.get("avg_citation_validity_rate", 0)
    cit2 = summary2.get("avg_citation_validity_rate", 0)
    delta_cit = calculate_delta(cit1, cit2, is_percentage=True)
    print(f"| Citation Validity       | {cit1:14.1%} | {cit2:14.1%} | {delta_cit:12s} |")

    time1 = summary1.get("avg_response_time_ms", 0)
    time2 = summary2.get("avg_response_time_ms", 0)
    delta_time = calculate_delta(time1, time2)
    print(f"| Avg Response Time (ms)  | {time1:14.0f} | {time2:14.0f} | {delta_time:12s} |")

    total1 = summary1.get("total_questions", 0)
    total2 = summary2.get("total_questions", 0)
    print(f"| Total Questions         | {total1:15d} | {total2:15d} |              |")

    success1 = summary1.get("successful", 0)
    success2 = summary2.get("successful", 0)
    print(f"| Successful              | {success1:15d} | {success2:15d} |              |")

    errors1 = summary1.get("errors", 0)
    errors2 = summary2.get("errors", 0)
    print(f"| Errors                  | {errors1:15d} | {errors2:15d} |              |")

    # LLM-as-Judge metrics (if available)
    judge1 = summary1.get("llm_judge_evaluation")
    judge2 = summary2.get("llm_judge_evaluation")

    if judge1 and judge2:
        print(f"\nLLM-as-Judge Metrics")
        print(f"| Metric                  | {label1:15s} | {label2:15s} | Delta        |")
        print(f"|-------------------------|-----------------|-----------------|--------------|")

        total1 = summary1.get("total_questions", 1)
        total2 = summary2.get("total_questions", 1)

        concl1 = judge1['conclusion_match_correct'] / total1
        concl2 = judge2['conclusion_match_correct'] / total2
        delta_concl = calculate_delta(concl1, concl2, is_percentage=True)
        print(f"| Conclusion Match        | {concl1:14.1%} | {concl2:14.1%} | {delta_concl:12s} |")

        reas1 = judge1['reasoning_match_correct'] / total1
        reas2 = judge2['reasoning_match_correct'] / total2
        delta_reas = calculate_delta(reas1, reas2, is_percentage=True)
        print(f"| Reasoning Match         | {reas1:14.1%} | {reas2:14.1%} | {delta_reas:12s} |")

        faith1 = judge1['avg_faithfulness']
        faith2 = judge2['avg_faithfulness']
        delta_faith = calculate_delta(faith1, faith2)
        print(f"| Faithfulness (1-5)      | {faith1:14.1f} | {faith2:14.1f} | {delta_faith:12s} |")

        rel1 = judge1['avg_relevance']
        rel2 = judge2['avg_relevance']
        delta_rel = calculate_delta(rel1, rel2)
        print(f"| Relevance (1-5)         | {rel1:14.1f} | {rel2:14.1f} | {delta_rel:12s} |")

        prec1 = judge1['avg_precision']
        prec2 = judge2['avg_precision']
        delta_prec = calculate_delta(prec1, prec2)
        print(f"| Precision (1-5)         | {prec1:14.1f} | {prec2:14.1f} | {delta_prec:12s} |")

        rec1 = judge1['avg_recall']
        rec2 = judge2['avg_recall']
        delta_rec = calculate_delta(rec1, rec2)
        print(f"| Recall (1-5)            | {rec1:14.1f} | {rec2:14.1f} | {delta_rec:12s} |")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze evaluation results for one or two run versions",
        epilog="Examples:\n"
               "  Single version:  python -m evals.analyze_run baseline/v1\n"
               "  Comparison:      python -m evals.analyze_run baseline/v1 baseline/v2",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("run_version_1", help="First run/version (e.g., baseline/v1)")
    parser.add_argument("run_version_2", nargs='?', help="Second run/version for comparison (optional)")

    args = parser.parse_args()

    # Parse run/version format for first version
    run1, version1 = parse_run_version(args.run_version_1)
    results1 = load_complete_results(run1, version1)

    if args.run_version_2:
        # Two versions - comparison mode
        run2, version2 = parse_run_version(args.run_version_2)
        results2 = load_complete_results(run2, version2)

        print(f"Loading: {args.run_version_1} vs {args.run_version_2}")
        print(f"\n=== Evaluation Comparison ===\n")
        print_comparison_table(args.run_version_1, args.run_version_2, results1, results2)
    else:
        # Single version - just show metrics
        print(f"Loading: {args.run_version_1}")
        print(f"\n=== Evaluation Results ===\n")
        print_single_version(args.run_version_1, results1)


if __name__ == "__main__":
    main()
