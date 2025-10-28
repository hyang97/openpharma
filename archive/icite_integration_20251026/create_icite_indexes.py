"""
Create indexes for iCite tables with progress tracking.
"""
import time
import threading
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@postgres:5432/{os.getenv('POSTGRES_DB')}"
engine = create_engine(DATABASE_URL)

def monitor_progress(index_name, stop_event):
    """Monitor index creation progress in a separate thread."""
    monitor_engine = create_engine(DATABASE_URL)

    with monitor_engine.connect() as conn:
        while not stop_event.is_set():
            result = conn.execute(text("""
                SELECT
                    phase,
                    blocks_total,
                    blocks_done,
                    CASE
                        WHEN blocks_total > 0
                        THEN ROUND(100.0 * blocks_done / blocks_total, 1)
                        ELSE 0
                    END as percent_done
                FROM pg_stat_progress_create_index
                WHERE relid = (SELECT oid FROM pg_class WHERE relname = :table_name)
            """), {"table_name": index_name.replace("idx_", "").split("_")[0] + "_" + index_name.replace("idx_", "").split("_")[1] if "icite" in index_name else "citation_links"})

            row = result.fetchone()
            if row:
                phase, blocks_total, blocks_done, percent = row
                print(f"  [{phase}] {blocks_done:,}/{blocks_total:,} blocks ({percent}%)", end="\r")

            time.sleep(2)

    monitor_engine.dispose()

print("="*80)
print("Creating indexes for iCite tables")
print("="*80)

indexes = [
    ("idx_icite_percentile", "icite_metadata(nih_percentile)"),
    ("idx_icite_year", "icite_metadata(year)"),
    ("idx_icite_citation_count", "icite_metadata(citation_count)"),
    ("idx_citation_links_citing", "citation_links(citing)"),
    ("idx_citation_links_cited", "citation_links(referenced)")
]

overall_start = time.time()

for idx_name, idx_def in indexes:
    idx_start = time.time()
    print(f"\nCreating {idx_name} on {idx_def}...")

    # Start progress monitoring thread
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_progress, args=(idx_name, stop_event))
    monitor_thread.start()

    # Create index
    with engine.connect() as conn:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def}"))
        conn.commit()

    # Stop monitoring
    stop_event.set()
    monitor_thread.join()

    idx_time = time.time() - idx_start
    print(f"\n  ✓ Created in {idx_time:.1f}s ({idx_time/60:.2f} min)")

overall_time = time.time() - overall_start
print("\n" + "="*80)
print(f"✓ All indexes created in {overall_time/60:.1f} minutes ({overall_time/3600:.2f} hours)")
print("="*80)
