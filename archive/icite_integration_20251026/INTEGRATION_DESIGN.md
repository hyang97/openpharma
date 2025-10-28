# iCite Integration Design - Revised

## Overview

iCite provides citation metrics for all PubMed papers. We integrate it as a **lightweight utility** to enhance the ingestion pipeline with optional citation-based filtering and metadata enrichment.

## Core Philosophy

**iCite is a utility, not a workflow.** It augments the existing 4-stage pipeline with:
1. Optional citation filtering in Stage 1 (collect high-impact papers)
2. Citation metadata enrichment in Stage 2 (store metrics alongside papers)

## Problem: ID Mismatch

- **iCite uses PMID** (PubMed ID) - covers all ~36M PubMed papers
- **OpenPharma uses PMC ID** (PubMed Central ID) - only ~8M open access papers
- **Solution**: Maintain a cached PMC ↔ PMID mapping in our database

## Database Schema

### Enhanced Table: `pubmed_papers`

Add PMID column to existing `pubmed_papers` table for cached PMC ↔ PMID mapping:

```sql
ALTER TABLE pubmed_papers ADD COLUMN pmid BIGINT;
ALTER TABLE pubmed_papers ADD COLUMN doi TEXT;

CREATE INDEX idx_pubmed_papers_pmid ON pubmed_papers(pmid);
```

**Schema after migration:**
```sql
pubmed_papers (
    pmc_id VARCHAR PRIMARY KEY,        -- "1234567" (numeric only)
    pmid BIGINT,                       -- 98765432 (NULL if not yet fetched or no PMID exists)
    doi TEXT,                          -- 10.1234/journal.5678 (from NCBI API)
    discovered_at TIMESTAMP,
    fetch_status VARCHAR               -- 'pending', 'wont_fetch', 'fetched', 'failed'
)
```

**Fetch Statuses:**
- `pending` - Ready to fetch (default for papers passing citation filter)
- `wont_fetch` - Discovered but filtered out (failed citation filter, save for later)
- `fetched` - Successfully fetched and stored
- `failed` - Fetch failed (network error, invalid PMC ID, etc.)

**Benefits:**
- No new table needed - extend existing structure
- One-time API call per PMC ID
- Fast lookups for repeated queries
- PMID populated during Stage 1 (before fetch)
- Can be used in Stage 2 for citation metadata enrichment

### Enhanced Table: `documents`

Add citation metadata as JSONB column (optional, only populated if iCite data available):

```sql
ALTER TABLE documents ADD COLUMN citation_metadata JSONB;

-- Example citation_metadata structure:
{
  "pmid": 12345678,
  "nih_percentile": 99.2,
  "relative_citation_ratio": 3.45,
  "citation_count": 156,
  "year": 2018,
  "is_clinical": true,
  "field_citation_rate": 2.1
}
```

**Index for citation queries:**
```sql
CREATE INDEX idx_citation_percentile ON documents((citation_metadata->>'nih_percentile'));
```

## Implementation: Citation Utilities Module

**Location:** `app/ingestion/citation_utils.py`

### Core Functions

