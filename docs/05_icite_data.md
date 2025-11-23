# iCite Citation Data

## Overview

OpenPharma uses the NIH iCite database for citation-based filtering and quality assessment of research papers.

**Source**: NIH Office of Portfolio Analysis
**Dataset**: iCite Database Snapshot 2025-09
**URL**: https://nih.figshare.com/collections/iCite_Database_Snapshots_NIH_Open_Citation_Collection_/4586573

## Database Tables

### `icite_metadata` (39.4M rows, ~12GB)
Citation metrics and metadata for all PubMed papers.

**Key Fields**:
- `pmid`: PubMed identifier (primary key)
- `is_research_article`: Boolean flag for primary research articles (excludes reviews, editorials, letters, comments, errata)
- `is_clinical`: Boolean flag for clinical articles
- `nih_percentile`: Percentile rank vs all NIH publications (99 = top 1%)
- `citation_count`: Number of unique articles citing this paper
- `citations_per_year`: Annual citation rate
- `relative_citation_ratio` (RCR): Field-adjusted citation metric (median NIH paper = 1.0)
- `year`: Publication year
- `apt`: Approximate Potential to Translate (ML-based likelihood of clinical impact)

### `citation_links` (DROPPED 2025-01-23)
**Previous schema**: 870M citation network edges (81 GB)
- `citing`: PMID of citing paper
- `referenced`: PMID of referenced paper

**Status**: Dropped - imported but never used in Phase 1. Can be re-imported from NIH iCite snapshot if needed for Phase 2 KOL/co-citation features.

## Use Cases

### Phase 1 (Current)
1. **Historical paper filtering**: Filter by `nih_percentile >= 95` AND `year BETWEEN 1990 AND 2019` (58K landmark papers)
2. **Research article filtering**: Use `is_research_article = TRUE` to exclude non-research content (reviews, editorials, etc.)
3. **Priority assignment**: Set document priority based on citation metrics

### Phase 2 (Planned)
- Re-import citation_links if needed for:
  - KOL identification via citation aggregation
  - Co-citation analysis for related papers
- Citation enrichment in RAG responses (uses icite_metadata only)

## Import Status

✅ **icite_metadata** (2025-10-26)
- 39.4M rows imported (32 GB)
- Indexes: Created on `nih_percentile`, `year`, `citation_count`

❌ **citation_links** (dropped 2025-01-23)
- Previously: 870M rows imported (81 GB with indexes)
- Reason: Not used in Phase 1, consumed 49% of database storage
- Can be re-imported from NIH iCite snapshot if needed for Phase 2

## Field Definitions

### Publication Classification
- **`is_research_article`**: Primary research articles only (TRUE excludes: reviews, editorials, letters, comments, errata)
- **`is_clinical`**: Clinical research focus

### Citation Metrics
- **`nih_percentile`**: Percentile rank of RCR vs all NIH publications
  - 99 = top 1% most influential
  - 95 = top 5%
  - 50 = median
- **`relative_citation_ratio` (RCR)**: Field-normalized, time-normalized citation impact
  - 1.0 = median NIH-funded paper in same field/year
  - 2.0 = twice as influential
  - 0.5 = half as influential
- **`citation_count`**: Total citations received
- **`citations_per_year`**: Annual citation rate since publication
- **`provisional`**: TRUE if published within last 2 years (less stable metrics)

### Translation Metrics
- **`apt`**: Approximate Potential to Translate (0-1 scale)
- **`human`**: Fraction of MeSH terms in Human category
- **`animal`**: Fraction of MeSH terms in Animal category
- **`molecular_cellular`**: Fraction of MeSH terms in Molecular/Cellular category

## References

Hutchins BI, et al. (2019) The NIH Open Citation Collection: A public access, broad coverage resource. PLoS Biology 17(10): e3000416.
DOI: https://doi.org/10.1371/journal.pbio.3000385
