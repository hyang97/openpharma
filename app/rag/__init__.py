"""
RAG (Retrieval-Augmented Generation) module for question answering.
"""
from .generation import answer_query, RAGResponse, Citation

__all__ = ['answer_query', 'RAGResponse', 'Citation']
