"""
Semantic search for OpenPharma RAG system.

This module provides vector similarity search over embedded document chunks,
returning the most relevant chunks with full citation metadata.
"""
from dataclasses import dataclass
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import engine
from app.ingestion.embeddings import EmbeddingService

# Cache EmbeddingService instance to avoid repeated initialization overhead
_embedding_service = None


@dataclass
class SearchResult:
    """
    A single search result containing chunk content and parent document metadata.
    """
    chunk_id: int
    section: str
    content: str
    query: str
    similarity_score: float

    # Parent document metadata for citations
    document_id: int
    source_id: str  # PMC ID
    title: str
    authors: Optional[List[str]] = None
    publication_date: Optional[str] = None
    journal: Optional[str] = None
    doi: Optional[str] = None


def semantic_search(query: str, top_k: int = 10) -> List[SearchResult]:
    """
    Perform semantic search over document chunks.

    Args:
        query: Natural language query string
        top_k: Number of top results to return (default: 10)

    Returns:
        List of SearchResult objects ordered by similarity (highest first)

    Example:
        >>> results = semantic_search("What are GLP-1 agonists used for?", top_k=5)
        >>> for result in results:
        ...     print(f"{result.title} (similarity: {result.similarity_score:.3f})")
    """
    global _embedding_service

    # Initialize EmbeddingService once and reuse across queries
    if _embedding_service is None:
        _embedding_service = EmbeddingService()

    # Embed query
    query_embedding = _embedding_service.embed_single(query)

    # Execute vector similarity search with SQL
    stmt = text(
        """
select
chk.document_chunk_id
, chk.content
, chk.section
, 1 - (chk.embedding <=> :query_vector) as similarity_score
, chk.document_id
, doc.source_id
, doc.title
, doc.doc_metadata

from document_chunks chk
join documents doc
  on chk.document_id = doc.document_id
order by chk.embedding <=> :query_vector asc
limit :top_k
"""
    )

    with Session(engine) as session:
        result_chunks = session.execute(stmt, {
            'query_vector': str(query_embedding),
            'top_k': top_k
        }).fetchall()

    # Parse results and construct SearchResult objects
    search_results = []
    for chunk in result_chunks:
        metadata = chunk.doc_metadata or {} # handles None metadata case
        result = SearchResult(
            chunk_id= chunk.document_chunk_id, 
            section= chunk.section, 
            content= chunk.content, 
            query= query,
            similarity_score= chunk.similarity_score, 
            document_id= chunk.document_id,
            source_id= chunk.source_id, 
            title= chunk.title, 
            authors= metadata.get("authors", []),
            publication_date= metadata.get("pub_date", ""),
            journal= metadata.get("journal", ""),
            doi= metadata.get("doi", "")
        )
        search_results.append(result)

    return search_results


if __name__ == "__main__":
    # Simple test to verify the function works
    results = semantic_search("diabetes treatment GLP-1 agonists", top_k=5)

    print(f"Found {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.title}")
        print(f"   Source: PMC{result.source_id}")
        print(f"   Section: {result.section}")
        print(f"   Similarity: {result.similarity_score:.4f}")
        print(f"   Content preview: {result.content[:200]}...")
        print()
