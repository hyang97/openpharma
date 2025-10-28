# iCite Database Snapshot 2025-09

**Source**: NIH Office of Portfolio Analysis
**Posted**: 2025-10-02
**Size**: 28.75 GB (compressed)
**Format**: CSV (zipped) and JSON (compressed, tarred)
**Info**: https://nih.figshare.com/collections/iCite_Database_Snapshots_NIH_Open_Citation_Collection_/4586573
**Download**: https://nih.figshare.com/articles/dataset/iCite_Database_Snapshot_2025-09/30266419

## Description

This is a database snapshot of the iCite web service providing bibliometrics and metadata on publications indexed in PubMed. The dataset is organized into three modules:

1. **Influence**: Metrics of scientific influence, field-adjusted and benchmarked to NIH publications
2. **Translation**: Measures how Human, Animal, or Molecular/Cellular Biology-oriented each paper is
3. **Open Cites**: Link-level, public-domain citation data from the NIH Open Citation Collection

## Data Fields

### Core Identifiers
- `pmid`: PubMed Identifier
- `doi`: Digital Object Identifier (if available)
- `year`: Publication year
- `title`: Article title
- `authors`: List of author names
- `journal`: Journal name (ISO abbreviation)

### Publication Classification
- `is_research_article`: Flag for primary research articles
- `is_clinical`: Flag for clinical articles

### Citation Metrics
- `relative_citation_ratio` (RCR): Field-adjusted, time-adjusted citation metric benchmarked to NIH-funded papers
  - Median RCR for NIH-funded papers = 1.0
  - RCR of 2.0 = twice as many citations/year as median NIH paper in same field/year
  - RCR of 0.5 = half as many citations/year
- `provisional`: Flag for RCRs from papers published in previous 2 years (less stable metrics)
- `citation_count`: Number of unique articles citing this paper
- `citations_per_year`: Annual citation rate since publication
- `field_citation_rate`: Intrinsic citation rate of paper's field (estimated via co-citation network)
- `expected_citations_per_year`: Expected citations for NIH-funded papers with same field citation rate
- `nih_percentile`: Percentile rank of RCR compared to all NIH publications
  - Example: 95% = RCR higher than 95% of all NIH-funded publications
  - **99% = Top 1% most influential papers**

### Translation Metrics
- `H`: Fraction of MeSH terms in Human category
- `animal`: Fraction of MeSH terms in Animal category
- `molecular_cellular`: Fraction of MeSH terms in Molecular/Cellular Biology category
- `x_coord`: X coordinate on Triangle of Biomedicine
- `y_coord`: Y coordinate on Triangle of Biomedicine
- `apt`: Approximate Potential to Translate (ML-based likelihood of citation in clinical trials/guidelines)

### Citation Network
- `cited_by_clin`: PMIDs of clinical articles that cited this paper
- `cited_by`: PMIDs of all articles that cited this paper
- `references`: PMIDs in this paper's reference list

## File Format Notes

- Large CSV files are zipped using **zip version 4.5**
- Default `unzip` in some Linux distributions may not support this version
- Use tools supporting zip 4.5+ (e.g., 7zip, updated unzip)
- Alternative: JSON files are compressed with standard tar/gzip

## Citation

Hutchins BI, et al. (2019) The NIH Open Citation Collection: A public access, broad coverage resource. PLoS Biology 17(10): e3000416.
DOI: https://doi.org/10.1371/journal.pbio.3000385

## Usage for OpenPharma

This dataset will be used to identify landmark papers for the OpenPharma platform:

**Filtering Criteria**:
- `nih_percentile >= 99` (top 1% most influential papers)
- `1990 <= year <= 2020` (historical papers, 30-year window)
- Must have open access PMC version (checked via NCBI ID Converter)

**Expected Result**: ~20,000-25,000 landmark papers across all biomedicine

## Directory Structure

After downloading and extracting, this directory should contain:

```
data/icite_2025_09/
├── README.md                          # This file
├── DESIGN.md                          # Schema design documentation
├── INTEGRATION_DESIGN.md              # Integration strategy for OpenPharma
├── create_icite_tables.sql            # SQL schema for iCite tables
├── import_icite_data.sh               # Shell script for COPY-based import (deprecated)
├── import_icite_data.py               # Python script for pandas-based import (used)
├── create_icite_indexes.py            # Python script to create indexes with progress
├── icite_metadata.csv                 # Main iCite dataset (unzipped, 28.75GB)
├── open_citation_collection.csv       # Citation links (unzipped, 14GB)
└── [original .zip files]              # Keep originals for reference
```

## Import Status (COMPLETE)

The iCite dataset has been successfully imported into Postgres:
- `icite_metadata`: 39.4M rows imported (100%)
- `citation_links`: 870M rows imported (100%)
- Indexes: 5 indexes created (percentile, year, citation_count, citing, cited)
- Disk space: CSV/ZIP files cleaned up (freed 57GB)

## One-Time Import Instructions (COMPLETE)

The import has been completed. For reference, the original steps were:

1. Download files from Figshare collection
2. Extract CSV files to this directory
3. Create tables: `docker-compose exec postgres psql -U admin -d openpharma -f data/icite_2025_09/create_icite_tables.sql`
4. Import data: `docker-compose run --rm api python data/icite_2025_09/import_icite_data.py`
5. Create indexes: `docker-compose run --rm api python data/icite_2025_09/create_icite_indexes.py`

## Integration with OpenPharma

See `INTEGRATION_DESIGN.md` for the full integration strategy.

**Query-First Approach**: Instead of filtering iCite by percentile upfront, we:
1. Run PubMed queries as usual (e.g., diabetes research)
2. Convert PMC IDs to PMIDs using NCBI ID Converter API (batched, 200 IDs/request)
3. Filter by citation percentile using iCite data (e.g., `nih_percentile >= 95`)
4. Continue with normal ingestion pipeline

## Contact

Comments and questions: iCite@mail.nih.gov
