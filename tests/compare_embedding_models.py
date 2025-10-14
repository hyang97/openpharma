"""
Compare different embedding models for self-hosting.

Tests:
1. OpenAI text-embedding-3-small (current)
2. sentence-transformers models (local CPU)
3. Performance and quality comparison
"""

import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logging_config import setup_logging, get_logger

setup_logging(level="INFO")
logger = get_logger(__name__)

# Sample diabetes-related texts for testing
TEST_TEXTS = [
    "Insulin therapy is essential for type 1 diabetes management and advanced type 2 diabetes.",
    "Blood glucose monitoring helps patients track their diabetes control throughout the day.",
    "Metformin is the first-line oral medication for type 2 diabetes treatment.",
    "Diabetic retinopathy is a serious eye complication that can lead to vision loss.",
    "Regular exercise and healthy diet are key lifestyle interventions for diabetes prevention.",
]


def test_openai_embeddings():
    """Test OpenAI embeddings (current approach)."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        logger.info("\n" + "=" * 80)
        logger.info("OPENAI text-embedding-3-small")
        logger.info("=" * 80)

        times = []
        embeddings = []

        for text in TEST_TEXTS:
            start = time.time()
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            embeddings.append(response.data[0].embedding)

        avg_time = sum(times) / len(times)
        dimensions = len(embeddings[0])

        logger.info(f"Dimensions: {dimensions}")
        logger.info(f"Average time per embedding: {avg_time:.1f}ms")
        logger.info(f"Total time for {len(TEST_TEXTS)} texts: {sum(times):.1f}ms")
        logger.info(f"Cost per query: ~$0.00001")
        logger.info(f"Pros: High quality, no infrastructure")
        logger.info(f"Cons: API latency (~{avg_time:.0f}ms), costs at scale, requires internet")

        return "openai", embeddings, avg_time

    except Exception as e:
        logger.error(f"OpenAI test failed: {e}")
        return None, None, None


def test_sentence_transformers():
    """Test sentence-transformers (local CPU)."""
    try:
        from sentence_transformers import SentenceTransformer

        models_to_test = [
            ("all-MiniLM-L6-v2", 384),      # Fast, small
            ("all-mpnet-base-v2", 768),     # Slower, better quality
            ("paraphrase-MiniLM-L6-v2", 384),  # Alternative
        ]

        results = {}

        for model_name, expected_dims in models_to_test:
            logger.info("\n" + "=" * 80)
            logger.info(f"sentence-transformers: {model_name}")
            logger.info("=" * 80)

            try:
                # Load model
                logger.info("Loading model...")
                load_start = time.time()
                model = SentenceTransformer(model_name)
                load_time = (time.time() - load_start) * 1000
                logger.info(f"Model load time: {load_time:.0f}ms")

                # Warm-up
                _ = model.encode("warm up")

                # Test embeddings
                times = []
                embeddings = []

                for text in TEST_TEXTS:
                    start = time.time()
                    embedding = model.encode(text)
                    elapsed = (time.time() - start) * 1000
                    times.append(elapsed)
                    embeddings.append(embedding.tolist())

                avg_time = sum(times) / len(times)
                dimensions = len(embeddings[0])

                logger.info(f"Dimensions: {dimensions}")
                logger.info(f"Average time per embedding: {avg_time:.1f}ms")
                logger.info(f"Total time for {len(TEST_TEXTS)} texts: {sum(times):.1f}ms")
                logger.info(f"Cost per query: $0 (self-hosted)")
                logger.info(f"Pros: Free, works offline, fast on CPU")
                logger.info(f"Cons: Lower quality than OpenAI, requires re-embedding all docs")

                results[model_name] = (embeddings, avg_time)

            except Exception as e:
                logger.error(f"Failed to test {model_name}: {e}")

        return results

    except ImportError:
        logger.warning("sentence-transformers not installed. Run: pip install sentence-transformers")
        return {}


def calculate_similarity(emb1, emb2):
    """Calculate cosine similarity between two embeddings."""
    emb1 = np.array(emb1)
    emb2 = np.array(emb2)
    return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))


def test_semantic_quality(embeddings_dict):
    """Test semantic quality by checking if similar texts have high similarity."""
    logger.info("\n" + "=" * 80)
    logger.info("SEMANTIC QUALITY TEST")
    logger.info("=" * 80)
    logger.info("\nChecking if similar texts cluster together...")
    logger.info(f"Text 0: {TEST_TEXTS[0][:60]}...")
    logger.info(f"Text 1: {TEST_TEXTS[1][:60]}...")
    logger.info(f"Text 4: {TEST_TEXTS[4][:60]}...")

    for model_name, (embeddings, _) in embeddings_dict.items():
        # Text 0 (insulin) should be more similar to Text 1 (glucose) than Text 4 (exercise)
        sim_0_1 = calculate_similarity(embeddings[0], embeddings[1])
        sim_0_4 = calculate_similarity(embeddings[0], embeddings[4])

        logger.info(f"\n{model_name}:")
        logger.info(f"  Similarity(Text 0, Text 1): {sim_0_1:.3f}")
        logger.info(f"  Similarity(Text 0, Text 4): {sim_0_4:.3f}")

        if sim_0_1 > sim_0_4:
            logger.info(f"  ✓ Correctly clusters similar texts")
        else:
            logger.info(f"  ✗ Poor semantic understanding")


def main():
    """Compare embedding models."""
    logger.info("=" * 80)
    logger.info("EMBEDDING MODEL COMPARISON")
    logger.info("=" * 80)
    logger.info(f"\nTesting with {len(TEST_TEXTS)} sample diabetes texts")

    all_results = {}

    # Test OpenAI
    model_name, embeddings, avg_time = test_openai_embeddings()
    if embeddings:
        all_results["openai-text-embedding-3-small"] = (embeddings, avg_time)

    # Test sentence-transformers
    st_results = test_sentence_transformers()
    all_results.update(st_results)

    # Quality test
    if len(all_results) > 1:
        test_semantic_quality(all_results)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("RECOMMENDATION")
    logger.info("=" * 80)

    if st_results:
        logger.info("\nFor self-hosting, recommended options:")
        logger.info("\n1. all-MiniLM-L6-v2 (384 dimensions)")
        logger.info("   - Fastest local option")
        logger.info("   - Good for prototyping")
        logger.info("   - ~50-100ms per query on CPU")
        logger.info("   - MUST re-embed all 1.8M chunks")

        logger.info("\n2. all-mpnet-base-v2 (768 dimensions)")
        logger.info("   - Better quality than MiniLM")
        logger.info("   - Still reasonably fast")
        logger.info("   - ~100-200ms per query on CPU")
        logger.info("   - MUST re-embed all 1.8M chunks")

        logger.info("\n3. Keep OpenAI for now")
        logger.info("   - Highest quality")
        logger.info("   - Already embedded 203K chunks")
        logger.info("   - $0.00001 per query is negligible")
        logger.info("   - Can switch later if needed")

        logger.info("\nNext steps if switching:")
        logger.info("  1. Choose model (recommend: all-MiniLM-L6-v2 for speed)")
        logger.info("  2. Update embedding dimension in schema (1536 → 384 or 768)")
        logger.info("  3. Re-embed all documents (~2 hours on CPU)")
        logger.info("  4. Update EmbeddingService to use sentence-transformers")
    else:
        logger.info("\nInstall sentence-transformers to test local models:")
        logger.info("  pip install sentence-transformers")


if __name__ == "__main__":
    main()
