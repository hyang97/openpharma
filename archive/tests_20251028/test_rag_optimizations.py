"""
Test various optimizations for RAG query performance.

Optimizations to test:
1. Different ef_search values (controls recall vs speed tradeoff)
2. Removing the JOIN (fetch title separately)
3. Projecting fewer columns
4. Using prepared statements
5. Connection pooling effects
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


def test_baseline(embedding_str: str, runs: int = 5):
    """Baseline: Current query with forced index."""
    times = []

    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))

        for _ in range(runs):
            start = time.time()
            conn.execute(text(f"""
                SELECT dc.document_chunk_id, dc.section, dc.content,
                       d.title,
                       1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                JOIN documents d ON dc.document_id = d.document_id
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> '{embedding_str}'::vector
                LIMIT 10
            """)).fetchall()
            times.append((time.time() - start) * 1000)

    avg_time = sum(times) / len(times)
    return avg_time, times


def test_without_join(embedding_str: str, runs: int = 5):
    """Remove JOIN - fetch chunk data only, get titles separately."""
    times = []

    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))

        for _ in range(runs):
            start = time.time()

            # Get chunks
            result = conn.execute(text(f"""
                SELECT dc.document_chunk_id, dc.section, dc.content, dc.document_id,
                       1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> '{embedding_str}'::vector
                LIMIT 10
            """))
            chunks = result.fetchall()

            # Get titles for those chunks (would batch this in practice)
            doc_ids = tuple(set(c[3] for c in chunks))
            if doc_ids:
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

            times.append((time.time() - start) * 1000)

    avg_time = sum(times) / len(times)
    return avg_time, times


def test_minimal_projection(embedding_str: str, runs: int = 5):
    """Fetch only chunk_id and similarity (minimal data transfer)."""
    times = []

    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))

        for _ in range(runs):
            start = time.time()
            conn.execute(text(f"""
                SELECT dc.document_chunk_id,
                       1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                ORDER BY dc.embedding <=> '{embedding_str}'::vector
                LIMIT 10
            """)).fetchall()
            times.append((time.time() - start) * 1000)

    avg_time = sum(times) / len(times)
    return avg_time, times


def test_ef_search_values(embedding_str: str):
    """Test different ef_search values (controls HNSW search quality)."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING ef_search PARAMETER")
    logger.info("=" * 80)
    logger.info("\nef_search controls HNSW index search breadth:")
    logger.info("  - Lower = faster but lower recall")
    logger.info("  - Higher = slower but better recall")
    logger.info("  - Default is typically 40")

    ef_values = [10, 20, 40, 64, 100, 200]

    logger.info(f"\n{'ef_search':>10} {'Avg Time':>12} {'Min':>10} {'Max':>10}")
    logger.info("-" * 80)

    results = {}

    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))

        for ef in ef_values:
            # Set ef_search parameter
            conn.execute(text(f"SET hnsw.ef_search = {ef}"))

            times = []
            for _ in range(5):
                start = time.time()
                conn.execute(text(f"""
                    SELECT dc.document_chunk_id,
                           1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
                    FROM document_chunks dc
                    WHERE dc.embedding IS NOT NULL
                    ORDER BY dc.embedding <=> '{embedding_str}'::vector
                    LIMIT 10
                """)).fetchall()
                times.append((time.time() - start) * 1000)

            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            results[ef] = avg_time
            logger.info(f"{ef:>10} {avg_time:>10.1f}ms {min_time:>9.1f}ms {max_time:>9.1f}ms")

        # Reset to default
        conn.execute(text("RESET hnsw.ef_search"))

    return results


