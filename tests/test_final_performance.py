"""
Final performance test with optimized query pattern.
Uses a sample embedding to test database query speed only.
"""

import os
import sys
import time

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger

setup_logging(level="INFO")
logger = get_logger(__name__)

engine = create_engine(os.getenv("DATABASE_URL"))


def get_sample_embedding():
    """Get a real embedding from the database to use for testing."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT embedding FROM document_chunks
            WHERE embedding IS NOT NULL
            LIMIT 1
        """))
        row = result.fetchone()
        if row:
            # Convert vector to list format
            return str(row[0])
    return None


def optimized_search(embedding_str: str, limit: int = 5):
    """Optimized search pattern (no JOIN, forced index)."""
    with engine.connect() as conn:
        # Enable optimizations
        conn.execute(text("SET enable_seqscan = off"))
        conn.execute(text("SET hnsw.ef_search = 40"))

        start = time.time()

        # Get chunks first
        chunk_result = conn.execute(text(f"""
            SELECT dc.document_chunk_id, dc.document_id, dc.section, dc.content,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """))
        chunks = list(chunk_result)

        # Batch-fetch titles
        if chunks:
            doc_ids = tuple(set(c[1] for c in chunks))
            if len(doc_ids) == 1:
                title_result = conn.execute(text(f"""
                    SELECT document_id, title FROM documents
                    WHERE document_id = {doc_ids[0]}
                """))
            else:
                title_result = conn.execute(text(f"""
                    SELECT document_id, title FROM documents
                    WHERE document_id IN {doc_ids}
                """))
            titles = {row[0]: row[1] for row in title_result}
        else:
            titles = {}

        elapsed = (time.time() - start) * 1000

        # Combine results
        results = []
        for chunk in chunks:
            chunk_id, doc_id, section, content, similarity = chunk
            title = titles.get(doc_id, "Unknown")
            results.append((chunk_id, section, content, title, similarity))

        return elapsed, results


def old_search_with_join(embedding_str: str, limit: int = 5):
    """Original search pattern with JOIN for comparison."""
    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))

        start = time.time()

        result = conn.execute(text(f"""
            SELECT dc.document_chunk_id, dc.section, dc.content,
                   d.title,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.document_id
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """))
        rows = list(result)

        elapsed = (time.time() - start) * 1000

        return elapsed, rows


def main():
    """Test optimized search performance."""
    logger.info("=" * 80)
    logger.info("FINAL PERFORMANCE TEST - DATABASE QUERY ONLY")
    logger.info("=" * 80)

    # Get a sample embedding from the database
    logger.info("\nFetching sample embedding from database...")
    embedding_str = get_sample_embedding()

    if not embedding_str:
        logger.error("No embeddings found in database!")
        return

    logger.info("Sample embedding obtained.")

    # Test old pattern (with JOIN)
    logger.info("\n" + "=" * 80)
    logger.info("OLD PATTERN (with JOIN) - 10 runs")
    logger.info("=" * 80)

    old_times = []
    for i in range(10):
        elapsed, results = old_search_with_join(embedding_str, limit=5)
        old_times.append(elapsed)

    old_avg = sum(old_times) / len(old_times)
    logger.info(f"Average: {old_avg:6.1f}ms  |  Min: {min(old_times):6.1f}ms  |  Max: {max(old_times):6.1f}ms")

    # Test new pattern (no JOIN)
    logger.info("\n" + "=" * 80)
    logger.info("NEW PATTERN (no JOIN, optimized) - 10 runs")
    logger.info("=" * 80)

    new_times = []
    for i in range(10):
        elapsed, results = optimized_search(embedding_str, limit=5)
        new_times.append(elapsed)

    new_avg = sum(new_times) / len(new_times)
    logger.info(f"Average: {new_avg:6.1f}ms  |  Min: {min(new_times):6.1f}ms  |  Max: {max(new_times):6.1f}ms")

    # Show improvement
    logger.info("\n" + "=" * 80)
    logger.info("PERFORMANCE IMPROVEMENT")
    logger.info("=" * 80)
    speedup = old_avg / new_avg if new_avg > 0 else 0
    improvement_pct = ((old_avg - new_avg) / old_avg * 100) if old_avg > 0 else 0

    logger.info(f"\nOld pattern (with JOIN):    {old_avg:6.1f}ms")
    logger.info(f"New pattern (no JOIN):      {new_avg:6.1f}ms")
    logger.info(f"Improvement:                {improvement_pct:6.1f}%")
    logger.info(f"Speedup:                    {speedup:6.1f}x")

    logger.info("\nOptimizations applied:")
    logger.info("  ✓ SET enable_seqscan = off (forces HNSW index)")
    logger.info("  ✓ SET hnsw.ef_search = 40 (balance speed/quality)")
    logger.info("  ✓ Removed JOIN (fetch titles separately)")
    logger.info("  ✓ Batch title lookup (single query for all doc_ids)")

    # Show sample results
    logger.info("\n" + "=" * 80)
    logger.info("SAMPLE RESULTS")
    logger.info("=" * 80)
    _, results = optimized_search(embedding_str, limit=3)
    for i, (chunk_id, section, content, title, similarity) in enumerate(results, 1):
        logger.info(f"\n{i}. Similarity: {similarity:.4f}")
        logger.info(f"   Paper: {title[:70]}...")
        logger.info(f"   Section: {section}")
        logger.info(f"   Content: {content[:100]}...")


if __name__ == "__main__":
    main()
