# PMC Collection Tracker

Last updated: 2025-11-16

## Summary

## Total: 2,683,453 papers discovered
## Fetched: 110,912 papers total (52,014 diabetes + 58,705 historical 95th percentile + 194 PubMedQA eval + 1 failed)
## Fully Processed: 110,912 papers (fetched, chunked, embedded)
## Total Chunks: 4,745,881 (all embedded)
## Active (RAG): 65,759 papers (priority > 0, includes 194 PubMedQA)
## Excluded: 45,151 papers (priority = 0, non-research)
## Baseline 5-year open access: 4,386,906 papers (not loaded)
## Filtered baseline: 869,593 papers (not loaded)


## Collections

### 1. Diabetes Research (2020-2025)
- **Date**: 2025-10-10
- **Query**: `diabetes[Title/Abstract] AND open access[filter] AND 2020/01/01:2025/12/31[pdat]`
- **Papers**: 52,014
- **Status**: `fetched`

### 2. Historical Papers (1990-2019) - Baseline Counts
- **Date**: 2025-10-26
- **Status**: `not_loaded`
- **Notes**: Baseline counts to understand available historical papers before citation filtering

| Year Range | Papers | Query |
|------------|--------|-------|
| 1990 | 2,925 | `open access[filter] AND 1990/01/01:1990/12/31[pdat]` |
| 1991 | 3,053 | `open access[filter] AND 1991/01/01:1991/12/31[pdat]` |
| 1992 | 3,108 | `open access[filter] AND 1992/01/01:1992/12/31[pdat]` |
| 1993-2019 | 2,622,159 | `open access[filter] AND 1993/01/01:2019/12/31[pdat]` |
| **Total** | **2,631,245** | |

### 3. Historical Papers (1990-2019) - 95th Percentile by Citations
- **Date**: 2025-10-26
- **Query**: SQL query with iCite citation data to find top 95th percentile by nih_percentile
- **Papers**: 58,705
- **Status**: `fetched` (3 failed)
- **Notes**: Filtered historical papers by citation impact using NIH iCite data. Excludes diabetes research papers already fetched in collection #1. 58,702 successfully fetched and embedded, 3 fetch failures.

### 4. PubMedQA Evaluation Dataset (1989-2017)
- **Date**: 2025-11-16
- **Source**: PubMedQA expert-labeled dataset (ori_pqal.json)
- **Papers Total**: 1,000 PMIDs
- **Papers with PMC IDs**: 194 (all successfully ingested)
- **Papers without PMC IDs**: 806 (abstract-only, not available in PMC)
- **Status**: `fetched` (all 194 successfully processed)
- **Purpose**: Evaluation dataset with expert-labeled ground truth questions and answers
- **Notes**: Broad biomedical coverage (cardiology, oncology, surgery, neurology, infectious disease, pediatrics, etc.). ~60% pharma-relevant (drug efficacy, clinical trials, safety). No iCite percentile data available for these papers. Added for evaluation purposes despite not meeting 95th percentile citation criteria. Only 19% of PubMedQA papers are available in PMC open access; remainder are PMID-only without full text.
- **Data Files**:
  - Original dataset: `data/ori_pqal.json` (1,000 questions)
  - PMC ID list: `data/pubmedqa_pmc_ids.txt` (194 PMC IDs)
  - PMID→PMC mapping: `data/pubmedqa_pmid_to_pmc_mapping.json`
  - Golden eval set: `data/golden_eval_set.csv` (194 questions with ground truth)

## 4. Exclude Non-Research Articles from Collection #1 (Retroactive)

**Date**: 2025-11-02
**Tool**: `scripts/stage_1_3_set_priority_level.py`
**Strategy**: Retroactively mark non-research articles from Collection #1 (Diabetes Research 2020-2025) with priority = 0 to exclude from RAG retrieval

After fetching Collection #1, we retroactively identified and excluded non-research articles (reviews, editorials, letters, comments, errata) by setting priority = 0. Only papers with priority > 0 are searchable in RAG.

