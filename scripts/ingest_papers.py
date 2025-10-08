"""
Ingestion script for PubMed papers.
Fetches, parses, chunks, embeds, and stores papers in the database.
"""
import os
import argparse
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.db.database import engine, Base
from app.db.models import Document, DocumentChunk
from app.ingestion.pubmed_fetcher import PubMedFetcher
from app.ingestion.chunker import DocumentChunker
from app.ingestion.embeddings import EmbeddingService
from app.logging_config import setup_logging
import logging

load_dotenv()
logger = logging.getLogger(__name__)


def ingest_papers(max_results: int = 10, start_index: int = 0, use_batch_api: bool = False):
    """
    Ingest papers from PubMed into database.

    Args:
        max_results: Number of papers to fetch
        start_index: Starting index for pagination
        use_batch_api: Use Batch API for embeddings (cheaper, slower)
    """
    # Initialize services
    fetcher = PubMedFetcher()
    chunker = DocumentChunker()
    embedder = EmbeddingService()

    # Step 1: Search and fetch papers
    logger.info(f"Searching for papers (max: {max_results}, start: {start_index})")
    pmc_ids = fetcher.search_diabetes_papers(max_results=max_results, start_index=start_index)
    logger.info(f"Found {len(pmc_ids)} papers")

    if not pmc_ids:
        logger.warning("No papers found")
        return

    papers = fetcher.fetch_batch(pmc_ids)
    logger.info(f"Fetched {len(papers)} papers successfully")

    # Step 2: Chunk all papers
    all_chunks = []
    paper_chunk_map = {}  # Track which chunks belong to which paper

    for paper in papers:
        chunks = chunker.chunk_document(paper)

        # Add source fields required for batch API
        for chunk in chunks:
            chunk['source'] = 'pubmed'
            chunk['source_id'] = paper['metadata']['pmc_id']

        all_chunks.extend(chunks)
        paper_chunk_map[paper['source_id']] = len(chunks)

    logger.info(f"Created {len(all_chunks)} chunks from {len(papers)} papers")

    # Step 3: Embed chunks
    if use_batch_api:
        logger.info("Using Batch API (50% cheaper, 2-24 hour turnaround)")
        batch_id = embedder.submit_batch_embed(all_chunks)
        logger.info(f"Batch submitted: {batch_id}")
        logger.info("Check batch status later with: embedder.get_batch_embed(batch_id)")
        logger.info("Exiting - run completion separately after batch finishes")
        return batch_id
    else:
        logger.info("Using Regular API (instant, standard pricing)")
        texts = [chunk['embedding_text'] for chunk in all_chunks]
        embeddings = embedder.embed_chunks(texts)

        # Add embeddings to chunks
        for chunk, emb in zip(all_chunks, embeddings):
            chunk['embedding'] = emb

        failed = sum(1 for emb in embeddings if emb is None)
        if failed > 0:
            logger.warning(f"{failed} chunks failed to embed")

    # Step 4: Insert into database
    logger.info("Inserting documents and chunks into database")

    with Session(engine) as session:
        for paper in papers:
            # Check if document already exists
            existing = session.query(Document).filter_by(
                source='pubmed',
                source_id=paper['source_id']
            ).first()

            if existing:
                logger.info(f"Document PMC{paper['source_id']} already exists, skipping")
                continue

            # Create document
            doc = Document(
                source='pubmed',
                source_id=paper['source_id'],
                title=paper['title'],
                abstract=paper['abstract'],
                full_text=paper['full_text'],
                doc_metadata=paper['metadata']
            )
            session.add(doc)
            session.flush()  # Get document_id before adding chunks

            # Create chunks for this document
            doc_chunks = [c for c in all_chunks if c['source_id'] == paper['source_id']]

            for chunk in doc_chunks:
                db_chunk = DocumentChunk(
                    document_id=doc.document_id,
                    section=chunk['section'],
                    chunk_index=chunk['chunk_index'],
                    content=chunk['content'],
                    char_start=chunk['char_start'],
                    char_end=chunk['char_end'],
                    token_count=chunk['token_count'],
                    embedding=chunk.get('embedding')
                )
                session.add(db_chunk)

            logger.info(f"Inserted PMC{paper['source_id']} with {len(doc_chunks)} chunks")

        session.commit()
        logger.info("Database insertion complete")

    logger.info("Ingestion complete!")


def complete_batch_api_ingestion(batch_id: str, papers_file: str = None):
    """
    Complete an ingestion after OpenAI Batch API finishes.

    Args:
        batch_id: OpenAI Batch API job ID
        papers_file: Optional path to saved papers JSON (for re-running)
    """
    # TODO: Implement Batch API completion workflow
    # 1. Load original papers and chunks
    # 2. Call embedder.get_batch_embed(batch_id, chunks)
    # 3. Insert into database
    logger.info("Batch API completion not yet implemented")
    logger.info("For now, use regular API (--batch-api=False)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest PubMed papers into database")
    parser.add_argument("--max-results", type=int, default=10, help="Number of papers to fetch")
    parser.add_argument("--start-index", type=int, default=0, help="Starting index for pagination")
    parser.add_argument("--batch-api", action="store_true", help="Use Batch API (cheaper, async)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    setup_logging(level=args.log_level)

    ingest_papers(
        max_results=args.max_results,
        start_index=args.start_index,
        use_batch_api=args.batch_api
    )
