"""Automated metric calculations for RAG evaluation."""
import re
from typing import List
from app.db.database import get_db
from sqlalchemy import text


def calculate_retrieval_accuracy(expected_pmc_id: str, retrieved_chunk_ids: List[int]) -> bool:
    """Check if any retrieved chunk came from expected article."""
    db = next(get_db())
    stmt = text("""
        SELECT EXISTS (
            SELECT 1
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.document_id
            WHERE c.document_chunk_id = ANY(:chunk_ids)
            AND d.source_id = :expected_pmc_id
        )
    """)
    result = db.execute(stmt, {
        "chunk_ids": retrieved_chunk_ids,
        "expected_pmc_id": expected_pmc_id
    })
    return result.scalar()


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
    stmt = text("""
        SELECT DISTINCT d.source_id
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.document_id
        WHERE c.document_chunk_id = ANY(:chunk_ids)
    """)
    result = db.execute(stmt, {"chunk_ids": retrieved_chunk_ids})
    retrieved_pmc_ids = {row[0] for row in result}

    # Count valid citations: cited PMCs that ARE in retrieved set
    valid = sum(1 for pmc in unique_cited_pmcs if pmc in retrieved_pmc_ids)

    return valid / len(unique_cited_pmcs)


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
