"""
Stage 1: Collect PMC IDs from PubMed searches.

Searches PubMed for diabetes research papers and stores PMC IDs
in the pubmed_papers table for later fetching.
"""
import argparse
import logging
from datetime import datetime
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
  # Check how many papers match a query (without collecting)
  python -m scripts.stage_1_collect_ids --counts-only --query "obesity[MeSH] AND open access[filter]"

  # Collect 50 diabetes papers
  python -m scripts.stage_1_collect_ids --limit 50

  # Collect all oncology papers from 2023-2024
  python -m scripts.stage_1_collect_ids --keyword cancer --start-date 2023-01-01 --end-date 2024-12-31

  # Find papers updated in February 2025
  python -m scripts.stage_1_collect_ids --start-date 2025-02-01 --end-date 2025-02-28 --date-field lr

  # Use custom query for specific publication types (e.g., meta-analyses, reviews)
  python -m scripts.stage_1_collect_ids --query "diabetes[MeSH] AND meta-analysis[ptyp] AND open access[filter]"

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
    parser.add_argument("--reset-fetched", action="store_true",
                       help="Reset already-fetched papers to pending (default: skip already-fetched papers)")
    parser.add_argument("--fetch-status", type=str, default="wont_fetch", choices=["pending", "wont_fetch"],
                       help="Initial fetch status for collected papers (default: wont_fetch)")
    parser.add_argument("--counts-only", action="store_true",
                       help="Only report result count, don't collect or store PMC IDs")

    args = parser.parse_args()

    # Archive old log if it exists
    from pathlib import Path
    old_log = Path("logs/stage_1_collect_ids.log")
    if old_log.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_log.rename(f"logs/stage_1_collect_ids_{timestamp}.log")

    # Always log to the same active file
    setup_logging(level="INFO", log_file="logs/stage_1_collect_ids.log")

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

    # Log search to history file
    from pathlib import Path
    history_file = Path("logs/search_history.log")
    history_file.parent.mkdir(parents=True, exist_ok=True)

    with open(history_file, "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mode = "counts-only" if args.counts_only else f"limit: {args.limit or 'all'}"
        f.write(f"{timestamp} | Query: {query} | Mode: {mode}\n")

    # Search PubMed with pagination
    limit = args.limit
    fetcher = PubMedFetcher()

    # If counts-only mode, just get the count and exit
    if args.counts_only:
        result = fetcher.search_papers(query=query, counts_only=True)
        total_count = int(result[0])
        logger.info(f"\nTotal matching papers: {total_count:,}\n")

        with open(history_file, "a") as f:
            f.write(f"         → Result: {total_count:,} total papers\n\n")

        return

    api_max = 10000  # NCBI's per-request limit

    total_collected = 0
    result_start_idx = 0
    batch_num = 1

    with Session(engine) as session:
        while True:
            # How many to request this batch?
            num_to_request = api_max

            if limit is not None:
                num_remaining = limit - total_collected
                if num_remaining <= 0:
                    break
                elif num_remaining < num_to_request:
                    num_to_request = num_remaining

            # Fetch batch from NCBI
            logger.info(f"Fetching batch {batch_num} (requesting {num_to_request} PMC IDs, start index: {result_start_idx})")
            batch_pmc_ids = fetcher.search_papers(query=query, max_results=num_to_request, start_index=result_start_idx)
            result_start_idx += len(batch_pmc_ids)
            logger.info(f"Batch {batch_num} complete: got {len(batch_pmc_ids)} PMC IDs")

            # Insert batch into database (bulk insert)
            if batch_pmc_ids:
                values = [{"pmc_id": pmc_id, "fetch_status": args.fetch_status} for pmc_id in batch_pmc_ids]

                if args.reset_fetched:
                    # Reset all papers to specified fetch status (even if already fetched)
                    stmt = insert(PubMedPaper).values(values).on_conflict_do_update(
                        index_elements=['pmc_id'],
                        set_={'fetch_status': args.fetch_status}
                    )
                else:
                    # Skip papers that already exist (do nothing on conflict)
                    stmt = insert(PubMedPaper).values(values).on_conflict_do_nothing(index_elements=['pmc_id'])

                session.execute(stmt)
                session.commit()

                total_collected += len(batch_pmc_ids)
                logger.info(f"  → Inserted {len(batch_pmc_ids)} PMC IDs into database (total: {total_collected})\n")

            # Stop if we got fewer than requested (end of results)
            if len(batch_pmc_ids) < num_to_request:
                logger.info(f"Reached end of results (got {len(batch_pmc_ids)} < {num_to_request} requested)\n")
                break

            batch_num += 1

    logger.info(f"Collected {total_collected} PMC IDs")

    # Append result to search history
    with open(history_file, "a") as f:
        f.write(f"         → Result: {total_collected} PMC IDs collected\n\n")


if __name__ == "__main__":
    main()
