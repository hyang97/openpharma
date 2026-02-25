"""
OpenPharma MCP Server

Exposes the RAG pipeline (110K PubMed papers, 4.75M chunks) as MCP tools
for use with Claude Desktop or any MCP client.

Prerequisites:
  - Postgres running (docker-compose up -d postgres)
  - Ollama running locally with nomic-embed-text model
  - DATABASE_URL pointing to the openpharma database

Usage:
  python mcp_server.py
"""

from mcp.server.fastmcp import FastMCP

from app.retrieval import semantic_search
from app.rag.generation import generate_response
from app.rag.response_processing import strip_answer_heading, strip_references_section

mcp = FastMCP("openpharma")


@mcp.tool()
def search_papers(query: str, top_k: int = 10, top_n: int = 5) -> list[dict]:
    """Search 110K PubMed papers (4.75M chunks) using semantic vector search.

    Returns the most relevant paper chunks with full citation metadata.
    Use this to find scientific evidence on pharmaceutical topics like
    drug efficacy, mechanisms of action, clinical outcomes, etc.

    Args:
        query: Research question or topic to search for
        top_k: Number of candidates to retrieve before filtering (default 10)
        top_n: Number of final results to return (default 5)
    """
    results = semantic_search(query, top_k=top_k, top_n=top_n, use_reranker=False)
    return [
        {
            "source_id": r.source_id,
            "title": r.title,
            "authors": r.authors,
            "journal": r.journal,
            "publication_date": r.publication_date,
            "doi": r.doi,
            "section": r.section,
            "content": r.content,
            "similarity_score": round(r.similarity_score, 4) if r.similarity_score else None,
        }
        for r in results
    ]


@mcp.tool()
def ask_openpharma(question: str, top_k: int = 10, top_n: int = 5, use_local: bool = True) -> dict:
    """Ask a pharmaceutical research question and get a synthesized answer
    with citations from 110K PubMed papers.

    Performs semantic retrieval then LLM generation using the OpenPharma
    RAG pipeline. Returns the answer plus source citations.

    Args:
        question: Research question to answer
        top_k: Number of candidates to retrieve before filtering (default 10)
        top_n: Number of context chunks for generation (default 5)
        use_local: True for Ollama (local), False for Claude API (default True)
    """
    chunks = semantic_search(question, top_k=top_k, top_n=top_n, use_reranker=False)
    raw_response = generate_response(question, chunks, use_local=use_local)

    answer = strip_answer_heading(raw_response)
    answer = strip_references_section(answer)

    citations = []
    seen = set()
    for c in chunks:
        if c.source_id not in seen:
            seen.add(c.source_id)
            citations.append({
                "source_id": c.source_id,
                "title": c.title,
                "journal": c.journal,
                "authors": c.authors,
                "publication_date": c.publication_date,
            })

    return {
        "answer": answer,
        "citations": citations,
        "model": "ollama" if use_local else "anthropic",
    }


if __name__ == "__main__":
    mcp.run()