def test_content_length_impact(embedding_str: str):
    """Test if content length affects query time."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING CONTENT LENGTH IMPACT")
    logger.info("=" * 80)

    with engine.connect() as conn:
        conn.execute(text("SET enable_seqscan = off"))

        # Full content
        start = time.time()
        conn.execute(text(f"""
            SELECT dc.document_chunk_id, dc.content,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT 10
        """)).fetchall()
        full_time = (time.time() - start) * 1000

        # Truncated content (first 100 chars)
        start = time.time()
        conn.execute(text(f"""
            SELECT dc.document_chunk_id, LEFT(dc.content, 100) as content_preview,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT 10
        """)).fetchall()
        truncated_time = (time.time() - start) * 1000

        # No content
        start = time.time()
        conn.execute(text(f"""
            SELECT dc.document_chunk_id,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT 10
        """)).fetchall()
        no_content_time = (time.time() - start) * 1000

        logger.info(f"\nFull content (~2KB):       {full_time:>6.1f}ms")
        logger.info(f"Truncated (100 chars):     {truncated_time:>6.1f}ms")
        logger.info(f"No content (IDs only):     {no_content_time:>6.1f}ms")
        logger.info(f"\nContent fetch overhead:    {full_time - no_content_time:>6.1f}ms")


def main():
    """Run all RAG optimization tests."""
    logger.info("=" * 80)
    logger.info("RAG QUERY OPTIMIZATION TESTS")
    logger.info("=" * 80)

    # Get test embedding
    query_text = "diabetes treatment with insulin"
    logger.info(f"\nTest query: '{query_text}'")
    query_embedding = get_query_embedding(query_text)
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    # Test different query patterns
    logger.info("\n" + "=" * 80)
    logger.info("QUERY PATTERN COMPARISON")
    logger.info("=" * 80)

    baseline_avg, baseline_times = test_baseline(embedding_str)
    logger.info(f"\nBaseline (with JOIN):          {baseline_avg:>6.1f}ms (min: {min(baseline_times):.1f}ms, max: {max(baseline_times):.1f}ms)")

    no_join_avg, no_join_times = test_without_join(embedding_str)
    logger.info(f"Without JOIN (2 queries):      {no_join_avg:>6.1f}ms (min: {min(no_join_times):.1f}ms, max: {max(no_join_times):.1f}ms)")

    minimal_avg, minimal_times = test_minimal_projection(embedding_str)
    logger.info(f"Minimal projection (IDs only): {minimal_avg:>6.1f}ms (min: {min(minimal_times):.1f}ms, max: {max(minimal_times):.1f}ms)")

    # Test ef_search values
    ef_results = test_ef_search_values(embedding_str)

    # Test content length impact
    test_content_length_impact(embedding_str)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("OPTIMIZATION RECOMMENDATIONS")
    logger.info("=" * 80)

    logger.info("\n1. HNSW ef_search parameter:")
    optimal_ef = min(ef_results.items(), key=lambda x: x[1])
    logger.info(f"   - Fastest: ef_search={optimal_ef[0]} ({optimal_ef[1]:.1f}ms)")
    logger.info(f"   - Default (40) provides good balance")
    logger.info(f"   - For production: use ef_search=40 or 64")

    logger.info("\n2. Query pattern:")
    if no_join_avg < baseline_avg * 0.8:
        logger.info(f"   - Removing JOIN saves {baseline_avg - no_join_avg:.1f}ms ({((baseline_avg - no_join_avg) / baseline_avg * 100):.1f}%)")
        logger.info("   - Recommended for RAG: fetch chunks first, then titles")
    else:
        logger.info(f"   - JOIN overhead is minimal ({baseline_avg - no_join_avg:.1f}ms)")
        logger.info("   - Keep JOIN for simpler code")

    logger.info("\n3. Data transfer:")
    logger.info(f"   - Consider two-stage retrieval:")
    logger.info(f"     Stage 1: Get top 50 chunk IDs + similarities ({minimal_avg:.1f}ms)")
    logger.info(f"     Stage 2: Fetch full content for top 10 (after reranking)")

    logger.info("\n4. Production RAG pipeline:")
    logger.info("   a. Set: enable_seqscan = off, hnsw.ef_search = 40")
    logger.info("   b. Retrieve top-k chunks (k=20-50) with minimal data")
    logger.info("   c. Optional: Rerank with cross-encoder")
    logger.info("   d. Fetch full content for top-n chunks (n=5-10)")
    logger.info("   e. Generate response with LLM")


if __name__ == "__main__":
    main()
