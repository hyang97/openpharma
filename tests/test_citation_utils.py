"""
Test citation_utils.py populate_pmids() method.
"""
from app.db.database import engine
from app.db.models import PubMedPaper
from app.ingestion.citation_utils import CitationUtils
from sqlalchemy.orm import Session

# Test with a few known PMC IDs
test_pmc_ids = ['6432163', '6432164', '6432165']  # Random diabetes papers

print(f"Testing populate_pmids() with {len(test_pmc_ids)} PMC IDs...")

with Session(engine) as session:
    citation_utils = CitationUtils(session)

    # Populate PMIDs
    count = citation_utils.populate_pmids(test_pmc_ids)
    print(f"✓ Updated {count} rows")

    # Verify results
    papers = session.query(PubMedPaper).filter(
        PubMedPaper.pmc_id.in_(test_pmc_ids)
    ).all()

    print(f"\nResults:")
    for p in papers:
        print(f"  PMC{p.pmc_id} → PMID: {p.pmid}, DOI: {p.doi}")

print("\n✓ Test complete!")
