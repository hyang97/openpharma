"""
Stage 1.3: Set priority levels for papers in pubmed_papers table.

This script searches PubMed for papers that are non-research articles
(reviews, editorials, letters, comments, errata) and marks them with priority = 0
in the pubmed_papers table. Uses combined MeSH + Title/Abstract strategy for
maximum coverage.

Part of the 4-stage ingestion pipeline:
  Stage 1: Collect PMC IDs
  Stage 1.1: Backfill PMIDs
  Stage 1.2: Set fetch status by citation metrics
  Stage 1.3: Set priority levels (this script)
  Stage 2: Fetch papers
  Stage 3: Chunk papers
  Stage 4: Embed chunks

Usage:
    docker-compose exec api python -m scripts.stage_1_3_set_priority_level [--dry-run]
"""
import argparse
import time
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import engine
from app.ingestion.pubmed_fetcher import PubMedFetcher
from app.logging_config import setup_logging, get_logger

# Initialize logging
setup_logging(level="INFO", log_file="logs/stage_1_3_set_priority_level.log")
logger = get_logger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 1.3: Set priority levels for papers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with default query (non-research diabetes papers)
  python -m scripts.stage_1_3_set_priority_level --priority 0 --dry-run

  # Mark non-research diabetes papers as priority 0
  python -m scripts.stage_1_3_set_priority_level --priority 0

  # Mark high-impact papers as priority 100 with custom query
  python -m scripts.stage_1_3_set_priority_level --priority 100 --query "diabetes[Title/Abstract] AND open access[filter]"

  # Mark oncology papers with priority 50
  python -m scripts.stage_1_3_set_priority_level --priority 50 --query "(cancer[MeSH Terms] OR oncology[Title/Abstract]) AND open access[filter]"
        """
    )
    parser.add_argument(
        "--query",
        type=str,
        default=(
            "(diabetes mellitus[MeSH Terms] OR diabetes[Title/Abstract]) AND "
            "open access[filter] AND "
            "2020/01/01:2025/12/31[pdat] AND "
            "(Review[ptyp] OR Editorial[ptyp] OR Letter[ptyp] OR Comment[ptyp] OR Erratum[ptyp])"
        ),
        help="PubMed query to find papers. Default: non-research diabetes papers (2020-2025)"
    )
    parser.add_argument(
        "--priority",
        type=int,
        required=True,
        choices=[0, 10, 50, 100],
        help="Priority level to set (0=exclude, 10=low, 50=normal, 100=high)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating the database"
    )

    args = parser.parse_args()
    dry_run = args.dry_run
    query = args.query
    priority_level = args.priority

    logger.info("=" * 80)
    logger.info("Stage 1.3: Set Priority Levels")
    logger.info("=" * 80)
    logger.info(f"Query: {query}")
    logger.info(f"Priority level: {priority_level}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("")

    # Step 1: Get count of papers matching query
    fetcher = PubMedFetcher()
    logger.info("Step 1: Getting count of matching papers from PubMed...")
    count_result = fetcher.search_papers(query, counts_only=True)
    total_count = int(count_result[0])
    logger.info(f"Found {total_count:,} papers to mark as priority = {priority_level}")
    logger.info("")

    # Step 2: Fetch all PMC IDs in batches
    logger.info("Step 2: Fetching PMC IDs...")
    batch_size = 10000  # PubMed max retmax
    all_pmc_ids = []

    for start in range(0, total_count, batch_size):
        remaining = total_count - start
        fetch_count = min(batch_size, remaining)

        logger.info(f"  Fetching batch {start:,} to {start + fetch_count:,} ({start + fetch_count}/{total_count})")
        pmc_ids = fetcher.search_papers(query, max_results=fetch_count, start_index=start)
        all_pmc_ids.extend(pmc_ids)

        # Rate limiting
        time.sleep(0.34)  # 3 requests/second

    logger.info(f"Retrieved {len(all_pmc_ids):,} PMC IDs")
    logger.info("")

    # Step 3: Check how many exist in our database
    with Session(engine) as session:
        logger.info("Step 3: Checking which papers exist in our database...")

        stmt = text("""
            SELECT COUNT(*) as count
            FROM pubmed_papers
            WHERE pmc_id = ANY(:pmc_ids)
        """)

        result = session.execute(stmt, {"pmc_ids": all_pmc_ids}).fetchone()
        existing_count = result.count

        logger.info(f"  {existing_count:,} of {len(all_pmc_ids):,} papers exist in our database")
        logger.info("")

    # Step 4: Preview current priorities
    with Session(engine) as session:
        logger.info("Step 4: Current priority distribution for these papers...")

        stmt = text("""
            SELECT
                priority,
                COUNT(*) as count
            FROM pubmed_papers
            WHERE pmc_id = ANY(:pmc_ids)
            GROUP BY priority
            ORDER BY priority DESC
        """)

        results = session.execute(stmt, {"pmc_ids": all_pmc_ids}).fetchall()

        for row in results:
            priority_label = {
                0: "EXCLUDE",
                10: "LOW",
                50: "NORMAL",
                100: "HIGH"
            }.get(row.priority, f"OTHER ({row.priority})")
            logger.info(f"  Priority {row.priority:3d} ({priority_label:8s}): {row.count:,} papers")

        logger.info("")

    # Step 5: Update priorities (or dry run)
    if dry_run:
        logger.info(f"DRY RUN: Would update the following papers to priority = {priority_level}:")
        logger.info(f"  Total papers to update: {existing_count:,}")
        logger.info("")
        logger.info("Run without --dry-run to apply changes")
    else:
        logger.info(f"Step 5: Updating priorities to {priority_level}...")

        with Session(engine) as session:
            stmt = text("""
                UPDATE pubmed_papers
                SET priority = :priority
                WHERE pmc_id = ANY(:pmc_ids)
            """)

            result = session.execute(stmt, {"priority": priority_level, "pmc_ids": all_pmc_ids})
            session.commit()

            logger.info(f"  Updated {result.rowcount:,} papers to priority = {priority_level}")
            logger.info("")

        # Step 6: Show final distribution
        with Session(engine) as session:
            logger.info("Step 6: Final priority distribution for all fetched papers...")

            stmt = text("""
                SELECT
                    priority,
                    COUNT(*) as count
                FROM pubmed_papers
                WHERE fetch_status = 'fetched'
                GROUP BY priority
                ORDER BY priority DESC
            """)

            results = session.execute(stmt).fetchall()

            for row in results:
                priority_label = {
                    0: "EXCLUDE (non-research)",
                    10: "LOW",
                    50: "NORMAL (research)",
                    100: "HIGH"
                }.get(row.priority, f"OTHER ({row.priority})")
                logger.info(f"  Priority {row.priority:3d} ({priority_label:20s}): {row.count:,} papers")

    logger.info("")
    logger.info("=" * 80)
    logger.info("Done!")
    logger.info("=" * 80)
