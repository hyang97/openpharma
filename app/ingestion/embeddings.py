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

        if max_workers is None or max_workers == 1:
            # Sequential processing (safest for Ollama)
            logger.debug(f"Embedding {len(texts)} texts using Ollama (sequential)")
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
       