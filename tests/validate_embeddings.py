"""
Validate embedding quality and analyze topic coverage.

This script performs:
1. Semantic similarity tests with diabetes-related queries
2. Topic coverage analysis
3. HNSW index performance testing
"""

import os
import sys
import time
from typing import List, Tuple
from datetime import datetime

from sqlalchemy import create_engine, text
from openai import OpenAI

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger

# Setup logging
setup_logging(level="INFO", log_file="logs/validate_embeddings.log")
logger = get_logger(__name__)
engine = create_engine(os.getenv("DATABASE_URL"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_query_embedding(query_text: str) -> List[float]:
    """Generate embedding for a query string."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query_text
    )
    return response.data[0].embedding


def search_similar_chunks(query_embedding: List[float], limit: int = 5) -> List[Tuple]:
    """Search for similar chunks using cosine similarity (optimized for RAG)."""
    # Format embedding as pgvector string format
    embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

    with engine.connect() as conn:
        # Enable optimizations for vector search
        conn.execute(text("SET enable_seqscan = off"))
        conn.execute(text("SET hnsw.ef_search = 40"))

        # Get chunks first (fast: ~20-25ms)
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

        # Batch-fetch titles for returned chunks
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

        # Combine chunks with titles
        results = []
        for chunk in chunks:
            chunk_id, doc_id, section, content, similarity = chunk
            title = titles.get(doc_id, "Unknown")
            results.append((chunk_id, section, content, title, similarity))

        return results


def test_semantic_similarity():
    """Test semantic similarity with various diabetes-related queries."""
    logger.info("=" * 80)
    logger.info("SEMANTIC SIMILARITY TESTS")
    logger.info("=" * 80)

    test_queries = [
        "insulin therapy for type 2 diabetes",
        "blood glucose monitoring and control",
        "diabetic retinopathy complications",
        "metformin treatment efficacy",
        "lifestyle interventions for diabetes prevention",
    ]

    for query in test_queries:
        logger.info(f"\nQuery: '{query}'")
        logger.info("-" * 80)

        start_time = time.time()
        query_embedding = get_query_embedding(query)
        results = search_similar_chunks(query_embedding, limit=5)
        elapsed_ms = (time.time() - start_time) * 1000

        logger.info(f"Search time: {elapsed_ms:.1f}ms")
        logger.info(f"\nTop 5 results:")

        for i, row in enumerate(results, 1):
            chunk_id, section, content, title, similarity = row
            logger.info(f"\n  {i}. Similarity: {similarity:.4f}")
            logger.info(f"     Paper: {title}")
            logger.info(f"     Section: {section}")
            logger.info(f"     Content preview: {content[:150]}...")

        # Check quality
        avg_similarity = sum(row[4] for row in results) / len(results)
        if avg_similarity < 0.4:
            logger.warning(f"     WARNING: Low average similarity ({avg_similarity:.3f})")


def test_topic_diversity():
    """Test that different topics have low similarity."""
    logger.info("\n" + "=" * 80)
    logger.info("TOPIC DIVERSITY TEST")
    logger.info("=" * 80)

    topic_pairs = [
        ("diabetes insulin treatment", "cancer chemotherapy"),
        ("blood glucose levels", "cardiac arrhythmia"),
    ]

    for topic1, topic2 in topic_pairs:
        emb1 = get_query_embedding(topic1)
        emb2 = get_query_embedding(topic2)

        # Format embeddings as pgvector strings
        emb1_str = '[' + ','.join(str(x) for x in emb1) + ']'
        emb2_str = '[' + ','.join(str(x) for x in emb2) + ']'

        # Calculate cosine similarity between the two embeddings
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT 1 - ('{emb1_str}'::vector <=> '{emb2_str}'::vector) as similarity
            """))
            similarity = result.scalar()

        logger.info(f"\n'{topic1}' vs '{topic2}'")
        logger.info(f"  Similarity: {similarity:.4f}")

        if similarity > 0.5:
            logger.warning(f"  WARNING: Different topics have high similarity!")
        else:
            logger.info(f"  ✓ Good diversity (similarity < 0.5)")