```python
class CitationUtils:
    """Utility functions for iCite citation data and PMC ↔ PMID conversion."""

    def __init__(self, session: Session):
        self.session = session
        self.ncbi_batch_size = 200  # NCBI API limit
        self.rate_limit_delay = 0.34  # 3 requests/second

    # ===== ID Conversion with Database Caching =====

    def get_pmid_for_pmc(self, pmc_id: str) -> Optional[str]:
        """Get PMID for a single PMC ID (checks cache first)."""
        from app.db.models import PubMedPaper

        # Check cache
        paper = self.session.query(PubMedPaper).filter_by(pmc_id=pmc_id).first()
        if paper and paper.pmid:
            return str(paper.pmid)

        # Cache miss - fetch from API
        result = self._fetch_id_mapping_from_ncbi([pmc_id])
        return result.get(pmc_id)

    def get_pmids_for_pmcs(self, pmc_ids: List[str]) -> Dict[str, Optional[str]]:
        """
        Get PMIDs for multiple PMC IDs (batch operation).

        Returns:
            Dict mapping PMC ID → PMID (or None if no PMID exists)
        """
        from app.db.models import PubMedPaper

        # Check cache first
        cached = self.session.query(PubMedPaper).filter(
            PubMedPaper.pmc_id.in_(pmc_ids)
        ).all()

        results = {p.pmc_id: str(p.pmid) if p.pmid else None for p in cached}

        # Identify cache misses
        uncached_pmcs = [pmc for pmc in pmc_ids if pmc not in results]

        if uncached_pmcs:
            logger.info(f"Cache hit: {len(cached)}/{len(pmc_ids)}, fetching {len(uncached_pmcs)} from NCBI API")

            # Fetch missing mappings from NCBI API in batches
            new_mappings = self._fetch_id_mapping_from_ncbi(uncached_pmcs)
            results.update(new_mappings)
        else:
            logger.info(f"Cache hit: {len(cached)}/{len(pmc_ids)} (100%)")

        return results

    def _fetch_id_mapping_from_ncbi(self, pmc_ids: List[str]) -> Dict[str, Optional[str]]:
        """Fetch PMC → PMID mappings from NCBI API and cache in pubmed_papers table."""
        from app.db.models import PubMedPaper
        from sqlalchemy.dialects.postgresql import insert

        results = {}

        # Batch API calls (200 IDs per request)
        for i in range(0, len(pmc_ids), self.ncbi_batch_size):
            batch = pmc_ids[i:i+self.ncbi_batch_size]
            ids_param = ','.join([f'PMC{id}' for id in batch])

            url = f'https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={ids_param}&format=json'

            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Parse response and cache in pubmed_papers table
                for record in data.get('records', []):
                    pmc_id = record['pmcid'].replace('PMC', '')  # Strip PMC prefix
                    pmid = record.get('pmid')  # May be None
                    doi = record.get('doi')

                    # UPSERT: update PMID if row exists, insert if not
                    stmt = insert(PubMedPaper).values(
                        pmc_id=pmc_id,
                        pmid=int(pmid) if pmid else None,
                        doi=doi
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['pmc_id'],
                        set_={'pmid': int(pmid) if pmid else None, 'doi': doi}
                    )
                    self.session.execute(stmt)

                    results[pmc_id] = pmid

                self.session.commit()

            except Exception as e:
                logger.error(f"NCBI API error for batch {i//self.ncbi_batch_size + 1}: {e}")
                # Continue with next batch (don't fail entire operation)

            # Rate limiting
            time.sleep(self.rate_limit_delay)

        return results

    # ===== Citation Filtering =====

    def get_citation_metrics(self, pmids: List[str]) -> Dict[str, Dict]:
        """
        Query iCite database for citation metrics.

        Returns:
            Dict mapping PMID → citation metrics
        """
        if not pmids:
            return {}

        # Query iCite database (local, fast)
        from app.db.models import ICiteMetadata

        results = self.session.query(ICiteMetadata).filter(
            ICiteMetadata.pmid.in_(pmids)
        ).all()

        return {
            str(row.pmid): {
                'pmid': row.pmid,
                'nih_percentile': row.nih_percentile,
                'relative_citation_ratio': row.relative_citation_ratio,
                'citation_count': row.citation_count,
                'year': row.year,
                'is_clinical': row.is_clinical,
                'field_citation_rate': row.field_citation_rate
            }
            for row in results
        }

    def filter_by_metrics(
        self,
        pmc_ids: List[str],
        min_percentile: Optional[float] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_citation_count: Optional[int] = None
    ) -> List[str]:
        """
        Filter PMC IDs by citation metrics.

        Args:
            pmc_ids: List of PMC IDs to filter
            min_percentile: Minimum NIH percentile (e.g., 95 = top 5%)
            min_year: Minimum publication year
            max_year: Maximum publication year
            min_citation_count: Minimum citation count

        Returns:
            Filtered list of PMC IDs meeting criteria
        """
        # Step 1: Get PMIDs for PMC IDs (with caching)
        pmc_to_pmid = self.get_pmids_for_pmcs(pmc_ids)
        pmids = [pmid for pmid in pmc_to_pmid.values() if pmid]

        if not pmids:
            logger.warning("No PMIDs found for provided PMC IDs")
            return []

        # Step 2: Query iCite with filters
        from app.db.models import ICiteMetadata

        query = self.session.query(ICiteMetadata).filter(
            ICiteMetadata.pmid.in_(pmids)
        )

        if min_percentile is not None:
            query = query.filter(ICiteMetadata.nih_percentile >= min_percentile)

        if min_year is not None:
            query = query.filter(ICiteMetadata.year >= min_year)

        if max_year is not None:
            query = query.filter(ICiteMetadata.year <= max_year)

        if min_citation_count is not None:
            query = query.filter(ICiteMetadata.citation_count >= min_citation_count)

        filtered_pmids = {str(row.pmid) for row in query.all()}

        # Step 3: Convert back to PMC IDs
        pmid_to_pmc = {v: k for k, v in pmc_to_pmid.items() if v}
        filtered_pmc_ids = [pmid_to_pmc[pmid] for pmid in filtered_pmids if pmid in pmid_to_pmc]

        logger.info(f"Citation filter: {len(pmc_ids)} → {len(filtered_pmc_ids)} PMC IDs")
        return filtered_pmc_ids
```

