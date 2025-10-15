"""
Data integrity tests for embedding database.

Validates database state, checks for anomalies, and ensures data quality.
"""

import os
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger

setup_logging(level="INFO", log_file="logs/test_data_integrity.log")
logger = get_logger(__name__)

engine = create_engine(os.getenv("DATABASE_URL"))


def test_orphaned_chunks():
    """Check for chunks without parent documents."""
    logger.info("=" * 80)
    logger.info("TEST: Orphaned Chunks")
    logger.info("=" * 80)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as orphaned_count
            FROM document_chunks dc
            LEFT JOIN documents d ON dc.document_id = d.document_id
            WHERE d.document_id IS NULL
        """))
        orphaned_count = result.scalar()

    if orphaned_count == 0:
        logger.info("✓ No orphaned chunks found")
    else:
        logger.error(f"✗ Found {orphaned_count} orphaned chunks without parent documents!")
        logger.error("  This indicates data corruption - chunks should always have parent docs")

    return orphaned_count == 0


def test_embedded_docs_have_chunks():
    """Check that documents marked 'embedded' actually have embedded chunks."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Embedded Documents Have Chunks")
    logger.info("=" * 80)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT d.document_id, d.title
            FROM documents d
            WHERE d.ingestion_status = 'embedded'
              AND NOT EXISTS (
                  SELECT 1 FROM document_chunks dc
                  WHERE dc.document_id = d.document_id
                    AND dc.embedding IS NOT NULL
              )
            LIMIT 10
        """))
        bad_docs = result.fetchall()

    if not bad_docs:
        logger.info("✓ All 'embedded' documents have embedded chunks")
    else:
        logger.error(f"✗ Found {len(bad_docs)} documents marked 'embedded' but missing chunks:")
        for doc_id, title in bad_docs[:5]:
            logger.error(f"  - Doc {doc_id}: {title[:60]}...")
        logger.error("  This indicates incomplete embedding pipeline execution")

    return len(bad_docs) == 0


def test_duplicate_chunks():
    """Check for duplicate chunks (same document_id + chunk_index)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Duplicate Chunks")
    logger.info("=" * 80)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT document_id, chunk_index, COUNT(*) as duplicate_count
            FROM document_chunks
            GROUP BY document_id, chunk_index
            HAVING COUNT(*) > 1
            LIMIT 10
        """))
        duplicates = result.fetchall()

    if not duplicates:
        logger.info("✓ No duplicate chunks found")
    else:
        logger.error(f"✗ Found duplicate chunks:")
        for doc_id, chunk_idx, count in duplicates:
            logger.error(f"  - Doc {doc_id}, chunk {chunk_idx}: {count} copies")
        logger.error("  This indicates chunking pipeline ran multiple times without cleanup")

    return len(duplicates) == 0


def test_embedding_dimensions():
    """Verify all embeddings have correct dimensions (768 for Ollama)."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Embedding Dimensions")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # pgvector doesn't support array_length casting, use vector_dims instead
        result = conn.execute(text("""
            SELECT COUNT(*) as wrong_dim_count
            FROM document_chunks
            WHERE embedding IS NOT NULL
              AND vector_dims(embedding) != 768
        """))
        wrong_dim_count = result.scalar()

        # Get sample of actual dimensions
        result = conn.execute(text("""
            SELECT DISTINCT vector_dims(embedding) as dimension
            FROM document_chunks
            WHERE embedding IS NOT NULL
            LIMIT 5
        """))
        dimensions = [row[0] for row in result]

    if wrong_dim_count == 0:
        logger.info(f"✓ All embeddings have correct dimensions: {dimensions[0] if dimensions else 'N/A'}")
    else:
        logger.error(f"✗ Found {wrong_dim_count} embeddings with wrong dimensions!")
        logger.error(f"  Expected: 768 (Ollama nomic-embed-text)")
        logger.error(f"  Found: {dimensions}")
        logger.error("  This indicates mixed embedding sources or migration issues")

    return wrong_dim_count == 0


