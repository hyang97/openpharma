"""
Stage 3: Chunk documents into chunks with NULL embeddings.

Processes documents with ingestion_status='fetched' and creates chunks.
"""
import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.models import Document, DocumentChunk
from app.ingestion.chunker import DocumentChunker
from app.logging_config import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)


def main():
    """Chunk documents and store in database."""
    parser = argparse.ArgumentParser(
        description="Chunk documents and create chunks with NULL embeddings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Chunk all fetched documents (default)
  python -m scripts.chunk_papers

  # Chunk only 50 documents
  python -m scripts.chunk_papers --limit 50

  # Re-chunk all documents (deletes existing chunks)
  python -m scripts.chunk_papers --rechunk-all
        """
    )

    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of documents to chunk (default: chunk all fetched)")
    parser.add_argument("--rechunk-all", action="store_true",
                       help="Re-chunk all documents, even those already chunked (default: only chunk 'fetched' status)")
    parser.add_argument("--log-level", type=str,
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: LOG_LEVEL env var or INFO)")

    args = parser.parse_args()

    # Precedence: CLI arg > env var > default
    log_level = args.log_level or os.getenv("LOG_LEVEL", "INFO")

    # Archive old log if it exists
    old_log = Path("logs/stage_3_chunk_papers.log")
    if old_log.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_log.rename(f"logs/stage_3_chunk_papers_{timestamp}.log")

    # Always log to the same active file
    setup_logging(level=log_level, log_file="logs/stage_3_chunk_papers.log")

    chunker = DocumentChunker(chunk_size=512, overlap=50)

    # Get total count and set up query
    with Session(engine) as session:
        if args.rechunk_all:
            count_query = session.query(Document)
        else:
            count_query = session.query(Document).filter(Document.ingestion_status == 'fetched')

        total_docs = count_query.count()

    if total_docs == 0:
        logger.info("No documents to chunk")
        return

    # Determine batch size
    batch_size = args.limit if args.limit is not None else total_docs

    logger.info(f"Found {total_docs} total documents to chunk")
    logger.info(f"Chunking {batch_size} documents in this batch\n")

    success_count = 0
    fail_count = 0
    total_chunks_created = 0

    # Stream documents to avoid loading all into memory
    with Session(engine) as session:
        if args.rechunk_all:
            query = session.query(Document)
        else:
            query = session.query(Document).filter(Document.ingestion_status == 'fetched')

        if args.limit is not None:
            query = query.limit(args.limit)

        # Use yield_per to stream in batches of 100
        for idx, doc in enumerate(query.yield_per(100), 1):
            try:
                # Delete existing chunks if re-chunking
                with Session(engine) as chunk_session:
                    existing_count = chunk_session.query(DocumentChunk).filter(
                        DocumentChunk.document_id == doc.document_id
                    ).count()

                    if existing_count > 0:
                        logger.debug(f"[{idx}/{batch_size}] Deleting {existing_count} existing chunks for {doc.source_id}")
                        chunk_session.query(DocumentChunk).filter(
                            DocumentChunk.document_id == doc.document_id
                        ).delete()
                        chunk_session.commit()

                # Prepare document dict for chunker
                section_offsets = doc.doc_metadata.get("section_offsets", []) if doc.doc_metadata else []

                document_dict = {
                    "title": doc.title or "",
                    "full_text": doc.full_text or "",
                    "section_offsets": section_offsets
                }

                # Chunk the document (chunker extracts sections internally)
                chunks = chunker.chunk_document(document_dict)

                if not chunks:
                    logger.warning(f"[{idx}/{batch_size}] No chunks created for {doc.source_id}")
                    fail_count += 1
                    continue

                # Insert chunks into database
                with Session(engine) as chunk_session:
                    for chunk in chunks:
                        db_chunk = DocumentChunk(
                            document_id=doc.document_id,
                            section=chunk["section"],
                            chunk_index=chunk["chunk_index"],
                            content=chunk["content"],
                            char_start=chunk["char_start"],
                            char_end=chunk["char_end"],
                            token_count=chunk["token_count"],
                            embedding=None  # NULL = needs embedding
                        )
                        chunk_session.add(db_chunk)

                    # Update document status
                    chunk_session.query(Document).filter(
                        Document.document_id == doc.document_id
                    ).update({'ingestion_status': 'chunked'})

                    chunk_session.commit()

                success_count += 1
                total_chunks_created += len(chunks)
                logger.debug(f"[{idx}/{batch_size}] Successfully chunked {doc.source_id} into {len(chunks)} chunks")

                # Log progress every 100 documents
                if idx % 100 == 0:
                    avg_chunks = total_chunks_created / success_count if success_count > 0 else 0
                    logger.info(f"Progress: {idx}/{batch_size} documents processed ({success_count} successful, {fail_count} failed, {total_chunks_created} total chunks, {avg_chunks:.1f} avg chunks/doc)\n")

            except Exception as e:
                logger.error(f"[{idx}/{batch_size}] Error chunking {doc.source_id}: {e}", exc_info=True)
                fail_count += 1

    avg_chunks = total_chunks_created / success_count if success_count > 0 else 0
    logger.info(f"\nBatch complete: {success_count} successful, {fail_count} failed")
    logger.info(f"Total chunks created: {total_chunks_created} ({avg_chunks:.1f} avg per document)")
    logger.info(f"Remaining documents to chunk: {total_docs - success_count}")


if __name__ == "__main__":
    main()
