"""
Stage 4: Embed document chunks using Ollama (primary) or OpenAI API (legacy).

Processes documents with ingestion_status='chunked' and generates embeddings
for all their chunks. Primary method uses Ollama (free, instant, 768d).
Legacy OpenAI batch API support preserved but deprecated.
"""
import argparse
import json
import logging
import os
import time
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


def batched(iterable, n):
    """Batch an iterable into batches of size n. Available in Python 3.12+ i think?"""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == n:
            yield batch 
            batch = []
    if batch:
        yield batch


def embed_regular(args):
    """Embed chunks using Ollama API (instant, free, 768d) with batched files"""

    DOC_BATCH_SIZE = 50  # Process 50 documents at once
    NUM_WORKERS = args.workers  # Parallel workers from CLI

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
    failed_batch_count = 0
    total_chunks_embedded = 0

    # Fetch document IDs to process (ordered for consistency)
    with Session(engine) as session:
        stmt = select(Document.document_id, Document.title).where(Document.ingestion_status == 'chunked').order_by(Document.document_id)
        if args.limit is not None:
            stmt = stmt.limit(args.limit)
        documents = session.execute(stmt).all()

    logger.info(f"Processing {len(documents)} documents\n")

    # Process documents in batches
    total_batches = (len(documents) + DOC_BATCH_SIZE - 1) // DOC_BATCH_SIZE
    start_time = time.time()

    for batch_idx, doc_batch in enumerate(batched(documents, DOC_BATCH_SIZE), 1):
        try:
            with Session(engine) as session:

                # Collect chunks from all docs in batch and gather chunk record and embedding_texts
                batch_chunks = []
                batch_doc_ids = set()
                for document_id, title in doc_batch:
                    
                    # Fetch all chunks for the document
                    chunks = session.execute(
                            select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                            ).scalars().all()
                    
                    # Check if chunks exist, warn and continue if not
                    if not chunks:
                        logger.warning(f"[Batch {batch_idx}/{total_batches}] No chunks found for {document_id}: {title}")
                        fail_count += 1
                        continue
                    
                    # Add chunks
                    for chunk in chunks:
                        embedding_text = f"Doc: {title}\nSection: {chunk.section}\n\n{chunk.content}"
                        batch_chunks.append({
                            'chunk_record': chunk,
                            'document_id': document_id,
                            'embedding_text': embedding_text
                            })
                    
                    batch_doc_ids.add(document_id)
                
                # Embed all chunks in the batch at once
                logger.info(f"[Batch {batch_idx}/{total_batches}] Processing {len(batch_chunks)} chunks for {len(batch_doc_ids)} documents")
                batch_embedding_texts = [item['embedding_text'] for item in batch_chunks]

                embed_start = time.time()
                embeddings, _ = embedder.embed_chunks(batch_embedding_texts, NUM_WORKERS)
                embed_time = time.time() - embed_start

                # Check if chunks were embedded, warn and continue if not
                if any(emb is None for emb in embeddings):
                    logger.warning(f"Batch {batch_idx}/{total_batches}: Failed embeddings detected, skipping batch")
                    failed_batch_count += 1
                    continue

                # Update all document chunks with embeddings
                db_start = time.time()
                for chunk, emb in zip(batch_chunks, embeddings):
                    chunk['chunk_record'].embedding = emb
                    total_chunks_embedded += 1

                # Update documents as embedded
                for doc_id in batch_doc_ids:
                    session.execute(
                        update(Document).where(Document.document_id == doc_id).values(ingestion_status='embedded')
                    )

                session.commit()
                db_time = time.time() - db_start
                success_count += len(batch_doc_ids)

                avg_embed_ms = (embed_time / len(batch_chunks)) * 1000
                logger.info(f"Batch {batch_idx}/{total_batches}: Embedded {len(batch_chunks)} chunks in {embed_time:.1f}s ({avg_embed_ms:.1f}ms/chunk), DB update {db_time:.1f}s\n\n")

        except Exception as e:
            logger.error(f"Batch {batch_idx}/{total_batches}: Error - {e}", exc_info=True)
            failed_batch_count += 1
    
    # Final summary
    total_time = time.time() - start_time
    avg_chunks = total_chunks_embedded / success_count if success_count > 0 else 0
    avg_time_per_chunk = (total_time / total_chunks_embedded) * 1000 if total_chunks_embedded > 0 else 0

    logger.info(f"\n{'='*80}")
    logger.info(f"Completed Ollama embedding:")
    logger.info(f"  Documents: {success_count} successful, {fail_count} failed")
    logger.info(f"  Chunks: {total_chunks_embedded:,} ({avg_chunks:.1f} avg/doc)")
    logger.info(f"  Workers: {NUM_WORKERS}")
    logger.info(f"  Total time: {total_time/60:.1f} minutes ({total_time:.0f}s)")
    logger.info(f"  Avg time/chunk: {avg_time_per_chunk:.1f}ms")
    logger.info(f"  Failed batches: {failed_batch_count}")
    logger.info(f"  Remaining docs: {total_docs - success_count}")
    logger.info(f"\n{'='*80}")


