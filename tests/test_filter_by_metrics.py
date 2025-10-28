"""
Test citation filtering functionality.

Tests filter_by_metrics() which uses JOIN with icite_metadata table.
"""
import logging
from app.db.database import engine
from app.db.models import PubMedPaper
from app.ingestion.citation_utils import CitationUtils
from sqlalchemy import text
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("Testing filter_by_metrics()...\n")

with Session(engine) as session:
    citation_utils = CitationUtils(session)

    # Get a sample of PMC IDs with various citation profiles (using JOIN with icite_metadata)
    sample_papers = session.execute(text("""
        SELECT p.pmc_id, p.pmid, i.nih_percentile, i.year, i.citation_count
        FROM pubmed_papers p
        JOIN icite_metadata i ON p.pmid = i.pmid
        WHERE p.pmid IS NOT NULL AND p.pmid > 0
        LIMIT 1000
    """)).fetchall()

    sample_pmc_ids = [row.pmc_id for row in sample_papers]
    print(f"Test sample: {len(sample_pmc_ids)} PMC IDs\n")

    # Show distribution of sample (query icite_metadata via JOIN)
    sample_stats = session.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE i.nih_percentile >= 0) as with_data,
            COUNT(*) FILTER (WHERE i.nih_percentile IS NULL) as no_data,
            COUNT(*) FILTER (WHERE i.nih_percentile >= 95) as top_5_pct,
            COUNT(*) FILTER (WHERE i.nih_percentile >= 90) as top_10_pct,
            COUNT(*) FILTER (WHERE i.year >= 2023) as recent_2023
        FROM pubmed_papers p
        JOIN icite_metadata i ON p.pmid = i.pmid
        WHERE p.pmc_id = ANY(:pmc_ids)
    """), {"pmc_ids": sample_pmc_ids}).fetchone()

    print(f"Sample distribution (from icite_metadata):")
    print(f"  Total papers: {sample_stats.total}")
    print(f"  With citation data: {sample_stats.with_data}")
    print(f"  Missing data (NULL): {sample_stats.no_data}")
    print(f"  Top 5% (≥95 percentile): {sample_stats.top_5_pct}")
    print(f"  Top 10% (≥90 percentile): {sample_stats.top_10_pct}")
    print(f"  Published 2023+: {sample_stats.recent_2023}\n")

    # Test 1: No filters (should return all papers WITH PMIDs in icite)
    print("=" * 60)
    print("Test 1: No filters (returns all with iCite data)")
    print("=" * 60)
    result = citation_utils.filter_by_metrics(sample_pmc_ids)
    # Sample already filtered to papers in icite_metadata, so should return all
    print(f"Expected: {len(sample_pmc_ids)} papers (all have iCite data)")
    print(f"Got: {len(result)} papers")
    print(f"✓ PASS\n" if len(result) == len(sample_pmc_ids) else f"✗ FAIL\n")

    # Test 2: Filter by top 5% (percentile >= 95)
    print("=" * 60)
    print("Test 2: Top 5% (percentile >= 95)")
    print("=" * 60)
    result = citation_utils.filter_by_metrics(sample_pmc_ids, min_percentile=95)
    print(f"Expected: ~{sample_stats.top_5_pct} papers")
    print(f"Got: {len(result)} papers")
    print(f"✓ PASS\n" if len(result) == sample_stats.top_5_pct else f"✗ FAIL\n")

    # Test 3: Filter by year (2023+)
    print("=" * 60)
    print("Test 3: Recent papers (2023+)")
    print("=" * 60)
    result = citation_utils.filter_by_metrics(sample_pmc_ids, min_year=2023)
    print(f"Expected: ~{sample_stats.recent_2023} papers")
    print(f"Got: {len(result)} papers")
    print(f"✓ PASS\n" if len(result) == sample_stats.recent_2023 else f"✗ FAIL\n")

    # Test 4: Combined filters (top 10% AND 2023+)
    print("=" * 60)
    print("Test 4: Combined filters (top 10% AND 2023+)")
    print("=" * 60)
    result = citation_utils.filter_by_metrics(
        sample_pmc_ids,
        min_percentile=90,
        min_year=2023
    )
    combined_count = session.execute(text("""
        SELECT COUNT(*)
        FROM pubmed_papers p
        JOIN icite_metadata i ON p.pmid = i.pmid
        WHERE p.pmc_id = ANY(:pmc_ids)
        AND i.nih_percentile >= 90
        AND i.year >= 2023
    """), {"pmc_ids": sample_pmc_ids}).scalar()
    print(f"Expected: {combined_count} papers")
    print(f"Got: {len(result)} papers")
    print(f"✓ PASS\n" if len(result) == combined_count else f"✗ FAIL\n")

    # Test 5: Verify only papers with valid metrics in icite_metadata pass through
    print("=" * 60)
    print("Test 5: Verify filtering uses icite_metadata correctly")
    print("=" * 60)
    result = citation_utils.filter_by_metrics(sample_pmc_ids, min_percentile=50)

    # Check that all returned papers have valid citation data in icite_metadata
    result_check = session.execute(text("""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE i.nih_percentile >= 50) as valid,
            COUNT(*) FILTER (WHERE i.nih_percentile IS NULL OR i.nih_percentile < 50) as invalid
        FROM pubmed_papers p
        JOIN icite_metadata i ON p.pmid = i.pmid
        WHERE p.pmc_id = ANY(:pmc_ids)
    """), {"pmc_ids": result}).fetchone()

    print(f"Returned papers: {result_check.total}")
    print(f"  With valid metrics (≥50): {result_check.valid}")
    print(f"  With invalid metrics (NULL or <50): {result_check.invalid}")
    print(f"✓ PASS\n" if result_check.invalid == 0 else f"✗ FAIL - Papers with invalid metrics passed through!\n")

    # Test 6: Filter by citation count (from icite_metadata)
    print("=" * 60)
    print("Test 6: Filter by citation count (≥10)")
    print("=" * 60)
    result = citation_utils.filter_by_metrics(sample_pmc_ids, min_citation_count=10)
    cited_count = session.execute(text("""
        SELECT COUNT(*)
        FROM pubmed_papers p
        JOIN icite_metadata i ON p.pmid = i.pmid
        WHERE p.pmc_id = ANY(:pmc_ids)
        AND i.citation_count >= 10
    """), {"pmc_ids": sample_pmc_ids}).scalar()
    print(f"Expected: {cited_count} papers")
    print(f"Got: {len(result)} papers")
    print(f"✓ PASS\n" if len(result) == cited_count else f"✗ FAIL\n")

print("=" * 60)
print("Test suite complete!")
print("=" * 60)
