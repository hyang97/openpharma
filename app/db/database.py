from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", default="postgresql://admin:password@localhost:5432/openpharma")

# Connection pool optimization (defaults: pool_size=5, max_overflow=10, recycle=-1, pre_ping=False)
engine = create_engine(
    DATABASE_URL,
    pool_size=10,           # Increased from 5 for concurrent eval workloads
    max_overflow=20,        # Increased from 10 (total: 30 max connections)
    pool_recycle=3600,      # Added: Recycle connections after 1 hour (was -1/never)
    pool_pre_ping=True      # Added: Test connection health before use
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) 

# Base class for declarative models
Base = declarative_base()


def get_db():
    """
    Database session dependency for FastAPI endpoints (our backend)
    Provides a database session for the request and closes it after the request is complete
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
