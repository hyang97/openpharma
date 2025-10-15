"""
Retrieval quality tests with gold-standard Q&A pairs.

Tests end-to-end RAG pipeline quality with known diabetes questions
and validates that correct papers appear in top results.
"""

import os
import sys
import time
from typing import List, Tuple

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger
from app.ingestion.embeddings import EmbeddingService

setup_logging(level="INFO", log_file="logs/test_retrieval_quality.log")
logger = get_logger(__name__)

engine = create_engine(os.getenv("DATABASE_URL"))
embedder = EmbeddingService()


def get_query_embedding(query_text: str) -> List[float]:
    """Generate embedding for a query string using Ollama."""
    return embedder.embed_single(query_text)


def search_similar_chunks(query_embedding: List[float], limit: int = 10) -> List[Tuple]:
    """Search for similar chunks using optimized RAG pattern."""
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    with engine.connect() as conn:
        # Enable optimizations
        conn.execute(text("SET enable_seqscan = off"))
        conn.execute(text("SET hnsw.ef_search = 40"))

        # Get chunks first (fast)
        chunk_result = conn.execute(text(f"""
            SELECT dc.document_chunk_id, dc.document_id, dc.section, dc.content,
                   1 - (dc.embedding <=> '{embedding_str}'::vector) as similarity
            FROM document_chunks dc
            WHERE dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> '{embedding_str}'::vector
            LIMIT {limit}
        """))
        chunks = list(chunk_result)

        if not chunks:
            return []

        # Batch-fetch titles
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

        # Combine results
        results = []
        for chunk in chunks:
            chunk_id, doc_id, section, content, similarity = chunk
            title = titles.get(doc_id, "Unknown")
            results.append((chunk_id, section, content, title, similarity, doc_id))

        return results


# ============================================================================
# GOLD-STANDARD TEST CASES
# ============================================================================

GOLD_STANDARD_QUERIES = [
    {
        "query": "What is the first-line medication for type 2 diabetes treatment?",
        "expected_terms": ["metformin", "first-line", "type 2"],
        "min_similarity": 0.5,
        "description": "Should find metformin as first-line therapy"
    },
    {
        "query": "How does insulin therapy work for diabetes?",
        "expected_terms": ["insulin", "blood glucose", "pancreas"],
        "min_similarity": 0.5,
        "description": "Should find insulin mechanism papers"
    },
    {
        "query": "What are the complications of diabetic retinopathy?",
        "expected_terms": ["retinopathy", "eye", "vision", "diabetic"],
        "min_similarity": 0.5,
        "description": "Should find retinopathy complication papers"
    },
    {
        "query": "What are the benefits of GLP-1 agonists?",
        "expected_terms": ["GLP-1", "glucagon", "weight"],
        "min_similarity": 0.4,
        "description": "Should find GLP-1 medication papers"
    },
    {
        "query": "How effective are SGLT2 inhibitors for cardiovascular outcomes?",
        "expected_terms": ["SGLT2", "cardiovascular", "heart"],
        "min_similarity": 0.4,
        "description": "Should find SGLT2 cardio benefit papers"
    },
    {
        "query": "What lifestyle interventions prevent diabetes?",
        "expected_terms": ["diet", "exercise", "lifestyle", "prevention"],
        "min_similarity": 0.5,
        "description": "Should find prevention/lifestyle papers"
    },
    {
        "query": "What is the role of continuous glucose monitoring?",
        "expected_terms": ["glucose monitoring", "CGM", "blood sugar"],
        "min_similarity": 0.4,
        "description": "Should find glucose monitoring papers"
    },
]


def test_gold_standard_query(test_case: dict) -> Tuple[bool, dict]:
    """Test a single gold-standard query."""
    query = test_case["query"]
    expected_terms = test_case["expected_terms"]
    min_similarity = test_case["min_similarity"]

    logger.info(f"\nQuery: '{query}'")
    logger.info(f"Expected: {test_case['description']}")
    logger.info("-" * 80)

    # Get query embedding and search
    start = time.time()
    query_embedding = get_query_embedding(query)
    results = search_similar_chunks(query_embedding, limit=10)
    elapsed_ms = (time.time() - start) * 1000

    if not results:
        logger.error("✗ No results returned!")
        return False, {"query_time_ms": elapsed_ms, "results_count": 0}

    # Check top result similarity
    top_similarity = results[0][4]
    if top_similarity < min_similarity:
        logger.warning(f"⚠️  Top similarity ({top_similarity:.3f}) below threshold ({min_similarity})")

    # Check if expected terms appear in top 5 results
    top_5_content = "\n".join([r[2].lower() for r in results[:5]])
    top_5_titles = "\n".join([r[3].lower() for r in results[:5]])
    combined_text = top_5_content + " " + top_5_titles

    found_terms = [term for term in expected_terms if term.lower() in combined_text]
    missing_terms = [term for term in expected_terms if term.lower() not in combined_text]

    # Log results
    logger.info(f"Query time: {elapsed_ms:.1f}ms")
    logger.info(f"\nTop 5 results:")
    for i, (chunk_id, section, content, title, similarity, doc_id) in enumerate(results[:5], 1):
        logger.info(f"\n  {i}. Similarity: {similarity:.4f}")
        logger.info(f"     Paper: {title[:70]}...")
        logger.info(f"     Section: {section}")
        logger.info(f"     Content: {content[:120]}...")

    # Check for document diversity (different papers in top 5)
    unique_docs = len(set(r[5] for r in results[:5]))
    logger.info(f"\nDiversity: {unique_docs}/5 unique papers in top 5")

    # Pass/fail criteria
    passed = True
    if top_similarity < min_similarity:
        logger.warning(f"⚠️  Low similarity score")
        passed = False

    if len(found_terms) < len(expected_terms) * 0.5:  # At least 50% of terms
        logger.warning(f"⚠️  Expected terms: {expected_terms}")
        logger.warning(f"    Found: {found_terms}")
        logger.warning(f"    Missing: {missing_terms}")
        passed = False
    else:
        logger.info(f"✓ Found expected terms: {found_terms}")

    if unique_docs < 2:
        logger.warning(f"⚠️  Low diversity - only {unique_docs} unique papers")

    if passed:
        logger.info("✓ PASS")
    else:
        logger.warning("⚠️  MARGINAL - review results")

    return passed, {
        "query_time_ms": elapsed_ms,
        "results_count": len(results),
        "top_similarity": top_similarity,
        "found_terms": found_terms,
        "missing_terms": missing_terms,
        "diversity": unique_docs
    }


