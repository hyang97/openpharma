"""
RAG (Retrieval-Augmented Generation) module for question answering.
"""
from .synthesis import answer_query, AnswerResult, Citation

__all__ = ['answer_query', 'AnswerResult', 'Citation']
