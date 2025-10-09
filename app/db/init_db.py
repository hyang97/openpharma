"""
Initialize the database with pgvector extension and create tables.

Run this script to set up your database:
    python -m app.db.init_db
"""
from sqlalchemy import text
from .database import engine, Base
from .models import PubMedPaper, Document, DocumentChunk


def init_db():
    """Create pgvector extension and all tables with indexes"""

    print("Initializing database...")

    # Enable pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        print("✓ pgvector extension enabled")

    # Create all tables (SQLAlchemy will create indexes defined in __table_args__)
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")
    print("✓ Database indexes created")

    print("\n✅ Database initialization complete!")
    print("\nTables created:")
    print("  - pubmed_papers (PMC ID tracking for Phase 1 & 2)")
    print("  - documents (metadata storage)")
    print("  - document_chunks (chunked content with embeddings)")
    print("\nIndexes created:")
    print("  - INDEX(fetch_status) on pubmed_papers")
    print("  - UNIQUE(source, source_id) on documents")
    print("  - INDEX(ingestion_status) on documents")
    print("  - INDEX(document_id) on document_chunks")
    print("  - HNSW INDEX(embedding) on document_chunks (m=16, ef_construction=64)")
    print("  - PARTIAL INDEX(document_chunk_id) on document_chunks WHERE embedding IS NULL")


if __name__ == "__main__":
    init_db()
