"""
Backfill citation data for existing pubmed_papers.
"""
import logging
from app.db.database import engine
from app.db.models import PubMedPaper
from app.ingestion.citation_utils import CitationUtils
from sqlalchemy import text
from sqlalchemy.orm import Session

# Configuration
BATCH_SIZE = 10000  # How many papers to process per run

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print(f"Starting citation data backfill (batch size: {BATCH_SIZE})...\n")

with Session(engine) as session:
    citation_utils = CitationUtils(session)

    # Step 1: Check how many papers need PMIDs
    papers_without_pmid = session.query(PubMedPaper).filter(
        PubMedPaper.pmid.is_(None)
    ).count()
    print(f"Papers without PMID: {papers_without_pmid}")

    if papers_without_pmid > 0:
        # Get PMC IDs that need PMIDs
        papers = session.query(PubMedPaper).filter(
            PubMedPaper.pmid.is_(None)
        ).limit(BATCH_SIZE).all()

        pmc_ids = [p.pmc_id for p in papers]
        print(f"\nPopulating PMIDs for {len(pmc_ids)} papers...")

        count = citation_utils.populate_pmids(pmc_ids)
        print(f"✓ Updated {count} rows with PMIDs\n")

    # Step 2: Populate citation metrics
    print("Populating citation metrics...")

    # Count before update
    before_counts = session.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE nih_percentile >= 0) as with_data,
            COUNT(*) FILTER (WHERE nih_percentile = -1) as marked_no_data,
            COUNT(*) FILTER (WHERE nih_percentile IS NULL AND pmid IS NOT NULL AND pmid > 0) as ready_to_update
        FROM pubmed_papers
    """)).fetchone()

    count = citation_utils.populate_citation_metrics(max_update=BATCH_SIZE)
    print(f"✓ Updated {count} rows with citation metrics")

    # Count after update
    after_counts = session.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE nih_percentile >= 0) as with_data,
            COUNT(*) FILTER (WHERE nih_percentile = -1) as marked_no_data,
            COUNT(*) FILTER (WHERE nih_percentile IS NULL AND pmid IS NOT NULL AND pmid > 0) as ready_to_update
        FROM pubmed_papers
    """)).fetchone()

    # Show breakdown
    print("\nVerification:")
    print(f"  Papers with citation data (nih_percentile >= 0): {before_counts.with_data} → {after_counts.with_data} (+{after_counts.with_data - before_counts.with_data})")
    print(f"  Papers marked with -1 (no data in iCite):       {before_counts.marked_no_data} → {after_counts.marked_no_data} (+{after_counts.marked_no_data - before_counts.marked_no_data})")
    print(f"  Papers ready to update (NULL, has PMID):         {before_counts.ready_to_update} → {after_counts.ready_to_update} ({after_counts.ready_to_update - before_counts.ready_to_update})")
    print(f"  Total updated: {(after_counts.with_data - before_counts.with_data) + (after_counts.marked_no_data - before_counts.marked_no_data)}")

print("\n✓ Backfill complete!")
