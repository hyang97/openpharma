# iCite Integration Design

## Overview

This document describes how iCite citation data integrates with OpenPharma's ingestion pipeline.

## Architecture Decision

**Approach**: Citation data stored in Postgres as helper tables, not a separate database
**Rationale**: See `docs/decisions.md` - "Postgres for Citation Data, Defer Graph Database to Phase 2"

## Database Tables

### `icite_metadata` (~12GB)
- Citation metrics for all PubMed papers
- Primary use: Filter by `nih_percentile >= 99` to identify landmark papers
- Secondary use: Enrich RAG responses with citation counts, identify KOLs

### `citation_links` (~12-18GB with indexes)
- Citation network edges (Paper A cites Paper B)
- Primary use: Co-citation analysis, author collaboration networks
- Secondary use: Future migration to Neo4j for Graph RAG (Phase 2)

## Integration with 4-Stage Pipeline

### Option A: Filter During Stage 1 (Recommended)
Add `--filter-citations --percentile 99` flag to `stage_1_collect_ids.py`:

```python
# Uses CitationFilter helper to cross-reference PMIDs with iCite
from app.ingestion.citation_filter import CitationFilter

cf = CitationFilter()
filtered_pmids = cf.filter_by_percentile(pmids, percentile=99)
# Only insert filtered PMIDs into pubmed_papers table
```

### Option B: Metadata Enrichment During Stage 2
Add citation metadata to `doc_metadata` during fetch:

```python
# In stage_2_fetch_papers.py
citation_info = cf.get_metadata(pmid)
doc_metadata['nih_percentile'] = citation_info['nih_percentile']
doc_metadata['citation_count'] = citation_info['citation_count']
```

## Helper Module

**File**: `app/ingestion/citation_filter.py`

**Purpose**: Provide reusable functions for filtering and enriching papers with citation data

**Key Functions**:
- `import_icite_data(csv_path)` - One-time import of iCite CSV to Postgres
- `filter_by_percentile(pmids, percentile)` - Filter PMIDs by citation percentile
- `get_metadata(pmid)` - Get citation metrics for a single paper

## Import Process

1. Download iCite snapshot from Figshare (28.75GB compressed)
2. Extract `icite_metadata.csv` and `open_citation_collection.csv` to this directory
3. Run import script: `python -m scripts.import_icite_data`
4. Import runs in chunks (1M rows at a time) to avoid memory issues
5. Estimated import time: 5-8 hours total

## Phase 1 Use Cases

- **Landmark paper collection**: Filter for `nih_percentile >= 99` AND `year BETWEEN 1990 AND 2020`
- **KOL identification**: Most-cited authors via SQL aggregation
- **Co-citation analysis**: 2-hop SQL queries to find frequently co-cited papers
- **Citation enrichment**: Display "This paper has 5,432 citations" in UI

## Phase 2 Migration Path

If building Graph RAG or citation network visualizations:
- Export citation data to Neo4j
- Keep Postgres tables for backward compatibility
- Hybrid architecture: Postgres for documents/chunks, Neo4j for graph queries

## Storage Requirements

- iCite metadata: ~12GB
- Citation links: ~12-18GB
- Total: ~30GB (fits comfortably within 200GB available disk space)
