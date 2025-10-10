"""
PubMed Central fetcher using NCBI Entrez API.
Fetches research papers from PubMed Central Open Access subset.
"""
from typing import List, Dict, Optional
import time
import os
from Bio import Entrez
import logging
from dotenv import load_dotenv
from .xml_parser import PMCXMLParser

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Entrez (NCBI requires email for API usage)
Entrez.email = "hyang97@gmail.com"
Entrez.tool = "OpenPharma"
Entrez.api_key = os.getenv("NCBI_API_KEY", "")  # Optional: 10 req/sec with key, 3 req/sec without

# HTTP timeout for all NCBI requests (seconds)
HTTP_TIMEOUT = 30 


class PubMedFetcher:
    """Fetches research papers from PubMed Central Open Access."""

    def __init__(self, email: Optional[str] = None, timeout: int = HTTP_TIMEOUT):
        if email:
            Entrez.email = email
        self.timeout = timeout
        self.xml_parser = PMCXMLParser()

    def search_papers(
        self,
        query: str,
        max_results: int = 100,
        start_index: int = 0
    ) -> List[str]:
        """
        Search PMC Open Access for papers matching query.

        Args:
            query: PubMed query string
            max_results: Maximum number of PMC IDs to return
            start_index: Starting index for pagination

        Returns:
            List of PMC IDs (numeric only, e.g., ['1234567', '2345678'])
        """
        try:
            logger.info(f"Searching PMC (max: {max_results}, start: {start_index})")
            handle = Entrez.esearch(
                db="pmc",
                term=query,
                retmax=max_results,
                retstart=start_index,
                sort="relevance",
                timeout=self.timeout
            )
            record = Entrez.read(handle)
            handle.close()

            pmc_ids = record["IdList"]
            logger.info(f"Found {len(pmc_ids)} papers")
            return pmc_ids

        except Exception as e:
            logger.error(f"Error searching PMC: {e}")
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
            # Fetch full XML record
            handle = Entrez.efetch(
                db="pmc",
                id=pmc_id,
                rettype="full",
                retmode="xml",
                timeout=self.timeout
            )
            xml_content = handle.read()
            handle.close()

            # Parse XML to extract title, abstract, and full text
            parsed = self.xml_parser.parse_article(xml_content)
            if not parsed:
                logger.warning(f"Failed to parse XML for PMC{pmc_id}")
                return None

            # NCBI rate limit: 10 req/sec with API key, 3 req/sec without
            # Use conservative timing to avoid 429 errors (0.15s = ~6.7 req/sec, 0.4s = ~2.5 req/sec)
            sleep_time = 0.15 if Entrez.api_key else 0.4
            time.sleep(sleep_time)

            # Fetch summary metadata (authors, journal, dates, etc.)
            handle = Entrez.esummary(db="pmc", id=pmc_id, timeout=self.timeout)
            summary = Entrez.read(handle)
            handle.close()

            # Rate limit after second API call
            time.sleep(sleep_time)

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