def analyze_topic_coverage():
    """Analyze what topics are covered in the embedded dataset."""
    logger.info("\n" + "=" * 80)
    logger.info("TOPIC COVERAGE ANALYSIS")
    logger.info("=" * 80)

    topics = {
        "Type 2 diabetes": ["type 2 diabetes", "T2DM", "type II diabetes"],
        "Type 1 diabetes": ["type 1 diabetes", "T1DM", "type I diabetes"],
        "Insulin": ["insulin therapy", "insulin treatment", "insulin resistance"],
        "Metformin": ["metformin"],
        "GLP-1 agonists": ["GLP-1", "glucagon-like peptide", "semaglutide", "liraglutide"],
        "SGLT2 inhibitors": ["SGLT2", "sodium-glucose cotransporter", "empagliflozin", "dapagliflozin"],
        "Complications - Eyes": ["retinopathy", "diabetic eye"],
        "Complications - Kidneys": ["nephropathy", "diabetic kidney"],
        "Complications - Nerves": ["neuropathy", "diabetic nerve"],
        "Complications - Heart": ["cardiovascular", "heart disease", "diabetic cardiomyopathy"],
        "Prevention": ["diabetes prevention", "prediabetes"],
        "Diet & Lifestyle": ["diet", "exercise", "lifestyle intervention", "weight loss"],
    }

    logger.info("\nSearching for papers by topic...")

    with engine.connect() as conn:
        for topic_name, keywords in topics.items():
            # Build OR condition for all keywords
            conditions = " OR ".join([f"dc.content ILIKE :kw{i}" for i in range(len(keywords))])
            params = {f"kw{i}": f"%{kw}%" for i, kw in enumerate(keywords)}

            query = text(f"""
                SELECT COUNT(DISTINCT dc.document_id) as paper_count,
                       COUNT(dc.document_chunk_id) as chunk_count
                FROM document_chunks dc
                WHERE dc.embedding IS NOT NULL
                  AND ({conditions})
            """)

            result = conn.execute(query, params)
            row = result.fetchone()

            logger.info(f"\n{topic_name:30s} {row.paper_count:4d} papers, {row.chunk_count:5d} chunks")


def test_index_performance():
    """Test HNSW index performance with multiple queries."""
    logger.info("\n" + "=" * 80)
    logger.info("INDEX PERFORMANCE TEST")
    logger.info("=" * 80)

    # Run 10 queries and measure average time
    test_query = "diabetes treatment"
    query_embedding = get_query_embedding(test_query)

    times = []
    for i in range(10):
        start_time = time.time()
        search_similar_chunks(query_embedding, limit=10)
        elapsed_ms = (time.time() - start_time) * 1000
        times.append(elapsed_ms)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    logger.info(f"\n10 similarity searches (10 results each):")
    logger.info(f"  Average: {avg_time:.1f}ms")
    logger.info(f"  Min: {min_time:.1f}ms")
    logger.info(f"  Max: {max_time:.1f}ms")

    if avg_time > 200:
        logger.warning("  WARNING: Queries are slow. HNSW index may not be used.")
    else:
        logger.info("  ✓ Good performance (HNSW index working)")


def main():
    """Run all validation tests."""
    logger.info(f"Starting embedding validation at {datetime.now()}")
    logger.info(f"Database: {os.getenv('DATABASE_URL').split('@')[1]}")

    # Get basic stats
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE embedding IS NOT NULL) as embedded_chunks,
                COUNT(*) FILTER (WHERE embedding IS NULL) as pending_chunks,
                COUNT(DISTINCT document_id) FILTER (WHERE embedding IS NOT NULL) as embedded_docs
            FROM document_chunks
        """))
        row = result.fetchone()

        logger.info(f"\nDataset stats:")
        logger.info(f"  Embedded chunks: {row.embedded_chunks:,}")
        logger.info(f"  Pending chunks: {row.pending_chunks:,}")
        logger.info(f"  Papers with embeddings: {row.embedded_docs:,}")

    # Run tests
    try:
        test_semantic_similarity()
        test_topic_diversity()
        analyze_topic_coverage()
        test_index_performance()

        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION COMPLETE")
        logger.info("=" * 80)
        logger.info("\nReview the results above to assess embedding quality.")
        logger.info("Look for:")
        logger.info("  - High similarity scores (>0.5) for relevant results")
        logger.info("  - Low similarity scores (<0.5) for diverse topics")
        logger.info("  - Good topic coverage across diabetes domains")
        logger.info("  - Fast query times (<200ms)")

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
