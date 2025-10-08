"""
Embedding generation service using OpenAI API.
Supports both regular API (instant, more expensive) and Batch API (slower, 50% cheaper).
"""
from typing import List, Dict, Optional
import os
import json
import time
from pathlib import Path
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates embeddings for document chunks using OpenAI."""

    # Pricing per 1M tokens (as of 2025)
    MODEL_PRICING = {
        "text-embedding-3-small": 0.02,
        "text-embedding-3-large": 0.13,
        "text-embedding-ada-002": 0.10,
    }

    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key parameter.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.price_per_million = self.MODEL_PRICING.get(model, 0.02)

        logger.info(f"Initialized EmbeddingService with model: {model} (${self.price_per_million}/1M tokens)")

    # ============================================================================
    # REGULAR API (synchronous, instant)
    # ============================================================================

    def embed_chunks(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """Generate embeddings synchronously. Returns embeddings (None for failures)."""
        if not texts:
            return []

        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        total_tokens = 0

        logger.info(f"Embedding {len(texts)} texts in {total_batches} batches")

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch = texts[start_idx:end_idx]

            try:
                response = self.client.embeddings.create(input=batch, model=self.model)
                all_embeddings.extend([item.embedding for item in response.data])
                total_tokens += response.usage.total_tokens

            except Exception as e:
                logger.error(f"Batch {batch_num + 1}/{total_batches} failed: {e}")
                all_embeddings.extend([None] * len(batch))

            if batch_num < total_batches - 1:
                time.sleep(0.1)

        successful = sum(1 for emb in all_embeddings if emb is not None)

        # Calculate cost based on model pricing
        cost = (total_tokens / 1_000_000) * self.price_per_million

        logger.info(f"Generated {successful}/{len(all_embeddings)} embeddings")
        logger.info(f"Model: {self.model} | Tokens: {total_tokens:,} | Cost: ${cost:.4f}")

        return all_embeddings

    # ============================================================================
    # BATCH API (async, 50% cheaper)
    # ============================================================================

    def submit_batch_embed(self, chunks: List[Dict], output_path: str = None) -> str:
        """Submit chunks to OpenAI Batch API. Returns batch_id for tracking."""
        # Validate required fields
        required = ['embedding_text', 'source', 'source_id', 'chunk_index']
        if any(f not in chunks[0] for f in required):
            raise ValueError(f"Chunks must have fields: {required}")

        # Create batch file
        if output_path is None:
            timestamp = int(time.time())
            output_path = f"data/batches/batch_{timestamp}.jsonl"

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            for chunk in chunks:
                custom_id = f"{chunk['source']}_{chunk['source_id']}_{chunk['chunk_index']}"
                request = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/embeddings",
                    "body": {"model": self.model, "input": chunk["embedding_text"]}
                }
                f.write(json.dumps(request) + '\n')

        # Upload and submit
        with open(output_file, 'rb') as f:
            batch_input_file = self.client.files.create(file=f, purpose="batch")

        batch = self.client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/embeddings",
            completion_window="24h"
        )

        logger.info(f"Submitted batch {batch.id} with {len(chunks)} chunks")
        return batch.id

    def get_batch_embed(self, batch_id: str, chunks: List[Dict] = None, output_path: str = None):
        """
        Check batch status or complete batch.

        If chunks=None: returns status dict
        If chunks provided and complete: returns chunks with embeddings
        If chunks provided but incomplete: returns status dict
        """
        batch = self.client.batches.retrieve(batch_id)

        # Return status if not complete or no chunks provided
        if batch.status != "completed" or chunks is None:
            return {
                "status": batch.status,
                "completed": batch.request_counts.completed,
                "total": batch.request_counts.total,
                "failed": batch.request_counts.failed,
            }

        # Download and save results
        if output_path is None:
            output_path = f"data/batches/results_{batch_id}.jsonl"

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        file_response = self.client.files.content(batch.output_file_id)
        with open(output_file, 'wb') as f:
            f.write(file_response.read())

        # Parse results into dict and track tokens
        results = {}
        total_tokens = 0
        with open(output_file, 'r') as f:
            for line in f:
                result = json.loads(line)
                if result.get("error"):
                    logger.error(f"Error for {result['custom_id']}: {result['error']}")
                    continue
                results[result["custom_id"]] = result["response"]["body"]["data"][0]["embedding"]
                total_tokens += result["response"]["body"]["usage"]["total_tokens"]

        # Add embeddings to chunks
        for chunk in chunks:
            custom_id = f"{chunk['source']}_{chunk['source_id']}_{chunk['chunk_index']}"
            chunk["embedding"] = results.get(custom_id)

        successful = sum(1 for c in chunks if c.get("embedding") is not None)

        # Calculate cost (Batch API: 50% discount)
        batch_price = self.price_per_million * 0.5
        cost = (total_tokens / 1_000_000) * batch_price

        logger.info(f"Completed batch {batch_id}: {successful}/{len(chunks)} chunks embedded")
        logger.info(f"Model: {self.model} | Tokens: {total_tokens:,} | Cost: ${cost:.4f} (50% batch discount)")

        return chunks


