"""
Test performance with forced index usage vs sequential scan.
"""

import os
import sys
import time

from sqlalchemy import create_engine, text
from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger

setup_logging(level="INFO")
logger = get_logger(__name__)

engine = create_engine(os.getenv("DATABASE_URL"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_query_embedding(query_text: str):
    """Generate embedding for a query string."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query_text
    )
    return response.data[0].embedding


def test_with_seqscan(embedding_str: str, limit: int = 10):
    """Test query with sequential scan enabled (default)."""
    with engine.connect() as conn:
        # Enable sequential scan (default)
        conn.execute(text("SET enable_seqscan = on"))

        start = time.time()
        result = conn.execute(text(f"""
            SELECT dc.document_chunk_id,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """))
        rows = result.fetchall()
        elapsed = (time.time() - start) * 1000

    return elapsed, rows


def test_without_seqscan(embedding_str: str, limit: int = 10):
    """Test query with sequential scan disabled (forces index usage)."""
    with engine.connect() as conn:
        # Disable sequential scan to force index usage
        conn.execute(text("SET enable_seqscan = off"))

        start = time.time()
        result = conn.execute(text(f"""
            SELECT dc.document_chunk_id,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """))
        rows = result.fetchall()
        elapsed = (time.time() - start) * 1000

        # Re-enable sequential scan
        conn.execute(text("SET enable_seqscan = on"))

    return elapsed, rows


def test_explain_with_force_index(embedding_str: str):
    """Show query plan with forced index usage."""
    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))

        result = conn.execute(text(f"""
            EXPLAIN ANALYZE
            SELECT dc.document_chunk_id,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT 10
        """))

        logger.info("\nQuery plan with FORCED INDEX USAGE:")
        logger.info("-" * 80)
        for row in result:
            logger.info(row[0])

        conn.execute(text("SET enable_seqscan = on"))


def main():
    """Compare performance with and without forced index usage."""
    logger.info("=" * 80)
    logger.info("TESTING FORCED INDEX USAGE")
    logger.info("=" * 80)

    # Get test embedding
    query_text = "diabetes treatment with insulin"
    logger.info(f"\nTest query: '{query_text}'")
    query_embedding = get_query_embedding(query_text)
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    # Test different LIMIT values
    limits = [5, 10, 50, 100]

    logger.info("\n" + "=" * 80)
    logger.info("PERFORMANCE COMPARISON")
    logger.info("=" * 80)
    logger.info(f"\n{'LIMIT':>6} {'Sequential Scan':>16} {'Forced Index':>16} {'Speedup':>12}")
    logger.info("-" * 80)

    for limit in limits:
        # Test with sequential scan (default)
        seqscan_time, seqscan_rows = test_with_seqscan(embedding_str, limit)

        # Test with forced index
        index_time, index_rows = test_without_seqscan(embedding_str, limit)

        # Calculate speedup
        speedup = seqscan_time / index_time if index_time > 0 else 0

        logger.info(f"{limit:>6} {seqscan_time:>13.1f}ms {index_time:>13.1f}ms {speedup:>11.1f}x")

        # Verify results are the same
        if seqscan_rows[0][0] != index_rows[0][0]:
            logger.warning(f"  WARNING: Different results! SeqScan chunk_id={seqscan_rows[0][0]}, Index chunk_id={index_rows[0][0]}")

    # Show query plan with forced index
    logger.info("\n" + "=" * 80)
    logger.info("QUERY EXECUTION PLAN")
    logger.info("=" * 80)
    test_explain_with_force_index(embedding_str)

    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)
    logger.info("\nIf forced index is faster, we should:")
    logger.info("  1. Add 'SET enable_seqscan = off' to similarity search queries")
    logger.info("  2. OR migrate to separate table for embedded chunks (Option 2)")


if __name__ == "__main__":
    main()
