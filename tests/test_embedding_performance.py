"""
Comprehensive embedding performance test suite.

Tests HNSW index configuration, query performance, and optimization strategies.
Consolidates test_index_performance.py, test_force_index.py, and test_final_performance.py.
"""

import os
import sys
import time
from typing import List

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger
from app.ingestion.embeddings import EmbeddingService

setup_logging(level="INFO", log_file="logs/test_embedding_performance.log")
logger = get_logger(__name__)

engine = create_engine(os.getenv("DATABASE_URL"))
embedder = EmbeddingService()


def get_query_embedding(query_text: str) -> List[float]:
    """Generate embedding for a query string using Ollama."""
    return embedder.embed_single(query_text)


def get_sample_embedding() -> str:
    """Get a real embedding from the database for testing."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT embedding FROM document_chunks
            WHERE embedding IS NOT NULL
            LIMIT 1
        """))
        row = result.fetchone()
        if row:
            return str(row[0])
    return None


# ============================================================================
# INDEX CONFIGURATION TESTS
# ============================================================================

def check_index_settings():
    """Check HNSW index configuration and stats."""
    logger.info("\n" + "=" * 80)
    logger.info("INDEX CONFIGURATION")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Check index exists and get settings
        result = conn.execute(text("""
            SELECT
                i.indexname,
                i.indexdef,
                pg_size_pretty(pg_relation_size(i.indexname::regclass)) as size
            FROM pg_indexes i
            WHERE i.tablename = 'document_chunks'
              AND i.indexname = 'idx_chunks_embedding'
        """))

        row = result.fetchone()
        if row:
            logger.info(f"\nIndex: {row.indexname}")
            logger.info(f"Size: {row.size}")
            logger.info(f"Definition: {row.indexdef}")
        else:
            logger.warning("\n⚠️  HNSW index not found! Create with:")
            logger.warning("    CREATE INDEX idx_chunks_embedding ON document_chunks")
            logger.warning("    USING hnsw (embedding vector_cosine_ops)")
            logger.warning("    WITH (m = 16, ef_construction = 64);")


