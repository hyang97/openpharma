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

    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        """
        Initialize the embedding service.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI embedding model to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key parameter.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model

        logger.info(f"Initialized EmbeddingService with model: {model}")

    # ============================================================================
    # REGULAR API (instant, more expensive)
    # ============================================================================

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string using regular API.

        Args:
            text: Text to embed

        Returns:
            List of floats (1536 dimensions for text-embedding-3-small)
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text (length: {len(text)} chars)")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            raise

    def embed_batch_sync(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using regular API.

        OpenAI allows up to 2048 texts per request, but we use smaller batches
        for better error handling and progress tracking.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to embed per API call (max 2048)

        Returns:
            List of embeddings (same order as input texts)
        """
        if not texts:
            return []

        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        logger.info(f"Embedding {len(texts)} texts in {total_batches} batches (batch_size={batch_size})")

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch = texts[start_idx:end_idx]

            try:
                logger.debug(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} texts)")

                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model
                )

                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.info(f"Completed batch {batch_num + 1}/{total_batches}")

                # Rate limiting: small delay between batches
                if batch_num < total_batches - 1:
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error processing batch {batch_num + 1}/{total_batches}: {e}", exc_info=True)
                raise

        logger.info(f"Successfully generated {len(all_embeddings)} embeddings")
        return all_embeddings

    # ============================================================================
    # BATCH API (async, 50% cheaper)
    # ============================================================================

    def create_batch_file(self, chunks: List[Dict], output_path: str) -> str:
        """
        Create JSONL batch file for OpenAI Batch API.

        Args:
            chunks: List of chunk dicts with 'embedding_text' field
            output_path: Path to save JSONL file

        Returns:
            Path to created file
        """
        logger.info(f"Creating batch file with {len(chunks)} chunks")

        # Validate chunks have embedding_text
        if any("embedding_text" not in chunk for chunk in chunks):
            raise ValueError("All chunks must have 'embedding_text' field")

        # Create JSONL format for batch API
        batch_requests = []
        for i, chunk in enumerate(chunks):
            request = {
                "custom_id": f"chunk_{i}",
                "method": "POST",
                "url": "/v1/embeddings",
                "body": {
                    "model": self.model,
                    "input": chunk["embedding_text"]
                }
            }
            batch_requests.append(request)

        # Write to JSONL file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            for request in batch_requests:
                f.write(json.dumps(request) + '\n')

        logger.info(f"Created batch file: {output_path} ({len(batch_requests)} requests)")
        return str(output_file)

    def submit_batch(self, batch_file_path: str) -> str:
        """
        Upload batch file and submit batch job to OpenAI.

        Args:
            batch_file_path: Path to JSONL batch file

        Returns:
            Batch ID for tracking
        """
        logger.info(f"Uploading batch file: {batch_file_path}")

        # Upload file
        with open(batch_file_path, 'rb') as f:
            batch_input_file = self.client.files.create(
                file=f,
                purpose="batch"
            )

        logger.info(f"File uploaded: {batch_input_file.id}")

        # Create batch job
        batch = self.client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/embeddings",
            completion_window="24h"
        )

        logger.info(f"Batch job created: {batch.id}")
        logger.info(f"Status: {batch.status}")

        return batch.id

    def get_batch_status(self, batch_id: str) -> Dict:
        """
        Check status of a batch job.

        Args:
            batch_id: Batch ID from submit_batch()

        Returns:
            Dict with status info
        """
        batch = self.client.batches.retrieve(batch_id)

        status_info = {
            "status": batch.status,
            "total_requests": batch.request_counts.total,
            "completed_requests": batch.request_counts.completed,
            "failed_requests": batch.request_counts.failed,
        }

        if batch.status == "completed":
            status_info["output_file_id"] = batch.output_file_id

        if batch.status == "failed":
            status_info["errors"] = batch.errors

        return status_info

    def wait_for_batch(self, batch_id: str, poll_interval: int = 60, max_wait: int = 86400) -> Dict:
        """
        Wait for batch job to complete, polling periodically.

        Args:
            batch_id: Batch ID to wait for
            poll_interval: Seconds between status checks (default: 60)
            max_wait: Maximum seconds to wait (default: 86400 = 24 hours)

        Returns:
            Final status info dict
        """
        logger.info(f"Waiting for batch {batch_id} to complete...")
        logger.info(f"Polling every {poll_interval} seconds (max wait: {max_wait}s)")

        start_time = time.time()
        last_status = None

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise TimeoutError(f"Batch did not complete within {max_wait} seconds")

            status_info = self.get_batch_status(batch_id)

            # Log if status changed
            if status_info["status"] != last_status:
                logger.info(
                    f"Status: {status_info['status']} | "
                    f"Completed: {status_info['completed_requests']}/{status_info['total_requests']}"
                )
                last_status = status_info["status"]

            # Check if done
            if status_info["status"] == "completed":
                logger.info(f"Batch completed successfully in {elapsed:.1f} seconds")
                return status_info

            if status_info["status"] == "failed":
                logger.error(f"Batch failed: {status_info.get('errors')}")
                raise RuntimeError(f"Batch job failed: {status_info.get('errors')}")

            if status_info["status"] in ["expired", "cancelled"]:
                raise RuntimeError(f"Batch job {status_info['status']}")

            time.sleep(poll_interval)

    def download_batch_results(self, batch_id: str, output_path: str = None) -> str:
        """
        Download results from completed batch job.

        Args:
            batch_id: Batch ID
            output_path: Path to save results JSONL (optional)

        Returns:
            Path to downloaded results file
        """
        status_info = self.get_batch_status(batch_id)

        if status_info["status"] != "completed":
            raise ValueError(f"Batch not completed yet. Status: {status_info['status']}")

        output_file_id = status_info["output_file_id"]
        logger.info(f"Downloading results from file: {output_file_id}")

        # Download file content
        file_response = self.client.files.content(output_file_id)
        content = file_response.read()

        # Save to file
        if output_path is None:
            output_path = f"data/batches/results_{batch_id}.jsonl"

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'wb') as f:
            f.write(content)

        logger.info(f"Results saved to: {output_path}")
        return str(output_file)

    def parse_batch_results(self, results_file_path: str, chunks: List[Dict]) -> List[Dict]:
        """
        Parse batch results and add embeddings to chunks.

        Args:
            results_file_path: Path to downloaded results JSONL
            chunks: Original chunks (same order as batch file)

        Returns:
            Chunks with 'embedding' field added
        """
        logger.info(f"Parsing batch results from: {results_file_path}")

        # Read results
        results = {}
        with open(results_file_path, 'r') as f:
            for line in f:
                result = json.loads(line)
                custom_id = result["custom_id"]

                if result.get("error"):
                    logger.error(f"Error for {custom_id}: {result['error']}")
                    continue

                # Extract embedding
                embedding = result["response"]["body"]["data"][0]["embedding"]
                results[custom_id] = embedding

        logger.info(f"Parsed {len(results)} embeddings from results")

        # Add embeddings to chunks
        for i, chunk in enumerate(chunks):
            custom_id = f"chunk_{i}"
            if custom_id in results:
                chunk["embedding"] = results[custom_id]
            else:
                logger.warning(f"No embedding found for chunk {i}")
                chunk["embedding"] = None

        successful = sum(1 for c in chunks if c.get("embedding") is not None)
        logger.info(f"Added embeddings to {successful}/{len(chunks)} chunks")

        return chunks

    # ============================================================================
    # UNIFIED INTERFACE
    # ============================================================================

    def embed_chunks(
        self,
        chunks: List[Dict],
        use_batch: bool = True,
        wait: bool = True,
        batch_file_path: str = None
    ) -> tuple[List[Dict], Optional[str]]:
        """
        Generate embeddings for chunks.

        Args:
            chunks: List of chunk dicts with 'embedding_text' field
            use_batch: If True, use Batch API (cheaper, slower). If False, use regular API (instant, more expensive)
            wait: Only for Batch API - If True, wait for completion. If False, return batch_id immediately.
            batch_file_path: Path for batch files (default: data/batches/embed_<timestamp>.jsonl)

        Returns:
            If use_batch=False OR (use_batch=True AND wait=True): (chunks with embeddings, batch_id or None)
            If use_batch=True AND wait=False: (original chunks, batch_id)
        """
        if not chunks:
            logger.warning("No chunks to embed")
            return chunks, None

        # Validate chunks have embedding_text
        if any("embedding_text" not in chunk for chunk in chunks):
            raise ValueError("All chunks must have 'embedding_text' field")

        # Regular API (instant)
        if not use_batch:
            logger.info(f"Using regular API to embed {len(chunks)} chunks")
            embedding_texts = [chunk["embedding_text"] for chunk in chunks]
            embeddings = self.embed_batch_sync(embedding_texts)

            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding

            logger.info(f"Added embeddings to {len(chunks)} chunks")
            return chunks, None

        # Batch API (cheaper but slower)
        logger.info(f"Using Batch API to embed {len(chunks)} chunks")

        # Generate batch file path if not provided
        if batch_file_path is None:
            timestamp = int(time.time())
            batch_file_path = f"data/batches/embed_{timestamp}.jsonl"

        # Create and submit batch
        batch_file = self.create_batch_file(chunks, batch_file_path)
        batch_id = self.submit_batch(batch_file)

        if not wait:
            logger.info(f"Batch submitted. Track with batch_id: {batch_id}")
            logger.info(f"Use get_batch_status('{batch_id}') to check progress")
            return chunks, batch_id

        # Wait for completion
        self.wait_for_batch(batch_id)

        # Download and parse results
        results_file = batch_file_path.replace(".jsonl", "_results.jsonl")
        self.download_batch_results(batch_id, output_path=results_file)
        chunks_with_embeddings = self.parse_batch_results(results_file, chunks)

        return chunks_with_embeddings, batch_id
