from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", default="postgresql://admin:password@localhost:5432/openpharma")

engine = create_engine(DATABASE_URL)
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
