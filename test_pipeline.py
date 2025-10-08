"""Test ingestion pipeline - step by step."""
import os
from dotenv import load_dotenv
from app.ingestion.pubmed_fetcher import PubMedFetcher
from app.ingestion.chunker import DocumentChunker
from app.ingestion.embeddings import EmbeddingService
from app.logging_config import setup_logging

load_dotenv()
setup_logging(level="INFO")

# ============================================================================
# STEP 1: FETCH
# ============================================================================

fetcher = PubMedFetcher()

print("Searching for diabetes papers...")
pmc_ids = fetcher.search_diabetes_papers(max_results=10)
print(f"Found {len(pmc_ids)} papers: {pmc_ids}")

print("\nFetching first paper with full content...")
paper = None
for pmc_id in pmc_ids:
    print(f"\n--- PMC{pmc_id} ---")
    paper = fetcher.fetch_paper_details(pmc_id)

    print(f"Title: {paper['title'][:80]}...")
    print(f"Abstract: {len(paper.get('abstract', ''))} chars")
    print(f"Sections: {len(paper.get('sections', {}))}")
    print(f"Journal: {paper['metadata'].get('journal', 'N/A')}")
    print(f"Pub date: {paper['metadata'].get('pub_date', 'N/A')}")

    # Stop at first paper with actual content
    if len(paper.get('sections', {})) > 0:
        print(f"\n✓ Found paper with content! Using PMC{pmc_id}")
        print(f"Section names: {list(paper.get('sections', {}).keys())}")
        break

# ============================================================================
# STEP 2: EXAMINE PARSED CONTENT
# ============================================================================

if paper and paper.get('sections'):
    print("\n" + "="*80)
    print("EXAMINING PARSED CONTENT")
    print("="*80)

    # Show first section to check for tables
    first_section = list(paper['sections'].keys())[0]
    first_content = paper['sections'][first_section]

    print(f"\nFirst section: {first_section}")
    print(f"Content length: {len(first_content)} chars")
    print(f"\nFirst 500 chars:")
    print(first_content[:500])

    # Check if any section contains markdown tables
    has_tables = any('|' in content for content in paper['sections'].values())
    print(f"\n✓ Tables detected: {has_tables}")

    if has_tables:
        for section_name, content in paper['sections'].items():
            if '|' in content:
                print(f"\nSection '{section_name}' contains table(s)")

                # Look for caption (bold text before table)
                table_start = content.index('|')
                snippet_start = max(0, table_start - 200)

                # Check for bold caption pattern (**...**)
                pre_table = content[snippet_start:table_start]
                if '**' in pre_table:
                    caption_start = pre_table.rfind('**')
                    caption_end = pre_table.find('**', caption_start + 2)
                    if caption_end != -1:
                        caption = pre_table[caption_start:caption_end+2]
                        print(f"Caption found: {caption}")

                # Show table snippet
                snippet_end = min(len(content), table_start + 600)
                print(f"\nTable snippet:\n{content[snippet_start:snippet_end]}")
                print("\n" + "-"*80)
                break

# ============================================================================
# STEP 3: CHUNK
# ============================================================================

if paper and paper.get('sections'):
    print("\n" + "="*80)
    print("CHUNKING DOCUMENT")
    print("="*80)

    chunker = DocumentChunker()
    chunks = chunker.chunk_document(paper)

    print(f"\nTotal chunks created: {len(chunks)}")
    print(f"Document title: {paper['title'][:60]}...")

    # Show first chunk details
    if chunks:
        first_chunk = chunks[0]
        print(f"\n--- First Chunk ---")
        print(f"Section: {first_chunk['section']}")
        print(f"Chunk index: {first_chunk['chunk_index']}")
        print(f"Token count: {first_chunk['token_count']}")
        print(f"Char range: {first_chunk['char_start']}-{first_chunk['char_end']}")
        print(f"\nContent (first 300 chars):\n{first_chunk['content'][:300]}...")
        print(f"\nEmbedding text (first 300 chars):\n{first_chunk['embedding_text'][:300]}...")

    # Show chunk distribution by section
    from collections import Counter
    section_counts = Counter(chunk['section'] for chunk in chunks)
    print(f"\n--- Chunks by Section ---")
    for section, count in section_counts.items():
        print(f"{section}: {count} chunks")

    # Validate chunking correctness
    print(f"\n--- Validation Checks ---")

    # Check 1: All token counts within limit
    max_tokens = max(chunk['token_count'] for chunk in chunks)
    oversized = [i for i, c in enumerate(chunks) if c['token_count'] > 512]
    print(f"✓ Max tokens: {max_tokens} (limit: 512)")
    if oversized:
        print(f"✗ WARNING: {len(oversized)} chunks exceed 512 tokens")

    # Check 2: Embedding text format
    sample_emb = chunks[0]['embedding_text']
    has_doc_prefix = sample_emb.startswith("Document:")
    has_section_prefix = "\nSection:" in sample_emb
    print(f"✓ Embedding text has 'Document:' prefix: {has_doc_prefix}")
    print(f"✓ Embedding text has 'Section:' prefix: {has_section_prefix}")

    # Check 3: Content matches source section
    first_section = chunks[0]['section']
    if first_section in paper['sections']:
        source_text = paper['sections'][first_section]
        chunk_content = chunks[0]['content']
        content_in_source = chunk_content[:50] in source_text
        print(f"✓ Chunk content found in source section: {content_in_source}")

    # Check 4: No missing chunks (check chunk_index sequence)
    chunk_indices = [c['chunk_index'] for c in chunks]
    expected_indices = list(range(len(chunks)))
    indices_correct = chunk_indices == expected_indices
    print(f"✓ Chunk indices sequential (0 to {len(chunks)-1}): {indices_correct}")

# ============================================================================
# STEP 4: EMBED
# ============================================================================

if chunks:
    print("\n" + "="*80)
    print("EMBEDDING CHUNKS")
    print("="*80)

    embedder = EmbeddingService()

    # Add required fields for embedding
    for chunk in chunks:
        chunk['source'] = 'pubmed'
        chunk['source_id'] = paper['metadata']['pmc_id']

    # Extract embedding texts
    texts = [chunk['embedding_text'] for chunk in chunks]

    print(f"\nEmbedding {len(texts)} chunks using Regular API...")
    embeddings = embedder.embed_chunks(texts)

    # Add embeddings back to chunks
    for chunk, emb in zip(chunks, embeddings):
        chunk['embedding'] = emb

    # Validate embeddings
    print(f"\n--- Embedding Validation ---")
    successful = sum(1 for emb in embeddings if emb is not None)
    failed = sum(1 for emb in embeddings if emb is None)

    print(f"✓ Successful: {successful}/{len(embeddings)}")
    if failed > 0:
        print(f"✗ Failed: {failed}")

    # Check embedding dimensions
    if embeddings[0] is not None:
        dim = len(embeddings[0])
        print(f"✓ Embedding dimensions: {dim} (expected: 1536)")

    print("\n" + "="*80)
    print("PIPELINE TEST COMPLETE")
    print("="*80)
    print(f"\nSummary:")
    print(f"- Fetched: 1 paper (PMC{paper['metadata']['pmc_id']})")
    print(f"- Parsed: {len(paper['sections'])} sections")
    print(f"- Chunked: {len(chunks)} chunks")
    print(f"- Embedded: {successful} chunks")
    print(f"\nReady for database insertion!")