**Exclusion Query**:
```
(diabetes mellitus[MeSH Terms] OR diabetes[Title/Abstract]) AND
open access[filter] AND
2020/01/01:2025/12/31[pdat] AND
(Review[ptyp] OR Editorial[ptyp] OR Letter[ptyp] OR Comment[ptyp] OR Erratum[ptyp])
```

**Papers Excluded**: 45,151 (reviews, editorials, letters, comments, errata)
**Papers Retained**: 65,759 research articles (diabetes + historical + PubMedQA)

### Priority Distribution (110,912 fetched papers)

| Priority | Count | Description |
|----------|-------|-------------|
| 50 | 65,759 | Research articles (searchable in RAG) |
| 0 | 45,151 | Non-research articles (excluded from RAG) |
| Failed | 2 | Fetch failures |

**Effective Collection**: 65,759 papers (59% of fetched)
- ~7K diabetes research articles (2020-2025)
- ~58K historical high-impact papers (1990-2019, 95th percentile citations)
- 194 PubMedQA evaluation papers (1989-2017, expert-labeled ground truth)

**Impact**: RAG searches ~4.7M chunks from research articles (priority > 0), excluding non-research content.

---


## Searches (Exploratory, Not Loaded)

### 1. All Open Access Papers (2020-2025) - Baseline Count
- **Date**: 2025-10-30
- **Query**: `open access[filter] AND 2020/01/01:2025/12/31[pdat]`
- **Papers**: 4,386,906
- **Status**: `not_loaded`
- **Notes**: Baseline count for 5-year recent paper landscape. This represents the total universe of available papers for potential therapeutic area expansion.
- **Estimated ingestion time**: ~5,900 hours (245 days wallclock)
  - Stage 1-1.2: 6 hours (ID collection + citation filtering)
  - Stage 2: 730 hours (30 days, must run off-peak)
  - Stage 3: 195 hours (8 days)
  - Stage 4: 4,970 hours (207 days, potentially optimizable to 1,240h / 52 days with parallelization)
- **Estimated storage**: ~1.9 TB additional
  - Documents: ~280 GB
  - Chunks (text): ~310 GB
  - Chunks (embeddings): ~570 GB
  - HNSW indexes: ~460 GB
  - PostgreSQL overhead: ~280 GB
- **Total database size after ingestion**: ~2.1 TB (current 165 GB + 1.9 TB new)
- **Practicality**: Not recommended - would require dedicated infrastructure and months of processing time

### 2. Filtered Baseline (Article Type Filter)
- **Date**: 2025-10-30
- **Query**: `open access[filter] AND 2020/01/01:2025/12/31[pdat] NOT (Review[ptyp] OR Editorial[ptyp] OR Letter[ptyp] OR Comment[ptyp] OR Erratum[ptyp])`
- **Papers**: 869,593
- **Status**: `not_loaded`
- **Notes**: 80% reduction from baseline by excluding non-research article types
- **Estimated ingestion time**: ~1,170 hours (49 days wallclock)
  - Stage 1-1.2: 1.5 hours (ID collection + citation filtering)
  - Stage 2: 145 hours (6 days, must run off-peak)
  - Stage 3: 39 hours (1.6 days)
  - Stage 4: 985 hours (41 days, potentially optimizable to 245h / 10 days with parallelization)
- **Estimated storage**: ~380 GB additional
  - Documents: ~56 GB
  - Chunks (text): ~61 GB
  - Chunks (embeddings): ~113 GB
  - HNSW indexes: ~91 GB
  - PostgreSQL overhead: ~57 GB
- **Total database size after ingestion**: ~545 GB (current 165 GB + 380 GB new)
- **Practicality**: Feasible but large - would require ~2 weeks of processing with optimized embedding parallelization, ~400 GB storage headroom

