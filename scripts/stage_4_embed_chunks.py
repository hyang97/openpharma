"""
Stage 4: Embed document chunks using OpenAI API.

Processes documents with ingestion_status='chunked' and generates embeddings
for all their chunks. Supports regular API (instant) and batch API (24h, 50% cheaper).
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
from app.ingestion.embeddings import EmbeddingService
from app.logging_config import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)


def embed_regular(args):
    """Embed chunks using regular API (instant)."""
    # Count total documents needing embedding
    with Session(engine) as session:
        total_docs = session.query(Document).filter(
            Document.ingestion_status == 'chunked'
        ).count()

    if total_docs == 0:
        logger.info("No documents need embedding")
        return

    # Determine how many to process
    docs_to_process = args.limit if args.limit is not None else total_docs

    logger.info(f"Found {total_docs} documents with status='chunked'")
    logger.info(f"Processing {docs_to_process} documents\n")

    # Initialize embedding service
    embedder = EmbeddingService(model=args.model)

    # Track Progress
    success_count = 0
    fail_count = 0
    total_chunks_embedded = 0

    # Process documents one at a time (memory efficient)
    with Session(engine) as session:
        # TODO: Query for Document.document_id, Document.source_id WHERE ingestion_status='chunked'
        # TODO: Apply limit if args.limit is set
        # TODO: Get all document IDs as a list (.all())

        # TODO: Loop through each (doc_id, source_id) with enumerate(documents, 1)
            # TODO: Open a NEW session for this document (enables per-document commit)
            # TODO: Fetch document by document_id to get title
            # TODO: Fetch all chunks for this document from document_chunks table
            # TODO: Check if chunks exist, warn and continue if not
            # TODO: Build embedding_text for each chunk: "Document: {title}\nSection: {section}\n\n{content}"
            # TODO: Extract embedding_text strings into a list
            # TODO: Call embedder.embed_chunks(texts, batch_size=100)
            # TODO: Check if ANY embeddings are None (failure case)
            #   - If yes: log error, increment fail_count, continue to next document
            # TODO: If all succeeded:
            #   - Loop through chunks with embeddings and update each chunk.embedding
            #   - Update document.ingestion_status = 'embedded'
            #   - Commit the transaction
            #   - Increment success_count and total_chunks_embedded
            # TODO: Log progress every 100 documents

    # TODO: Log final summary (success_count, fail_count, total_chunks_embedded, remaining)


def submit_batch(args):
    """Submit batch job to OpenAI Batch API."""
    # TODO: Count total documents with ingestion_status='chunked'
    # TODO: Check if any documents exist, return if not
    # TODO: Determine docs_to_process (args.limit or total)
    # TODO: Log found/processing counts
    # TODO: Initialize EmbeddingService

    # TODO: Collect all chunk data for batch
    # TODO: Query for document_id, source_id WHERE ingestion_status='chunked'
    # TODO: Apply limit and get all (.all())
    # TODO: Initialize batch_chunks list
    # TODO: Loop through each document:
    #   - Fetch document by document_id to get title
    #   - Fetch all chunks (document_chunk_id, section, content)
    #   - Build embedding_text for each chunk
    #   - Build chunk dict: {document_chunk_id, embedding_text}
    #   - Append to batch_chunks list

    # TODO: Create batch file path with timestamp (data/batches/batch_{timestamp}.jsonl)
    # TODO: Call embedder.submit_batch_embed(batch_chunks, output_path)
    # TODO: Log batch_id, file path, and get-batch command for user


def get_batch(args):
    """Get batch results and update database."""
    # TODO: Initialize EmbeddingService
    # TODO: Call embedder.get_batch_embed(args.batch_id) to check status
    # TODO: If not completed, log status and return
    # TODO: Log that batch is complete, downloading results

    # TODO: Query for all chunks with embedding=NULL (candidates for this batch)
    # TODO: Build chunk_data list with document_chunk_id and embedding_text
    # TODO: Call embedder.get_batch_embed(args.batch_id, chunk_data) to download and parse

    # TODO: Track success/fail counts
    # TODO: For each chunk in returned chunk_data:
    #   - If embedding exists, update chunk in database
    #   - Track success/fail

    # TODO: Update documents to 'embedded' if all their chunks have embeddings
    # TODO: Use same UPDATE query as embed_regular
    # TODO: Log final summary


def main():
    """Embed document chunks using OpenAI API."""
    parser = argparse.ArgumentParser(
        description="Embed document chunks using OpenAI API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Regular API (instant, default mode)
  python -m scripts.embed_chunks

  # Regular API with limit
  python -m scripts.embed_chunks --limit 100

  # Batch API - submit (24-hour turnaround, 50%% cheaper)
  python -m scripts.embed_chunks --mode submit-batch --limit 1000

  # Batch API - get results
  python -m scripts.embed_chunks --mode get-batch --batch-id batch_abc123
        """
    )

    # Embedding mode
    parser.add_argument("--mode", type=str,
                       choices=["regular", "submit-batch", "get-batch"],
                       default="regular",
                       help="Embedding mode (default: regular)")

    # Common options
    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of documents to process (default: all)")
    parser.add_argument("--batch-id", type=str,
                       help="Batch ID (required for batch-complete mode)")
    parser.add_argument("--model", type=str, default="text-embedding-3-small",
                       choices=["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
                       help="OpenAI embedding model (default: text-embedding-3-small)")
    parser.add_argument("--log-level", type=str,
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: LOG_LEVEL env var or INFO)")

    args = parser.parse_args()

    # Validate get-batch requires batch-id
    if args.mode == "get-batch" and not args.batch_id:
        parser.error("--batch-id is required when using --mode get-batch")

    # Setup logging
    log_level = args.log_level or os.getenv("LOG_LEVEL", "INFO")

    # Archive old log if it exists
    old_log = Path("logs/stage_4_embed_chunks.log")
    if old_log.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_log.rename(f"logs/stage_4_embed_chunks_{timestamp}.log")

    setup_logging(level=log_level, log_file="logs/stage_4_embed_chunks.log")

    # Route to appropriate function
    if args.mode == "regular":
        embed_regular(args)
    elif args.mode == "submit-batch":
        submit_batch(args)
    elif args.mode == "get-batch":
        get_batch(args)


if __name__ == "__main__":
    main()