def test_ingestion_status_consistency():
    """Check for inconsistent ingestion status across pipeline stages."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Ingestion Status Consistency")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Check documents with chunks but status='fetched'
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM documents d
            WHERE d.ingestion_status = 'fetched'
              AND EXISTS (
                  SELECT 1 FROM document_chunks dc
                  WHERE dc.document_id = d.document_id
              )
        """))
        fetched_with_chunks = result.scalar()

        # Check documents with embeddings but status='chunked'
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM documents d
            WHERE d.ingestion_status = 'chunked'
              AND EXISTS (
                  SELECT 1 FROM document_chunks dc
                  WHERE dc.document_id = d.document_id
                    AND dc.embedding IS NOT NULL
              )
        """))
        chunked_with_embeddings = result.scalar()

    issues = []
    if fetched_with_chunks > 0:
        issues.append(f"{fetched_with_chunks} docs with status='fetched' but have chunks")
    if chunked_with_embeddings > 0:
        issues.append(f"{chunked_with_embeddings} docs with status='chunked' but have embeddings")

    if not issues:
        logger.info("✓ All ingestion statuses are consistent")
    else:
        logger.warning("⚠️  Found status inconsistencies:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        logger.warning("  This may indicate pipeline interruptions (usually harmless)")

    return len(issues) == 0


def test_null_critical_fields():
    """Check for NULL values in critical fields."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: NULL Critical Fields")
    logger.info("=" * 80)

    issues_found = False

    with engine.connect() as conn:
        # Check documents
        result = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE title IS NULL) as null_titles,
                COUNT(*) FILTER (WHERE source IS NULL) as null_sources,
                COUNT(*) FILTER (WHERE source_id IS NULL) as null_source_ids
            FROM documents
        """))
        row = result.fetchone()

        if row.null_titles > 0:
            logger.error(f"✗ Found {row.null_titles} documents with NULL title")
            issues_found = True
        if row.null_sources > 0:
            logger.error(f"✗ Found {row.null_sources} documents with NULL source")
            issues_found = True
        if row.null_source_ids > 0:
            logger.error(f"✗ Found {row.null_source_ids} documents with NULL source_id")
            issues_found = True

        # Check chunks
        result = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE content IS NULL OR content = '') as null_content,
                COUNT(*) FILTER (WHERE section IS NULL) as null_sections
            FROM document_chunks
        """))
        row = result.fetchone()

        if row.null_content > 0:
            logger.error(f"✗ Found {row.null_content} chunks with NULL/empty content")
            issues_found = True
        if row.null_sections > 0:
            logger.warning(f"⚠️  Found {row.null_sections} chunks with NULL section")
            # This is a warning, not an error (section can be null for some sources)

    if not issues_found:
        logger.info("✓ No NULL values in critical fields")

    return not issues_found


def test_chunk_content_length():
    """Check for suspiciously short or long chunks."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Chunk Content Length")
    logger.info("=" * 80)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE length(content) < 50) as very_short,
                COUNT(*) FILTER (WHERE length(content) > 5000) as very_long,
                AVG(length(content))::int as avg_length,
                MIN(length(content)) as min_length,
                MAX(length(content)) as max_length
            FROM document_chunks
        """))
        row = result.fetchone()

    logger.info(f"\nChunk length stats:")
    logger.info(f"  Average: {row.avg_length} chars")
    logger.info(f"  Min: {row.min_length} chars")
    logger.info(f"  Max: {row.max_length} chars")

    if row.very_short > 0:
        pct = (row.very_short / row.total) * 100
        logger.warning(f"⚠️  {row.very_short} chunks (<50 chars, {pct:.1f}%)")
        if pct > 5:
            logger.warning("  High percentage of very short chunks - check chunking logic")

    if row.very_long > 0:
        pct = (row.very_long / row.total) * 100
        logger.warning(f"⚠️  {row.very_long} chunks (>5000 chars, {pct:.1f}%)")
        if pct > 1:
            logger.warning("  Some chunks are very long - may need better chunking")

    return True  # This is informational, not pass/fail


def print_summary_stats():
    """Print overall database statistics."""
    logger.info("\n" + "=" * 80)
    logger.info("DATABASE STATISTICS")
    logger.info("=" * 80)

    with engine.connect() as conn:
        # Documents
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE ingestion_status = 'fetched') as fetched,
                COUNT(*) FILTER (WHERE ingestion_status = 'chunked') as chunked,
                COUNT(*) FILTER (WHERE ingestion_status = 'embedded') as embedded
            FROM documents
        """))
        doc_stats = result.fetchone()

        # Chunks
        result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
                COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding
            FROM document_chunks
        """))
        chunk_stats = result.fetchone()

    logger.info(f"\nDocuments:")
    logger.info(f"  Total: {doc_stats.total:,}")
    logger.info(f"  Fetched: {doc_stats.fetched:,}")
    logger.info(f"  Chunked: {doc_stats.chunked:,}")
    logger.info(f"  Embedded: {doc_stats.embedded:,}")

    logger.info(f"\nChunks:")
    logger.info(f"  Total: {chunk_stats.total:,}")
    logger.info(f"  With embeddings: {chunk_stats.with_embedding:,}")
    logger.info(f"  Without embeddings: {chunk_stats.without_embedding:,}")

    if chunk_stats.total > 0:
        avg_chunks = chunk_stats.total / doc_stats.total if doc_stats.total > 0 else 0
        logger.info(f"  Average chunks/doc: {avg_chunks:.1f}")


def main():
    """Run all data integrity tests."""
    logger.info("=" * 80)
    logger.info("DATA INTEGRITY TEST SUITE")
    logger.info("=" * 80)
    logger.info(f"\nDatabase: {os.getenv('DATABASE_URL').split('@')[1]}\n")

    print_summary_stats()

    # Run all tests
    tests = [
        ("Orphaned Chunks", test_orphaned_chunks),
        ("Embedded Docs Have Chunks", test_embedded_docs_have_chunks),
        ("Duplicate Chunks", test_duplicate_chunks),
        ("Embedding Dimensions", test_embedding_dimensions),
        ("Ingestion Status Consistency", test_ingestion_status_consistency),
        ("NULL Critical Fields", test_null_critical_fields),
        ("Chunk Content Length", test_chunk_content_length),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"\n✗ Test '{test_name}' crashed: {e}", exc_info=True)
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status:8s} {test_name}")

    logger.info("\n" + "-" * 80)
    logger.info(f"Results: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        logger.info("\n🎉 All integrity tests passed!")
        return 0
    else:
        logger.error(f"\n⚠️  {total_count - passed_count} test(s) failed - review issues above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
