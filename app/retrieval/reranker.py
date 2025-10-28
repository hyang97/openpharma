"""
Cross-encoder reranking for OpenPharma RAG system.

This module provides reranking of retrieved chunks using a cross-encoder model,
which scores query-document pairs more accurately than bi-encoder embeddings.
Default: cross-encoder/ms-marco-MiniLM-L-6-v2 for fast reranking.
"""
from typing import List
import time
import os

from app.models import SearchResult
from app.logging_config import get_logger

from sentence_transformers import CrossEncoder

logger = get_logger(__name__)

# Cache reranker instance to avoid repeated initialization overhead
_reranker_service = None


class RerankerService:
    """
    Cross-encoder reranking service using sentence-transformers.

    Uses BAAI/bge-reranker-base model for scoring query-document relevance.
    This model directly scores (query, document) pairs for better accuracy
    than bi-encoder semantic search alone.
    """

    def __init__(self, model_name: str = None):
        """
        Initialize the reranker with specified model.

        Args:
            model: HuggingFace model name (default: BAAI/bge-reranker-v2-m3)
        """

        self.model_name = model_name or os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        try:
            self.model = CrossEncoder(self.model_name)
            logger.info(f"Initialized RerankerService with CrossEncoder model: {self.model_name}")
        except Exception as e:
            logger.error(f"Could not initialize RerankerService with model {self.model_name}: {e}")
            raise

            

    def rerank(self, query: str, chunks: List[SearchResult], top_n: int = 5) -> List[SearchResult]:
        """
        Rerank chunks using cross-encoder model.

        Args:
            query: User query string
            chunks: List of SearchResult objects from semantic search
            top_n: Number of top results to return after reranking

        Returns:
            List of top_n SearchResult objects, reordered by cross-encoder scores
        """

        if not chunks:
            return []

        rerank_start = time.time()

        # Create query and chunk content pairs
        pairs = [(query, chunk.content) for chunk in chunks]

        # Reranker model calculates a relevance score per pair
        scores = self.model.predict(pairs)

        # Zip results in [(chunk1, score1), (chunk2, score2), ...]
        zipped_chunks_and_scores = zip(chunks, scores)

        # Sort by score desc
        sorted_chunks_and_scores = sorted(zipped_chunks_and_scores, key=lambda x: x[1], reverse=True)

        # Return top n chunks by reranker score
        top_n_chunks = [chunk for chunk, _ in sorted_chunks_and_scores[:top_n]]

        rerank_time = (time.time() - rerank_start) * 1000
        logger.info(f"  Chunk reranking time: {rerank_time:.0f}ms")
        return top_n_chunks
        


def get_reranker() -> RerankerService:
    """
    Get singleton reranker instance.

    Lazily initializes the reranker on first call and caches for reuse.
    """
    global _reranker_service

    if _reranker_service is None:
        _reranker_service = RerankerService()
    
    return _reranker_service


def rerank_chunks(query: str, chunks: List[SearchResult], top_n: int = 5) -> List[SearchResult]:
    """
    Convenience function to rerank chunks using the cached reranker.

    Args:
        query: User query string
        chunks: List of SearchResult objects from semantic search
        top_n: Number of top results to return after reranking

    Returns:
        List of top_n reranked SearchResult objects
    """
    reranker = get_reranker()
    return reranker.rerank(query, chunks, top_n)
    


if __name__ == "__main__":
    # Test script - will be useful for testing your implementation
    from app.retrieval import semantic_search
    from app.logging_config import setup_logging
    setup_logging(level="INFO")

    print("Testing reranker...")

    query = "GLP-1 agonists for diabetes treatment"
    initial_results = semantic_search(query, top_k=20)

    print(f"\nInitial top 5 (semantic search only):")
    for i, result in enumerate(initial_results[:5], 1):
        print(f"{i}. {result.title[:80]}... (score: {result.similarity_score:.4f})")

    reranked_results = rerank_chunks(query, initial_results, top_n=5)

    print(f"\nTop 5 after reranking:")
    for i, result in enumerate(reranked_results, 1):
        print(f"{i}. {result.title[:80]}...")
