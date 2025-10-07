# OpenPharma

AI-powered search engine for diabetes research literature from PubMed Central.

## What is this?

A learning project building a RAG (Retrieval Augmented Generation) system that:
1. Fetches diabetes research papers from PubMed Central
2. Chunks them intelligently by section (methods, results, etc.)
3. Generates embeddings for semantic search
4. Lets you ask questions and get answers with citations

## Current Status

**Working:**
- Database (Postgres + pgvector)
- PubMed paper fetcher
- XML parser (extracts sections from research papers)
- Document chunker (512 tokens, section-aware)
- Embedding service (regular + batch API)
- Logging system

**Next:**
- Batch ingestion script (end-to-end pipeline)
- Test with sample diabetes papers
- RAG query system

## Quick Start

1. **Start the database:**
   ```bash
   docker-compose up -d postgres
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY to .env
   ```

4. **Initialize database:**
   ```bash
   python -m app.db.init_db
   ```

## Project Structure

```
app/
├── db/              # Database models and setup
├── ingestion/       # PubMed fetcher, XML parser, chunker, embeddings
├── logging_config.py
└── main.py          # FastAPI app

docs/
├── data_design.md   # How the data pipeline works
└── logging.md       # Logging guide

data/batches/        # Batch API files (gitignored)
```

## Documentation

- **[Data Design](docs/data_design.md)** - Detailed pipeline and schema docs
- **[Logging Guide](docs/logging.md)** - How to use logging
- **[CLAUDE.md](CLAUDE.md)** - Full project context

## Tools

- **FastAPI** - API framework
- **Postgres + pgvector** - Vector database
- **OpenAI** - Embeddings
- **Docker** - Services

## Learning Goals

- Build a RAG system from scratch
- Understand vector embeddings
- Learn data pipeline design
- Practice with modern AI tools
