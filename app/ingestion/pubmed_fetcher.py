"""
PubMed Central fetcher using NCBI Entrez API.
Fetches diabetes research papers from PubMed Central Open Access subset.
"""
from typing import List, Dict, Optional
import time
from Bio import Entrez
import logging
from .xml_parser import PMCXMLParser

logger = logging.getLogger(__name__)

# Configure Entrez (NCBI requires email for API usage)
Entrez.email = "hyang97@gmail.com"  
Entrez.tool = "OpenPharma" 


class PubMedFetcher:
    """Fetches research papers from PubMed Central Open Access."""

    def __init__(self, email: Optional[str] = None):
        if email:
            Entrez.email = email
        self.xml_parser = PMCXMLParser()

    def search_diabetes_papers(
        self,
        max_results: int = 100,
        start_index: int = 0
    ) -> List[str]:
        """
        Search for diabetes research papers in PMC Open Access.

        Args:
            max_results: Maximum number of PMCIDs to return
            retstart: Starting index for pagination

        Returns:
            List of PMC IDs (e.g., ['PMC1234567', 'PMC2345678'])
        """
        query = (
            "diabetes[Title/Abstract] AND " # diabetes in title or abstract
            "open access[filter] AND " # open access filter (legally free to download)
            "\"loattrfree full text\"[sb]" # most permissive licensing (no attribution required)
            # "hasfulltextsb[sb]" # Alternative: for all open access full text (more papers, may have licensing restrictions)
        )

        try:
            logger.info(f"Searching PubMed for diabetes papers (max: {max_results}, start: {start_index})")
            handle = Entrez.esearch(
                db="pmc", # PubMed Central
                term=query,
                retmax=max_results,
                retstart=start_index,
                sort="relevance"
            )
            record = Entrez.read(handle)
            handle.close()

            pmc_ids = record["IdList"]  # Just numeric IDs, no PMC prefix needed
            logger.info(f"Found {len(pmc_ids)} papers")
            return pmc_ids

        except Exception as e:
            logger.error(f"Error searching PubMed: {e}")
            raise

    def fetch_paper_details(self, pmc_id: str) -> Optional[Dict]:
        """
        Fetch full paper details including title, abstract, and full text.

        Args:
            pmc_id: PubMed Central numeric ID (e.g., '1234567')

        Returns:
            Dict with keys: source_id, title, abstract, full_text, metadata
        """
        try:
            logger.info(f"Fetching details for PMC{pmc_id}")

            # Fetch full XML record
            handle = Entrez.efetch(
                db="pmc",
                id=pmc_id,
                rettype="full",
                retmode="xml"
            )
            xml_content = handle.read()
            handle.close()

            # Parse XML to extract title, abstract, and full text
            parsed = self.xml_parser.parse_article(xml_content)
            if not parsed:
                logger.warning(f"Failed to parse XML for PMC{pmc_id}")
                return None

            time.sleep(0.34)  # NCBI rate limit: 3 requests/second

            # Fetch summary metadata (authors, journal, dates, etc.)
            handle = Entrez.esummary(db="pmc", id=pmc_id)
            summary = Entrez.read(handle)
            handle.close()

            if not summary:
                logger.warning(f"No summary found for PMC{pmc_id}")
                return None

            doc = summary[0]

            return {
                "source_id": pmc_id,
                "title": parsed["title"] or doc.get("Title", ""),  # Prefer parsed title
                "abstract": parsed["abstract"],
                "full_text": parsed["full_text"],
                "sections": parsed["sections"],  # Keep for chunking (not persisted)
                "metadata": {
                    "authors": doc.get("AuthorList", []),
                    "journal": doc.get("FullJournalName", ""),
                    "pub_date": doc.get("PubDate", ""),
                    "doi": doc.get("DOI", ""),
                    "pmid": doc.get("PmId", ""),
                    "pmc_id": pmc_id,
                    "section_offsets": parsed["section_offsets"]  # Character positions in full_text
                }
            }

        except Exception as e:
            logger.error(f"Error fetching PMC{pmc_id}: {e}")
            return None

    def fetch_batch(self, pmc_ids: List[str]) -> List[Dict]:
        """
        Fetch details for multiple papers.

        Args:
            pmc_ids: List of PMC IDs

        Returns:
            List of paper detail dicts
        """
        papers = []
        for pmc_id in pmc_ids:
            paper = self.fetch_paper_details(pmc_id)
            if paper:
                papers.append(paper)
        return papers
