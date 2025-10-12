"""
Stage 4: Embed document chunks using OpenAI API.

Processes documents with ingestion_status='chunked' and generates embeddings
for all their chunks. Supports regular API (instant) and batch API (24h, 50% cheaper).
"""
import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func
import tiktoken

from app.db.database import engine
from app.db.models import Document, DocumentChunk, OpenAIBatch
from app.ingestion.embeddings import EmbeddingService
from app.logging_config import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)

def count_tokens(text: str) -> int:
    """Count tokens in text."""
    encoding_name: str = "cl100k_base"  # OpenAI's tokenizer
    encoder = tiktoken.get_encoding(encoding_name)
    return len(encoder.encode(text))

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
    logger.info(f"Found {total_docs} documents with status='chunked'")
    
    # Initialize embedding service
    embedder = EmbeddingService(model=args.model)

    # Track Progress
    success_count = 0
    fail_count = 0
    total_chunks_embedded = 0
    total_cost = 0

    # Fetch document IDs to process (ordered for consistency)
    with Session(engine) as session:
        stmt = select(Document.document_id, Document.title).where(Document.ingestion_status == 'chunked').order_by(Document.document_id)
        if args.limit is not None:
            stmt = stmt.limit(args.limit)
        documents = session.execute(stmt).all()

    logger.info(f"Processing {len(documents)} documents\n")

    # Process documents one at a time (memory efficient)
    for doc_idx, (document_id, title) in enumerate(documents, 1):
        try:
            with Session(engine) as session:
                
                # Fetch all chunks for the document
                chunks = session.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                    ).scalars().all()
                
                # Check if chunks exist, warn and continue if not
                if not chunks:
                    logger.warning(f"[{doc_idx}/{len(documents)}] No chunks found for {document_id}: {title}")
                    fail_count += 1
                    continue

                # Embed document chunks
                text_chunks = []
                for chunk in chunks:
                    embedding_text = f"Doc: {title}\nSection: {chunk.section}\n\n{chunk.content}"
                    text_chunks.append(embedding_text)
                embedded_chunks, embedding_cost = embedder.embed_chunks(text_chunks)

                # Check if chunks were embedded, warn and continue if not
                if any(emb is None for emb in embedded_chunks):
                    logger.warning(f"[{doc_idx}/{len(documents)}] Embedding failed for {document_id}: {title}")
                    fail_count += 1
                    continue

                # Update database: all document chunks with embeddings, and update document as embedded
                for chunk, emb in zip(chunks, embedded_chunks):
                    chunk.embedding = emb
                session.execute(
                    update(Document).where(Document.document_id == document_id).values(ingestion_status='embedded')
                )
                session.commit()

                success_count += 1
                total_chunks_embedded += len(embedded_chunks)
                total_cost += embedding_cost
                logger.debug(f"[{doc_idx}/{len(documents)}] Successfully embedded {document_id}: {title}")

                # Log progress every 10 documents
                if doc_idx % 10 == 0:
                    avg_chunks = total_chunks_embedded / success_count if success_count > 0 else 0
                    logger.info(f"Progress: {doc_idx}/{len(documents)} documents embedded ({success_count} successful, {fail_count} failed, {total_chunks_embedded} total chunks, {avg_chunks:.1f} avg chunks/doc)\n")
        
        except Exception as e:
            logger.error(f"[{doc_idx}/{len(documents)}] Error embedding [{document_id}]{title}: {e}", exc_info=True)
            fail_count += 1
            continue
    
    avg_chunks = total_chunks_embedded / success_count if success_count > 0 else 0 
    logger.info(f"\nCompleted with regular embeddings API: {success_count} successful, {fail_count} failed")
    logger.info(f"Total chunks embedded: {total_chunks_embedded} ({avg_chunks:.1f} avg per document)")
    logger.info(f"Total cost: ${total_cost:.4f}")
    logger.info(f"Remaining documents to embed: {total_docs - success_count}")



