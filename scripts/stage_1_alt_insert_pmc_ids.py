"""
Stage 1 Alternative: Insert PMC IDs directly into pubmed_papers table.

This is an alternative to stage_1_collect_ids.py for cases where you already
have a list of PMC IDs (e.g., from PubMedQA dataset, manual curation, etc.)
and don't need to query PubMed.

Usage:
    python scripts/stage_1_alt_insert_pmc_ids.py --input data/pubmedqa_pmc_ids.txt --fetch-status pending
"""

import argparse
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import PubMedPaper
import os
from dotenv import load_dotenv

load_dotenv()

def insert_pmc_ids(pmc_ids_file: str, fetch_status: str = "pending", priority: int = 50, dry_run: bool = False):
    """
    Insert PMC IDs into pubmed_papers table.

    Args:
        pmc_ids_file: File with PMC IDs (one per line, numeric only)
        fetch_status: Initial status (pending, wont_fetch, fetched, failed)
        priority: Priority level (0=exclude, 10=low, 50=normal, 100=high)
        dry_run: If True, only report what would be done without making changes
    """
    # Database connection
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:admin@localhost:5432/openpharma")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Read PMC IDs
    with open(pmc_ids_file, 'r') as f:
        pmc_ids = [line.strip() for line in f if line.strip()]

    print(f"Read {len(pmc_ids)} PMC IDs from {pmc_ids_file}")

    if dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")

    # Insert or update
    inserted = 0
    skipped = 0
    updated = 0

    for pmc_id in pmc_ids:
        # Check if already exists
        existing = session.query(PubMedPaper).filter_by(pmc_id=pmc_id).first()

        if existing:
            # Skip any existing papers (don't update status)
            if dry_run and skipped < 5:  # Show first 5 examples
                print(f"  PMC{pmc_id}: Would skip (already exists, status={existing.fetch_status})")
            skipped += 1
        else:
            if dry_run and inserted < 5:  # Show first 5 examples
                print(f"  PMC{pmc_id}: Would insert as new")

            if not dry_run:
                # Insert new
                paper = PubMedPaper(
                    pmc_id=pmc_id,
                    fetch_status=fetch_status,
                    priority=priority,
                    discovered_at=datetime.now()
                )
                session.add(paper)
            inserted += 1

        # Commit in batches of 100
        if not dry_run and (inserted + updated) % 100 == 0:
            session.commit()

    # Final commit
    if not dry_run:
        session.commit()

    session.close()

    print(f"\nSummary:")
    if dry_run:
        print(f"  Would insert: {inserted}")
        print(f"  Would skip (already exists): {skipped}")
    else:
        print(f"  Inserted: {inserted}")
        print(f"  Skipped (already exists): {skipped}")
    print(f"  Total: {len(pmc_ids)}")

    print(f"\nNext steps:")
    print(f"  Stage 2: docker-compose exec api python -m scripts.stage_2_fetch_papers")
    print(f"  Stage 3: docker-compose exec api python -m scripts.stage_3_chunk_papers")
    print(f"  Stage 4: docker-compose exec api python -m scripts.stage_4_embed_chunks")


def main():
    parser = argparse.ArgumentParser(
        description="Stage 1 Alternative: Insert PMC IDs directly into database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Insert PubMedQA PMC IDs for ingestion
  python -m scripts.stage_1_alt_insert_pmc_ids --input data/pubmedqa_pmc_ids.txt --fetch-status pending

  # Insert with high priority
  python -m scripts.stage_1_alt_insert_pmc_ids --input data/my_pmc_ids.txt --priority 100

Note: This script is an alternative to stage_1_collect_ids.py for when you
already have PMC IDs and don't need to query PubMed.
        """
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input file with PMC IDs (one per line, numeric only)"
    )
    parser.add_argument(
        "--fetch-status",
        default="pending",
        choices=["pending", "wont_fetch"],
        help="Initial fetch status (default: pending)"
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=50,
        help="Priority level: 0=exclude, 10=low, 50=normal, 100=high (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be inserted without making changes"
    )

    args = parser.parse_args()

    insert_pmc_ids(args.input, args.fetch_status, args.priority, args.dry_run)


if __name__ == "__main__":
    main()
