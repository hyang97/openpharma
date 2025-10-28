"""
Stage 1.2: Set fetch_status based on citation metrics.

Uses filter_by_metrics() to identify papers matching criteria, then updates fetch_status.
Supports transitions: wont_fetch ↔ pending, failed → pending/wont_fetch
"""
import argparse
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.models import PubMedPaper
from app.ingestion.citation_utils import CitationUtils
from app.logging_config import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)


def main():
    """Filter papers by citation metrics and mark for fetch."""

    parser = argparse.ArgumentParser(
        description="Set fetch_status based on citation metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Select top 1% historical papers for fetch (wont_fetch → pending)
  python -m scripts.stage_1_2_set_fetch_status --from-status wont_fetch --to-status pending --min-percentile 99 --min-year 1990 --max-year 2019

  # Deselect papers (pending → wont_fetch)
  python -m scripts.stage_1_2_set_fetch_status --from-status pending --to-status wont_fetch --min-percentile 95

  # Retry failed papers (failed → pending)
  python -m scripts.stage_1_2_set_fetch_status --from-status failed --to-status pending

  # Clean up failures (failed → wont_fetch)
  python -m scripts.stage_1_2_set_fetch_status --from-status failed --to-status wont_fetch

  # Dry run to preview
  python -m scripts.stage_1_2_set_fetch_status --from-status wont_fetch --to-status pending --min-percentile 99 --dry-run

Note: Both --from-status and --to-status are required.
      Prevents accidental status changes by making transitions explicit.
        """
    )

    parser.add_argument("--min-percentile", type=float, default=None,
                       help="Minimum NIH percentile (e.g., 99 = top 1%%)")
    parser.add_argument("--min-year", type=int, default=None,
                       help="Minimum publication year")
    parser.add_argument("--max-year", type=int, default=None,
                       help="Maximum publication year")
    parser.add_argument("--min-citation-count", type=int, default=None,
                       help="Minimum citation count")
    parser.add_argument("--from-status", type=str, required=True,
                       choices=["pending", "wont_fetch", "failed"],
                       help="Source fetch_status to filter (required)")
    parser.add_argument("--to-status", type=str, required=True,
                       choices=["pending", "wont_fetch"],
                       help="Target fetch_status to set (required)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be selected without updating database")

    args = parser.parse_args()

    # Archive old log if it exists
    old_log = Path("logs/stage_1_2_set_fetch_status.log")
    if old_log.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_log.rename(f"logs/stage_1_2_set_fetch_status_{timestamp}.log")

    setup_logging(level="INFO", log_file="logs/stage_1_2_set_fetch_status.log")

    with Session(engine) as session:
        citation_utils = CitationUtils(session)

        # Get count of papers with specified source status
        candidate_count = session.execute(text("""
            SELECT COUNT(*) FROM pubmed_papers WHERE fetch_status = :from_status
        """), {"from_status": args.from_status}).scalar()

        logger.info(f"Starting citation filtering")
        logger.info(f"Candidate papers (fetch_status='{args.from_status}'): {candidate_count:,}")
        logger.info(f"Target status: '{args.to_status}'")

        has_filters = any([args.min_percentile, args.min_year, args.max_year, args.min_citation_count])
        if has_filters:
            logger.info(f"Filters:")
            if args.min_percentile:
                logger.info(f"  - Min percentile: {args.min_percentile} (top {100-args.min_percentile}%)")
            if args.min_year:
                logger.info(f"  - Min year: {args.min_year}")
            if args.max_year:
                logger.info(f"  - Max year: {args.max_year}")
            if args.min_citation_count:
                logger.info(f"  - Min citation count: {args.min_citation_count}")
        else:
            logger.info(f"Filters: None (will return all papers with iCite data)")
        logger.info("")

        if candidate_count == 0:
            logger.info(f"No candidate papers found with fetch_status='{args.from_status}'")
            return

        # Filter by citation metrics (no PMC IDs passed - uses fetch_status directly)
        filtered_pmc_ids = citation_utils.filter_by_metrics(
            fetch_status=args.from_status,
            min_percentile=args.min_percentile,
            min_year=args.min_year,
            max_year=args.max_year,
            min_citation_count=args.min_citation_count
        )

        logger.info(f"\nFiltering complete:")
        logger.info(f"  Candidate papers: {candidate_count:,}")
        logger.info(f"  Matching criteria: {len(filtered_pmc_ids):,} papers ({len(filtered_pmc_ids)/candidate_count*100:.2f}%)")

        if args.dry_run:
            logger.info(f"\nDRY RUN: Would mark {len(filtered_pmc_ids):,} papers as '{args.to_status}' (no changes made)")
            return

        if not filtered_pmc_ids:
            logger.info("\nNo papers matched criteria - nothing to update")
            return

        # Update fetch_status to target status
        logger.info(f"\nUpdating fetch_status from '{args.from_status}' to '{args.to_status}' for {len(filtered_pmc_ids):,} papers...")
        stmt = update(PubMedPaper).where(
            PubMedPaper.pmc_id.in_(filtered_pmc_ids)
        ).values(fetch_status=args.to_status)

        result = session.execute(stmt)
        session.commit()

        logger.info(f"Updated {result.rowcount:,} papers to fetch_status='{args.to_status}'")

        # Show final breakdown
        final_stats = session.execute(text("""
            SELECT fetch_status, COUNT(*) as count
            FROM pubmed_papers
            GROUP BY fetch_status
            ORDER BY fetch_status
        """)).fetchall()

        logger.info(f"\nFinal fetch_status breakdown:")
        for row in final_stats:
            logger.info(f"  {row.fetch_status}: {row.count:,} papers")


if __name__ == "__main__":
    main()
