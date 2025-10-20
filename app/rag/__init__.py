"""
RAG (Retrieval-Augmented Generation) module for question answering.
"""
from .generation import generate_response, RAGResponse, Citation

__all__ = ['generate_response', 'RAGResponse', 'Citation']
