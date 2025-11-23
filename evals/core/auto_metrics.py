"""Automated metric calculations for RAG evaluation."""
import re
from typing import List, Dict
import pandas as pd
from mlflow.metrics import MetricValue
from app.db.database import get_db
from sqlalchemy import text


def calculate_retrieval_accuracy(expected_pmc_id: str, retrieved_chunk_ids: List[int]) -> bool:
    """Check if any retrieved chunk came from expected article."""
    db = next(get_db())
    try:
        stmt = text("""
            SELECT EXISTS (
                SELECT 1
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.document_id
                WHERE c.document_chunk_id = ANY(:chunk_ids)
                AND d.source_id = :expected_pmc_id
            )
        """)
        # Convert numpy types to Python types for psycopg2
        chunk_ids_list = [int(x) for x in retrieved_chunk_ids]
        pmc_id_str = str(expected_pmc_id)

        result = db.execute(stmt, {
            "chunk_ids": chunk_ids_list,
            "expected_pmc_id": pmc_id_str
        })
        return result.scalar()
    finally:
        db.close()


def calculate_citation_validity(raw_llm_response: str, retrieved_chunk_ids: List[int]) -> float:
    """Calculate percentage of valid citations (0-1)."""
    # Extract all [PMCxxxxx] citations from raw LLM response
    cited_pmcs = re.findall(r'\[PMC(\d+)\]', raw_llm_response)

    if not cited_pmcs:
        return 0.0  # No citations = 0% validity (worst case)

    # Get unique cited PMC IDs
    unique_cited_pmcs = set(cited_pmcs)

    # Fetch source_ids (PMC IDs) for retrieved chunks from database
    db = next(get_db())
    try:
        stmt = text("""
            SELECT DISTINCT d.source_id
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.document_id
            WHERE c.document_chunk_id = ANY(:chunk_ids)
        """)
        # Convert numpy types to Python types for psycopg2
        chunk_ids_list = [int(x) for x in retrieved_chunk_ids]
        result = db.execute(stmt, {"chunk_ids": chunk_ids_list})
        retrieved_pmc_ids = {row[0] for row in result}

        # Count valid citations: cited PMCs that ARE in retrieved set
        valid = sum(1 for pmc in unique_cited_pmcs if pmc in retrieved_pmc_ids)

        return valid / len(unique_cited_pmcs)
    finally:
        db.close()


def calculate_summary_stats(results: List[dict]) -> dict:
    """Calculate summary statistics across evaluation results."""
    successful_results = [r for r in results if r['error'] is None]

    if successful_results:
        return {
            "total_questions": len(results),
            "successful": len(successful_results),
            "errors": len(results) - len(successful_results),
            "correct_article_retrieval_rate": sum(r['correct_article_retrieved'] for r in successful_results) / len(successful_results),
            "avg_citation_validity_rate": sum(r['citation_validity_rate'] for r in successful_results) / len(successful_results),
            "avg_citations_per_question": sum(len(r['citations']) for r in successful_results) / len(successful_results),
            "avg_response_time_ms": sum(r['response_time_ms'] for r in successful_results) / len(successful_results),
        }
    else:
        return {
            "total_questions": len(results),
            "successful": 0,
            "errors": len(results),
            "correct_article_retrieval_rate": 0.0,
            "avg_citation_validity_rate": 0.0,
            "avg_citations_per_question": 0.0,
            "avg_response_time_ms": 0.0,
        }


# MLFlow-compatible metric functions

def retrieval_accuracy_mlflow(predictions: pd.Series, targets: pd.Series, metrics: Dict, **kwargs) -> MetricValue:
    """
    MLFlow metric: Check if correct article was retrieved.

    MLFlow passes predictions and targets as Series, plus any extra columns via kwargs.
    We need pmc_id and retrieved_chunk_ids from the full eval DataFrame.
    """
    # Access full DataFrame from kwargs if available
    eval_df = kwargs.get('eval_df')
    if eval_df is None:
        return MetricValue(aggregate_results={"retrieval_accuracy": 0.0})

    scores = []
    for idx in predictions.index:
        row = eval_df.loc[idx]
        correct = calculate_retrieval_accuracy(row['pmc_id'], row['retrieved_chunk_ids'])
        scores.append(1.0 if correct else 0.0)

    aggregate_score = sum(scores) / len(scores) if scores else 0.0
    return MetricValue(aggregate_results={"retrieval_accuracy": aggregate_score})


def citation_validity_mlflow(predictions: pd.Series, targets: pd.Series, metrics: Dict, **kwargs) -> MetricValue:
    """
    MLFlow metric: Validate citations match retrieved chunks.

    Needs raw_llm_response and retrieved_chunk_ids from full DataFrame.
    """
    eval_df = kwargs.get('eval_df')
    if eval_df is None:
        return MetricValue(aggregate_results={"citation_validity": 0.0})

    scores = []
    for idx in predictions.index:
        row = eval_df.loc[idx]
        validity = calculate_citation_validity(row['raw_llm_response'], row['retrieved_chunk_ids'])
        scores.append(validity)

    aggregate_score = sum(scores) / len(scores) if scores else 0.0
    return MetricValue(aggregate_results={"citation_validity": aggregate_score})


def response_time_mlflow(predictions: pd.Series, targets: pd.Series, metrics: Dict, **kwargs) -> MetricValue:
    """
    MLFlow metric: Track average response time.

    Needs response_time_ms from full DataFrame.
    """
    eval_df = kwargs.get('eval_df')
    if eval_df is None:
        return MetricValue(aggregate_results={"avg_response_time_ms": 0.0})

    avg_time = eval_df['response_time_ms'].mean() if len(eval_df) > 0 else 0.0
    return MetricValue(aggregate_results={"avg_response_time_ms": avg_time})
