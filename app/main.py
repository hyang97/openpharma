from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from typing import Optional, List
from .db.database import get_db
from .logging_config import setup_logging, get_logger
from .rag.generation import answer_query, RAGResponse

# Configure logging on startup
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file="logs/openpharma.log"
)

logger = get_logger(__name__)

app = FastAPI(title="OpenPharma API", version="0.1.0")

# Configure CORS to allow requests from React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting OpenPharma API")
    logger.info(f"Using local LLM: {os.getenv('USE_LOCAL_LLM', 'true')}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down OpenPharma API")

class QuestionRequest(BaseModel):
    question: str
    use_local: Optional[bool] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "OpenPharma API is running"}

@app.post("/ask", response_model=RAGResponse)
async def ask_question(request: QuestionRequest):
    """Ask a question and get a RAG-powered AI response with citations"""

    # Determine which model to use
    use_local = request.use_local if request.use_local is not None else os.getenv("USE_LOCAL_LLM", default="true").lower() == "true"

    logger.info(f"Received question: {request.question[:100]}...")
    logger.debug(f"Using local model: {use_local}")

    try:
        # Use RAG pipeline - returns RAGResponse directly
        result = answer_query(query=request.question, use_local=use_local)

        logger.info(f"Generated RAG response with {len(result.citations)} citations in {result.generation_time_ms:.0f}ms")

        return result

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Welcome to OpenPharma API", "docs": "/docs"}