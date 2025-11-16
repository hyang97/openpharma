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

from app.retrieval.reranker import rerank_chunks
from app.models import SearchResult
from app.db.database import engine
from app.ingestion.embeddings import EmbeddingService
from app.logging_config import get_logger

logger = get_logger(__name__)

# Cache EmbeddingService instance to avoid repeated initialization overhead
_embedding_service = None


def semantic_search(
    query: str,
    top_k: int = 10,
    top_n: int = 5,
    use_reranker: bool = False,
    expand_chunks: bool = False,
    additional_chunks_per_doc: int = 5
) -> List[SearchResult]:
    """
    Perform semantic search over document chunks.

    Args:
        query: Natural language query string
        top_k: Number of top results from vector search (default: 10)
        top_n: Number of final results to return (default: 5)
        use_reranker: Whether to use cross-encoder re-ranking (default: False)
        expand_chunks: When True and using re-ranker, fetch additional chunks from
            retrieved documents to give re-ranker more options (default: False)
        additional_chunks_per_doc: Number of additional chunks to fetch per document
            when expand_chunks=True (default: 5)

    Returns:
        List of SearchResult objects ordered by similarity (or re-ranker score if enabled)

    Example:
        >>> # Basic re-ranking
        >>> results = semantic_search("What are GLP-1 agonists used for?", top_k=10, use_reranker=True)
        >>>
        >>> # Re-ranking with chunk expansion to reduce title bias
        >>> results = semantic_search("What are GLP-1 agonists used for?", top_k=10, use_reranker=True, expand_chunks=True)
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
where doc.priority > 0
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

    # Return top n search result, reranking if use_reranker is set
    if use_reranker:
        from app.retrieval.reranker import get_reranker
        reranker = get_reranker()
        logger.info(f"  Using reranker model: {reranker.model_name}")

        # Optionally expand chunks before re-ranking
        if expand_chunks:
            # Fetch additional chunks from the same documents to give re-ranker more options
            # This helps when initial retrieval found papers based on title matching,
            # but the actual relevant content is in different chunks
            expand_start = time.time()
            document_ids = list(set(result.document_id for result in search_results))
            initial_chunk_ids = [result.chunk_id for result in search_results]

            additional_chunks = fetch_additional_chunks_from_documents(
                document_ids=document_ids,
                exclude_chunk_ids=initial_chunk_ids,
                chunks_per_document=additional_chunks_per_doc
            )

            expand_time = (time.time() - expand_start) * 1000
            logger.info(f"  Expanded to {len(additional_chunks)} additional chunks from {len(document_ids)} documents ({expand_time:.0f}ms)")

            # Combine initial results with additional chunks for re-ranking
            all_chunks = search_results + additional_chunks
            logger.info(f"  Re-ranking {len(all_chunks)} total chunks ({len(search_results)} initial + {len(additional_chunks)} additional)")
        else:
            # Re-rank only the initial search results
            all_chunks = search_results

        top_n_search_results = rerank_chunks(query, all_chunks, top_n)
    else:
        top_n_search_results = search_results[:top_n]

    return top_n_search_results


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


def fetch_additional_chunks_from_documents(
    document_ids: List[int],
    exclude_chunk_ids: List[int] = None,
    chunks_per_document: int = 5
) -> List[SearchResult]:
    """
    Fetch additional chunks from specified documents.

    This allows the re-ranker to consider more content from papers that were
    initially retrieved, helping to find more relevant chunks based on content
    rather than just title matching.

    Args:
        document_ids: List of document IDs to fetch chunks from
        exclude_chunk_ids: Chunk IDs to exclude (e.g., already retrieved chunks)
        chunks_per_document: Maximum number of chunks to fetch per document

    Returns:
        List of SearchResult objects
    """
    if not document_ids:
        return []

    exclude_chunk_ids = exclude_chunk_ids or []

    # Use DISTINCT ON to get diverse chunks from each document
    # Order by chunk_index to get sequential content from the paper
    stmt = text(
        """
WITH ranked_chunks AS (
  SELECT
    chk.document_chunk_id,
    chk.content,
    chk.section,
    chk.document_id,
    chk.chunk_index,
    doc.source_id,
    doc.title,
    doc.doc_metadata,
    ROW_NUMBER() OVER (PARTITION BY chk.document_id ORDER BY chk.chunk_index) as rn
  FROM document_chunks chk
  JOIN documents doc ON chk.document_id = doc.document_id
  WHERE chk.document_id = ANY(:document_ids)
    AND (:exclude_empty OR chk.document_chunk_id != ALL(:exclude_chunk_ids))
)
SELECT
  document_chunk_id,
  content,
  section,
  document_id,
  source_id,
  title,
  doc_metadata
FROM ranked_chunks
WHERE rn <= :chunks_per_doc
ORDER BY document_id, chunk_index
"""
    )

    with Session(engine) as session:
        result_chunks = session.execute(stmt, {
            'document_ids': document_ids,
            'exclude_chunk_ids': exclude_chunk_ids if exclude_chunk_ids else [-1],
            'exclude_empty': len(exclude_chunk_ids) > 0,
            'chunks_per_doc': chunks_per_document
        }).fetchall()

    additional_chunks = []
    for chunk in result_chunks:
        chunk_metadata = chunk.doc_metadata or {}
        result = SearchResult(
            chunk_id=chunk.document_chunk_id,
            section=chunk.section,
            content=chunk.content,
            query="",  # No query for additional chunks
            similarity_score=None,  # No similarity score
            document_id=chunk.document_id,
            source_id=chunk.source_id,
            title=chunk.title,
            authors=chunk_metadata.get("authors", []),
            publication_date=chunk_metadata.get("pub_date", ""),
            journal=chunk_metadata.get("journal", ""),
            doi=chunk_metadata.get("doi", "")
        )
        additional_chunks.append(result)

    return additional_chunks

def hybrid_retrieval(
        query: str,
        conversation_history: Optional[List[dict]] = None,
        top_k = 20,
        top_n = 5,
        max_historical_chunks = 15,
        use_reranker = False,
        expand_chunks: bool = False,
        additional_chunks_per_doc: int = 5
) -> List[SearchResult]:
    """
    Hybrid retrieval, semantic search + most recent historical chunks

    Args:
        query: Natural language query string
        conversation_history: List of previous conversation turns
        top_k: Number of top results from vector search
        top_n: Number of final results to return
        max_historical_chunks: Maximum historical chunks to include
        use_reranker: Whether to use cross-encoder re-ranking
        expand_chunks: Whether to expand chunks before re-ranking (requires use_reranker=True)
        additional_chunks_per_doc: Number of additional chunks per document when expanding

    Returns:
        List of SearchResult objects
    """

    hybrid_start = time.time()
    new_chunks = semantic_search(query, top_k, top_n, use_reranker, expand_chunks, additional_chunks_per_doc)
    
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
