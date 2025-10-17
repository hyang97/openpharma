"""
Retrieval module for semantic search and RAG functionality.
"""

# allows users to do: from app.retrieval import semantic search
# without it, users do: from app.retrieval.semantic_search import semantic search
from .semantic_search import semantic_search, SearchResult 

# allows users to do: from app.retrieval import *
__all__ = ['semantic_search', 'SearchResult']
