"""
Test HNSW index performance and analyze query execution.
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


def test_explain_plan():
    """Check if HNSW index is being used."""
    logger.info("=" * 80)
    logger.info("QUERY EXECUTION PLAN ANALYSIS")
    logger.info("=" * 80)

    # Get a test embedding
    query_embedding = get_query_embedding("diabetes treatment")
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    with engine.connect() as conn:
        # Run EXPLAIN ANALYZE
        result = conn.execute(text(f"""
            EXPLAIN ANALYZE
            SELECT dc.document_chunk_id, dc.section,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT 10
        """))

        logger.info("\nQuery execution plan:")
        for row in result:
            logger.info(row[0])


def check_index_settings():
    """Check HNSW index configuration and stats."""
    logger.info("\n" + "=" * 80)
    logger.info("INDEX CONFIGURATION")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Check index settings
        result = conn.execute(text("""
            SELECT
                i.indexname,
                i.indexdef,
                pg_size_pretty(pg_relation_size(i.indexname::regclass)) as size
            FROM pg_indexes i
            WHERE i.tablename = 'document_chunks'
              AND i.indexname = 'idx_chunks_embedding'
        """))

        for row in result:
            logger.info(f"\nIndex: {row.indexname}")
            logger.info(f"Size: {row.size}")
            logger.info(f"Definition: {row.indexdef}")


def test_with_different_limits():
    """Test query performance with different LIMIT values."""
    logger.info("\n" + "=" * 80)
    logger.info("PERFORMANCE WITH DIFFERENT LIMITS")
    logger.info("=" * 80)

    query_embedding = get_query_embedding("diabetes treatment")
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    limits = [5, 10, 50, 100]

    for limit in limits:
        with engine.connect() as conn:
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

        logger.info(f"LIMIT {limit:3d}: {elapsed:7.1f}ms")


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

        for setting in settings:
            result = conn.execute(text(f"SHOW {setting}"))
            value = result.scalar()
            logger.info(f"{setting:25s}: {value}")


def test_index_coverage():
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


def main():
    """Run all index performance tests."""
    try:
        check_index_settings()
        check_postgres_config()
        test_index_coverage()
        test_with_different_limits()
        test_explain_plan()

        logger.info("\n" + "=" * 80)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
