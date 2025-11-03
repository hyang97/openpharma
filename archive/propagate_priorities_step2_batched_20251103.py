"""
Step 2: Propagate priorities from documents -> document_chunks with batched updates.

This performs the same update as Step 2 in propagate_priorities.sql but with
batched processing and progress logging.

Usage:
    docker-compose exec api python -m scripts.propagate_priorities_step2_batched [--batch-size BATCH_SIZE]
"""
import argparse
import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import engine
from app.logging_config import setup_logging, get_logger

setup_logging(level="INFO", log_file="logs/propagate_priorities_step2_batched.log")
logger = get_logger(__name__)


def propagate_documents_to_chunks_batched(session: Session, batch_size: int = 1000):
    """Propagate documents -> document_chunks in batches by document_id"""
    logger.info(f"Propagating priorities from documents to chunks (batch_size={batch_size:,} documents)...")

    # Get total documents and chunks
    doc_count_stmt = text("SELECT COUNT(*) FROM documents")
    total_docs = session.execute(doc_count_stmt).scalar()

    chunk_count_stmt = text("SELECT COUNT(*) FROM document_chunks")
    total_chunks = session.execute(chunk_count_stmt).scalar()

    logger.info(f"Total documents: {total_docs:,}")
    logger.info(f"Total chunks: {total_chunks:,}")
    logger.info(f"Avg chunks per doc: {total_chunks/total_docs:.1f}")
    logger.info("")

    # Process documents in batches
    total_chunks_updated = 0
    docs_processed = 0
    start_time = time.time()
    offset = 0

    while True:
        batch_time = time.time()

        # Get batch of document IDs and their priorities, then update all chunks for those docs
        stmt = text("""
            WITH doc_batch AS (
                SELECT document_id, priority
                FROM documents
                ORDER BY document_id
                LIMIT :batch_size OFFSET :offset
            )
            UPDATE document_chunks c
            SET priority = d.priority
            FROM doc_batch d
            WHERE c.document_id = d.document_id
        """)

        result = session.execute(stmt, {"batch_size": batch_size, "offset": offset})
        session.commit()

        batch_elapsed = time.time() - batch_time
        chunks_updated = result.rowcount
        total_chunks_updated += chunks_updated
        docs_processed += min(batch_size, total_docs - offset)
        total_elapsed = time.time() - start_time

        # Calculate ETA based on documents processed
        if docs_processed > 0:
            rate_docs = docs_processed / total_elapsed
            rate_chunks = total_chunks_updated / total_elapsed
            remaining_docs = total_docs - docs_processed
            eta_seconds = remaining_docs / rate_docs if rate_docs > 0 else 0
            eta_minutes = eta_seconds / 60

            logger.info(
                f"Docs {offset:,}-{offset+batch_size:,}: "
                f"{chunks_updated:,} chunks in {batch_elapsed:.2f}s | "
                f"Progress: {docs_processed:,}/{total_docs:,} docs ({100*docs_processed/total_docs:.1f}%) | "
                f"Chunks: {total_chunks_updated:,}/{total_chunks:,} ({100*total_chunks_updated/total_chunks:.1f}%) | "
                f"Rate: {rate_chunks:.0f} chunks/s | "
                f"ETA: {eta_minutes:.1f}min"
            )

        # Stop if no more rows to process
        if chunks_updated == 0:
            break

        offset += batch_size

    total_elapsed = time.time() - start_time
    logger.info("")
    logger.info(f"Completed: Updated {total_chunks_updated:,} chunks across {docs_processed:,} documents in {total_elapsed/60:.2f} minutes")
    return total_chunks_updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step 2: Propagate document priorities to chunks (batched)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of documents to process per batch (default: 1,000)"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Step 2: Propagate documents -> document_chunks (Batched)")
    logger.info("=" * 80)
    logger.info(f"Batch size: {args.batch_size:,}")
    logger.info("")

    with Session(engine) as session:
        chunks_updated = propagate_documents_to_chunks_batched(session, args.batch_size)

    logger.info("=" * 80)
    logger.info("Done!")
    logger.info("=" * 80)
