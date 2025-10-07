"""
Initialize the database with pgvector extension and create tables.

Run this script to set up your database:
    python -m app.db.init_db
"""
from sqlalchemy import text
from .database import engine, Base
from .models import Document, DocumentChunk


def init_db():
    """Create pgvector extension and all tables with indexes"""

    print("Initializing database...")

    # Enable pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        print("✓ pgvector extension enabled")

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created")

    # Create HNSW index for vector similarity search
    with engine.connect() as conn:
        # Check if index already exists
        result = conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'document_chunks'
            AND indexname = 'idx_chunks_embedding_hnsw'
        """))

        if result.fetchone() is None:
            print("Creating HNSW index on embeddings (this may take a while for large datasets)...")
            conn.execute(text("""
                CREATE INDEX idx_chunks_embedding_hnsw
                ON document_chunks
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """))
            conn.commit()
            print("✓ HNSW vector similarity index created")
        else:
            print("✓ HNSW vector similarity index already exists")

    print("\n✅ Database initialization complete!")
    print("\nTables created:")
    print("  - documents (metadata storage)")
    print("  - document_chunks (chunked content with embeddings)")
    print("\nIndexes created:")
    print("  - UNIQUE(source, source_id) on documents")
    print("  - INDEX(document_id) on document_chunks")
    print("  - HNSW INDEX(embedding) on document_chunks")


if __name__ == "__main__":
    init_db()
