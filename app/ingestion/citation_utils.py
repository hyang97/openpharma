"""
Citation utilities for iCite integration.

Provides PMC <-> PMID conversion with database caching and citation filtering.
"""
import logging
import time
from typing import Dict, List, Optional
import requests
from sqlalchemy import text, update
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CitationUtils:
    """Utility functions for iCite citation data and PMC <-> PMID conversion."""

    def __init__(self, session: Session):
        self.session = session
        self.ncbi_batch_size = 200  # NCBI API limit
        self.rate_limit_delay = 0.34  # 3 requests/second

    # ===== PMID Population =====

    def populate_pmids(self, pmc_ids: List[str]) -> int:
        """
        Fetch PMIDs from NCBI and UPDATE pubmed_papers table, returning number of rows with PMIDs.
        """

        from app.db.models import PubMedPaper

        cached_papers = self.session.query(PubMedPaper).filter(
            PubMedPaper.pmc_id.in_(pmc_ids), 
            PubMedPaper.pmid.isnot(None)
        ).all()
        
        cached = {p.pmc_id for p in cached_papers} 
        uncached = [pmc for pmc in pmc_ids if pmc not in cached]

        rows_with_pmid = 0
        rows_without_pmid = 0

        if not uncached:
            logger.info(f"PMIDs all populated for PMC IDs")
            return rows_with_pmid
        
        total_batches = (len(uncached) + self.ncbi_batch_size - 1) // self.ncbi_batch_size
        logger.info(f"Fetching PMIDs from NCBI API: {len(uncached):,} papers in {total_batches:,} batches (200 per batch)")

        # Batch API calls (200 IDs per request)
        for i in range(0, len(uncached), self.ncbi_batch_size):
            batch_num = i // self.ncbi_batch_size + 1
            batch = uncached[i:i+self.ncbi_batch_size]
            ids_param = ','.join([f'PMC{id}' for id in batch])

            url = f'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={ids_param}&format=json'

            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Track which PMC IDs were found in the response
                found_pmc_ids = set()

                # Parse response and update existing pubmed_papers rows
                for record in data.get('records', []):
                    pmc_id = record['pmcid'].replace('PMC', '') # Strip PMC prefix
                    pmid = record.get('pmid') # May be None
                    doi = record.get('doi')

                    found_pmc_ids.add(pmc_id)

                    # Only UPDATE existing rows, don't INSERT new ones
                    stmt = update(PubMedPaper).where(
                        PubMedPaper.pmc_id == pmc_id
                    ).values(
                        pmid=int(pmid) if pmid else -1,  # -1 = looked up but no PMID found
                        doi=doi
                    )
                    result = self.session.execute(stmt)
                    if result.rowcount > 0:
                        if pmid:
                            rows_with_pmid += 1
                        else:
                            rows_without_pmid += 1

                # Mark PMC IDs not found in API response (invalid/non-existent)
                not_found = set(batch) - found_pmc_ids
                if not_found:
                    logger.warning(f"No NCBI records found for {len(not_found)} PMC IDs (may be invalid)")
                    # Set pmid to -1 to indicate "looked up but not found"
                    for pmc_id in not_found:
                        stmt = update(PubMedPaper).where(
                            PubMedPaper.pmc_id == pmc_id
                        ).values(pmid=-1)
                        result = self.session.execute(stmt)
                        if result.rowcount > 0:
                            rows_without_pmid += 1

                self.session.commit()

                # Progress logging every 50 batches (~10K papers)
                if batch_num % 50 == 0:
                    logger.info(f"Progress: {batch_num:,}/{total_batches:,} batches | {rows_with_pmid:,} PMIDs found so far")

            except Exception as e:
                logger.error(f"NCBI API error for batch {batch_num}: {e}")
                # continue with next batch

            time.sleep(self.rate_limit_delay)

        logger.info(f"Completed: {rows_with_pmid:,} papers with PMID, {rows_without_pmid:,} papers without PMID")
        return rows_with_pmid
        

    def populate_citation_metrics(self, max_update: Optional[int] = 50000) -> int:
        """
        Query iCite table and UPDATE pubmed_papers with citation metrics. 
        For fields with no data, update with -1 for numeric/float and NULL for boolean
        """
        from app.db.models import PubMedPaper, ICiteMetadata

        query = self.session.query(PubMedPaper).filter(
            PubMedPaper.pmid.isnot(None),
            PubMedPaper.pmid > 0,  # Exclude papers with pmid=-1 (no PMID found)
            PubMedPaper.nih_percentile.is_(None)  # Only papers not yet queried
        )

        if max_update is not None:
            query = query.limit(max_update)

        papers = query.all()

        if not papers:
            logger.info(f"All papers with PMIDs already have citation metrics")
            return 0

        # Build mapping: PMID -> PMC_ID (filter out invalid PMIDs like -1)
        pmid_to_pmc = {p.pmid: p.pmc_id for p in papers if p.pmid and p.pmid > 0}
        pmids = list(pmid_to_pmc.keys())

        logger.info(f"Processing {len(papers)} papers with PMIDs, querying iCite for {len(pmids)} valid PMIDs")

        icite_records = self.session.query(ICiteMetadata).filter(
            ICiteMetadata.pmid.in_(pmids)
        ).all()

        if not icite_records:
            logger.warning(f"No iCite records found for {len(pmids)} PMIDs")
            return 0

        logger.info(f"Found {len(icite_records)} iCite records out of {len(pmids)} PMIDs")

        # Track which PMC IDs we're updating
        icite_pmids = {record.pmid for record in icite_records}
        rows_updated = 0

        for record in icite_records:
            pmc_id = pmid_to_pmc.get(record.pmid)
            if not pmc_id:
                continue

            # Use sentinel value -1 for NULL numeric/float metrics (checked but no data available)
            # Use NULL for boolean fields when no data available
            stmt = update(PubMedPaper).where(
                PubMedPaper.pmc_id == pmc_id
            ).values(
                nih_percentile=record.nih_percentile if record.nih_percentile is not None else -1,
                publication_year=record.year if record.year is not None else -1,
                citation_count=record.citation_count if record.citation_count is not None else -1,
                relative_citation_ratio=record.relative_citation_ratio if record.relative_citation_ratio is not None else -1,
                is_clinical=record.is_clinical,  # NULL if no data
                is_research_article=record.is_research_article  # NULL if no data
            )
            result = self.session.execute(stmt)
            if result.rowcount > 0:
                rows_updated += 1

        self.session.commit()

        papers_without_icite = len(pmids) - len(icite_records)
        logger.info(f"Completed: {rows_updated} papers updated with citation metrics (actual data or -1 for missing fields), {papers_without_icite} papers not in iCite")

        return rows_updated

    # ===== Citation Filtering =====

    def filter_by_metrics(
        self,
        fetch_status: str,
        min_percentile: Optional[float] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_citation_count: Optional[int] = None
    ) -> List[str]:
        """
        Filter papers by fetch_status and citation metrics using JOIN with icite_metadata table.

        Args:
            fetch_status: Fetch status to filter on (e.g., "wont_fetch", "pending")
            min_percentile: Minimum NIH percentile (e.g., 95 = top 5%)
            min_year: Minimum publication year
            max_year: Maximum publication year
            min_citation_count: Minimum citation count

        Returns:
            Filtered list of PMC IDs meeting criteria. Papers without PMIDs or citation data are excluded.

        Note:
            This function assumes PMIDs are already populated. Run stage_1_1_backfill_pmids.py first.
        """

        from app.db.models import PubMedPaper, ICiteMetadata

        logger.info(f"Starting filter_by_metrics for papers with fetch_status='{fetch_status}'")

        # Build query with JOIN to icite_metadata - filter by fetch_status directly
        query = self.session.query(PubMedPaper.pmc_id).join(
            ICiteMetadata, PubMedPaper.pmid == ICiteMetadata.pmid
        ).filter(
            PubMedPaper.fetch_status == fetch_status,
            PubMedPaper.pmid.isnot(None),
            PubMedPaper.pmid > 0
        )

        if min_percentile is not None:
            query = query.filter(ICiteMetadata.nih_percentile >= min_percentile)

        if min_year is not None:
            query = query.filter(ICiteMetadata.year >= min_year)

        if max_year is not None:
            query = query.filter(ICiteMetadata.year <= max_year)

        if min_citation_count is not None:
            query = query.filter(ICiteMetadata.citation_count >= min_citation_count)

        filtered_pmc_ids = [row.pmc_id for row in query.all()]

        logger.info(f"Filtered papers -> {len(filtered_pmc_ids):,} papers meeting criteria")

        return filtered_pmc_ids