def submit_batch(args):
    """Submit batch job to OpenAI Batch API."""
    MAX_CHUNKS_PER_BATCH = 50000 
    MAX_TOKENS_PER_BATCH = 3_000_000

    # Count total documents needing embedding
    with Session(engine) as session:
        total_docs = session.query(Document).filter(
            Document.ingestion_status == 'chunked'
        ).count()

    if total_docs == 0:
        logger.info("No documents need embedding")
        return
    logger.info(f"Found {total_docs} documents with status='chunked'")

    # Initialize embedding service
    embedder = EmbeddingService(model=args.model)

    # Fetch document IDs to process (ordered for consistency)
    with Session(engine) as session:
        stmt = select(Document.document_id, Document.title).where(Document.ingestion_status == 'chunked').order_by(Document.document_id)
        if args.limit is not None:
            stmt = stmt.limit(args.limit)
        documents = session.execute(stmt).all()

    # Calculate number of batches
    logger.info(f"Processing {len(documents)} documents\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # # Track batch submissions
    # metadata_file = f"data/stage_4_batches/batch_metadata_{timestamp}.jsonl"
    # Path(metadata_file).parent.mkdir(parents=True, exist_ok=True)

    # Track progress
    current_batch_idx = 0
    docs_processed = 0
    doc_idx = 0
    
    while doc_idx < len(documents):

        # Start a new batch 
        current_batch_chunks = []
        current_batch_doc_ids = []
        current_batch_num_tokens = 0
        current_batch_idx += 1
        logger.info(f"[Batch {current_batch_idx}] collecting chunks...")

        # Collect all chunks for all documents until we run out or hit the max
        with Session(engine) as session:
            while doc_idx < len(documents) and len(current_batch_chunks) < MAX_CHUNKS_PER_BATCH and current_batch_num_tokens < MAX_TOKENS_PER_BATCH:

                # Fetch all chunks for the document
                document_id, title = documents[doc_idx]
                chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()

                # Check if chunks exist, warn and continue if not
                if not chunks: 
                    logger.warning(f"No chunks found for {document_id}: {title}, skipping")
                    doc_idx += 1
                    continue

               

                # Prepare chunks to add to current batch
                doc_embedding_texts = []
                doc_tokens = 0
                for chunk in chunks:
                    embedding_text = f"Doc: {title}\nSection: {chunk.section}\n\n{chunk.content}"
                    doc_embedding_texts.append({
                        'document_chunk_id': chunk.document_chunk_id,
                        'embedding_text': embedding_text
                    })
                    doc_tokens += count_tokens(embedding_text)
                
                # Check if adding the document chunks would max out our current batch, break if so
                if len(current_batch_chunks) + len(chunks) > MAX_CHUNKS_PER_BATCH or current_batch_num_tokens + doc_tokens > MAX_TOKENS_PER_BATCH:
                    doc_idx += 1
                    break

                # Add chunks to current batch
                current_batch_chunks.extend(doc_embedding_texts)

                docs_processed += 1
                current_batch_doc_ids.append(document_id)
                current_batch_num_tokens += doc_tokens
                doc_idx += 1
        
        # Complete the batch
        if not current_batch_chunks:
            logger.warning(f"[Batch {current_batch_idx}] No chunks collected, we are done")
            break

        # Create batch file and submit 
        batch_filepath = f"data/stage_4_batches/batch_{timestamp}_{current_batch_idx}.jsonl"
        try:
            openai_batch_id = embedder.submit_batch_embed(current_batch_chunks, batch_filepath)

            # # Record metadata
            # metadata = {
            #     'openai_batch_id': openai_batch_id,
            #     'batch_number': current_batch_idx,
            #     'submitted_at': datetime.now().isoformat(),
            #     'doc_count': len(current_batch_doc_ids),
            #     'chunk_count': len(current_batch_chunks),
            #     'input_file': batch_filepath
            # }

            # # Write metadata incrementally (append mode)
            # with open(metadata_file, 'a') as f:
            #     f.write(json.dumps(metadata) + '\n')

            # Record metadata in OpenAIBatch table
            openai_batch_record = OpenAIBatch(
                openai_batch_id = openai_batch_id,
                status = 'submitted',
                doc_count = len(current_batch_doc_ids),
                chunk_count = len(current_batch_chunks),
                token_count = current_batch_num_tokens,
                input_file = batch_filepath
            )

            # Mark documents as batch_submitted
            with Session(engine) as session:
                session.execute(
                    update(Document).where(Document.document_id.in_(current_batch_doc_ids)).values(
                        ingestion_status='batch_submitted', 
                        openai_batch_id=openai_batch_id
                        )
                )
                session.add(openai_batch_record)
                session.commit()

            logger.info(f"[Batch {current_batch_idx}] Submitted: {openai_batch_id} ({len(current_batch_chunks)} chunks)")

        except Exception as e:
            logger.error(f"[Batch {current_batch_idx}] Failed to submit: {e}", exc_info=True)
            continue

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"Submitted {current_batch_idx} batches!")
    logger.info(f"{'='*80}")


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
  python -m scripts.stage_4_embed_chunks

  # Regular API with limit
  python -m scripts.stage_4_embed_chunks --limit 100

  # Batch API - submit (24-hour turnaround, 50%% cheaper)
  python -m scripts.stage_4_embed_chunks --mode submit-batch --limit 1000

  # Batch API - get results
  python -m scripts.stage_4_embed_chunks --mode get-batch --batch-id batch_abc123
        """
    )

    # Pricing per 1M tokens (as of 2025)
    MODEL_PRICING = {
        "text-embedding-3-small": 0.02,
        "text-embedding-3-large": 0.13,
        "text-embedding-ada-002": 0.10,
    }

    # Embedding mode
    parser.add_argument("--mode", type=str,
                       choices=["regular", "submit-batch", "get-batch"],
                       default="regular",
                       help="Embedding mode (default: regular)")

    # Common options
    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of documents to process (default: all)")
    parser.add_argument("--budget", type=float, default=0.1,
                       help="API budget in dollars (default: 0.1)")
    parser.add_argument("--batch-id", type=str,
                       help="Single OpenAI batch ID to check/retrieve")
    parser.add_argument("--batch-file", type=str,
                       help="JSONL file containing multiple batch IDs (from submit-batch)")
    parser.add_argument("--model", type=str, default="text-embedding-3-small",
                       choices=["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
                       help="OpenAI embedding model (default: text-embedding-3-small)")
    parser.add_argument("--log-level", type=str,
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: LOG_LEVEL env var or INFO)")

    args = parser.parse_args()

    # Validate get-batch requires batch-id OR batch-file
    if args.mode == "get-batch" and not (args.batch_id or args.batch_file):
        parser.error("--batch-id or --batch-file is required when using --mode get-batch")

    # Setup logging
    log_level = args.log_level or os.getenv("LOG_LEVEL", "INFO")

    # Archive old log if it exists
    old_log = Path("logs/stage_4_embed_chunks.log")
    if old_log.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_log.rename(f"logs/stage_4_embed_chunks_{timestamp}.log")

    setup_logging(level=log_level, log_file="logs/stage_4_embed_chunks.log")

    # Cost warning for embedding modes
    if args.mode in ["regular", "submit-batch"]:
        with Session(engine) as session:
            doc_stmt = select(Document.document_id).where(Document.ingestion_status == 'chunked').order_by(Document.document_id)
            if args.limit is not None:
                doc_stmt = doc_stmt.limit(args.limit)
            doc_ids = session.execute(doc_stmt).scalars().all()

            if doc_ids:
                total_tokens = session.execute(
                    select(func.sum(DocumentChunk.token_count)).where(DocumentChunk.document_id.in_(doc_ids))
                ).scalar() or 0 
            else:
                total_tokens = 0

        logger.warning("=" * 80)
        logger.warning("COST WARNING: This operation will use the OpenAI Embeddings API")
        
        price_per_million = MODEL_PRICING.get(args.model, 0.02)
        cost = (total_tokens / 1_000_000) * price_per_million

        if args.mode == "regular":
            logger.warning(f"Model: {args.model} @ ${price_per_million} / 1M toks | Tokens: {total_tokens:,} | Estimated Cost: ${cost:.4f}")
        elif args.mode == "submit-batch":
            cost /= 2
            logger.warning(f"Model: {args.model} @ ${price_per_million/2} / 1M toks (50% discount with batch API) | Tokens: {total_tokens:,} | Estimated Cost: ${cost:.4f}")
        
        # Check budget limit and return early if out of budget
        if cost > args.budget:
            logger.error(f"Estimated cost ${cost:.4f} exceeds budget limit of ${args.budget:.2f}")
            logger.error("Use --budget to increase the limit or --limit to process fewer documents")
            return


    # Route to appropriate function
    if args.mode == "regular":
        embed_regular(args)
    elif args.mode == "submit-batch":
        submit_batch(args)
    elif args.mode == "get-batch":
        get_batch(args)


if __name__ == "__main__":
    main()
