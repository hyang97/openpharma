"""
Embedding generation service using Ollama API (primary) with OpenAI fallback.
Supports self-hosted embeddings (nomic-embed-text, 768d) and legacy OpenAI (1536d).
"""
from typing import List, Dict, Optional
import os
import json
import time
from pathlib import Path
import requests
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates embeddings for document chunks using Ollama (primary) or OpenAI (legacy)."""

    # OpenAI pricing per 1M tokens (as of 2025) - only used for legacy functions
    MODEL_PRICING = {
        "text-embedding-3-small": 0.02,
        "text-embedding-3-large": 0.13,
        "text-embedding-ada-002": 0.10,
    }

    def __init__(self, base_url: str = None, model: str = "nomic-embed-text"):
        """
        Initialize with Ollama as primary embedding service.

        Args:
            base_url: Ollama API URL (default: http://host.docker.internal:11434)
            model: Ollama model name (default: nomic-embed-text)
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.model = model

        # Verify Ollama is accessible
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            logger.info(f"Initialized EmbeddingService with Ollama model: {model} at {self.base_url}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not connect to Ollama at {self.base_url}: {e}")
            logger.warning("Embeddings will fail until Ollama is accessible")

    # ============================================================================
    # OLLAMA API (primary embedding method)
    # ============================================================================

    def embed_chunks(self, texts: List[str], max_workers: int = None) -> tuple[List[Optional[List[float]]], float]:
        """
        Generate embeddings using Ollama (primary method) with optional parallel processing.

        Args:
            texts: List of text strings to embed
            max_workers: Number of concurrent embedding requests (default: None = sequential)
                        Set to 4-8 if OLLAMA_NUM_PARALLEL is configured appropriately

        Returns:
            tuple: (embeddings, cost) where:
                - embeddings: List of embedding vectors (None for failures)
                - cost: Always 0.0 for Ollama (self-hosted)
        """
        if not texts:
            return [], 0.0
        
        all_embeddings = []
        for text in texts:
            try:
                response = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=30
                )
                response.raise_for_status()
                all_embeddings.append(response.json()["embedding"])
                # logger.debug(f"successfully embedded {text[:100]}")
                # time.sleep(0.1)

            except requests.exceptions.HTTPError as e:
                logger.error(f"Embedding HTTP error: {e}")
                logger.error(f"Response status: {response.status_code}")
                logger.error(f"Response body: {response.text}")  
                logger.error(f"Failed embedding text: {text}")
                all_embeddings.append(None)
            except Exception as e:
                logger.error(f"Embedding failed: {e}", exc_info=True)
                all_embeddings.append(None)
                
        return all_embeddings, 0.0

        # Sequential processing by default (safest for Ollama)
        if max_workers is None or max_workers == 1:
            logger.debug(f"Embedding {len(texts)} texts using Ollama (sequential)")
            all_embeddings = []
            for i, text in enumerate(texts):
                max_retries = 3
                retry_count = 0
                embedding = None

                while retry_count < max_retries and embedding is None:
                    try:
                        response = requests.post(
                            f"{self.base_url}/api/embeddings",
                            json={"model": self.model, "prompt": text},
                            timeout=30
                        )
                        response.raise_for_status()
                        embedding = response.json()["embedding"]
                        all_embeddings.append(embedding)

                        # Add small delay to prevent overwhelming Ollama
                        time.sleep(0.1)
                        break  # Success, exit retry loop

                    except requests.exceptions.HTTPError as e:
                        retry_count += 1
                        if retry_count == 1:  # Only log first failure
                            logger.warning(f"Text {i+1}/{len(texts)} failed (attempt {retry_count}/{max_retries}): {e}")
                            try:
                                logger.debug(f"Response body: {response.text[:500]}")
                            except:
                                pass

                        if retry_count < max_retries:
                            time.sleep(0.5 * retry_count)  # Exponential backoff
                        else:
                            logger.error(f"Text {i+1}/{len(texts)} failed after {max_retries} attempts")
                            all_embeddings.append(None)

                    except Exception as e:
                        retry_count += 1
                        if retry_count == 1:
                            logger.warning(f"Text {i+1}/{len(texts)} exception (attempt {retry_count}/{max_retries}): {e}")

                        if retry_count < max_retries:
                            time.sleep(0.5 * retry_count)
                        else:
                            logger.error(f"Text {i+1}/{len(texts)} failed after {max_retries} attempts: {e}")
                            all_embeddings.append(None)
        else:
            # Parallel embedding with ThreadPoolExecutor
            import concurrent.futures
            logger.debug(f"Embedding {len(texts)} texts using Ollama with {max_workers} workers")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                all_embeddings = list(executor.map(self.embed_single, texts))

        failed_count = sum(1 for emb in all_embeddings if emb is None)
        successful = len(texts) - failed_count

        logger.info(f"Generated {successful}/{len(texts)} embeddings (768 dimensions, $0 cost)")

        return all_embeddings, 0.0

    def embed_single(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text (used for queries).

        Args:
            text: Text string to embed

        Returns:
            Embedding vector or None if failed
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30
            )
            response.raise_for_status()
            return response.json()["embedding"]

        except requests.exceptions.HTTPError as e:
            logger.error(f"Embedding HTTP error: {e}")
            logger.error(f"Response status: {response.status_code}")
            logger.error(f"Response body: {response.text[:1000]}")  # First 1000 chars
            return None
        except Exception as e:
            logger.error(f"Embedding failed: {e}", exc_info=True)
            return None

    # ============================================================================
    # LEGACY: OPENAI API (deprecated, kept for reference)
    # ============================================================================

    def embed_chunks_openai(self, texts: List[str], api_key: str, model: str = "text-embedding-3-small", batch_size: int = 100) -> tuple[List[Optional[List[float]]], float]:
        """
        DEPRECATED: Generate embeddings using OpenAI API.
        Use embed_chunks() for Ollama instead.

        Args:
            texts: List of text strings to embed
            api_key: OpenAI API key
            model: OpenAI model name
            batch_size: Number of texts per API call

        Returns:
            tuple: (embeddings, cost)
        """
        if not texts:
            return [], 0.0

        client = OpenAI(api_key=api_key)
        price_per_million = self.MODEL_PRICING.get(model, 0.02)

        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        total_tokens = 0

        logger.debug(f"Embedding {len(texts)} texts in {total_batches} batches (OpenAI)")

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(texts))
            batch = texts[start_idx:end_idx]

            try:
                response = client.embeddings.create(input=batch, model=model)
                all_embeddings.extend([item.embedding for item in response.data])
                total_tokens += response.usage.total_tokens

            except Exception as e:
                logger.error(f"Batch {batch_num + 1}/{total_batches} failed: {e}")
                all_embeddings.extend([None] * len(batch))

            if batch_num < total_batches - 1:
                time.sleep(0.05)

        successful = sum(1 for emb in all_embeddings if emb is not None)
        cost = (total_tokens / 1_000_000) * price_per_million

        logger.debug(f"Generated {successful}/{len(all_embeddings)} embeddings")
        logger.info(f"Model: {model} | Tokens: {total_tokens:,} | Cost: ${cost:.4f}")

        return all_embeddings, cost

    # ============================================================================
    # LEGACY: OPENAI BATCH API (async, 50% cheaper)
    # ============================================================================

    def submit_batch_embed_openai(self, chunks: List[Dict], api_key: str, model: str = "text-embedding-3-small", output_path: str = None) -> str:
        """
        DEPRECATED: Submit chunks to OpenAI Batch API.
        Ollama does not support batch API.

        Args:
            chunks: List of dicts with 'document_chunk_id' and 'embedding_text'
            api_key: OpenAI API key
            model: OpenAI model name
            output_path: Path to save batch JSONL file

        Returns:
            batch_id: OpenAI batch job ID
        """
        client = OpenAI(api_key=api_key)

        # Validate required fields
        required = ['document_chunk_id', 'embedding_text']
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
                custom_id = f"chunk_{chunk['document_chunk_id']}"
                request = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/embeddings",
                    "body": {"model": model, "input": chunk["embedding_text"]}
                }
                f.write(json.dumps(request) + '\n')

        # Upload and submit
        with open(output_file, 'rb') as f:
            batch_input_file = client.files.create(file=f, purpose="batch")

        batch = client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/embeddings",
            completion_window="24h"
        )

        logger.info(f"Submitted batch {batch.id} with {len(chunks)} chunks")
        return batch.id

    def get_batch_embed_openai(self, batch_id: str, api_key: str, model: str = "text-embedding-3-small", chunks: List[Dict] = None, output_path: str = None):
        """
        DEPRECATED: Check batch status or retrieve completed batch results.
        Ollama does not support batch API.

        Args:
            batch_id: OpenAI batch job ID
            api_key: OpenAI API key
            model: OpenAI model name
            chunks: List of chunks to populate with embeddings
            output_path: Path to save results JSONL file

        Returns:
            Status dict or chunks with embeddings
        """
        client = OpenAI(api_key=api_key)
        price_per_million = self.MODEL_PRICING.get(model, 0.02)

        batch = client.batches.retrieve(batch_id)

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

        file_response = client.files.content(batch.output_file_id)
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
            custom_id = f"chunk_{chunk['document_chunk_id']}"
            chunk["embedding"] = results.get(custom_id)

        successful = sum(1 for c in chunks if c.get("embedding") is not None)

        # Calculate cost (Batch API: 50% discount)
        batch_price = price_per_million * 0.5
        cost = (total_tokens / 1_000_000) * batch_price

        logger.info(f"Completed batch {batch_id}: {successful}/{len(chunks)} chunks embedded")
        logger.info(f"Model: {model} | Tokens: {total_tokens:,} | Cost: ${cost:.4f} (50% batch discount)")

        return chunks