## Stage 1 Integration: Optional Citation Filtering

Add citation filtering flags to `stage_1_collect_ids.py`:

```python
# New arguments
parser.add_argument("--citation-percentile", type=float,
                   help="Filter by minimum NIH percentile (e.g., 95 = top 5%)")
parser.add_argument("--citation-year-range", type=str,
                   help="Filter by publication year range (e.g., 2010-2020)")
parser.add_argument("--citation-min-count", type=int,
                   help="Filter by minimum citation count")
```

**Workflow:**

```python
# In main():

# 1. Run PubMed query as usual
pmc_ids = fetcher.search_papers(query=query)
logger.info(f"Found {len(pmc_ids)} PMC IDs from PubMed query")

# 2. Apply citation filter if requested
if args.citation_percentile or args.citation_year_range or args.citation_min_count:
    from app.ingestion.citation_utils import CitationUtils

    citation_utils = CitationUtils(session)

    # Parse year range
    min_year, max_year = None, None
    if args.citation_year_range:
        years = args.citation_year_range.split('-')
        min_year = int(years[0])
        max_year = int(years[1]) if len(years) > 1 else None

    # Filter by citation metrics (also populates PMIDs in database)
    filtered_pmc_ids = citation_utils.filter_by_metrics(
        pmc_ids=pmc_ids,
        min_percentile=args.citation_percentile,
        min_year=min_year,
        max_year=max_year,
        min_citation_count=args.citation_min_count
    )
    logger.info(f"Citation filter: {len(pmc_ids)} → {len(filtered_pmc_ids)} PMC IDs")

    # 3a. Insert filtered PMC IDs with 'pending' status
    for pmc_id in filtered_pmc_ids:
        stmt = insert(PubMedPaper).values(pmc_id=pmc_id, fetch_status='pending')
        stmt = stmt.on_conflict_do_nothing(index_elements=['pmc_id'])
        session.execute(stmt)

    # 3b. Mark unfiltered papers as 'wont_fetch' (save for later)
    filtered_set = set(filtered_pmc_ids)
    wont_fetch_ids = [pmc for pmc in pmc_ids if pmc not in filtered_set]
    for pmc_id in wont_fetch_ids:
        stmt = insert(PubMedPaper).values(pmc_id=pmc_id, fetch_status='wont_fetch')
        stmt = stmt.on_conflict_do_nothing(index_elements=['pmc_id'])
        session.execute(stmt)

    logger.info(f"Marked {len(wont_fetch_ids)} papers as 'wont_fetch' for later")

else:
    # 3. No filter - insert all PMC IDs with 'pending' status (as usual)
    for pmc_id in pmc_ids:
        stmt = insert(PubMedPaper).values(pmc_id=pmc_id, fetch_status='pending')
        stmt = stmt.on_conflict_do_nothing(index_elements=['pmc_id'])
        session.execute(stmt)

session.commit()
```

## Stage 2 Integration: Store Citation Metadata

Add optional citation metadata storage to `stage_2_fetch_papers.py`:

```python
# New argument
parser.add_argument("--store-citations", action="store_true",
                   help="Store citation metadata alongside papers")

# In fetch loop:
if args.store_citations:
    from app.ingestion.citation_utils import CitationUtils
    citation_utils = CitationUtils(session)

    # Get PMID for this PMC ID
    pmid = citation_utils.get_pmid_for_pmc(pmc_id)

    if pmid:
        # Get citation metrics from iCite
        metrics = citation_utils.get_citation_metrics([pmid])
        citation_metadata = metrics.get(pmid)
    else:
        citation_metadata = None
else:
    citation_metadata = None

# Store document with citation metadata
document = Document(
    source='pubmed',
    source_id=f'PMC{pmc_id}',
    full_text=parsed_content['full_text'],
    doc_metadata=parsed_content['metadata'],
    citation_metadata=citation_metadata,  # NEW
    ingestion_status='completed'
)
```

## Usage Examples

### Example 1: Filter Diabetes Papers by Top 5% Citations

```bash
# Collect top 5% cited diabetes papers from 2015-2020
python -m scripts.stage_1_collect_ids \
    --keyword diabetes \
    --start-date 2015-01-01 \
    --end-date 2020-12-31 \
    --citation-percentile 95
```

### Example 2: Landmark Papers Across All Biomedicine

```bash
# Collect top 1% papers from 1990-2020 (any topic)
python -m scripts.stage_1_collect_ids \
    --query "open access[filter] AND 1990/01/01:2020/12/31[pdat]" \
    --citation-percentile 99 \
    --citation-year-range 1990-2020 \
    --limit 10000
```

