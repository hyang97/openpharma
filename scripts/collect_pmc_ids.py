"""
Stage 1: Collect PMC IDs from PubMed searches.

Searches PubMed for diabetes research papers and stores PMC IDs
in the pubmed_papers table for later fetching.
"""
import argparse
import logging
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.database import engine
from app.db.models import PubMedPaper
from app.ingestion.pubmed_fetcher import PubMedFetcher
from app.logging_config import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)


def main():
    """Collect PMC IDs and store in database."""
    parser = argparse.ArgumentParser(
        description="Collect PMC IDs from PubMed and store in database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect 50 diabetes papers
  python -m scripts.collect_pmc_ids --limit 50

  # Collect all oncology papers from 2023-2024
  python -m scripts.collect_pmc_ids --keyword cancer --start-date 2023-01-01 --end-date 2024-12-31

  # Find papers updated in February 2025
  python -m scripts.collect_pmc_ids --start-date 2025-02-01 --end-date 2025-02-28 --date-field lr

  # Use custom query for specific publication types (e.g., meta-analyses, reviews)
  python -m scripts.collect_pmc_ids --query "diabetes[MeSH] AND meta-analysis[ptyp] AND open access[filter]"

Note: Default search filters to open access articles only (full-text available).
For custom queries, always include 'open access[filter]' to ensure full-text availability.
        """
    )

    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of PMC IDs to collect (default: not set, return all results)")
    parser.add_argument("--query", type=str,
                       help="Custom PubMed query string (overrides other search options)")
    parser.add_argument("--keyword", type=str, default="diabetes",
                       help="Search keyword in title/abstract (default: diabetes)")
    parser.add_argument("--start-date", type=str, default="2020-01-01",
                       help="Start date in YYYY-MM-DD format (default: 2020-01-01)")
    parser.add_argument("--end-date", type=str, default="2025-12-31",
                       help="End date in YYYY-MM-DD format (default: 2025-12-31)")
    parser.add_argument("--date-field", type=str, default="pdat", choices=["pdat", "lr", "crdt"],
                       help="Date field to search: pdat=publication date, lr=last revision, crdt=created (default: pdat)")

    args = parser.parse_args()
    setup_logging(level="INFO")

    # Build query
    if args.query:
        query = args.query
    else:
        # Convert dates from YYYY-MM-DD to PubMed format YYYY/MM/DD
        start = args.start_date.replace("-", "/")
        end = args.end_date.replace("-", "/")
        query = (
            f"{args.keyword}[Title/Abstract] AND "
            "open access[filter] AND "
            f"{start}:{end}[{args.date_field}]"
        )

    logger.info(f"Query: {query}\n")

    # Search PubMed with pagination
    limit = args.limit
    fetcher = PubMedFetcher()
    api_max = 10000  # NCBI's per-request limit

    all_pmc_ids = []
    result_start_idx = 0

    batch_num = 1
    while True:
        # How many to request this batch?
        num_to_request = api_max

        if limit is not None:
            num_remaining = limit - len(all_pmc_ids)
            if num_remaining <= 0:
                break
            elif num_remaining < num_to_request:
                num_to_request = num_remaining

        # Fetch batch
        logger.info(f"Fetching batch {batch_num} (requesting {num_to_request} PMC IDs, start index: {result_start_idx})")
        batch = fetcher.search_papers(query=query, max_results=num_to_request, start_index=result_start_idx)
        all_pmc_ids.extend(batch)
        result_start_idx += len(batch)
        logger.info(f"Batch {batch_num} complete: got {len(batch)} PMC IDs (total so far: {len(all_pmc_ids)})\n")

        # Stop if we got fewer than requested (end of results)
        if len(batch) < num_to_request:
            logger.info(f"Reached end of results (got {len(batch)} < {num_to_request} requested)\n")
            break

        batch_num += 1

    # Insert into database (reset to pending if already exists)
    with Session(engine) as session:
        for pmc_id in all_pmc_ids:
            stmt = insert(PubMedPaper).values(pmc_id=pmc_id, fetch_status='pending')
            stmt = stmt.on_conflict_do_update(
                index_elements=['pmc_id'],
                set_={'fetch_status': 'pending'}
            )
            session.execute(stmt)
        session.commit()

    logger.info(f"Collected and inserted {len(all_pmc_ids)} PMC IDs")


if __name__ == "__main__":
    main()
