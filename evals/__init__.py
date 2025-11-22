"""
OpenPharma RAG Evaluation System

Modular evaluation framework for measuring RAG performance across
automated metrics and LLM-as-judge assessments.

Usage:
    python -m evals.run --run baseline --version v1 --limit 10
    python -m evals.merge_auto_and_judge --run baseline --version v1
    python -m evals.analyze_run baseline/v1              # Single version
    python -m evals.analyze_run baseline/v1 baseline/v2  # Comparison
"""
