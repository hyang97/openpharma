"""
Semantic search for OpenPharma RAG system.

This module provides vector similarity search over embedded document chunks,
returning the most relevant chunks with full citation metadata.
Supports hybrid retrieval combining fresh semantic search with historical chunks.
"""
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text
import time

from app.models import SearchResult
from app.db.database import engine
from app.ingestion.embeddings import EmbeddingService
from app.logging_config import get_logger

logger = get_logger(__name__)

# Cache EmbeddingService instance to avoid repeated initialization overhead
_embedding_service = None


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
    embed_start = time.time()
    query_embedding = _embedding_service.embed_single(query)
    embed_time = (time.time() - embed_start) * 1000
    logger.info(f"  Query embedding time: {embed_time:.0f}ms")

    # Execute vector similarity search with SQL
    search_start = time.time()
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

    search_time = (time.time() - search_start) * 1000
    logger.info(f"  Vector search time: {search_time:.0f}ms")

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


def fetch_chunks_by_chunk_ids(chunk_ids: List[str]) -> Dict[int, SearchResult]:
    """Fetch chunks by their chunk IDs, returning chunk_id -> SearchResult"""
    if not chunk_ids:
        return {}
    
    stmt = text(
        """
select
chk.document_chunk_id
, chk.content
, chk.section
, chk.document_id
, doc.source_id
, doc.title
, doc.doc_metadata

from document_chunks chk
join documents doc
  on chk.document_id = doc.document_id
where chk.document_chunk_id = ANY(:chunk_ids)
"""
    )
    
    with Session(engine) as session:
        result_chunks = session.execute(stmt, {'chunk_ids': chunk_ids}).fetchall()
    
    chunkid_to_searchresult = {}
    for chunk in result_chunks:
        chunk_metadata = chunk.doc_metadata or {}
        result = SearchResult(
            chunk_id=chunk.document_chunk_id,
            section=chunk.section,
            content=chunk.content,
            query="", # Not semantic search, no query
            similarity_score=None, # Not semantic search, no similarity score
            document_id=chunk.document_id,
            source_id=chunk.source_id,
            title=chunk.title,
            authors=chunk_metadata.get("authors", []),
            publication_date=chunk_metadata.get("pub_date", ""),
            journal=chunk_metadata.get("journal", ""),
            doi=chunk_metadata.get("doi", "")
        )
        chunkid_to_searchresult[chunk.document_chunk_id] = result
    return chunkid_to_searchresult

def hybrid_retrieval(
        query: str, 
        conversation_history: Optional[List[dict]] = None, 
        top_k = 20,
        top_n = 5,
        max_historical_chunks = 15
) -> List[SearchResult]:
    """Hybrid retrieval, semantic search + most recent historical chunks"""

    hybrid_start = time.time()
    new_chunks = semantic_search(query, top_k=top_k)[:top_n] # fetch top_k and keep top_n most similar
    
    recent_chunk_ids = []
    seen_chunk_ids = set(chunk.chunk_id for chunk in new_chunks) 

    if conversation_history:
        for msg in reversed(conversation_history):
            if msg['role'] == 'assistant' and 'cited_chunk_ids' in msg:
                for chunk_id in msg['cited_chunk_ids']:
                    if chunk_id not in seen_chunk_ids:
                        recent_chunk_ids.append(chunk_id)
                        seen_chunk_ids.add(chunk_id)
                    if len(recent_chunk_ids) >= max_historical_chunks:
                        break
    
    historical_chunks = []

    if recent_chunk_ids:
        result_chunks = fetch_chunks_by_chunk_ids(recent_chunk_ids)
        for chunk_id in recent_chunk_ids:
            historical_chunks.append(result_chunks[chunk_id])
    
    all_chunks = new_chunks + historical_chunks
    hybrid_time = (time.time() - hybrid_start) * 1000
    logger.info(f"  Hybrid retrieval time: {hybrid_time:.0f}ms ({len(all_chunks)} chunks, {len(new_chunks)} new, {len(historical_chunks)} historical)")
    return all_chunks



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
