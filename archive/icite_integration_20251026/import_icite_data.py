"""
Import iCite data using pandas (handles messy CSV better than raw COPY).
"""
import time
import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@postgres:5432/{os.getenv('POSTGRES_DB')}"
engine = create_engine(DATABASE_URL)

def import_with_progress(csv_path, table_name, chunksize):
    """Import CSV in chunks with progress tracking."""
    print(f"\nImporting {csv_path} → {table_name}")
    print(f"Chunk size: {chunksize:,} rows\n")

    start = time.time()
    total_rows = 0
    chunk_num = 0

    try:
        # Pandas handles newlines in quotes, malformed rows, etc.
        for chunk in pd.read_csv(
            csv_path,
            chunksize=chunksize,
            low_memory=False,
            on_bad_lines='warn',  # Warn but continue on bad rows
            encoding='utf-8',
            quoting=1  # QUOTE_ALL
        ):
            chunk_num += 1
            chunk_start = time.time()

            # Import chunk to database
            chunk.to_sql(
                table_name,
                engine,
                if_exists='append',
                index=False,
                method='multi'
            )

            total_rows += len(chunk)
            chunk_time = time.time() - chunk_start
            total_time = time.time() - start
            rate = total_rows / total_time if total_time > 0 else 0

            print(f"Chunk {chunk_num:4d}: {len(chunk):7,} rows in {chunk_time:5.1f}s | "
                  f"Total: {total_rows:10,} rows | Rate: {rate:6,.0f} rows/sec | "
                  f"Elapsed: {total_time/60:5.1f} min")

        total_time = time.time() - start
        print(f"\n✓ Complete: {total_rows:,} rows in {total_time/60:.1f} minutes")
        print(f"  Average rate: {total_rows/total_time:,.0f} rows/sec\n")

    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        raise

print("="*80)
print("iCite Data Import - Using pandas for robust CSV handling")
print("="*80)

overall_start = time.time()

# Import metadata
print("\n[1/2] Importing metadata...")
import_with_progress(
    'data/icite_2025_09/icite_metadata.csv',
    'icite_metadata',
    chunksize=100_000
)

# Import citation links
print("\n[2/2] Importing citation links...")
import_with_progress(
    'data/icite_2025_09/open_citation_collection.csv',
    'citation_links',
    chunksize=500_000
)

# Create indexes
# Commented out - moved to create_icite_indexes.py
# print("\n[3/3] Creating indexes...")
# index_start = time.time()
#
# with engine.connect() as conn:
#     indexes = [
#         ("idx_icite_percentile", "icite_metadata(nih_percentile)"),
#         ("idx_icite_year", "icite_metadata(year)"),
#         ("idx_icite_citation_count", "icite_metadata(citation_count)"),
#         ("idx_citation_links_citing", "citation_links(citing)"),
#         ("idx_citation_links_cited", "citation_links(referenced)")
#     ]
#
#     for idx_name, idx_def in indexes:
#         print(f"  Creating {idx_name}...")
#         conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}")
#         conn.commit()
#
# index_time = time.time() - index_start
# print(f"\n✓ Indexes created in {index_time/60:.1f} minutes\n")

overall_time = time.time() - overall_start
print("="*80)
print(f"✓ Import complete in {overall_time/3600:.2f} hours")
print("="*80)
