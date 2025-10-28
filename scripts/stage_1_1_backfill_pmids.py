"""
Stage 1.1: Backfill PMIDs for historical papers.

Queries papers with pmid IS NULL and fetches PMIDs from NCBI API.
PMIDs are needed to JOIN with icite_metadata table for citation filtering.
"""
import argparse
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.ingestion.citation_utils import CitationUtils
from app.logging_config import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)


def main():
    """Backfill PMIDs for papers with pmid IS NULL."""

    parser = argparse.ArgumentParser(
        description="Backfill PMIDs for papers in database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with 1000 papers
  python -m scripts.stage_1_1_backfill_pmids --limit 1000

  # Ramp up to 50K papers
  python -m scripts.stage_1_1_backfill_pmids --limit 50000

  # Process all papers (no limit)
  python -m scripts.stage_1_1_backfill_pmids

Note: Progress is automatically resumable - script queries 'pmid IS NULL' each time.
        """
    )

    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of papers to process (default: all papers with pmid IS NULL)")

    args = parser.parse_args()

    # Archive old log if it exists
    old_log = Path("logs/stage_1_1_backfill_pmids.log")
    if old_log.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_log.rename(f"logs/stage_1_1_backfill_pmids_{timestamp}.log")

    setup_logging(level="INFO", log_file="logs/stage_1_1_backfill_pmids.log")

    with Session(engine) as session:
        citation_utils = CitationUtils(session)

        # Get total count of papers needing PMIDs
        total_count = session.execute(text("""
            SELECT COUNT(*) FROM pubmed_papers WHERE pmid IS NULL
        """)).scalar()

        logger.info(f"Starting PMID backfill")
        logger.info(f"Papers needing PMIDs: {total_count:,}")
        logger.info(f"Limit: {args.limit:,} papers" if args.limit else f"Limit: None (processing all {total_count:,} papers)")
        logger.info(f"Note: Citation metrics will be queried via JOIN with icite_metadata (not stored)\n")

        # Query papers with NULL pmid
        query = "SELECT pmc_id FROM pubmed_papers WHERE pmid IS NULL"
        if args.limit:
            query += f" LIMIT {args.limit}"

        result = session.execute(text(query))
        pmc_ids = [row.pmc_id for row in result.fetchall()]

        if not pmc_ids:
            logger.info("No papers to process\n")
            return

        logger.info(f"Processing {len(pmc_ids):,} papers\n")

        # Populate PMIDs (internally batches 200 at a time with API calls)
        rows_with_pmid = citation_utils.populate_pmids(pmc_ids)

        logger.info(f"\nBackfill complete:")
        logger.info(f"  Total processed: {len(pmc_ids):,} papers")
        logger.info(f"  With PMID: {rows_with_pmid:,} papers")
        logger.info(f"  Without PMID: {len(pmc_ids) - rows_with_pmid:,} papers")
        logger.info(f"\nCitation filtering: Use filter_by_metrics() which JOINs with icite_metadata table")


if __name__ == "__main__":
    main()
