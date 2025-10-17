"""
LLM-based generation for OpenPharma RAG system.

Takes search results and generates synthesized answers with citations.
"""
from dataclasses import dataclass
from typing import List, Optional
import time

from app.retrieval import semantic_search, SearchResult


@dataclass
class Citation:
    """A single citation reference."""
    number: int
    title: str
    source_id: str  # PMC ID
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None
    chunk_id: int = None


@dataclass
class AnswerResult:
    """Complete answer with citations and metadata."""
    query: str
    answer: str  # Synthesized response with inline citations [1], [2]
    citations: List[Citation]
    chunks_used: List[SearchResult]
    llm_provider: str
    generation_time_ms: float


def answer_query(
    query: str,
    top_k: int = 10,
    llm_provider: str = "ollama"
) -> AnswerResult:
    """
    Answer a question using RAG (retrieval + LLM generation).

    Args:
        query: Natural language question
        top_k: Number of chunks to retrieve
        llm_provider: "ollama" or "openai"

    Returns:
        AnswerResult with synthesized answer and citations

    Example:
        >>> result = answer_query("What are GLP-1 agonists used for?")
        >>> print(result.answer)
        >>> for citation in result.citations:
        ...     print(f"[{citation.number}] {citation.title}")
    """
    start_time = time.time()

    # TODO: Step 1 - Retrieve relevant chunks using semantic_search()
    # chunks = semantic_search(query, top_k=top_k)

    # TODO: Step 2 - Build prompt with numbered chunks
    # Include: chunk content, paper title, section
    # Format for inline citations [1], [2], etc.

    # TODO: Step 3 - Call LLM (Ollama or OpenAI based on llm_provider)
    # if llm_provider == "ollama":
    #     # Call Ollama API
    # elif llm_provider == "openai":
    #     # Call OpenAI API

    # TODO: Step 4 - Parse response and build Citation objects

    # TODO: Step 5 - Return AnswerResult

    generation_time_ms = (time.time() - start_time) * 1000

    pass


if __name__ == "__main__":
    # Simple test
    result = answer_query("What are GLP-1 agonists used for in diabetes treatment?")

    print(f"Query: {result.query}\n")
    print(f"Answer:\n{result.answer}\n")
    print(f"Citations:")
    for citation in result.citations:
        print(f"  [{citation.number}] {citation.title} (PMC{citation.source_id})")
    print(f"\nGeneration time: {result.generation_time_ms:.0f}ms")
    print(f"LLM provider: {result.llm_provider}")
