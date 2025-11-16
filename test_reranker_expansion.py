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

    # Test WITHOUT re-ranker (baseline)
    print("-" * 80)
    print("1. WITHOUT re-ranker (baseline):")
    print("-" * 80)
    results_no_rerank = semantic_search(
        query=query,
        top_k=10,
        top_n=5,
        use_reranker=False
    )

    print(f"\nFound {len(results_no_rerank)} results:\n")
    for i, result in enumerate(results_no_rerank, 1):
        print(f"{i}. {result.title}")
        print(f"   Document ID: {result.document_id}")
        print(f"   Chunk ID: {result.chunk_id}")
        print(f"   Section: {result.section}")
        print(f"   Similarity: {result.similarity_score:.4f}" if result.similarity_score else "   Similarity: N/A")
        print(f"   Content preview: {result.content[:150]}...")
        print()

    # Test WITH re-ranker and chunk expansion
    print("-" * 80)
    print("2. WITH re-ranker and chunk expansion (5 additional chunks per doc):")
    print("-" * 80)
    results_with_rerank = semantic_search(
        query=query,
        top_k=10,
        top_n=5,
        use_reranker=True,
        additional_chunks_per_doc=5
    )

    print(f"\nFound {len(results_with_rerank)} results:\n")
    for i, result in enumerate(results_with_rerank, 1):
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
    no_rerank_ids = set(r.chunk_id for r in results_no_rerank)
    with_rerank_ids = set(r.chunk_id for r in results_with_rerank)

    different_chunks = no_rerank_ids.symmetric_difference(with_rerank_ids)

    print(f"\nChunks in baseline: {no_rerank_ids}")
    print(f"Chunks with re-ranker: {with_rerank_ids}")
    print(f"\nNumber of different chunks: {len(different_chunks)}")

    if different_chunks:
        print("✓ Re-ranker successfully selected different chunks!")
        print(f"  Changed chunk IDs: {different_chunks}")
    else:
        print("⚠ Re-ranker selected the same chunks (might be optimal, or query needs adjustment)")

    # Check document diversity
    no_rerank_docs = set(r.document_id for r in results_no_rerank)
    with_rerank_docs = set(r.document_id for r in results_with_rerank)

    print(f"\nUnique documents in baseline: {len(no_rerank_docs)}")
    print(f"Unique documents with re-ranker: {len(with_rerank_docs)}")

    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    test_reranker_expansion()