### Example 3: Highly-Cited Clinical Papers

```bash
# Diabetes clinical papers with 100+ citations
python -m scripts.stage_1_collect_ids \
    --keyword "diabetes clinical trial" \
    --citation-min-count 100 \
    --citation-percentile 90
```

### Example 4: Store Citation Metadata During Fetch

```bash
# Fetch papers and store their citation metrics
python -m scripts.stage_2_fetch_papers \
    --store-citations
```

## Performance Considerations

### ID Mapping Cache

**First run (cold cache):**
- 52K PMC IDs: ~88 seconds (260 API calls at 3 req/sec)
- Cache populated for future queries

**Subsequent runs (warm cache):**
- 52K PMC IDs: <1 second (database lookup only)
- No API calls needed

**Cache growth:**
- ~100 bytes per mapping (PMC ID, PMID, DOI, timestamps)
- 1M mappings ≈ 100 MB storage
- Full PubMed Open Access (~8M papers) ≈ 800 MB

### iCite Queries

**Local database queries are fast:**
- Query 52K PMIDs with filters: ~100-500ms
- No external API calls
- Postgres indexes on percentile, year, citation_count

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: Collect IDs (with optional citation filtering)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
                    PubMed Query (52K PMC IDs)
                              │
                              ↓
                   [Citation Filter Enabled?]
                              │
                    ┌─────────┴─────────┐
                    │                   │
                   YES                  NO
                    │                   │
                    ↓                   │
    ┌───────────────────────────────┐  │
    │ CitationUtils.filter_by_metrics│  │
    └───────────────────────────────┘  │
                    │                   │
                    ↓                   │
         Get PMIDs (with cache)         │
                    │                   │
                    ↓                   │
         Query iCite (local DB)         │
                    │                   │
                    ↓                   │
         Filter by percentile/year      │
                    │                   │
                    ↓                   │
         Convert back to PMC IDs        │
                    │                   │
                    └─────────┬─────────┘
                              ↓
                    Filtered PMC IDs (~500-1K)
                              │
                              ↓
                    Insert into pubmed_papers
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: Fetch Papers (with optional citation metadata)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
                    Fetch from PMC API
                              │
                              ↓
                   [Store Citations Enabled?]
                              │
                    ┌─────────┴─────────┐
                    │                   │
                   YES                  NO
                    │                   │
                    ↓                   │
         Get PMID (with cache)          │
                    │                   │
                    ↓                   │
         Query iCite for metrics        │
                    │                   │
                    └─────────┬─────────┘
                              ↓
         Store document with citation_metadata
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 3 & 4: Chunk and Embed (unchanged)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Migration Script

Create `scripts/add_citation_support.sql`:

```sql
-- Add PMID and DOI columns to pubmed_papers table
ALTER TABLE pubmed_papers ADD COLUMN IF NOT EXISTS pmid BIGINT;
ALTER TABLE pubmed_papers ADD COLUMN IF NOT EXISTS doi TEXT;

-- Create index for PMID lookups
CREATE INDEX IF NOT EXISTS idx_pubmed_papers_pmid ON pubmed_papers(pmid);

-- Add citation metadata to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS citation_metadata JSONB;

-- Create GIN index for citation metadata queries
CREATE INDEX IF NOT EXISTS idx_citation_metadata ON documents USING gin(citation_metadata);

-- Create index for percentile lookups (for future UI filtering/sorting)
CREATE INDEX IF NOT EXISTS idx_citation_percentile
ON documents((citation_metadata->>'nih_percentile'));
```

**Run with:**
```bash
docker-compose exec postgres psql -U admin -d openpharma -f scripts/add_citation_support.sql
```

## Benefits of This Design

1. **No Repeated API Calls**: PMC ↔ PMID mappings cached in database
2. **Fast Queries**: iCite queries are local (no external API)
3. **Incremental Adoption**: Citation features are optional, no workflow changes
4. **Flexible Filtering**: Combine PubMed queries with citation filters
5. **Future-Proof**: Citation metadata enables UI sorting, filtering, KOL identification
6. **Cost-Effective**: Only fetch what you need, cache everything

## Future Enhancements

### Phase 2: Citation-Enhanced Features
- Sort search results by citation impact
- Filter by clinical relevance (is_clinical flag)
- Identify key opinion leaders (authors of top 1% papers)
- Visualize citation networks

### Phase 3: Advanced Analytics
- Co-citation analysis (papers cited together)
- Citation trajectories (RCR over time)
- Field-normalized benchmarking
- Predictive models for emerging research areas