def main():
    """Embed document chunks using Ollama (primary) or OpenAI (legacy)."""
    parser = argparse.ArgumentParser(
        description="Embed document chunks using Ollama API (free, instant, 768d)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ollama API (instant, free, default mode)
  python -m scripts.stage_4_embed_chunks

  # Ollama API with limit
  python -m scripts.stage_4_embed_chunks --limit 100

  # Legacy batch modes (deprecated, Ollama does not support batch API)
  # python -m scripts.stage_4_embed_chunks --mode submit-batch
  # python -m scripts.stage_4_embed_chunks --mode get-batch --batch-id batch_abc123
        """
    )

    # Legacy OpenAI pricing (only used for deprecated batch modes)
    MODEL_PRICING = {
        "text-embedding-3-small": 0.02,
        "text-embedding-3-large": 0.13,
        "text-embedding-ada-002": 0.10,
    }

    # Embedding mode, options other than regular are not currently supported
    parser.add_argument("--mode", type=str,
                       choices=["regular", "submit-batch", "get-batch"],
                       default="regular",
                       help="Embedding mode (default: regular with Ollama)")

    # Common options
    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of documents to process (default: all)")
    parser.add_argument("--model", type=str, default="nomic-embed-text",
                       help="Ollama embedding model (default: nomic-embed-text)")
    parser.add_argument("--workers", type=int, default=1,
                       help="Number of parallel workers for embedding (default: 1 sequential, set to 8 if OLLAMA_NUM_PARALLEL=8)")
    parser.add_argument("--log-level", type=str,
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: LOG_LEVEL env var or INFO)")
    
    # Deprecated options
    parser.add_argument("--budget", type=float, default=None,
                       help="DEPRECATED: Not used with Ollama (always free)")
    parser.add_argument("--batch-id", type=str,
                       help="DEPRECATED: OpenAI batch ID (batch mode no longer supported)")
    parser.add_argument("--batch-file", type=str,
                       help="DEPRECATED: Batch file (batch mode no longer supported)")

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

    # DEPRECATED: Legacy OpenAI cost tracking (not executed for Ollama)
    if False and args.mode in ["regular", "submit-batch"]:
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
        if args.budget and cost > args.budget:
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

# ============================================================================
# OpenAI Batch APIs (deprecated))
# ============================================================================


def count_tokens(text: str) -> int:
    """Count tokens in text."""
    encoding_name: str = "cl100k_base"  # OpenAI's tokenizer
    encoder = tiktoken.get_encoding(encoding_name)
    return len(encoder.encode(text))

def embed_regular_with_legacy_support(args):
    """Embed chunks using Ollama API (instant, free, 768d) or OpenAI API (legacy)"""

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
    """
    DEPRECATED: Submit batch job to OpenAI Batch API.
    Ollama does not support batch API. Use embed_regular() instead.
    """
    logger.error("Batch API mode is deprecated. Ollama does not support batch operations.")
    logger.error("Use --mode regular instead (Ollama is instant and free).")
    return

    # Legacy OpenAI batch code preserved below (unreachable)
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
    """
    DEPRECATED: Get batch results from OpenAI Batch API.
    Ollama does not support batch API. Use embed_regular() instead.
    """
    logger.error("Batch API mode is deprecated. Ollama does not support batch operations.")
    logger.error("Use --mode regular instead (Ollama is instant and free).")
    return
