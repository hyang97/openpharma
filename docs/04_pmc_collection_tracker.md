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

## Total: 2,683,259 papers discovered
## Fetched or to-be-fetched: 101,719 papers total (52,014 diabetes + 58,705 historical 95th percentile)
