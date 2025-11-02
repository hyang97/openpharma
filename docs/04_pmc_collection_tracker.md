# PMC Collection Tracker

Last updated: 2025-10-26

## Collections

### 1. Diabetes Research (2020-2025)
- **Date**: 2025-10-10
- **Query**: `diabetes[Title/Abstract] AND open access[filter] AND 2020/01/01:2025/12/31[pdat]`
- **Papers**: 52,014
- **Status**: `fetched`

### 2. Historical Papers - 1990
- **Date**: 2025-10-26
- **Query**: `open access[filter] AND 1990/01/01:1990/12/31[pdat]`
- **Papers**: 2,925
- **Status**: `wont_fetch`

### 3. Historical Papers - 1991
- **Date**: 2025-10-26
- **Query**: `open access[filter] AND 1991/01/01:1991/12/31[pdat]`
- **Papers**: 3,053
- **Status**: `wont_fetch`

### 4. Historical Papers - 1992
- **Date**: 2025-10-26
- **Query**: `open access[filter] AND 1992/01/01:1992/12/31[pdat]`
- **Papers**: 3,108
- **Status**: `wont_fetch`

### 5. Historical Papers - 1993-2019
- **Date**: 2025-10-26
- **Query**: `open access[filter] AND 1993/01/01:2019/12/31[pdat]`
- **Papers**: 2,622,159
- **Status**: `wont_fetch`

### 6. All Historical Papers (1990-2019) - 95th Percentile by Citations (1990-2019)
- **Date**: 2025-10-26
- **Query**: SQL query with iCite citation data to find top 95th percentile by nih_percentage
- **Papers**: 58,705 
- **Status**: In progress
- **Notes**: Filtered historical papers by citation impact using NIH iCite data. Excludes diabetes research papers already fetched in collection #1.

### 7. All Open Access Papers (2020-2025) - Baseline Count
- **Date**: 2025-10-30
- **Query**: `open access[filter] AND 2020/01/01:2025/12/31[pdat]`
- **Papers**: 4,386,906
- **Status**: `not_loaded`
- **Notes**: Baseline count for 5-year recent paper landscape. This represents the total universe of available papers for potential therapeutic area expansion.

### 8. Filtered Baseline (Article Type Filter)
- **Date**: 2025-10-30
- **Query**: `open access[filter] AND 2020/01/01:2025/12/31[pdat] NOT (Review[ptyp] OR Editorial[ptyp] OR Letter[ptyp] OR Comment[ptyp] OR Erratum[ptyp])`
- **Papers**: 869,593
- **Status**: `not_loaded`
- **Notes**: 80% reduction from baseline by excluding non-research article types

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

## Total: 2,683,259 papers discovered
## Fetched or to-be-fetched: 110,719 papers total (52,014 diabetes + 58,705 historical 95th percentile)
## Baseline 5-year open access: 4,386,906 papers (not loaded)
## Filtered baseline: 869,593 papers (not loaded)
