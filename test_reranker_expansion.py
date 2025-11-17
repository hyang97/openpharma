#!/usr/bin/env python3
"""
Quick test to verify re-ranker chunk expansion is working correctly.
This tests the new functionality where additional chunks from retrieved papers
are fetched and re-ranked based on content only.
"""

from app.retrieval.semantic_search import semantic_search
from app.logging_config import get_logger

logger = get_logger(__name__)

def test_reranker_expansion():
    """Test semantic search with re-ranker and chunk expansion"""

    # Test query that might match on title but need content-based re-ranking
    query = "What are the side effects of GLP-1 receptor agonists?"

    print("=" * 80)
    print("Testing Re-ranker with Chunk Expansion")
    print("=" * 80)
    print(f"\nQuery: {query}\n")

    # Test WITHOUT chunk expansion (baseline)
    print("-" * 80)
    print("1. Baseline (no chunk expansion):")
    print("-" * 80)
    results_no_expansion = semantic_search(
        query=query,
        top_k=10,
        top_n=5,
        use_reranker=True,
        additional_chunks_per_doc=0
    )

    print(f"\nFound {len(results_no_expansion)} results:\n")
    for i, result in enumerate(results_no_expansion, 1):
        print(f"{i}. {result.title}")
        print(f"   Document ID: {result.document_id}")
        print(f"   Chunk ID: {result.chunk_id}")
        print(f"   Section: {result.section}")
        print(f"   Similarity: {result.similarity_score:.4f}" if result.similarity_score else "   Similarity: N/A")
        print(f"   Content preview: {result.content[:150]}...")
        print()

    # Test WITH chunk expansion
    print("-" * 80)
    print("2. WITH chunk expansion (5 additional chunks per doc):")
    print("-" * 80)
    results_with_expansion = semantic_search(
        query=query,
        top_k=10,
        top_n=5,
        use_reranker=True,
        additional_chunks_per_doc=5
    )

    print(f"\nFound {len(results_with_expansion)} results:\n")
    for i, result in enumerate(results_with_expansion, 1):
        print(f"{i}. {result.title}")
        print(f"   Document ID: {result.document_id}")
        print(f"   Chunk ID: {result.chunk_id}")
        print(f"   Section: {result.section}")
        print(f"   Similarity: {result.similarity_score:.4f}" if result.similarity_score else "   Similarity: N/A")
        print(f"   Content preview: {result.content[:150]}...")
        print()

    # Compare results
    print("=" * 80)
    print("COMPARISON:")
    print("=" * 80)

    # Check if chunk IDs changed
    no_expansion_ids = set(r.chunk_id for r in results_no_expansion)
    with_expansion_ids = set(r.chunk_id for r in results_with_expansion)

    print(f"\nChunks without expansion: {no_expansion_ids}")
    print(f"Chunks with expansion: {with_expansion_ids}")

    diff = no_expansion_ids.symmetric_difference(with_expansion_ids)

    print(f"\nDifference: {len(diff)} chunks")
    if diff:
        print("  ✓ Chunk expansion successfully found different chunks!")
        print(f"  Changed chunk IDs: {diff}")
    else:
        print("  ⚠ No difference (might be optimal, or query needs adjustment)")

    # Check document diversity
    no_expansion_docs = set(r.document_id for r in results_no_expansion)
    with_expansion_docs = set(r.document_id for r in results_with_expansion)

    print(f"\nUnique documents without expansion: {len(no_expansion_docs)}")
    print(f"Unique documents with expansion: {len(with_expansion_docs)}")

    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    test_reranker_expansion()
