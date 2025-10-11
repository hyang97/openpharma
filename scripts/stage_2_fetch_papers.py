"""
Stage 2: Fetch papers from PubMed Central and store in documents table.

Fetches full XML for pending PMC IDs and stores parsed content in database.
"""
import argparse
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db.database import engine
from app.db.models import PubMedPaper, Document
from app.ingestion.pubmed_fetcher import PubMedFetcher
from app.logging_config import setup_logging

load_dotenv()
logger = logging.getLogger(__name__)


def main():
    """Fetch papers and store in database."""
    parser = argparse.ArgumentParser(
        description="Fetch papers from PubMed Central and store in database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch all pending papers (default)
  python -m scripts.fetch_papers

  # Fetch only 100 papers
  python -m scripts.fetch_papers --limit 100

Note: NCBI rate limit is 3 requests/second. Script includes automatic rate limiting.
Fetching 52K papers takes ~9 hours.

IMPORTANT: NCBI requests large jobs (>1000 papers) run during off-peak hours:
  - Weekends (anytime)
  - Weekdays: 9pm - 5am Eastern Time
        """
    )

    parser.add_argument("--limit", type=int, default=None,
                       help="Maximum number of papers to fetch (default: fetch all pending)")
    parser.add_argument("--retry-failed", action="store_true",
                       help="Also retry papers that previously failed (default: skip failed papers)")
    parser.add_argument("--confirm-large-job", action="store_true",
                       help="Skip confirmation prompt for large jobs (use for background jobs)")
    parser.add_argument("--log-level", type=str,
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: LOG_LEVEL env var or INFO)")

    args = parser.parse_args()

    # Precedence: CLI arg > env var > default
    log_level = args.log_level or os.getenv("LOG_LEVEL", "INFO")

    # Archive old log if it exists
    from pathlib import Path
    old_log = Path("logs/stage_2_fetch_papers.log")
    if old_log.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_log.rename(f"logs/stage_2_fetch_papers_{timestamp}.log")

    # Always log to the same active file
    setup_logging(level=log_level, log_file="logs/stage_2_fetch_papers.log")

    # Use longer timeout when retrying failed papers (some failed due to size/timeout)
    timeout = 120 if args.retry_failed else 30
    fetcher = PubMedFetcher(timeout=timeout)

    if args.retry_failed:
        logger.info(f"Retry mode: Using extended timeout ({timeout}s) for large papers")

    # Get pending papers (and optionally failed papers)
    with Session(engine) as session:
        if args.retry_failed:
            query = session.query(PubMedPaper).filter(
                PubMedPaper.fetch_status.in_(['pending', 'failed'])
            )
            total_pending = session.query(PubMedPaper).filter(
                PubMedPaper.fetch_status.in_(['pending', 'failed'])
            ).count()
        else:
            query = session.query(PubMedPaper).filter(PubMedPaper.fetch_status == 'pending')
            total_pending = session.query(PubMedPaper).filter(
                PubMedPaper.fetch_status == 'pending'
            ).count()

        if args.limit is not None:
            pending_papers = query.limit(args.limit).all()
        else:
            pending_papers = query.all()

    if not pending_papers:
        logger.info("No pending papers to fetch")
        return

    logger.info(f"Found {total_pending} total pending papers")

    # Check NCBI off-peak hours policy for large jobs
    if len(pending_papers) > 1000:
        et_now = datetime.now(ZoneInfo("America/New_York"))
        is_weekend = et_now.weekday() >= 5  # Saturday=5, Sunday=6
        is_off_peak = is_weekend or (21 <= et_now.hour or et_now.hour < 5)  # 9pm-5am ET

        # Estimate based on rate limiting (2 API calls per paper, conservative timing)
        has_api_key = bool(os.getenv("NCBI_API_KEY"))
        time_per_paper = 0.3 if has_api_key else 0.8  # Conservative: ~6.7 req/sec with key, ~2.5 req/sec without
        est_hours = (len(pending_papers) * time_per_paper) / 3600

        logger.warning(f"Large job: {len(pending_papers):,} papers, ~{est_hours:.1f} hours ({et_now.strftime('%A %I:%M %p ET')})")
        logger.warning("NCBI requests large jobs run weekends or weekdays 9pm-5am ET")

        if not is_off_peak:
            logger.warning("WARNING: Currently during PEAK hours")

        if not args.confirm_large_job:
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Aborted")
                return

    
    logger.info(f"Fetching {len(pending_papers)} papers in this batch\n")

    success_count = 0
    fail_count = 0

    for idx, paper in enumerate(pending_papers, 1):
        pmc_id = paper.pmc_id

        try:
            # Fetch and parse paper
            paper_data = fetcher.fetch_paper_details(pmc_id)

            if not paper_data:
                logger.warning(f"[{idx}/{len(pending_papers)}] Failed to fetch PMC{pmc_id}")
                with Session(engine) as session:
                    session.query(PubMedPaper).filter(
                        PubMedPaper.pmc_id == pmc_id
                    ).update({'fetch_status': 'failed'})
                    session.commit()
                fail_count += 1
                continue

            # UPSERT into documents table
            with Session(engine) as session:
                stmt = insert(Document).values(
                    source='pmc',
                    source_id=paper_data['source_id'],
                    title=paper_data['title'],
                    abstract=paper_data['abstract'],
                    full_text=paper_data['full_text'],
                    doc_metadata=paper_data['metadata'],
                    ingestion_status='fetched'
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['source', 'source_id'],
                    set_={
                        'title': paper_data['title'],
                        'abstract': paper_data['abstract'],
                        'full_text': paper_data['full_text'],
                        'doc_metadata': paper_data['metadata'],
                        'ingestion_status': 'fetched'
                    }
                )
                session.execute(stmt)

                # Update fetch status
                session.query(PubMedPaper).filter(
                    PubMedPaper.pmc_id == pmc_id
                ).update({'fetch_status': 'fetched'})

                session.commit()

            success_count += 1
            logger.debug(f"[{idx}/{len(pending_papers)}] Successfully fetched PMC{pmc_id}")

            # Log progress every 100 papers
            if idx % 100 == 0:
                logger.info(f"Progress: {idx}/{len(pending_papers)} papers processed ({success_count} successful, {fail_count} failed)\n")

        except Exception as e:
            logger.error(f"[{idx}/{len(pending_papers)}] Error processing PMC{pmc_id}: {e}")
            with Session(engine) as session:
                session.query(PubMedPaper).filter(
                    PubMedPaper.pmc_id == pmc_id
                ).update({'fetch_status': 'failed'})
                session.commit()
            fail_count += 1

    logger.info(f"\nBatch complete: {success_count} successful, {fail_count} failed")
    logger.info(f"Remaining pending papers: {total_pending - len(pending_papers)}")


if __name__ == "__main__":
    main()
