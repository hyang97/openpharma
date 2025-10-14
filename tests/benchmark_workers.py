"""
Quick benchmark to find optimal worker count for Ollama embeddings.
Run: docker-compose exec api python -m tests.benchmark_workers
"""
import time
import concurrent.futures
from app.ingestion.embeddings import EmbeddingService

def test_workers(num_workers, num_embeddings=100):
    """Test embedding speed with different worker counts."""
    service = EmbeddingService()

    # Create test texts
    test_texts = [f"Test document {i} about diabetes treatment and glucose levels" for i in range(num_embeddings)]

    start = time.time()

    # Embed with threading
    if num_workers == 1:
        # Sequential baseline
        embeddings = []
        for text in test_texts:
            emb = service.embed_single(text)
            embeddings.append(emb)
    else:
        # Parallel with ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            embeddings = list(executor.map(service.embed_single, test_texts))

    elapsed = time.time() - start
    successful = sum(1 for e in embeddings if e is not None)

    return elapsed, successful

if __name__ == "__main__":
    print("Benchmarking Ollama embedding concurrency...")
    print("=" * 60)

    num_embeddings = 100
    worker_counts = [1, 4, 8, 16, 32, 64, 128]

    results = []

    for workers in worker_counts:
        print(f"\nTesting {workers} workers...")
        elapsed, successful = test_workers(workers, num_embeddings)

        avg_per_embedding = (elapsed / num_embeddings) * 1000  # ms
        speedup = results[0][1] / elapsed if results else 1.0

        print(f"  Total time: {elapsed:.2f}s")
        print(f"  Avg per embedding: {avg_per_embedding:.1f}ms")
        print(f"  Speedup vs sequential: {speedup:.1f}x")
        print(f"  Success rate: {successful}/{num_embeddings}")

        results.append((workers, elapsed, avg_per_embedding, speedup))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Workers':<10} {'Total Time':<12} {'Avg/Emb':<12} {'Speedup':<10}")
    print("-" * 60)

    for workers, elapsed, avg, speedup in results:
        print(f"{workers:<10} {elapsed:>8.2f}s    {avg:>8.1f}ms    {speedup:>6.1f}x")

    # Find optimal
    best_idx = min(range(len(results)), key=lambda i: results[i][1])
    optimal_workers = results[best_idx][0]

    print("\n" + "=" * 60)
    print(f"RECOMMENDATION: Use {optimal_workers} workers (fastest)")

    # Check for diminishing returns
    if best_idx > 0:
        prev_time = results[best_idx - 1][1]
        best_time = results[best_idx][1]
        improvement = ((prev_time - best_time) / prev_time) * 100

        if improvement < 10:
            conservative = results[best_idx - 1][0]
            print(f"NOTE: {conservative} workers is only {improvement:.1f}% slower")
            print(f"      Consider {conservative} for stability/safety")

    print("=" * 60)