def check_index_coverage():
    """Check what percentage of chunks have embeddings."""
    logger.info("\n" + "=" * 80)
    logger.info("INDEX COVERAGE")
    logger.info("=" * 80)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
                COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding,
                COUNT(*) as total,
                ROUND(100.0 * COUNT(*) FILTER (WHERE embedding IS NOT NULL) / COUNT(*), 2) as coverage_pct
            FROM document_chunks
        """))

        row = result.fetchone()
        logger.info(f"\nChunks with embeddings: {row.with_embedding:,}")
        logger.info(f"Chunks without embeddings: {row.without_embedding:,}")
        logger.info(f"Total chunks: {row.total:,}")
        logger.info(f"Coverage: {row.coverage_pct}%")

        if row.coverage_pct < 100:
            logger.warning(f"⚠️  Only {row.coverage_pct}% of chunks have embeddings")


def check_postgres_config():
    """Check relevant PostgreSQL configuration."""
    logger.info("\n" + "=" * 80)
    logger.info("POSTGRESQL CONFIGURATION")
    logger.info("=" * 80)

    with engine.connect() as conn:
        settings = [
            'shared_buffers',
            'work_mem',
            'maintenance_work_mem',
            'effective_cache_size',
            'random_page_cost',
        ]

        logger.info("")
        for setting in settings:
            result = conn.execute(text(f"SHOW {setting}"))
            value = result.scalar()
            logger.info(f"{setting:25s}: {value}")


# ============================================================================
# QUERY PERFORMANCE TESTS
# ============================================================================

def test_query_performance_with_limits():
    """Test query performance with different LIMIT values."""
    logger.info("\n" + "=" * 80)
    logger.info("QUERY PERFORMANCE (Different LIMIT values)")
    logger.info("=" * 80)

    query_embedding = get_query_embedding("diabetes treatment")
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    limits = [5, 10, 20, 50, 100]

    logger.info(f"\n{'LIMIT':>6} {'Time (ms)':>12}")
    logger.info("-" * 20)

    for limit in limits:
        with engine.connect() as conn:
            conn.execute(text("SET enable_seqscan = off"))
            conn.execute(text("SET hnsw.ef_search = 40"))

            start = time.time()
            conn.execute(text(f"""
                SELECT dc.document_chunk_id,
                       1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> '{embedding_str}'::vector
                LIMIT {limit}
            """)).fetchall()
            elapsed = (time.time() - start) * 1000

        logger.info(f"{limit:>6} {elapsed:>11.1f}")

    logger.info("")
    if elapsed > 200:
        logger.warning("⚠️  Queries >200ms - index may not be working properly")
    else:
        logger.info("✓ Good performance (<200ms)")


def test_seqscan_vs_index():
    """Compare sequential scan vs forced index usage."""
    logger.info("\n" + "=" * 80)
    logger.info("SEQUENTIAL SCAN vs FORCED INDEX")
    logger.info("=" * 80)

    query_embedding = get_query_embedding("insulin therapy")
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    limits = [5, 10, 50, 100]

    logger.info(f"\n{'LIMIT':>6} {'SeqScan (ms)':>14} {'Index (ms)':>12} {'Speedup':>10}")
    logger.info("-" * 50)

    for limit in limits:
        # Test with sequential scan enabled
        with engine.connect() as conn:
            conn.execute(text("SET enable_seqscan = on"))

            start = time.time()
            conn.execute(text(f"""
                SELECT dc.document_chunk_id,
                       1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> '{embedding_str}'::vector
                LIMIT {limit}
            """)).fetchall()
            seqscan_time = (time.time() - start) * 1000

        # Test with index forced
        with engine.connect() as conn:
            conn.execute(text("SET enable_seqscan = off"))

            start = time.time()
            conn.execute(text(f"""
                SELECT dc.document_chunk_id,
                       1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> '{embedding_str}'::vector
                LIMIT {limit}
            """)).fetchall()
            index_time = (time.time() - start) * 1000

        speedup = seqscan_time / index_time if index_time > 0 else 0
        logger.info(f"{limit:>6} {seqscan_time:>13.1f} {index_time:>11.1f} {speedup:>9.1f}x")

    logger.info("")
    if speedup > 2:
        logger.info("✓ Index provides significant speedup (>2x)")
        logger.info("  Recommendation: Use 'SET enable_seqscan = off' in RAG queries")
    else:
        logger.warning("⚠️  Index speedup <2x - may need optimization")


def test_join_vs_no_join():
    """Compare JOIN vs separate title lookup performance."""
    logger.info("\n" + "=" * 80)
    logger.info("JOIN vs NO-JOIN OPTIMIZATION")
    logger.info("=" * 80)

    embedding_str = get_sample_embedding()
    if not embedding_str:
        logger.warning("⚠️  No embeddings in database - skipping test")
        return

    # Test with JOIN (original pattern)
    join_times = []
    for _ in range(10):
        with engine.connect() as conn:
            conn.execute(text("SET enable_seqscan = off"))

            start = time.time()
            conn.execute(text(f"""
                SELECT dc.document_chunk_id, dc.section, dc.content,
                       d.title,
                       1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.document_id
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> '{embedding_str}'::vector
                LIMIT 5
            """)).fetchall()
            elapsed = (time.time() - start) * 1000
            join_times.append(elapsed)

    # Test without JOIN (optimized pattern)
    nojoin_times = []
    for _ in range(10):
        with engine.connect() as conn:
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
                LIMIT 5
            """))
            chunks = list(chunk_result)

            # Batch-fetch titles
            if chunks:
                doc_ids = tuple(set(c[1] for c in chunks))
                if len(doc_ids) == 1:
                    conn.execute(text(f"""
                        SELECT document_id, title FROM documents
                        WHERE document_id = {doc_ids[0]}
                    """)).fetchall()
                else:
                    conn.execute(text(f"""
                        SELECT document_id, title FROM documents
                        WHERE document_id IN {doc_ids}
                    """)).fetchall()

            elapsed = (time.time() - start) * 1000
            nojoin_times.append(elapsed)

    join_avg = sum(join_times) / len(join_times)
    nojoin_avg = sum(nojoin_times) / len(nojoin_times)
    improvement = ((join_avg - nojoin_avg) / join_avg * 100) if join_avg > 0 else 0

    logger.info(f"\nWith JOIN (10 runs):     {join_avg:6.1f}ms avg")
    logger.info(f"Without JOIN (10 runs):  {nojoin_avg:6.1f}ms avg")
    logger.info(f"Improvement:             {improvement:6.1f}%")

    if improvement > 10:
        logger.info("\n✓ No-JOIN pattern is faster")
        logger.info("  Recommendation: Use separate title lookup in RAG queries")
    else:
        logger.info("\n  No significant difference - either pattern is fine")


def test_explain_plan():
    """Show query execution plan to verify index usage."""
    logger.info("\n" + "=" * 80)
    logger.info("QUERY EXECUTION PLAN")
    logger.info("=" * 80)

    query_embedding = get_query_embedding("diabetes")
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))
        conn.execute(text("SET hnsw.ef_search = 40"))

        result = conn.execute(text(f"""
            EXPLAIN ANALYZE
            SELECT dc.document_chunk_id, dc.section,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT 10
        """))

        logger.info("")
        for row in result:
            logger.info(row[0])

        logger.info("\nLook for 'Index Scan using idx_chunks_embedding' to confirm HNSW is used")


# ============================================================================
# MAIN TEST SUITE
# ============================================================================

def main():
    """Run all embedding performance tests."""
    logger.info("=" * 80)
    logger.info("EMBEDDING PERFORMANCE TEST SUITE")
    logger.info("=" * 80)
    logger.info(f"\nDatabase: {os.getenv('DATABASE_URL').split('@')[1]}")

    try:
        # Configuration checks
        check_index_settings()
        check_index_coverage()
        check_postgres_config()

        # Performance tests
        test_query_performance_with_limits()
        test_seqscan_vs_index()
        test_join_vs_no_join()
        test_explain_plan()

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUITE COMPLETE")
        logger.info("=" * 80)
        logger.info("\nKey Takeaways:")
        logger.info("  1. Check index is properly configured and being used")
        logger.info("  2. Verify query times are <200ms for production RAG")
        logger.info("  3. Use 'SET enable_seqscan = off' if index speedup >2x")
        logger.info("  4. Consider no-JOIN pattern if >10% faster")

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