### 3. Cardiometabolic + Alzheimer's (2020-2025) - Time-Graduated Citation Filter
- **Date**: 2025-11-03
- **Query**:
```
(
  (diabetes mellitus[MeSH Terms] OR diabetes[Title/Abstract]) OR
  (obesity[MeSH Terms] OR obesity[Title/Abstract]) OR
  (alzheimer disease[MeSH Terms] OR alzheimer*[Title/Abstract]) OR
  (non-alcoholic fatty liver disease[MeSH Terms] OR NASH[Title/Abstract] OR NAFLD[Title/Abstract])
)
AND open access[filter]
AND 2020/01/01:2025/12/31[pdat]
AND NOT (Review[ptyp] OR Editorial[ptyp] OR Letter[ptyp] OR Comment[ptyp] OR Erratum[ptyp])
```
- **Citation Filter** (applied via Stage 1.2):
  - 2020: nih_percentile >= 80 (top 20%)
  - 2021: nih_percentile >= 70 (top 30%)
  - 2022: nih_percentile >= 60 (top 40%)
  - 2023: nih_percentile >= 40 (top 60%)
  - 2024-2025: All papers (too recent for citation filtering)
- **Papers (unfiltered)**: 125,494
- **Papers (after citation filter)**: ~63,500 (estimated 50% reduction)
- **New papers beyond Collection #1**: ~37,000
- **Status**: `planned`
- **Notes**: Combined MeSH + Title/Abstract strategy. Breakdown before filtering: Diabetes (67K), Obesity (35K), Alzheimer's (23K), NASH/NAFLD (7K). Time-graduated filtering reduces corpus by ~50% while preserving recent papers and high-impact older research.
- **Estimated ingestion time**: 50-55 hours (2-3 days wallclock)
  - Stage 1-1.2: 30 min (ID collection + citation filtering)
  - Stage 2: 6-7 hours (fetch, must run off-peak)
  - Stage 3: 2 hours (chunking)
  - Stage 4: 40-45 hours (embedding, potentially optimizable to 12-15h with parallelization)
- **Estimated storage**: ~16 GB additional
  - Documents: ~2.4 GB
  - Chunks (text): ~2.6 GB
  - Chunks (embeddings): ~4.8 GB
  - HNSW indexes: ~3.8 GB
  - PostgreSQL overhead: ~1.5 GB
- **Total database size after ingestion**: ~181 GB (current 165 GB + 16 GB new)

## Therapeutic Area Scoping (2025-10-30)
All queries include article type filter (NOT Review/Editorial/Letter/Comment/Erratum)
Search strategy: Combined MeSH + Title/Abstract for maximum coverage

### Major Therapeutic Areas
- Diabetes: 10,768
- Oncology: 74,095
- Cardiovascular: 27,075
- Immunology: 15,171
- CNS/Neurology: 29,312

### Hot Competitive Areas
- Alzheimer's: 4,911
- GLP-1/Obesity: 4,648
- NASH/Liver: 1,576
- CAR-T/Cell Therapy: 1,142
- Gene Therapy: 798
- mRNA Vaccines: 282
- Rare Diseases: 277

### Oncology by Cancer Type
- Breast Cancer: 9,524
- Lung Cancer: 8,257
- Leukemia: 5,693
- Colorectal Cancer: 5,518
- Prostate Cancer: 3,071
- Lymphoma: 3,709
- Melanoma: 2,550
- Pancreatic Cancer: 2,367

### Oncology by Treatment Modality
- Immunotherapy: 3,489
- Checkpoint Inhibitors: 880
- CAR-T (oncology): 315
- Targeted Therapy: 389
- KRAS Inhibitors: 261
- CDK4/6 Inhibitors: 115
- ADCs: 46

### Cardiometabolic Expansion
- Cardiovascular (broad): 27,075
- Heart Failure: 3,307
- Hypertension: 4,065
- Stroke: 4,144
- Atherosclerosis: 1,718
- Metabolic Syndrome: 780
- Obesity: 4,433
- NASH/NAFLD: 1,646
- Hyperlipidemia: 391

### Cardiometabolic Drug Classes
- GLP-1 agonists: 520
- SGLT2 inhibitors: 435
- PCSK9 inhibitors: 125
- Statins: 104