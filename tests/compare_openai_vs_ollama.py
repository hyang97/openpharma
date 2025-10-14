"""
Compare OpenAI embeddings vs Ollama nomic-embed-text.
Tests performance and quality for RAG use case.
"""

import os
import sys
import time
import requests
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger
from openai import OpenAI

setup_logging(level="INFO")
logger = get_logger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

# Sample diabetes texts
TEST_TEXTS = [
    "Insulin therapy is essential for type 1 diabetes management and advanced type 2 diabetes.",
    "Blood glucose monitoring helps patients track their diabetes control throughout the day.",
    "Metformin is the first-line oral medication for type 2 diabetes treatment.",
    "Diabetic retinopathy is a serious eye complication that can lead to vision loss.",
    "Regular exercise and healthy diet are key lifestyle interventions for diabetes prevention.",
]


def get_openai_embedding(text: str, client: OpenAI):
    """Get embedding from OpenAI."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def get_ollama_embedding(text: str):
    """Get embedding from Ollama nomic-embed-text."""
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    return response.json()["embedding"]


def calculate_similarity(emb1, emb2):
    """Calculate cosine similarity."""
    emb1 = np.array(emb1)
    emb2 = np.array(emb2)
    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))


def main():
    logger.info("=" * 80)
    logger.info("OPENAI VS OLLAMA EMBEDDING COMPARISON")
    logger.info("=" * 80)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Test OpenAI
    logger.info("\n" + "=" * 80)
    logger.info("OPENAI text-embedding-3-small")
    logger.info("=" * 80)

    openai_times = []
    openai_embeddings = []

    for text in TEST_TEXTS:
        start = time.time()
        emb = get_openai_embedding(text, client)
        elapsed = (time.time() - start) * 1000
        openai_times.append(elapsed)
        openai_embeddings.append(emb)

    openai_avg = sum(openai_times) / len(openai_times)
    logger.info(f"Dimensions: 1536")
    logger.info(f"Avg time per embedding: {openai_avg:.1f}ms")
    logger.info(f"Cost per query: ~$0.00001")

    # Test Ollama
    logger.info("\n" + "=" * 80)
    logger.info("OLLAMA nomic-embed-text (local)")
    logger.info("=" * 80)

    ollama_times = []
    ollama_embeddings = []

    for text in TEST_TEXTS:
        start = time.time()
        emb = get_ollama_embedding(text)
        elapsed = (time.time() - start) * 1000
        ollama_times.append(elapsed)
        ollama_embeddings.append(emb)

    ollama_avg = sum(ollama_times) / len(ollama_times)
    logger.info(f"Dimensions: 768")
    logger.info(f"Avg time per embedding: {ollama_avg:.1f}ms")
    logger.info(f"Cost per query: $0 (self-hosted)")

    # Performance comparison
    logger.info("\n" + "=" * 80)
    logger.info("PERFORMANCE COMPARISON")
    logger.info("=" * 80)

    speedup = openai_avg / ollama_avg
    logger.info(f"\nOpenAI:  {openai_avg:>6.1f}ms")
    logger.info(f"Ollama:  {ollama_avg:>6.1f}ms")
    logger.info(f"Speedup: {speedup:>6.1f}x {'(Ollama faster)' if speedup > 1 else '(OpenAI faster)'}")

    # Quality comparison
    logger.info("\n" + "=" * 80)
    logger.info("SEMANTIC QUALITY TEST")
    logger.info("=" * 80)
    logger.info("\nTesting if models cluster similar texts correctly...")
    logger.info(f"Text 0 (insulin): {TEST_TEXTS[0][:60]}...")
    logger.info(f"Text 1 (glucose): {TEST_TEXTS[1][:60]}...")
    logger.info(f"Text 4 (lifestyle): {TEST_TEXTS[4][:60]}...")
    logger.info("\nExpected: insulin more similar to glucose than to lifestyle")

    # OpenAI similarities
    openai_sim_0_1 = calculate_similarity(openai_embeddings[0], openai_embeddings[1])
    openai_sim_0_4 = calculate_similarity(openai_embeddings[0], openai_embeddings[4])

    logger.info(f"\nOpenAI:")
    logger.info(f"  Insulin ↔ Glucose:   {openai_sim_0_1:.3f}")
    logger.info(f"  Insulin ↔ Lifestyle: {openai_sim_0_4:.3f}")
    logger.info(f"  {'✓ Correct clustering' if openai_sim_0_1 > openai_sim_0_4 else '✗ Poor clustering'}")

    # Ollama similarities
    ollama_sim_0_1 = calculate_similarity(ollama_embeddings[0], ollama_embeddings[1])
    ollama_sim_0_4 = calculate_similarity(ollama_embeddings[0], ollama_embeddings[4])

    logger.info(f"\nOllama:")
    logger.info(f"  Insulin ↔ Glucose:   {ollama_sim_0_1:.3f}")
    logger.info(f"  Insulin ↔ Lifestyle: {ollama_sim_0_4:.3f}")
    logger.info(f"  {'✓ Correct clustering' if ollama_sim_0_1 > ollama_sim_0_4 else '✗ Poor clustering'}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("DECISION MATRIX")
    logger.info("=" * 80)

    logger.info("\nOpenAI text-embedding-3-small (1536d):")
    logger.info(f"  ✓ Current setup - already embedded 203K chunks ($2 spent)")
    logger.info(f"  ✓ High quality embeddings")
    logger.info(f"  ✓ No re-embedding needed")
    logger.info(f"  ✗ ~{openai_avg:.0f}ms per query (API latency)")
    logger.info(f"  ✗ ~$0.00001 per query (negligible but adds up)")
    logger.info(f"  ✗ Requires internet")

    logger.info("\nOllama nomic-embed-text (768d):")
    logger.info(f"  ✓ ~{ollama_avg:.0f}ms per query (faster)" if ollama_avg < openai_avg else f"  ✗ ~{ollama_avg:.0f}ms per query (slower)")
    logger.info(f"  ✓ $0 per query (self-hosted)")
    logger.info(f"  ✓ Works offline")
    logger.info(f"  ✗ Must re-embed all 1.8M chunks (~2-3 hours)")
    logger.info(f"  ✗ Need to rebuild HNSW index with 768d")
    logger.info(f"  ✗ Lose $2 of OpenAI embeddings")

    logger.info("\n" + "=" * 80)
    logger.info("RECOMMENDATION")
    logger.info("=" * 80)

    if ollama_avg < openai_avg * 0.5:
        logger.info("\nOllama is significantly faster - consider switching!")
    elif ollama_avg < openai_avg:
        logger.info("\nOllama is slightly faster but OpenAI quality may be worth the cost.")
    else:
        logger.info("\nOpenAI is faster - keep current setup unless cost is a concern.")

    logger.info("\nIf switching to Ollama:")
    logger.info("  1. Update schema: VECTOR(1536) → VECTOR(768)")
    logger.info("  2. Truncate document_chunks table")
    logger.info("  3. Re-chunk all documents (Stage 3)")
    logger.info("  4. Re-embed with nomic-embed-text (Stage 4)")
    logger.info("  5. Rebuild HNSW index")
    logger.info(f"  6. Est. time: ~2-3 hours for 1.8M chunks at {ollama_avg:.0f}ms/chunk")


if __name__ == "__main__":
    main()