def test_result_diversity():
    """Test that top results come from different papers."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Result Diversity")
    logger.info("=" * 80)

    test_queries = [
        "diabetes treatment options",
        "blood glucose control",
        "diabetic complications"
    ]

    diversity_scores = []

    for query in test_queries:
        query_embedding = get_query_embedding(query)
        results = search_similar_chunks(query_embedding, limit=10)

        unique_docs = len(set(r[5] for r in results[:10]))
        diversity_scores.append(unique_docs)

        logger.info(f"\nQuery: '{query}'")
        logger.info(f"  Diversity: {unique_docs}/10 unique papers")

    avg_diversity = sum(diversity_scores) / len(diversity_scores)
    logger.info(f"\nAverage diversity: {avg_diversity:.1f}/10")

    if avg_diversity >= 7:
        logger.info("✓ Good diversity (≥7 unique papers)")
        return True
    elif avg_diversity >= 5:
        logger.warning("⚠️  Moderate diversity (5-7 unique papers)")
        return True
    else:
        logger.error("✗ Poor diversity (<5 unique papers)")
        logger.error("  Results may be too concentrated in few papers")
        return False


def test_query_performance():
    """Test that queries complete quickly."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Query Performance")
    logger.info("=" * 80)

    query = "diabetes insulin treatment"

    times = []
    for i in range(10):
        start = time.time()
        query_embedding = get_query_embedding(query)
        results = search_similar_chunks(query_embedding, limit=10)
        elapsed_ms = (time.time() - start) * 1000
        times.append(elapsed_ms)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    logger.info(f"\n10 query runs:")
    logger.info(f"  Average: {avg_time:.1f}ms")
    logger.info(f"  Min: {min_time:.1f}ms")
    logger.info(f"  Max: {max_time:.1f}ms")

    # Target: <500ms total (embedding + search)
    if avg_time < 200:
        logger.info("✓ Excellent performance (<200ms)")
        return True
    elif avg_time < 500:
        logger.info("✓ Good performance (<500ms)")
        return True
    else:
        logger.warning(f"⚠️  Slow performance (>{avg_time:.0f}ms)")
        return False


def main():
    """Run all retrieval quality tests."""
    logger.info("=" * 80)
    logger.info("RETRIEVAL QUALITY TEST SUITE")
    logger.info("=" * 80)
    logger.info(f"\nDatabase: {os.getenv('DATABASE_URL').split('@')[1]}")

    # Check we have embeddings
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL
        """))
        embedded_count = result.scalar()

    if embedded_count == 0:
        logger.error("\n✗ No embeddings found in database!")
        logger.error("  Run stage_4_embed_chunks.py first")
        return 1

    logger.info(f"\nEmbedded chunks: {embedded_count:,}")

    # Run gold-standard queries
    logger.info("\n" + "=" * 80)
    logger.info("GOLD-STANDARD Q&A TESTS")
    logger.info("=" * 80)

    query_results = []
    for test_case in GOLD_STANDARD_QUERIES:
        passed, metrics = test_gold_standard_query(test_case)
        query_results.append((test_case["query"], passed, metrics))

    # Run other quality tests
    diversity_passed = test_result_diversity()
    performance_passed = test_query_performance()

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    passed_queries = sum(1 for _, passed, _ in query_results if passed)
    total_queries = len(query_results)

    logger.info(f"\nGold-standard queries: {passed_queries}/{total_queries} passed")
    logger.info(f"Diversity test: {'✓ PASS' if diversity_passed else '✗ FAIL'}")
    logger.info(f"Performance test: {'✓ PASS' if performance_passed else '⚠️  MARGINAL'}")

    # Detailed query results
    logger.info("\n" + "-" * 80)
    logger.info("Query Details:")
    for query, passed, metrics in query_results:
        status = "✓" if passed else "⚠️ "
        logger.info(f"\n{status} {query[:60]}...")
        logger.info(f"   Similarity: {metrics['top_similarity']:.3f} | "
                   f"Diversity: {metrics['diversity']}/5 | "
                   f"Time: {metrics['query_time_ms']:.0f}ms")

    if passed_queries >= total_queries * 0.7 and diversity_passed:
        logger.info("\n🎉 Retrieval quality is good!")
        return 0
    else:
        logger.warning("\n⚠️  Some quality issues detected - review results above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
