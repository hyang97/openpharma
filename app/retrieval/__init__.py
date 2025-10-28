"""
Retrieval module for semantic search and RAG functionality.
"""

# allows users to do: from app.retrieval import semantic_search, hybrid_retrieval, rerank_chunks
# without it, users do: from app.retrieval.semantic_search import semantic_search
from .semantic_search import semantic_search, hybrid_retrieval, rerank_chunks

# allows users to do: from app.retrieval import *
__all__ = ['semantic_search', 'hybrid_retrieval', 'rerank_chunks']
